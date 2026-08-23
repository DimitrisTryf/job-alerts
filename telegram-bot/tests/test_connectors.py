from __future__ import annotations

import unittest
from unittest.mock import patch

from job_alerts_lib.connectors.standard import fetch_greenhouse
from job_alerts_lib.connectors.enterprise import workday_location


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

    @patch("job_alerts_lib.connectors.standard.get_json")
    def test_multiple_offices_are_retained(self, get_json) -> None:
        get_json.return_value = {
            "jobs": [{
                "id": 456,
                "title": "Software Engineer",
                "location": {"name": "Multiple locations"},
                "offices": [{"name": "London"}, {"name": "New York"}],
                "departments": [],
                "absolute_url": "https://example.test/jobs/456",
            }]
        }

        jobs = fetch_greenhouse("example", "Example", "example")

        self.assertEqual(jobs[0]["location"], "Multiple locations; London; New York")


class WorkdayLocationTests(unittest.TestCase):
    def test_location_count_uses_primary_location_from_path(self) -> None:
        self.assertEqual(
            workday_location(
                "2 Locations",
                "/job/San-Jose-California-US/Software-Engineer_123",
            ),
            "San Jose, California, US (+1 additional location)",
        )

    def test_plural_additional_location_count(self) -> None:
        self.assertEqual(
            workday_location(
                "4 Locations",
                "/job/Remote-Quebec-Canada/Software-Engineer_123",
            ),
            "Remote, Quebec, Canada (+3 additional locations)",
        )

    def test_explicit_location_is_unchanged(self) -> None:
        self.assertEqual(
            workday_location("London, United Kingdom", "/job/London-UK/role"),
            "London, United Kingdom",
        )


if __name__ == "__main__":
    unittest.main()
