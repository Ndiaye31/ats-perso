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


class DetectModeCSPTests(unittest.TestCase):
    def test_detect_mode_csp_returns_choisir_service_public(self):
        offer = build_offer(
            url="https://choisirleservicepublic.gouv.fr/offre-emploi/REF-2024-001/",
            candidature_url="https://choisirleservicepublic.gouv.fr/offre-emploi/REF-2024-001/",
        )
        self.assertEqual(_detect_mode(offer), "choisir-service-public")

    def test_detect_mode_csp_not_confused_with_portail_tiers(self):
        """CSP candidature_url ne doit pas tomber dans portail_tiers."""
        offer = build_offer(
            url="https://choisirleservicepublic.gouv.fr/offre-emploi/ABC/",
            candidature_url="https://choisirleservicepublic.gouv.fr/offre-emploi/ABC/",
            contact_email="rh@mairie.fr",
        )
        self.assertNotEqual(_detect_mode(offer), "portail_tiers")
        self.assertEqual(_detect_mode(offer), "choisir-service-public")

    def test_detect_mode_csp_with_only_url(self):
        """Offre CSP sans candidature_url explicite → email si email dispo."""
        offer = build_offer(
            url="https://choisirleservicepublic.gouv.fr/offre-emploi/XYZ/",
            contact_email="rh@mairie.fr",
        )
        # Pas de candidature_url → pas de choisir-service-public, fallback email
        self.assertEqual(_detect_mode(offer), "email")


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

    async def test_auto_apply_does_not_block_supported_portail_tiers(self):
        """Beetween est un portail tiers supporté — pas de blocage PORTAIL_TIERS."""
        offer = build_offer(
            url="https://emploi-territorial.fr/offre/o456",
            candidature_url="https://app.beetween.com/WeaselWeb/p/#/apply/job/abc123/poste",
        )
        cand = build_candidature(offer_id=offer.id, mode="portail_tiers")
        db = FakeDB(candidature=cand, offer=offer)
        # Ne doit PAS lever AUTOAPPLY_PORTAIL_TIERS_BLOCKED.
        # Va lever une autre erreur (Playwright non dispo en test) mais pas le blocage portail.
        try:
            await auto_apply(cand.id, dry_run=True, db=db)
        except HTTPException as e:
            self.assertNotIn("AUTOAPPLY_PORTAIL_TIERS_BLOCKED", str(e.detail))
        except Exception:
            pass  # Playwright import error expected in test env

    async def test_auto_apply_still_blocks_unsupported_portail_tiers(self):
        """Un portail tiers non supporté reste bloqué."""
        offer = build_offer(
            url="https://emploi-territorial.fr/offre/o789",
            candidature_url="https://unknown-portal.com/jobs/42",
        )
        cand = build_candidature(offer_id=offer.id, mode="portail_tiers")
        db = FakeDB(candidature=cand, offer=offer)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(cand.id, dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("AUTOAPPLY_PORTAIL_TIERS_BLOCKED", str(ctx.exception.detail))

    async def test_auto_apply_csp_not_blocked_as_portail_tiers(self):
        """Une offre CSP ne doit pas être bloquée par le garde portail_tiers."""
        offer = build_offer(
            url="https://choisirleservicepublic.gouv.fr/offre-emploi/REF-001/",
            candidature_url="https://choisirleservicepublic.gouv.fr/offre-emploi/REF-001/",
        )
        cand = build_candidature(offer_id=offer.id, mode="choisir-service-public")
        db = FakeDB(candidature=cand, offer=offer)
        try:
            await auto_apply(cand.id, dry_run=True, db=db)
        except HTTPException as e:
            self.assertNotIn("AUTOAPPLY_PORTAIL_TIERS_BLOCKED", str(e.detail))
        except Exception:
            pass  # Playwright non dispo en test env

    async def test_auto_apply_csp_blocked_by_email_guard_when_mode_email(self):
        """Mode email reste bloqué même pour une URL CSP."""
        offer = build_offer(
            url="https://choisirleservicepublic.gouv.fr/offre-emploi/REF-002/",
            contact_email="rh@mairie.fr",
        )
        cand = build_candidature(offer_id=offer.id, mode="email")
        db = FakeDB(candidature=cand, offer=offer)
        with self.assertRaises(HTTPException) as ctx:
            await auto_apply(cand.id, dry_run=True, db=db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("AUTOAPPLY_EMAIL_MODE_BLOCKED", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
