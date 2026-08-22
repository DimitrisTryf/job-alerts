from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from job_alerts_lib.filter_audit import record_filtered_jobs


class FilterAuditTests(unittest.TestCase):
    def test_records_each_filtered_job_once_with_reason(self) -> None:
        job = {
            "id": "example:123",
            "companyName": "Example",
            "title": "Accountant",
            "location": "Paris",
            "url": "https://example.test/jobs/123",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filtered.jsonl"
            terms = {"example:123": ["accountant"]}
            self.assertEqual(record_filtered_jobs(path, [job], "role", terms), 1)
            self.assertEqual(record_filtered_jobs(path, [job], "role"), 0)
            entries = [
                json.loads(line)
                for line in path.read_text().splitlines()
                if not line.startswith("#")
            ]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["jobId"], "example:123")
            self.assertEqual(entries[0]["reason"], "role")
            self.assertEqual(entries[0]["matchedTerms"], ["accountant"])


if __name__ == "__main__":
    unittest.main()
