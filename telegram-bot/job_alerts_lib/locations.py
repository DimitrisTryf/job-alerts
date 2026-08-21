"""Location normalization and exclusion rules."""

from __future__ import annotations

import re
from pathlib import Path


def load_excluded_location_keywords(path: Path) -> list[str]:
    try:
        return [
            line.casefold()
            for raw_line in path.read_text().splitlines()
            for line in [raw_line.strip()]
            if line and not line.startswith("#")
        ]
    except FileNotFoundError:
        return []


def is_remote_location(location: str) -> bool:
    normalized = location.casefold()
    return "remote" in normalized or "work from home" in normalized


def is_excluded_location(location: str, keywords: list[str]) -> bool:
    if is_remote_location(location):
        return False
    normalized = location.casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
        for keyword in keywords
    )
