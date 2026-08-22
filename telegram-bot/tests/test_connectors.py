from __future__ import annotations

import unittest
from unittest.mock import patch

from job_alerts_lib.connectors.standard import fetch_greenhouse


class GreenhouseLocationTests(unittest.TestCase):
    @patch("job_alerts_lib.connectors.standard.get_json")
    def test_placeholder_location_falls_back_to_office(self, get_json) -> None:
        get_json.return_value = {
            "jobs": [{
                "id": 123,
                "title": "Software Engineer",
                "location": {"name": "N/A"},
                "offices": [{"name": "US"}],
                "departments": [],
                "absolute_url": "https://example.test/jobs/123",
            }]
        }

        jobs = fetch_greenhouse("example", "Example", "example")

        self.assertEqual(jobs[0]["location"], "US")


if __name__ == "__main__":
    unittest.main()
