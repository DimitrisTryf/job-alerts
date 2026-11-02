"""Regression cases from the November 2 role and location audit."""
from pathlib import Path
import unittest
from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords
from job_alerts_lib.location_audit import classify_location, should_exclude_location

class November2ReviewTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_excluded_job_title_keywords(
            Path(__file__).parents[1] / "config/excluded-job-title-keywords.txt")

    def test_adjacent_roles_take_precedence_over_exclusions(self):
        for title in (
            "Software Engineer – Release Management",
            "Senior Researcher - Software Verification - Microsoft Research",
            "Senior Consultant- Patient Accounting",
            "Senior Techincal Leader - Software Engineering | Java/Kafka",
            "Senior Manager, Application Software Engineering",
            "Senior Director, Data Systems Software Engineering",
            "Director, Systems Software Engineering",
            "Director, Application Software Engineering",
            "Global Process Owner - Accounts Receivable (AR Subledger)",
            "Leader, Sales Operations",
        ):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, self.rules))

    def test_related_words_do_not_protect_unrelated_roles(self):
        for title in ("Software Engineer - Backend", "Leader, Sales - Splunk",
                      "Patient Accounting Analyst", "Senior Researcher - Machine Learning",
                      "Account Executive - Identity Verification"):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, self.rules))

    def test_precise_new_titles_and_mixed_role_safeguards(self):
        for title in TITLE_CASES:
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title.upper(), self.rules))
                self.assertFalse(is_excluded_job_title(title + " / QA Project Manager", self.rules))
        for title in ("Financial Manager", "Business Compensation Analyst", "Executive Assistant",
                      "Administrative Assistant", "Senior Finance Manager"):
            self.assertFalse(is_excluded_job_title(title, self.rules))

    def test_precise_non_european_locations(self):
        for location in OUTSIDE_CASES:
            with self.subTest(location=location):
                self.assertEqual(classify_location(location.upper())[0], "OUTSIDE_EUROPE")
                self.assertTrue(should_exclude_location(location, []))
                self.assertEqual(classify_location(location + "; London, United Kingdom")[0], "EUROPE")
                self.assertFalse(should_exclude_location(location + "; Worldwide Remote", []))

    def test_european_city_country_labels(self):
        for location in EUROPE_CASES:
            with self.subTest(location=location):
                self.assertEqual(classify_location(location.upper())[0], "EUROPE")
                self.assertFalse(should_exclude_location(location + "; United States", ["united states"]))
        self.assertEqual(classify_location("München, DE +11 more…")[0], "EUROPE")
        self.assertEqual(classify_location("Échirolles, FR")[0], "EUROPE")
        self.assertEqual(classify_location("Remote — AU-Melbourne")[0], "OUTSIDE_EUROPE")

    def test_ambiguous_labels_remain_unresolved(self):
        for location in ("Remote", "Remote (IL)", "Remote (MS)", "Georgia", "IN", "CA", "TEMPLATE"):
            with self.subTest(location=location):
                self.assertTrue(classify_location(location)[0].startswith("UNKNOWN"))

TITLE_CASES = ('receptionist', 'asic physical design engineer', 'web developer', 'hr shared services', 'labor relations consultant', 'employment counsel', 'head of growth marketing', 'recruitment consultant', 'business development rep', 'user experience designer', 'backend developer', 'ingénieur développement logiciel', 'administrateur système', 'system administrator', 'global legal associate', 'administrateur réseaux', 'ingénieur logiciel', 'interaction designer', 'director, government affairs', 'help desk agent', 'frontend developer', 'legal services manager', 'accounts assistant', 'java fullstack developer', 'senior manager, seo', 'data analytics engineer', 'enterprise sales solution specialist', 'incubation sales leader', 'audio signal processing engineer', 'wafer-scale cryogenic probing engineer', 'full stack developer', 'asic layout engineer', 'software-entwickler', 'senior director, demand generation', 'growth sales lead', 'circuit design engineer', 'motion designer', 'travel agent', 'sales development intern', 'director, emea regional marketing')
OUTSIDE_CASES = ('virtual office (ontario)', 'remote (can-nb)', 'mississauga, ca', 'taipei, tw', 'brasil - remote', 'riyadh (flexible)', 'au-melbourne', 'thane belapur road, in', 'airoli, in', 'wellington (flexible)', 'auckland (flexible)', 'dalian, cn', 'virtual, cn', 'virtual, au', 'virtual, ph', 'manilla, ph', 'virtual, th', 'manilla, th')
EUROPE_CASES = ('courbevoie, fr', 'münchen, de', 'echirolles, fr', 'köln, de', 'neutal, at', 'puteaux, fr', 'nantes, fr', 'düzce, tr', 'villeurbanne cedex, fr')
