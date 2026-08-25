from __future__ import annotations

import unittest
from unittest.mock import patch

from job_alerts_lib.connectors.standard import fetch_greenhouse
from job_alerts_lib.connectors.enterprise import resolve_workday_locations, workday_location


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

        self.assertEqual(jobs[0]["location"], "London; New York")


class WorkdayLocationTests(unittest.TestCase):
    def test_location_count_uses_primary_location_from_path(self) -> None:
        self.assertEqual(
            workday_location(
                "2 Locations",
                "/job/San-Jose-California-US/Software-Engineer_123",
            ),
            "San Jose, California, US",
        )

    def test_actual_additional_locations_are_retained(self) -> None:
        self.assertEqual(
            workday_location(
                "4 Locations",
                "/job/Remote-Quebec-Canada/Software-Engineer_123",
                ["Remote, Quebec, Canada", "London, United Kingdom", "Paris, France"],
            ),
            "Remote, Quebec, Canada; London, United Kingdom; Paris, France",
        )

    def test_explicit_location_is_unchanged(self) -> None:
        self.assertEqual(
            workday_location("London, United Kingdom", "/job/London-UK/role"),
            "London, United Kingdom",
        )

    @patch("job_alerts_lib.connectors.enterprise.get_json")
    def test_unseen_job_locations_are_resolved_from_detail_api(self, get_json) -> None:
        get_json.return_value = {
            "jobPostingInfo": {
                "location": "London, United Kingdom",
                "additionalLocations": ["Paris, France", "Berlin, Germany"],
            }
        }
        job = {
            "id": "example:/job/London-UK/role",
            "companyName": "Example",
            "title": "Engineer",
            "location": "London, UK",
            "locationsText": "3 Locations",
            "externalPath": "/job/London-UK/role",
            "locationDetailsUrl": "https://example.test/detail",
            "team": "Other",
            "url": "https://example.test/job",
        }

        resolved = resolve_workday_locations(job)

        self.assertEqual(
            resolved["location"],
            "London, UK; London, United Kingdom; Paris, France; Berlin, Germany",
        )
        self.assertNotIn("locationDetailsUrl", resolved)


if __name__ == "__main__":
    unittest.main()
