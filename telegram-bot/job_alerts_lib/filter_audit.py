"""Persistent audit log for jobs excluded before Telegram publishing."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


HEADER = "# Jobs filtered before Telegram publishing, one JSON object per line."


def _existing_job_ids(path: Path) -> set[str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return set()
    ids = set()
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("jobId"):
            ids.add(str(entry["jobId"]))
    return ids


def record_filtered_jobs(
    path: Path,
    jobs: list[dict[str, str]],
    reason: str,
    matched_terms: dict[str, list[str]] | None = None,
) -> int:
    """Append each job once and return the number of newly recorded entries."""
    existing_ids = _existing_job_ids(path)
    new_jobs = [job for job in jobs if job["id"] not in existing_ids]
    if not new_jobs:
        return 0
    if not path.exists() or not path.read_text().strip():
        path.write_text(HEADER + "\n")
    filtered_at = datetime.now(timezone.utc).isoformat()
    with path.open("a") as log:
        for job in new_jobs:
            entry = {
                "jobId": job["id"],
                "filteredAt": filtered_at,
                "reason": reason,
                "matchedTerms": (matched_terms or {}).get(job["id"], []),
                "companyName": job["companyName"],
                "title": job["title"],
                "location": job["location"],
                "url": job["url"],
            }
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(new_jobs)
