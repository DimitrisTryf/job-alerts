"""Conservative job-title exclusion rules."""

from __future__ import annotations

import re
from pathlib import Path


def load_excluded_job_title_keywords(path: Path) -> list[str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    return list(dict.fromkeys(
        line.casefold()
        for raw_line in lines
        for line in [raw_line.strip()]
        if line and not line.startswith("#")
    ))


def is_excluded_job_title(title: str, keywords: list[str]) -> bool:
    normalized = " ".join(title.casefold().split())
    return any(
        re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
        for keyword in keywords
    )
