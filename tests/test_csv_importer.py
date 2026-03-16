import os
import sys
import unittest

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.scrapers.csv_importer import CsvImporter, CsvImporterConfig


def _make_config(**overrides):
    defaults = {
        "name": "choisirleservicepublic.gouv.fr",
        "csv_url": "https://example.test/csp.csv",
        "separator": ";",
        "columns": {
            "title": "Intitulé du poste",
            "company": "Employeur",
            "company_fallback": "Organisme de rattachement",
            "location": "Localisation du poste",
            "reference": "Référence",
            "description": "Compétences attendues",
            "date_limite": "Date de fin de publication par défaut",
        },
    }
    defaults.update(overrides)
    return CsvImporterConfig(**defaults)


CSV_HEADER = (
    "Intitulé du poste;Employeur;Organisme de rattachement;"
    "Localisation du poste;Référence;Compétences attendues;"
    "Date de fin de publication par défaut"
)


class TestParseCsvBasic(unittest.TestCase):
    def test_parse_csv_basic(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Chef de projet SI;Mairie de Lyon;Métropole de Lyon;"
            "Rhône (69);REF-2024-001;Gestion de projets informatiques;"
            "31/03/2026\n"
            "Développeur Python;DINUM;;Paris (75);REF-2024-002;"
            "Python, Django, PostgreSQL;30/06/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0].title, "Chef de projet SI")
        self.assertEqual(offers[0].company, "Mairie de Lyon")
        self.assertEqual(offers[0].location, "Rhône (69)")
        self.assertEqual(
            offers[0].url,
            "https://choisirleservicepublic.gouv.fr/offre-emploi/REF-2024-001/",
        )
        self.assertEqual(offers[0].date_limite, "31/03/2026")

        self.assertEqual(offers[1].title, "Développeur Python")
        self.assertEqual(offers[1].company, "DINUM")
        self.assertEqual(offers[1].description, "Python, Django, PostgreSQL")


class TestParseCsvDedup(unittest.TestCase):
    def test_parse_csv_dedup(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Chef de projet SI;Mairie de Lyon;;Lyon;REF-001;Compétences;31/03/2026\n"
            "Chef de projet SI;Mairie de Lyon;;Lyon;REF-001;Compétences;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1, "Duplicate rows should be skipped")


class TestParseCsvEmailExtraction(unittest.TestCase):
    def test_email_in_description(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Analyste;Ministère X;;Paris;REF-003;"
            "Envoyer CV à recrutement@ministere.gouv.fr;31/12/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].email_contact, "recrutement@ministere.gouv.fr")

    def test_no_email(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Analyste;Ministère X;;Paris;REF-004;Pas d'email ici;31/12/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1)
        self.assertIsNone(offers[0].email_contact)


class TestParseCsvCompanyFallback(unittest.TestCase):
    def test_company_fallback(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "DBA PostgreSQL;;Conseil Départemental 33;Gironde;REF-005;SQL;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].company, "Conseil Départemental 33")

    def test_company_both_empty(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "DBA PostgreSQL;;;Gironde;REF-006;SQL;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].company, "Inconnu")


class TestParseCsvUrlConstruction(unittest.TestCase):
    def test_url_from_reference(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Admin sys;DINUM;;Paris;2024-ABC-123;Linux;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(
            offers[0].url,
            "https://choisirleservicepublic.gouv.fr/offre-emploi/2024-ABC-123/",
        )
        self.assertEqual(offers[0].candidature_url, offers[0].url)

    def test_no_reference_no_url(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            "Admin sys;DINUM;;Paris;;Linux;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 1)
        self.assertIsNone(offers[0].url)


class TestParseCsvSkipNoTitle(unittest.TestCase):
    def test_skip_empty_title(self):
        csv_text = (
            f"{CSV_HEADER}\n"
            ";DINUM;;Paris;REF-007;Linux;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, set())

        self.assertEqual(len(offers), 0)


class TestParseCsvKnownHashes(unittest.TestCase):
    def test_known_hashes_skip(self):
        from app.utils import compute_content_hash

        h = compute_content_hash("Admin sys", "DINUM", "Paris")
        csv_text = (
            f"{CSV_HEADER}\n"
            "Admin sys;DINUM;;Paris;REF-008;Linux;31/03/2026\n"
        )
        config = _make_config()
        importer = CsvImporter(config)
        offers = importer._parse_csv(csv_text, {h})

        self.assertEqual(len(offers), 0, "Known hash should be skipped")


class TestResolveCsvUrl(unittest.TestCase):
    def test_resolve_dynamic_url(self):
        from unittest.mock import Mock, patch

        config = _make_config(
            dataset_page="https://www.data.gouv.fr/datasets/les-offres-diffusees-sur-choisir-le-service-public",
            resource_url_pattern=r"https://www\.data\.gouv\.fr/api/1/datasets/r/[0-9a-f-]+",
        )
        importer = CsvImporter(config)

        response = Mock()
        response.text = """
        <a href="https://www.data.gouv.fr/api/1/datasets/r/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">CSV</a>
        """
        response.raise_for_status.return_value = None

        with patch("app.scrapers.csv_importer.requests.get", return_value=response):
            url = importer._resolve_csv_url()

        self.assertEqual(url, "https://www.data.gouv.fr/api/1/datasets/r/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    def test_resolve_fallback_on_error(self):
        from unittest.mock import patch
        import requests as req

        config = _make_config(
            dataset_page="https://www.data.gouv.fr/datasets/test",
        )
        importer = CsvImporter(config)

        with patch("app.scrapers.csv_importer.requests.get", side_effect=req.RequestException("timeout")):
            url = importer._resolve_csv_url()

        self.assertEqual(url, config.csv_url, "Should fallback to static csv_url")

    def test_no_dataset_page_uses_csv_url(self):
        config = _make_config()  # no dataset_page
        importer = CsvImporter(config)
        url = importer._resolve_csv_url()
        self.assertEqual(url, config.csv_url)


if __name__ == "__main__":
    unittest.main()
