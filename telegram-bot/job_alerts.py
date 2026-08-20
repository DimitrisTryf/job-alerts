#!/usr/bin/env python3
"""Collect authoritative job postings and publish unseen ones to Telegram."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def load_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding real environment variables."""
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


load_env(Path(__file__).with_name(".env"))

CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@dtjobalerts")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
STATE_PATH = Path(__file__).with_name("seen-jobs.json")
EXCLUDED_LOCATIONS_PATH = Path(__file__).with_name("excluded-location-keywords.txt")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_POST_AGE_DAYS = 14

GREENHOUSE_SOURCES = [
    ("assemblyai", "AssemblyAI", "assemblyai"),
    ("callrail", "CallRail", "callrail"),
    ("talkdesk", "Talkdesk", "talkdesk2"),
    ("vonage", "Vonage", "vonage"),
    ("dialpad", "Dialpad", "dialpad"),
    ("aircall", "Aircall", "aircallioinc"),
    ("ada", "Ada", "ada18"),
    ("polyai", "PolyAI", "polyai"),
    ("remote", "Remote", "remotecom"),
    ("twilio", "Twilio", "twilio"),
]

SMARTRECRUITERS_SOURCES = [
    ("devexperts", "Devexperts", "Devexperts"),
]


def get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DTJobAlerts/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_greenhouse(company_id: str, company_name: str, board: str) -> list[dict[str, str]]:
    base = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    listing = get_json(base)
    jobs: list[dict[str, str]] = []

    def detail(job: dict[str, Any]) -> dict[str, Any]:
        return get_json(f"{base}/{job['id']}")

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(detail, job) for job in listing["jobs"]]
        for future in as_completed(futures):
            try:
                job = future.result()
            except Exception:
                continue
            posted_at = (job.get("first_published") or "")[:10]
            if not DATE_PATTERN.fullmatch(posted_at):
                continue
            departments = job.get("departments") or []
            jobs.append({
                "id": f"{company_id}:{job['id']}",
                "companyName": company_name,
                "title": job["title"],
                "location": (job.get("location") or {}).get("name") or "Location not specified",
                "team": departments[0].get("name", "Other") if departments else "Other",
                "postedAt": posted_at,
                "url": job["absolute_url"],
            })
    return jobs


def fetch_smartrecruiters(
    company_id: str, company_name: str, tenant: str
) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    offset = 0
    while True:
        encoded_tenant = urllib.parse.quote(tenant)
        root = get_json(
            f"https://api.smartrecruiters.com/v1/companies/{encoded_tenant}/postings"
            f"?limit=100&offset={offset}&destination=PUBLIC"
        )
        content = root["content"]
        for job in content:
            posted_at = (job.get("releasedDate") or "")[:10]
            if not DATE_PATTERN.fullmatch(posted_at):
                continue
            location_data = job.get("location") or {}
            location = ", ".join(
                str(value)
                for value in (
                    location_data.get("city"),
                    location_data.get("region"),
                    location_data.get("country"),
                )
                if value
            ) or ("Remote" if location_data.get("remote") else "Location not specified")
            title = job["name"]
            slug = re.sub(r"^-|-+$", "", re.sub(r"[^a-z0-9]+", "-", title.lower()))
            jobs.append({
                "id": f"{company_id}:{job['id']}",
                "companyName": company_name,
                "title": title,
                "location": location,
                "team": (job.get("department") or {}).get("label")
                or (job.get("function") or {}).get("label")
                or "Other",
                "postedAt": posted_at,
                "url": f"https://jobs.smartrecruiters.com/{tenant}/{job['id']}-{slug}",
            })
        offset += len(content)
        if not content or offset >= root["totalFound"]:
            break
    return jobs


def collect_jobs() -> list[dict[str, str]]:
    feeds = [
        (name, fetch_greenhouse, source)
        for source in GREENHOUSE_SOURCES
        for name in [source[1]]
    ] + [
        (name, fetch_smartrecruiters, source)
        for source in SMARTRECRUITERS_SOURCES
        for name in [source[1]]
    ]
    jobs: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetcher, *source): name for name, fetcher, source in feeds}
        for future in as_completed(futures):
            try:
                jobs.extend(future.result())
            except Exception as error:
                print(f"{futures[future]} failed: {error}", file=sys.stderr)
    if not jobs:
        raise RuntimeError("All company feeds failed")
    unique = {job["id"]: job for job in jobs}
    return sorted(unique.values(), key=lambda job: (job["postedAt"], job["id"]), reverse=True)


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"initialized": False, "seenIds": []}


def load_excluded_location_keywords() -> list[str]:
    try:
        return [
            line.casefold()
            for raw_line in EXCLUDED_LOCATIONS_PATH.read_text().splitlines()
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


def save_state(ids: list[str] | set[str]) -> None:
    state = {
        "initialized": True,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "seenIds": sorted(set(ids)),
    }
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def send_job(job: dict[str, str]) -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    text = "\n".join([
        f"💼 <b>{html.escape(job['companyName'])}</b>",
        f"<b>{html.escape(job['title'])}</b>",
        f"📍 {html.escape(job['location'])}",
        f"📅 Posted: {html.escape(job['postedAt'])}",
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
                return
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


def main() -> None:
    jobs = collect_jobs()
    if "--collect-only" in sys.argv:
        print(f"Validated {len(jobs)} jobs")
        return

    state = load_state()
    seen = set(state["seenIds"])
    post_existing = "--post-existing" in sys.argv
    if not state["initialized"] and not post_existing:
        save_state([job["id"] for job in jobs])
        print(f"Initial seed complete: {len(jobs)} existing jobs recorded; no messages sent.")
        return

    candidate_jobs = jobs if post_existing and not state["initialized"] else [
        job for job in jobs if job["id"] not in seen
    ]
    excluded_keywords = load_excluded_location_keywords()
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
        save_state(seen)
        print(
            f"Marked {len(excluded_jobs)} excluded-location openings as seen; "
            "none were sent.",
            flush=True,
        )
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=MAX_POST_AGE_DAYS)
    stale_jobs = [job for job in candidate_jobs if date.fromisoformat(job["postedAt"]) < cutoff]
    new_jobs = [job for job in candidate_jobs if date.fromisoformat(job["postedAt"]) >= cutoff]
    if stale_jobs:
        seen.update(job["id"] for job in stale_jobs)
        save_state(seen)
        print(
            f"Marked {len(stale_jobs)} openings older than {cutoff.isoformat()} as seen; "
            "none were sent.",
            flush=True,
        )
    total = len(new_jobs)
    for index, job in enumerate(reversed(new_jobs), start=1):
        send_job(job)
        seen.add(job["id"])
        save_state(seen)
        print(f"Posted {index}/{total}: {job['companyName']} — {job['title']}", flush=True)
        time.sleep(1.1)
    print(
        f"Checked {len(jobs)} jobs; posted {len(new_jobs)} new openings; "
        f"skipped {len(stale_jobs)} older than {MAX_POST_AGE_DAYS} days; "
        f"filtered {len(excluded_jobs)} by location."
    )


if __name__ == "__main__":
    main()
