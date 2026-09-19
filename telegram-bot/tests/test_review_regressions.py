import unittest
from pathlib import Path

from job_alerts_lib.location_audit import classify_location, classify_post, should_exclude_location
from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords


class SeptemberReviewTests(unittest.TestCase):
    def test_non_european_locations_missed_in_posts(self):
        for location in ('Jordan, Multiple Locations', 'Kuwait City, Kuwait',
                         'MONTEVIDEO, Uruguay', 'Monterrey, MX', 'Mumbai, IN',
                         'Mumbai (IND)', 'Kowloon, HK', 'Virtual Office (Texas)',
                         'Virtual Office, Texas', 'Virtual Office (Illinois)',
                         'Virtual Office (Colorado)', 'Remote — Houston, TX', 'Remote-AMER'):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location)[0], 'OUTSIDE_EUROPE')
                self.assertTrue(should_exclude_location(location, []))
                self.assertFalse(should_exclude_location(location + '; Paris, France', []))

    def test_european_spelling_and_location_variants(self):
        for location in ('Kraków', 'Krakow', 'Wroclaw, PL', 'Wrocław',
                         'Frankfurt (Flexible)', 'Bad Homburg vor der Höhe',
                         'Les Clayes-sous-Bois, FR', 'Toulouse, FR', 'Beograd, RS',
                         'UK-Remote', 'Saint Petersburg, Russian Federation'):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location)[0], 'EUROPE')
                self.assertFalse(should_exclude_location('Denver, Colorado, US; ' + location, ['us']))

    def test_eu_remote_us_hours_are_not_a_us_location(self):
        self.assertEqual(classify_post('Remote',
            'ML Engineer( Remote from EU /US business hours overlap)',
            'https://example.test/job')[0], 'EUROPE')
        self.assertEqual(classify_location('Remote')[0], 'UNKNOWN_REMOTE')
        self.assertEqual(classify_location('Remote US')[0], 'OUTSIDE_EUROPE')

    def test_related_roles_previously_rejected(self):
        rules = load_excluded_job_title_keywords(Path(__file__).parents[1] / 'config/excluded-job-title-keywords.txt')
        for title in ('Logistics, Tax, & Customs Business Architect - Components Transformation',
                      'Recruiting Project Manager', 'Global Payroll Implementation Specialist - GPIS',
                      'Coordinator, Payroll Client Services - EMEA', 'Recruiting Coordinator (Fixed-Term)',
                      'Payroll Vendor Relationship Manager', 'Director, Talent Acquisition Transformation',
                      'Senior People Technology Analyst - Talent Acquisition',
                      'Advanced Services Engineer- Patient Accounting Experience',
                      'Manager, Advanced Services Engineering- Patient Accounting',
                      'Technical Account Manager', 'Services Account Manager',
                      'Software Engineer, Solution Validation, Benchmarking & Release Engineer',
                      'Software Developer Full-Stack Intern, AI Scoring, Evaluations and Surveys',
                      'Principal Software Engineering Manager',
                      'Senior Manager, Platform Software Engineering',
                      'Data Scientist, Experimental Projects'):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, rules))

    def test_new_unrelated_titles_and_mixed_roles(self):
        rules = load_excluded_job_title_keywords(Path(__file__).parents[1] / 'config/excluded-job-title-keywords.txt')
        for title in ('Copywriter', 'Frontend Engineer', 'Staff Backend Engineer - API Platform',
                      'SAP ABAP Developer', 'Legal Intern France', 'Senior SEO Specialist',
                      'Senior Quantum Measurement Engineer', 'Senior/Principal Optical Packaging Engineer',
                      'Wireless Software Engineer_ Intern'):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, rules))
                self.assertFalse(is_excluded_job_title(title + ' / QA Project Coordinator', rules))
        self.assertFalse(is_excluded_job_title('Software Engineer_QA', rules))


class AuditConsumptionTests(unittest.TestCase):
    def test_only_resolved_snapshot_ids_are_consumed(self):
        import json
        import tempfile
        from telegram_location_audit import consume_posts, load_posts
        reviewed = {"messageId": 1, "title": "Project Manager", "location": "Paris"}
        unknown = {"messageId": 2, "title": "Quality Analyst", "location": "Remote"}
        arrived_later = {"messageId": 3, "title": "FinOps", "location": "London"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posted.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in
                                    (reviewed, unknown, arrived_later)))
            self.assertEqual(consume_posts(path, [reviewed]), 1)
            self.assertEqual(load_posts(path), [unknown, arrived_later])

    def test_main_consume_preserves_unknown_location(self):
        import json
        import tempfile
        from argparse import Namespace
        from unittest.mock import patch
        import telegram_location_audit as audit
        known = {"messageId": 1, "title": "Project Manager", "location": "Paris", "url": ""}
        unknown = {"messageId": 2, "title": "Quality Analyst", "location": "Remote", "url": ""}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts.jsonl"
            path.write_text(json.dumps(known) + "\n" + json.dumps(unknown) + "\n")
            with patch.object(audit, "POST_LOG_PATH", path), \
                 patch.object(audit, "parse_args", return_value=Namespace(all=True, consume=True, dry_run=False)), \
                 patch.object(audit, "load_env"), patch.object(audit, "write_outputs"):
                audit.main()
            self.assertEqual(audit.load_posts(path), [unknown])
