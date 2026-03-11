import os
import sys
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import Mock, patch

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.database import Base
from app.importers.choisirleservicepublic_csv import ChoisirLeServicePublicCsvImporter
from app.models.offer import Offer
from app.scrapers.base import RawOffer
from app.services.offer_ingestion import ingest_raw_offers, load_known_hashes


class ChoisirLeServicePublicCsvImporterTests(unittest.TestCase):
    def test_resolve_csv_url_prefers_latest_dataset_resource(self):
        importer = ChoisirLeServicePublicCsvImporter(csv_url="https://fallback.example/csp.csv")
        response = Mock()
        response.text = """
        <a href="https://www.data.gouv.fr/api/1/datasets/r/11111111-1111-1111-1111-111111111111">JSON</a>
        <a href="https://www.data.gouv.fr/api/1/datasets/r/22222222-2222-2222-2222-222222222222">CSV</a>
        """
        response.raise_for_status.return_value = None

        with patch("app.importers.choisirleservicepublic_csv.requests.get", return_value=response):
            csv_url = importer._resolve_csv_url()

        self.assertEqual(
            csv_url,
            "https://www.data.gouv.fr/api/1/datasets/r/11111111-1111-1111-1111-111111111111",
        )

    def test_parse_csv_keeps_email_only_offers(self):
        csv_text = """Intitule;Employeur;Localisation;Modalites de candidature;URL
Data Engineer;Ministere A;Paris;candidatures@example.fr;https://csp.example/offre-1
Chef de projet;Ministere B;Lyon;Candidater en ligne;https://csp.example/offre-2
Analyste;Ministere C;Lille;Portail employeur https://site.example/jobs/1;https://csp.example/offre-3
"""
        importer = ChoisirLeServicePublicCsvImporter(csv_url="https://example.test/csp.csv")

        offers, stats = importer.parse_csv_text(csv_text)

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "Data Engineer")
        self.assertEqual(offers[0].company, "Ministere A")
        self.assertEqual(offers[0].email_contact, "candidatures@example.fr")
        self.assertEqual(stats["kept_email"], 1)
        self.assertEqual(stats["skipped_non_email"], 2)

    def test_builds_structured_description_when_no_free_text_exists(self):
        csv_text = """Reference;Intitule du poste;Organisme de rattachement;Localisation du poste;Lieu d'affectation;Avis de vacances au JO
REF-1;Data Engineer;Ministere A;Paris;12 rue Exemple;Envoyer CV à data@example.fr
"""
        importer = ChoisirLeServicePublicCsvImporter(csv_url="https://example.test/csp.csv")

        offers, stats = importer.parse_csv_text(csv_text)

        self.assertEqual(stats["kept_email"], 1)
        self.assertIsNotNone(offers[0].description)
        self.assertIn("Référence: REF-1", offers[0].description)
        self.assertIn("Lieu d'affectation: 12 rue Exemple", offers[0].description)
        self.assertIn("Avis de vacances au JO: Envoyer CV à data@example.fr", offers[0].description)


class OfferIngestionDuplicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def test_ingest_raw_offers_skips_duplicate_hashes_in_same_batch(self):
        offers = [
            RawOffer(
                title="Data Engineer",
                company="Ministere A",
                location="Paris",
                url="https://csp.example/offre-1",
                description="desc",
                date_limite=None,
                email_contact="a@example.fr",
            ),
            RawOffer(
                title="Data Engineer",
                company="Ministere A",
                location="Paris",
                url="https://csp.example/offre-1-bis",
                description="desc bis",
                date_limite=None,
                email_contact="a@example.fr",
            ),
        ]

        with self.SessionLocal() as db, patch("app.services.offer_ingestion.score_offer", return_value=(100, {})), patch(
            "app.services.offer_ingestion.MIN_SCORE",
            0,
        ):
            result = ingest_raw_offers(
                db,
                source_name="choisirleservicepublic.gouv.fr",
                source_url="https://choisirleservicepublic.gouv.fr",
                raw_offers=offers,
                known_hashes=load_known_hashes(db),
            )
            db.commit()
            stored = db.execute(select(Offer)).scalars().all()

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(len(stored), 1)

    def test_ingest_raw_offers_enriches_existing_duplicate_with_better_description(self):
        first = RawOffer(
            title="Data Engineer",
            company="Ministere A",
            location="Paris",
            url=None,
            description=None,
            date_limite=None,
            email_contact="a@example.fr",
        )
        enriched = RawOffer(
            title="Data Engineer",
            company="Ministere A",
            location="Paris",
            url=None,
            description="Référence: REF-1\nMétier: Data Engineer",
            date_limite="31/03/2026",
            email_contact="a@example.fr",
        )

        with self.SessionLocal() as db, patch("app.services.offer_ingestion.score_offer", return_value=(100, {})), patch(
            "app.services.offer_ingestion.MIN_SCORE",
            0,
        ):
            ingest_raw_offers(
                db,
                source_name="choisirleservicepublic.gouv.fr",
                source_url="https://choisirleservicepublic.gouv.fr",
                raw_offers=[first],
                known_hashes=load_known_hashes(db),
            )
            db.commit()
            result = ingest_raw_offers(
                db,
                source_name="choisirleservicepublic.gouv.fr",
                source_url="https://choisirleservicepublic.gouv.fr",
                raw_offers=[enriched],
                known_hashes=load_known_hashes(db),
            )
            db.commit()
            stored = db.execute(select(Offer)).scalars().all()

        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(stored[0].description, "Référence: REF-1\nMétier: Data Engineer")
        self.assertEqual(stored[0].date_limite, "31/03/2026")


if __name__ == "__main__":
    unittest.main()
