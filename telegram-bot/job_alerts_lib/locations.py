"""Location normalization and exclusion rules."""

from __future__ import annotations

import re
from pathlib import Path


GLOBAL_REMOTE_PHRASES = (
    "anywhere in the world",
    "anywhere worldwide",
    "global remote",
    "globally remote",
    "remote - global",
    "remote — global",
    "remote worldwide",
    "work from anywhere",
    "worldwide remote",
)


def load_excluded_location_keywords(*paths: Path) -> list[str]:
    keywords = []
    for path in paths:
        try:
            lines = path.read_text().splitlines()
        except FileNotFoundError:
            continue
        keywords.extend(
            line.casefold()
            for raw_line in lines
            for line in [raw_line.strip()]
            if line and not line.startswith("#")
        )
    return list(dict.fromkeys(keywords))


def is_remote_location(location: str) -> bool:
    normalized = location.casefold()
    return "remote" in normalized or "work from home" in normalized


def is_global_remote_location(location: str) -> bool:
    normalized = " ".join(location.casefold().split())
    return any(phrase in normalized for phrase in GLOBAL_REMOTE_PHRASES)


def is_excluded_location(location: str, keywords: list[str]) -> bool:
    return bool(matching_excluded_location_keywords(location, keywords))


def matching_excluded_location_keywords(location: str, keywords: list[str]) -> list[str]:
    if is_global_remote_location(location):
        return []
    normalized = location.casefold()
    return [
        keyword for keyword in keywords
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
    ]
