"""Regressions for roles and locations evidenced in the October 6 audit."""
from pathlib import Path
import unittest

from job_alerts_lib.location_audit import classify_location, should_exclude_location
from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords


class OctoberReviewTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_excluded_job_title_keywords(
            Path(__file__).parents[1] / 'config/excluded-job-title-keywords.txt')

    def test_related_management_systems_and_mixed_finance_roles(self):
        for title in (
            'Principal Software Engineer Manager',
            'Data Center Technician Manager', 'Data Center Technicians Manager',
            'Critical Environment Technician Manager (Data Center)',
            'Data Center Critical Environment Technician Manager - Melbourne',
            'Logistics Technician Manager', 'Director, Platform Software Engineering',
            'Leader, Software Engineering', 'Software Engineering Technical Leader',
            'Embedded Software Engineering Technical Leader',
            'People Operations Systems Administrator',
            'Global People Operations - Systems Administrator',
            'Senior Analyst, Revenue Accounting Systems & Automation',
            'M&A/Integration Accounting Lead',
            'Senior Software Engineer - Performance Tooling',
            'Principal FDE - Software Engineer', 'Senior Software Engineer - FDE',
            'Software Engineer - Forward Deployed Engineer',
            'Senior Software Engineer (RubyOnRails/Cypress/Cloud)',
            'Account Manager', 'Account Manager, Ada Accelerate',
            'Senior Account Manager - Healthcare',
        ):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, self.rules))

    def test_unrelated_roles_remain_excluded(self):
        for title in (
            'Software Engineer', 'Data Center Technician',
            'Critical Environment Technician', 'Logistics Technician',
            'People Operations Associate', 'Revenue Accounting Analyst',
            'Manager, Sales Development', 'Head of Enterprise Sales - Common Room',
            'Senior Golang Developer with Kubernetes', 'Salesforce Developer',
            'Machine Learning Engineer', 'Memory Layout Design Engineer',
            'Optical Fibre Manufacturing Technician', 'Leader, Services Sales',
        ):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, self.rules))
                self.assertFalse(is_excluded_job_title(title + ' / QA Project Manager', self.rules))

    def test_precise_non_european_location_pairs(self):
        for location in ('Hyderabad, IN', 'Taguig City, PH', 'Johannesburg, MEA, ZA',
                         'Seoul (Flexible)', 'Bogota (Flexible)', 'CASABLANCA, MA'):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location)[0], 'OUTSIDE_EUROPE')
                self.assertTrue(should_exclude_location(location, []))
                self.assertFalse(should_exclude_location(location + '; Athens, Greece', []))
                self.assertFalse(should_exclude_location('Worldwide remote; ' + location, []))

    def test_european_local_spelling_and_country_pairs(self):
        for location in ('Cork (IRL)', 'Vimercate (Flexible)', 'Échirolles, FR',
                         'Praha, CZ', 'Wien, AT', 'Aix en Provence, FR',
                         'Six Fours Les Plages, FR'):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location)[0], 'EUROPE')
                self.assertFalse(should_exclude_location('United States; ' + location, ['united states']))
        # Do not turn ambiguous codes/cities into reusable country exclusions.
        for location in ('Remote (CA)', 'Belmont', 'IN', 'Georgia'):
            with self.subTest(location=location):
                self.assertTrue(classify_location(location)[0].startswith('UNKNOWN'))
