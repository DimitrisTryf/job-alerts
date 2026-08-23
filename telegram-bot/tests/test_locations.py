from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from job_alerts_lib.locations import is_excluded_location
from job_alerts_lib.location_audit import (
    classify_location,
    classify_post,
    should_exclude_location,
)
from telegram_location_audit import clear_post_log, load_posts, posts_for_date


class LocationClassificationTests(unittest.TestCase):
    def test_european_remote_is_kept(self) -> None:
        self.assertEqual(classify_location("Remote - Germany")[0], "EUROPE")

    def test_us_remote_is_excluded(self) -> None:
        classification, terms = classify_location("Remote - United States")
        self.assertEqual(classification, "OUTSIDE_EUROPE")
        self.assertIn("united states", terms)
        self.assertTrue(is_excluded_location("Remote - United States", terms))

    def test_worldwide_remote_bypasses_exclusions(self) -> None:
        location = "Remote worldwide"
        self.assertEqual(classify_location(location)[0], "GLOBAL_REMOTE")
        self.assertFalse(is_excluded_location(location, ["remote"]))

    def test_bare_remote_requires_review(self) -> None:
        self.assertEqual(classify_location("Remote")[0], "UNKNOWN_REMOTE")

    def test_mixed_europe_and_us_location_is_kept(self) -> None:
        self.assertEqual(
            classify_location("London, United Kingdom; New York, United States")[0],
            "EUROPE",
        )
        self.assertFalse(
            should_exclude_location(
                "London, United Kingdom; New York, United States",
                ["new york", "united states"],
            )
        )

    def test_ambiguous_georgia_is_not_assumed_european(self) -> None:
        self.assertEqual(classify_location("Georgia")[0], "UNKNOWN")

    def test_country_codes_from_ats_locations(self) -> None:
        self.assertEqual(classify_location("Brasov, RO")[0], "EUROPE")
        self.assertEqual(classify_location("Remote Home, GB")[0], "EUROPE")
        self.assertEqual(classify_location("Milpitas, California, US")[0], "OUTSIDE_EUROPE")

    def test_generic_multi_location_uses_official_url_evidence(self) -> None:
        self.assertEqual(
            classify_post(
                "2 Locations",
                "Account Executive",
                "https://example.test/job/Amsterdam-Netherlands/role",
            )[0],
            "EUROPE",
        )
        self.assertEqual(
            classify_post(
                "2 Locations",
                "Software Engineer - United States",
                "https://example.test/job/Milpitas-California-US/role",
            )[0],
            "OUTSIDE_EUROPE",
        )

    def test_workday_ui_locale_is_not_location_evidence(self) -> None:
        self.assertEqual(
            classify_post(
                "Remote",
                "Software Engineer",
                "https://example.myworkdayjobs.com/en-US/site/job/Remote/role",
            )[0],
            "UNKNOWN_REMOTE",
        )

    def test_hyphenated_url_location_is_evidence(self) -> None:
        self.assertEqual(
            classify_post(
                "2 Locations",
                "Senior Data Scientist",
                "https://example.myworkdayjobs.com/en-US/site/job/San-Jose-CA/role",
            )[0],
            "OUTSIDE_EUROPE",
        )

    def test_country_codes_from_reviewed_ats_locations(self) -> None:
        self.assertEqual(classify_location("GRANADA, ES")[0], "EUROPE")
        self.assertEqual(classify_location("Remote (SAU)")[0], "OUTSIDE_EUROPE")
        self.assertEqual(classify_location("LIMA, PE")[0], "OUTSIDE_EUROPE")
        self.assertEqual(classify_location("BR")[0], "OUTSIDE_EUROPE")

    def test_reviewed_region_abbreviations_and_city(self) -> None:
        self.assertEqual(classify_location("Remote-UK&I")[0], "EUROPE")
        self.assertEqual(classify_location("Remote-NORAM")[0], "OUTSIDE_EUROPE")
        self.assertEqual(classify_location("Erlangen, BY, DE, 91052")[0], "EUROPE")

    def test_selects_posts_by_local_calendar_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts.jsonl"
            path.write_text(
                "# comment\n"
                + json.dumps({
                    "postedAt": "2026-08-20T22:30:00+00:00",
                    "location": "Paris",
                })
                + "\n"
            )
            posts = posts_for_date(
                load_posts(path),
                datetime(2026, 8, 21).date(),
                ZoneInfo("Europe/Athens"),
            )
            self.assertEqual(len(posts), 1)

    def test_clear_post_log_leaves_valid_empty_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts.jsonl"
            path.write_text('{"messageId": 1}\n')
            clear_post_log(path)
            self.assertEqual(load_posts(path), [])


if __name__ == "__main__":
    unittest.main()
