from __future__ import annotations

import unittest

from job_alerts import format_job_message


class TelegramMessageTests(unittest.TestCase):
    def test_multiple_locations_are_rendered_one_per_line(self) -> None:
        message = format_job_message({
            "companyName": "Example",
            "title": "Engineer",
            "location": "London; Paris; Remote worldwide",
            "foundAt": "2026-08-25",
            "url": "https://example.test/job",
        })

        self.assertIn("📍 <b>Locations:</b>\n• London\n• Paris\n• Remote worldwide", message)
        self.assertNotIn("additional locations", message)


if __name__ == "__main__":
    unittest.main()
