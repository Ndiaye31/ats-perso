import unittest
from unittest.mock import patch

from app import scheduler


class SchedulerTests(unittest.TestCase):
    def test_optional_batch_disabled(self):
        with patch("app.scheduler.settings.scheduler_batch_enabled", False):
            result = scheduler.run_optional_batch_job()
        self.assertFalse(result["enabled"])

    def test_run_scheduled_jobs_once_aggregates_jobs(self):
        with patch("app.scheduler.run_scrape_job", return_value={"inserted": 1}), patch(
            "app.scheduler.run_rescore_job", return_value={"scored": 2}
        ), patch("app.scheduler.settings.scheduler_batch_enabled", False):
            result = scheduler.run_scheduled_jobs_once()

        self.assertIn("scrape", result)
        self.assertIn("rescore", result)
        self.assertIn("optional_batch", result)
        self.assertEqual(result["scrape"]["inserted"], 1)
        self.assertEqual(result["rescore"]["scored"], 2)


if __name__ == "__main__":
    unittest.main()
