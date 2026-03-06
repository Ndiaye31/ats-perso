import os
import sys
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

# Evite la dépendance locale à psycopg pendant les imports.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
if "app.config" in sys.modules:
    sys.modules["app.config"].settings.database_url = "sqlite+pysqlite:///:memory:"

from app.main import app


class AlertingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        @app.get("/__tests__/raise-http-503")
        def _raise_http_503():
            raise HTTPException(status_code=503, detail="Service temporairement indisponible")

        @app.get("/__tests__/raise-unhandled")
        def _raise_unhandled():
            raise RuntimeError("boom")

        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_http_5xx_contains_alert_fields(self):
        res = self.client.get("/__tests__/raise-http-503")
        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertEqual(data["alert_code"], "HTTP_5XX")
        self.assertTrue(data.get("incident_id"))

    def test_unhandled_exception_contains_alert_fields(self):
        res = self.client.get("/__tests__/raise-unhandled")
        self.assertEqual(res.status_code, 500)
        data = res.json()
        self.assertEqual(data["alert_code"], "UNHANDLED_EXCEPTION")
        self.assertTrue(data.get("incident_id"))


if __name__ == "__main__":
    unittest.main()
