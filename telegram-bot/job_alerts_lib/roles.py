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
    return bool(matching_excluded_job_title_keywords(title, keywords))


def matching_excluded_job_title_keywords(title: str, keywords: list[str]) -> list[str]:
    normalized = " ".join(title.casefold().split())
    if has_potentially_relevant_role(normalized):
        return []
    return [
        keyword for keyword in keywords
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
    ]


# Err on the side of retaining adjacent roles, including mixed-role titles.
# This is a protection against exclusions, never a restrictive allowlist.
RELATED_ROLE_PATTERN = re.compile(
    r"(?<!\w)(?:project|program|programme|pmo|portfolio|coordinator|coordination|"
    r"professional[\s-]+services|delivery|implementation|onboarding|"
    r"service[\s-]+management|customer[\s-]+success|"
    r"quality|qa|sqa|sdet|test|testing|tester|finops|fin[\s-]+ops|"
    r"financial[\s-]+operations|finance[\s-]+operations|cloud[\s-]+cost|"
    r"cost[\s-]+optimization|cost[\s-]+optimisation|scrum|agile|"
    r"product[\s-]+manager|product[\s-]+owner|business[\s-]+analyst)(?!\w)"
)


def has_potentially_relevant_role(title: str) -> bool:
    return bool(RELATED_ROLE_PATTERN.search(title.casefold()))
