"""Regressions for precise phrases approved in the September 21 audit."""
from pathlib import Path
import unittest

from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords
from job_alerts_lib.location_audit import classify_post


class September21ReviewTests(unittest.TestCase):
    def test_explicit_city_country_and_state_pairs(self):
        for location in ('Cairo, EG', 'Remote — Dallas, TX', 'Remote - Dallas, TX'):
            with self.subTest(location=location):
                self.assertEqual(classify_post(location, 'Technical Lead', '')[0],
                                 'OUTSIDE_EUROPE')
        self.assertEqual(classify_post('Cairo, EG; Athens, Greece', '', '')[0], 'EUROPE')
        self.assertEqual(classify_post('Remote — Dallas, TX; London, UK', '', '')[0], 'EUROPE')

    def test_confirmed_roles_and_mixed_role_safeguards(self):
        rules = load_excluded_job_title_keywords(
            Path(__file__).resolve().parents[1] / 'config/excluded-job-title-keywords.txt')
        for title in (
            'Senior Director, Key Accounts Sales, UKI',
            'GPU/AI Global Sales - Customer Acquisition',
            'AI Workforce Digital Specialist - Finish Speaking',
            'Digital Solution Specialist Security - German & French Speaking',
            'Digital Solution Specialist Security - German Speaking',
            'Commercial Executive - Healthcare & Life Sciences',
            'Senior Client Director - UK Market - Microsoft Advertising',
            'NOC Engineer / SRE',
            'Leader, Sales',
        ):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, rules))
                self.assertFalse(is_excluded_job_title(title + ' / Project Manager', rules))
        for title in ('Global Sales Operations Program Manager',
                      'NOC Engineer - Quality Assurance',
                      'Commercial Executive / FinOps',
                      'Leader, Sales Implementation',
                      'Financial Manager, EMEA GTM',
                      'Senior Cloud Solution Architect'):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, rules))
