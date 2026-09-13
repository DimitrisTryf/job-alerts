import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import job_alerts
from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords


class TitleReviewTests(unittest.TestCase):
    def test_related_and_ambiguous_roles_survive(self):
        rules = load_excluded_job_title_keywords(job_alerts.EXCLUDED_JOB_TITLES_PATH)
        for title in (
            'Project Manager', 'Project Coordinator', 'Professional Services Manager',
            'Quality Assurance', 'FinOps Engineer', 'Financial Manager, EMEA GTM',
            'Senior Software Developer in Test (Java)', 'Software Engineer - QA',
            'Software Engineer - Test Automation', 'SDET Software Engineer',
            'Customer Success Account Manager', 'Marketing Operations Program Manager',
            'Cloud Engineer - Fin-Ops', 'Cloud Engineer - Cloud Cost Optimization',
            'Accounting Software Implementation Consultant', 'Payroll Project Manager',
            'Service Management Consultant', 'Senior Programme Planner',
            'Software Engineer / Project Manager', 'Business Analyst',
        ):
            with self.subTest(title=title):
                self.assertFalse(is_excluded_job_title(title, rules))

    def test_unrelated_roles_are_excluded(self):
        rules = load_excluded_job_title_keywords(job_alerts.EXCLUDED_JOB_TITLES_PATH)
        for title in ('Senior Software Engineer', 'Account Executive', 'ASIC Engineer',
                      'Senior Legal Counsel', 'Data Center Technician', 'Recruiter',
                      'Senior Data Scientist', 'Sales Director', 'Angular Developer'):
            with self.subTest(title=title):
                self.assertTrue(is_excluded_job_title(title, rules))

    def test_separate_logs_and_seen_checkpoint_without_sending(self):
        jobs = [dict(id='example:1', companyName='Example', title='Account Executive',
                     location='Paris', url='https://example.test/1'),
                dict(id='example:2', companyName='Example', title='Project Manager',
                     location='United States', url='https://example.test/2')]
        with tempfile.TemporaryDirectory() as directory:
            title_path = Path(directory) / 'title-filtered.jsonl'
            location_path = Path(directory) / 'location-filtered.jsonl'
            with patch.multiple(job_alerts,
                                TITLE_FILTERED_JOBS_LOG_PATH=title_path,
                                LOCATION_FILTERED_JOBS_LOG_PATH=location_path), \
                 patch.object(job_alerts, 'collect_jobs', return_value=jobs), \
                 patch.object(job_alerts, 'load_state', return_value={
                     'initialized': True, 'seenIds': [], 'initializedSources': ['example']}), \
                 patch.object(job_alerts, 'configured_source_ids', return_value={'example'}), \
                 patch.object(job_alerts, 'resolve_workday_locations', side_effect=lambda job: job), \
                 patch.object(job_alerts, 'save_state') as save, \
                 patch.object(job_alerts, 'send_job') as send, \
                 patch.object(job_alerts.sys, 'argv', ['job_alerts.py']):
                job_alerts.main()
                send.assert_not_called()
                self.assertEqual(save.call_args.args[0], {'example:1', 'example:2'})
            for path, job_id, reason in ((title_path, 'example:1', 'role'),
                                         (location_path, 'example:2', 'location')):
                rows = [json.loads(line) for line in path.read_text().splitlines()
                        if not line.startswith('#')]
                self.assertEqual([(r['jobId'], r['reason']) for r in rows], [(job_id, reason)])

    def test_already_seen_rejections_are_not_logged_again(self):
        jobs = [dict(id='example:1', companyName='Example', title='Account Executive',
                     location='Paris', url='https://example.test/1')]
        with patch.object(job_alerts, 'collect_jobs', return_value=jobs), \
             patch.object(job_alerts, 'load_state', return_value={
                 'initialized': True, 'seenIds': ['example:1'],
                 'initializedSources': ['example']}), \
             patch.object(job_alerts, 'configured_source_ids', return_value={'example'}), \
             patch.object(job_alerts, 'record_filtered_jobs') as record, \
             patch.object(job_alerts, 'save_state') as save, \
             patch.object(job_alerts, 'send_job') as send, \
             patch.object(job_alerts.sys, 'argv', ['job_alerts.py']):
            job_alerts.main()
            record.assert_not_called()
            save.assert_not_called()
            send.assert_not_called()
