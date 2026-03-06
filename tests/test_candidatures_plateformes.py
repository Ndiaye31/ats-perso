import uuid
import unittest
import os
import sys

from fastapi import HTTPException

# Utilise SQLite en memoire pour eviter la dependance locale a PostgreSQL/psycopg.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.models.candidature import Candidature
from app.models.offer import Offer
from app.routers.candidatures import _detect_mode, auto_apply


class FakeDB:
    def __init__(self, candidature=None, offer=None):
        self._candidature = candidature
        self._offer = offer

    def get(self, model, obj_id):
        if model is Candidature:
            return self._candidature
        if model is Offer:
            return self._offer
        return None

    def commit(self):
        return None


def build_offer(
    *,
    url: str | None,
    contact_email: str | None = None,
    candidature_url: str | None = None,
) -> Offer:
    return Offer(
        id=uuid.uuid4(),
        title="Offre test",
        company="Entreprise",
        location="Paris",
        url=url,
        description=None,
        status="new",
        content_hash=None,
        source_id=None,
        contact_email=contact_email,
        candidature_url=candidature_url,
    )


def build_candidature(*, offer_id: uuid.UUID, mode: str) -> Candidature:
    return Candidature(
        id=uuid.uuid4(),
        offer_id=offer_id,
        statut="brouillon",
        mode_candidature=mode,
        lm_texte=None,
        email_contact=None,
    )


class DetectModeTests(unittest.TestCase):
    def test_detect_mode_fhf_force_plateforme_even_with_email(self):
        offer = build_offer(url="https://emploi.fhf.fr/emploi/offre/123", contact_email="contact@fhf.fr")
        self.assertEqual(_detect_mode(offer), "plateforme")

    def test_detect_mode_portail_tiers_has_priority(self):
        offer = build_offer(
            url="https://emploi.fhf.fr/emploi/offre/123",
            contact_email="contact@fhf.fr",
            candidature_url="https://flatchr.io/job/42",
        )
        self.assertEqual(_detect_mode(offer), "portail_tiers")

    def test_detect_mode_email_when_no_platform_hint(self):
        offer = build_offer(url=None, contact_email="hr@example.com")
        self.assertEqual(_detect_mode(offer), "email")


class AutoApplyGuardsTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_apply_returns_404_when_candidature_missing(self):
        db = FakeDB(candidature=None, offer=None)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(uuid.uuid4(), dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("AUTOAPPLY_CANDIDATURE_NOT_FOUND", str(ctx.exception.detail))

    async def test_auto_apply_blocks_portail_tiers(self):
        offer = build_offer(
            url="https://emploi-territorial.fr/offre/o123",
            candidature_url="https://agglo-larochelle.fr/jobs/1",
        )
        cand = build_candidature(offer_id=offer.id, mode="plateforme")
        db = FakeDB(candidature=cand, offer=offer)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(cand.id, dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("portail tiers", ctx.exception.detail)

    async def test_auto_apply_blocks_unsupported_site_if_mode_not_plateforme(self):
        offer = build_offer(url="https://example.com/jobs/99")
        cand = build_candidature(offer_id=offer.id, mode="email")
        db = FakeDB(candidature=cand, offer=offer)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(cand.id, dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Candidature par email", ctx.exception.detail)

    async def test_auto_apply_blocks_unsupported_site_even_if_mode_plateforme(self):
        offer = build_offer(url="https://example.com/jobs/100")
        cand = build_candidature(offer_id=offer.id, mode="plateforme")
        db = FakeDB(candidature=cand, offer=offer)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(cand.id, dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Site non supporté", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
