#!/usr/bin/env python3
"""Collect employer job postings and publish newly discovered ones to Telegram."""

from __future__ import annotations

import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from job_alerts_lib.collector import collect_jobs
from job_alerts_lib.env import load_env
from job_alerts_lib.locations import is_excluded_location, load_excluded_location_keywords
from job_alerts_lib.roles import is_excluded_job_title, load_excluded_job_title_keywords
from job_alerts_lib.sources import configured_source_ids

SCRIPT_DIRECTORY = Path(__file__).parent
load_env(SCRIPT_DIRECTORY / ".env")

CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@dtjobalerts")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FOUND_TIMEZONE = ZoneInfo(os.environ.get("JOB_ALERTS_TIMEZONE", "Europe/Athens"))
STATE_PATH = SCRIPT_DIRECTORY / "seen-jobs.json"
POST_LOG_PATH = SCRIPT_DIRECTORY / "posted-jobs.jsonl"
EXCLUDED_LOCATIONS_PATH = SCRIPT_DIRECTORY / "excluded-location-keywords.txt"
GENERATED_EXCLUDED_LOCATIONS_PATH = (
    SCRIPT_DIRECTORY / "telegram-generated-excluded-location-keywords.txt"
)
EXCLUDED_JOB_TITLES_PATH = SCRIPT_DIRECTORY / "excluded-job-title-keywords.txt"


def load_state() -> dict[str, Any]:
    try:
        state = json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"initialized": False, "initializedSources": [], "seenIds": []}
    if "initializedSources" not in state:
        state["initializedSources"] = sorted(
            {job_id.partition(":")[0] for job_id in state.get("seenIds", [])}
        )
    return state


def save_state(
    ids: list[str] | set[str], initialized_sources: list[str] | set[str]
) -> None:
    state = {
        "initialized": True,
        "initializedSources": sorted(set(initialized_sources)),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "seenIds": sorted(set(ids)),
    }
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def send_job(job: dict[str, str]) -> int:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    text = "\n".join([
        f"💼 <b>{html.escape(job['companyName'])}</b>",
        f"<b>{html.escape(job['title'])}</b>",
        f"📍 {html.escape(job['location'])}",
        f"📅 Found: {html.escape(job['foundAt'])}",
        f"🔗 <a href=\"{html.escape(job['url'], quote=True)}\">View opening</a>",
    ])
    body = json.dumps({
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.load(response)
                if not result.get("ok"):
                    raise RuntimeError(f"Telegram rejected the message: {result}")
                return int(result["result"]["message_id"])
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read().decode() or "{}")
            retry_after = detail.get("parameters", {}).get("retry_after")
            if error.code == 429 and retry_after is not None and attempt < 4:
                time.sleep(int(retry_after) + 1)
                continue
            if error.code >= 500 and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"Telegram sendMessage failed ({error.code}): "
                f"{detail.get('description', 'unknown error')}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("Telegram connection failed after retries") from error
    raise RuntimeError("Telegram sendMessage failed after retries")


def record_post(job: dict[str, str], message_id: int) -> None:
    entry = {
        "messageId": message_id,
        "postedAt": datetime.now(timezone.utc).isoformat(),
        "companyName": job["companyName"],
        "title": job["title"],
        "location": job["location"],
        "url": job["url"],
    }
    with POST_LOG_PATH.open("a") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    jobs = collect_jobs()
    if "--collect-only" in sys.argv:
        print(f"Validated {len(jobs)} jobs")
        return

    state = load_state()
    seen = set(state["seenIds"])
    initialized_sources = set(state["initializedSources"])
    current_sources = configured_source_ids()
    post_existing = "--post-existing" in sys.argv
    if not state["initialized"] and not post_existing:
        save_state([job["id"] for job in jobs], current_sources)
        print(f"Initial seed complete: {len(jobs)} existing jobs recorded; no messages sent.")
        return

    new_sources = current_sources - initialized_sources
    if new_sources:
        seeded_jobs = [job for job in jobs if job["id"].partition(":")[0] in new_sources]
        seen.update(job["id"] for job in seeded_jobs)
        initialized_sources.update(new_sources)
        save_state(seen, initialized_sources)
        print(
            f"Initialized {len(new_sources)} new company sources with "
            f"{len(seeded_jobs)} existing jobs; none were sent.",
            flush=True,
        )

    candidate_jobs = jobs if post_existing and not state["initialized"] else [
        job for job in jobs if job["id"] not in seen
    ]
    excluded_title_keywords = load_excluded_job_title_keywords(EXCLUDED_JOB_TITLES_PATH)
    excluded_role_jobs = [
        job for job in candidate_jobs
        if is_excluded_job_title(job["title"], excluded_title_keywords)
    ]
    candidate_jobs = [
        job for job in candidate_jobs
        if not is_excluded_job_title(job["title"], excluded_title_keywords)
    ]
    if excluded_role_jobs:
        seen.update(job["id"] for job in excluded_role_jobs)
        save_state(seen, initialized_sources)
        print(
            f"Marked {len(excluded_role_jobs)} excluded-role openings as seen; none were sent.",
            flush=True,
        )
    excluded_keywords = load_excluded_location_keywords(
        EXCLUDED_LOCATIONS_PATH,
        GENERATED_EXCLUDED_LOCATIONS_PATH,
    )
    excluded_jobs = [
        job for job in candidate_jobs
        if is_excluded_location(job["location"], excluded_keywords)
    ]
    candidate_jobs = [
        job for job in candidate_jobs
        if not is_excluded_location(job["location"], excluded_keywords)
    ]
    if excluded_jobs:
        seen.update(job["id"] for job in excluded_jobs)
        save_state(seen, initialized_sources)
        print(
            f"Marked {len(excluded_jobs)} excluded-location openings as seen; none were sent.",
            flush=True,
        )

    found_at = datetime.now(FOUND_TIMEZONE).date().isoformat()
    new_jobs = [dict(job, foundAt=found_at) for job in candidate_jobs]
    total = len(new_jobs)
    for index, job in enumerate(new_jobs, start=1):
        message_id = send_job(job)
        record_post(job, message_id)
        seen.add(job["id"])
        save_state(seen, initialized_sources)
        print(f"Posted {index}/{total}: {job['companyName']} — {job['title']}", flush=True)
        time.sleep(1.1)
    print(
        f"Checked {len(jobs)} jobs; posted {len(new_jobs)} new openings; "
        f"filtered {len(excluded_role_jobs)} by role and {len(excluded_jobs)} by location."
    )


if __name__ == "__main__":
    main()
