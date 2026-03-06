import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# Evite la dépendance locale à psycopg pendant les imports.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.main import app
from app.routers.health import get_db


class _FakeDBOk:
    def execute(self, _query):
        return 1


class _FakeDBKo:
    def execute(self, _query):
        raise RuntimeError("db down")


class HealthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_returns_ok_with_details(self):
        def _override_db():
            yield _FakeDBOk()

        app.dependency_overrides[get_db] = _override_db
        with patch("app.routers.health.settings.database_url", "sqlite+pysqlite:///:memory:"), patch(
            "app.routers.health.settings.cv_path", ""
        ), patch("app.routers.health.settings.diplome_path", ""):
            res = self.client.get("/health")

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["checks"]["db"]["status"], "ok")
        self.assertEqual(data["checks"]["config"]["status"], "ok")

    def test_health_returns_503_when_db_check_fails(self):
        def _override_db():
            yield _FakeDBKo()

        app.dependency_overrides[get_db] = _override_db
        with patch("app.routers.health.settings.database_url", "sqlite+pysqlite:///:memory:"), patch(
            "app.routers.health.settings.cv_path", ""
        ), patch("app.routers.health.settings.diplome_path", ""):
            res = self.client.get("/health")

        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertEqual(data["status"], "ko")
        self.assertEqual(data["checks"]["db"]["status"], "ko")


if __name__ == "__main__":
    unittest.main()
