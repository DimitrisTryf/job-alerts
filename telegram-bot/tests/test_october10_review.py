"""Precise title decisions from the October 10 queue review."""
from pathlib import Path
import unittest

from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords


class October10ReviewTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_excluded_job_title_keywords(
            Path(__file__).parents[1] / 'config/excluded-job-title-keywords.txt')

    def test_global_sales_describes_the_role_not_its_audience(self):
        self.assertFalse(is_excluded_job_title(
            'Communications Manager, Global Sales Enablement', self.rules))
        self.assertFalse(is_excluded_job_title('Global Sales Operations Analyst', self.rules))
        self.assertTrue(is_excluded_job_title(
            'GPU/AI Global Sales - Customer Acquisition', self.rules))

    def test_technical_leadership_variants_are_retained(self):
        for title in ('Software Engineer Technical Leader - Embedded C, Networking',
                      'Software Engineering Technical Leader',
                      'Senior Data Engineer / Technical Lead (Azure Databricks)',
                      'Technical Lead, AI-Native Software Engineering (hybrid)',
                      'Presales Application & Software Architect',
                      'Software Engineer Technical Leader / QA'):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, self.rules))
        self.assertTrue(is_excluded_job_title('Software Engineer - Embedded C', self.rules))

    def test_patient_accounting_consulting_is_not_automatically_accounting_work(self):
        for title in ('Associate Consultant, OH Patient Accounting',
                      'Senior Principal Consultant, OH Patient Accounting',
                      'Consultant, Patient Accounting'):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, self.rules))
        self.assertTrue(is_excluded_job_title('Patient Accounting Analyst', self.rules))

    def test_new_precise_roles_preserve_mixed_titles(self):
        for title in ('.NET Developer with Angular',
                      'Senior DC IT Support Technician',
                      'Inside Sales - Representative (Active) 2',
                      'Responsable Commercial EMEA H/F'):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, self.rules))
                self.assertFalse(is_excluded_job_title(title + ' / QA Project Manager', self.rules))
        self.assertFalse(is_excluded_job_title('Senior .NET Development Project Manager', self.rules))

    def test_explicit_testing_and_release_roles_are_retained(self):
        for title in ('Software Engineer / Release Engineer',
                      'Security Engineer / Senior Red Team Pentester',
                      'Security Engineer - Pentesting',
                      'Hardware Engineer - Design Verification',
                      'Hardware Engineer - Hardware Verification'):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, self.rules))
        self.assertTrue(is_excluded_job_title('Hardware Engineer - Board Design', self.rules))
        self.assertTrue(is_excluded_job_title('Account Executive - Identity Verification', self.rules))
