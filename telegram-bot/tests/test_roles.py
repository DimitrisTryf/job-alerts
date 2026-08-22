from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords


class RoleFilterTests(unittest.TestCase):
    def test_matches_whole_words_and_phrases(self) -> None:
        rules = ["hr", "recruiter", "accounting", "people operations"]
        self.assertTrue(is_excluded_job_title("Senior HR Manager", rules))
        self.assertTrue(is_excluded_job_title("Technical Recruiter", rules))
        self.assertTrue(is_excluded_job_title("Director, People Operations", rules))
        self.assertTrue(is_excluded_job_title("Accounting Manager", rules))

    def test_does_not_match_substrings_or_unrelated_finance_roles(self) -> None:
        rules = ["hr", "accounting"]
        self.assertFalse(is_excluded_job_title("Threat Researcher", rules))
        self.assertFalse(is_excluded_job_title("Finance Systems Engineer", rules))

    def test_loads_unique_rules_and_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.txt"
            path.write_text("# comment\nRecruiter\nrecruiter\n\nAccounting\n")
            self.assertEqual(
                load_excluded_job_title_keywords(path),
                ["recruiter", "accounting"],
            )


if __name__ == "__main__":
    unittest.main()
