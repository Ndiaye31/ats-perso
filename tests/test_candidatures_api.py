import os
import sys
import types
import unittest
import uuid
from datetime import date
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure tests do not require local PostgreSQL driver during imports.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.database import Base
from app.main import app
from app.models.candidature import Candidature
from app.models.offer import Offer
from app.routers.candidatures import get_db


class _FakeBrowser:
    async def new_context(self, **kwargs):
        return _FakeBrowserContext()

    async def close(self):
        return None


class _FakeBrowserContext:
    async def new_page(self):
        return object()

    async def close(self):
        return None


class _FakeChromium:
    async def launch(self, **kwargs):
        return _FakeBrowser()


class _FakePlaywright:
    chromium = _FakeChromium()


class _FakePlaywrightContext:
    async def __aenter__(self):
        return _FakePlaywright()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _fake_async_playwright():
    return _FakePlaywrightContext()


class _FakeApplicator:
    async def login(self, page, login, password):
        return True

    async def navigate_to_offer(self, page, url):
        return True

    async def find_apply_button(self, page):
        return True

    async def screenshot(self, page, path):
        return None

    async def fill_form(self, page, lm_texte, cv_path, profil, offer_title, offer_company):
        return True

    async def submit(self, page):
        return True


class CandidaturesApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=cls.engine)

        def _get_test_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_test_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def _insert_offer(self, **overrides) -> Offer:
        offer = Offer(
            id=uuid.uuid4(),
            title=overrides.get("title", "Data Analyst"),
            company=overrides.get("company", "ACME"),
            location=overrides.get("location", "Paris"),
            url=overrides.get("url", "https://emploi-territorial.fr/offre/o123"),
            description=overrides.get("description", "Poste de data analyst"),
            status=overrides.get("status", "new"),
            content_hash=overrides.get("content_hash", str(uuid.uuid4())),
            source_id=None,
            contact_email=overrides.get("contact_email"),
            candidature_url=overrides.get("candidature_url"),
        )
        with self.SessionLocal() as db:
            db.add(offer)
            db.commit()
            db.refresh(offer)
            return offer

    def _insert_candidature(self, offer_id: uuid.UUID, mode: str = "plateforme") -> Candidature:
        cand = Candidature(
            id=uuid.uuid4(),
            offer_id=offer_id,
            statut="brouillon",
            mode_candidature=mode,
            lm_texte="LM initiale",
        )
        with self.SessionLocal() as db:
            db.add(cand)
            db.commit()
            db.refresh(cand)
            return cand

    def test_create_candidature_is_idempotent_for_same_offer(self):
        offer = self._insert_offer(url="https://emploi.fhf.fr/emploi/offre/1", contact_email="hr@example.com")

        res1 = self.client.post("/candidatures", json={"offer_id": str(offer.id)})
        self.assertEqual(res1.status_code, 201)
        data1 = res1.json()

        res2 = self.client.post("/candidatures", json={"offer_id": str(offer.id)})
        self.assertEqual(res2.status_code, 201)
        data2 = res2.json()

        self.assertEqual(data1["id"], data2["id"])
        self.assertEqual(data1["mode_candidature"], "plateforme")

    def test_get_candidature_by_offer_returns_active(self):
        offer = self._insert_offer()
        cand = self._insert_candidature(offer.id, mode="plateforme")

        res = self.client.get(f"/candidatures/offer/{offer.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], str(cand.id))
        self.assertEqual(data["offer_id"], str(offer.id))

    def test_generate_lm_saves_text(self):
        offer = self._insert_offer(description="desc")
        cand = self._insert_candidature(offer.id, mode="plateforme")

        fake_lm_module = types.ModuleType("app.ai.generate_lm")
        fake_lm_module.generate_lm = lambda **kwargs: "LM mockee"
        with patch.dict(sys.modules, {"app.ai.generate_lm": fake_lm_module}):
            res = self.client.post(f"/candidatures/{cand.id}/generate-lm")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["lm_texte"], "LM mockee")

        with self.SessionLocal() as db:
            refreshed = db.get(Candidature, cand.id)
            self.assertEqual(refreshed.lm_texte, "LM mockee")

    def test_send_email_marks_candidature_as_sent(self):
        offer = self._insert_offer(contact_email="hr@example.com")
        cand = self._insert_candidature(offer.id, mode="email")

        with patch("app.email_sender.send_candidature_email", return_value=None):
            res = self.client.post(f"/candidatures/{cand.id}/send-email")

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        with self.SessionLocal() as db:
            refreshed = db.get(Candidature, cand.id)
            self.assertEqual(refreshed.statut, "envoyée")
            self.assertEqual(refreshed.date_envoi, date.today())

    def test_auto_apply_blocks_portail_tiers(self):
        offer = self._insert_offer(candidature_url="https://portail.externe/jobs/1")
        cand = self._insert_candidature(offer.id, mode="plateforme")

        res = self.client.post(f"/candidatures/{cand.id}/auto-apply?dry_run=true")
        self.assertEqual(res.status_code, 400)
        self.assertIn("portail tiers", res.json()["detail"])

    def test_auto_apply_blocks_email_mode_even_on_supported_domain(self):
        offer = self._insert_offer(
            url="https://www.emploi-territorial.fr/offre/o094260225000150-technicien-systemes-reseaux",
            contact_email="recrutement@example.fr",
        )
        cand = self._insert_candidature(offer.id, mode="email")

        res = self.client.post(f"/candidatures/{cand.id}/auto-apply?dry_run=true")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Candidature par email", res.json()["detail"])

    def test_auto_apply_dry_run_supported_platform_returns_success(self):
        offer = self._insert_offer(url="https://emploi-territorial.fr/offre/o123")
        cand = self._insert_candidature(offer.id, mode="plateforme")

        fake_async_api = types.ModuleType("playwright.async_api")
        fake_async_api.async_playwright = _fake_async_playwright

        with patch("app.routers.candidatures._get_applicator", return_value=_FakeApplicator()), patch(
            "app.config.settings.cv_path", "C:/fake/cv.pdf"
        ), patch("app.config.settings.emploi_territorial_login", "user"), patch(
            "app.config.settings.emploi_territorial_password", "pass"
        ), patch.dict(sys.modules, {"playwright.async_api": fake_async_api}):
            res = self.client.post(f"/candidatures/{cand.id}/auto-apply?dry_run=true")

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn("Dry-run", body["message"])

    def test_bulk_generate_lm_returns_success_for_all(self):
        offer1 = self._insert_offer(title="Data Analyst 1")
        offer2 = self._insert_offer(title="Data Analyst 2")
        cand1 = self._insert_candidature(offer1.id, mode="plateforme")
        cand2 = self._insert_candidature(offer2.id, mode="plateforme")

        fake_lm_module = types.ModuleType("app.ai.generate_lm")
        fake_lm_module.generate_lm = lambda **kwargs: "LM bulk"
        with patch.dict(sys.modules, {"app.ai.generate_lm": fake_lm_module}):
            res = self.client.post(
                "/candidatures/bulk-generate-lm",
                json={"candidature_ids": [str(cand1.id), str(cand2.id)]},
            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["success"], 2)
        self.assertEqual(body["failed"], 0)

    def test_bulk_generate_and_auto_apply_chains_operations(self):
        offer1 = self._insert_offer(title="Data Analyst 3")
        offer2 = self._insert_offer(title="Data Analyst 4")
        cand1 = self._insert_candidature(offer1.id, mode="plateforme")
        cand2 = self._insert_candidature(offer2.id, mode="plateforme")

        fake_lm_module = types.ModuleType("app.ai.generate_lm")
        fake_lm_module.generate_lm = lambda **kwargs: "LM chain"
        async_mock = AsyncMock(return_value=types.SimpleNamespace(success=True, message="ok"))
        with patch.dict(sys.modules, {"app.ai.generate_lm": fake_lm_module}), patch(
            "app.routers.candidatures._auto_apply_with_db",
            async_mock,
        ):
            res = self.client.post(
                "/candidatures/bulk-generate-lm-and-auto-apply",
                json={"candidature_ids": [str(cand1.id), str(cand2.id)], "dry_run": True},
            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["success"], 2)
        self.assertEqual(body["failed"], 0)


if __name__ == "__main__":
    unittest.main()
