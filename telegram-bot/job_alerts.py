#!/usr/bin/env python3
"""Collect employer job postings and publish newly discovered ones to Telegram."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


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
FOUND_TIMEZONE = ZoneInfo(os.environ.get("JOB_ALERTS_TIMEZONE", "Europe/Athens"))
STATE_PATH = Path(__file__).with_name("seen-jobs.json")
EXCLUDED_LOCATIONS_PATH = Path(__file__).with_name("excluded-location-keywords.txt")

GREENHOUSE_SOURCES = [
    ("stripe", "Stripe", "stripe"),
    ("five9", "Five9", "five9"),
    ("ujet", "UJET", "ujet"),
    ("cresta", "Cresta", "cresta"),
    ("invoca", "Invoca", "invoca"),
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

ASHBY_SOURCES = [
    ("docker", "Docker", "Docker"),
    ("replicant", "Replicant", "Replicant"),
]

WORKABLE_SOURCES = [
    ("epignosis", "Epignosis", "epignosis"),
    ("cloudtalk", "CloudTalk", "cloudtalk"),
    ("remofirst", "Remofirst", "remofirst"),
]

LEVER_SOURCES = [
    ("netomi", "Netomi", "netomi"),
    ("sugarcrm", "SugarCRM", "sugarcrm"),
]

TEAMTAILOR_SOURCES = [
    ("puzzel", "Puzzel", "puzzel"),
    ("sumsub", "Sumsub", "sumsub"),
]

WORKDAY_SOURCES = [
    ("8x8", "8x8", "8x8inc", "wd5", "8x8_External_Careers"),
    ("ringcentral", "RingCentral", "ringcentral", "wd1", "RingCentral_Careers"),
    ("genesys", "Genesys", "genesys", "wd1", "Genesys"),
]


def get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DTJobAlerts/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "DTJobAlerts/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_greenhouse(company_id: str, company_name: str, board: str) -> list[dict[str, str]]:
    encoded_board = urllib.parse.quote(board)
    listing = get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{encoded_board}/jobs?content=true"
    )
    jobs: list[dict[str, str]] = []
    for job in listing["jobs"]:
        departments = job.get("departments") or []
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["title"],
            "location": (job.get("location") or {}).get("name") or "Location not specified",
            "team": departments[0].get("name", "Other") if departments else "Other",
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
                "url": f"https://jobs.smartrecruiters.com/{tenant}/{job['id']}-{slug}",
            })
        offset += len(content)
        if not content or offset >= root["totalFound"]:
            break
    return jobs


def fetch_ashby(company_id: str, company_name: str, board: str) -> list[dict[str, str]]:
    encoded_board = urllib.parse.quote(board)
    root = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{encoded_board}")
    jobs: list[dict[str, str]] = []
    for job in root["jobs"]:
        location = job.get("location") or "Location not specified"
        if job.get("isRemote") and not is_remote_location(location):
            location = f"Remote — {location}"
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["title"].strip(),
            "location": location,
            "team": job.get("team") or job.get("department") or "Other",
            "url": job["jobUrl"],
        })
    return jobs


def fetch_workable(
    company_id: str, company_name: str, account: str
) -> list[dict[str, str]]:
    encoded_account = urllib.parse.quote(account)
    root = get_json(
        f"https://apply.workable.com/api/v1/widget/accounts/{encoded_account}"
        "?details=true"
    )
    jobs: list[dict[str, str]] = []
    for job in root["jobs"]:
        location_parts = []
        for location in job.get("locations") or []:
            value = ", ".join(
                str(part)
                for part in (
                    location.get("city"),
                    location.get("region"),
                    location.get("country"),
                )
                if part
            )
            if value and value not in location_parts:
                location_parts.append(value)
        location = "; ".join(location_parts) or "Location not specified"
        if job.get("telecommuting") and not is_remote_location(location):
            location = f"Remote — {location}"
        department = job.get("department") or "Other"
        if isinstance(department, list):
            department = ", ".join(department) or "Other"
        jobs.append({
            "id": f"{company_id}:{job['shortcode']}",
            "companyName": company_name,
            "title": job["title"].strip(),
            "location": location,
            "team": department,
            "url": job["url"],
        })
    return jobs


def fetch_lever(company_id: str, company_name: str, account: str) -> list[dict[str, str]]:
    encoded_account = urllib.parse.quote(account)
    root = get_json(f"https://api.lever.co/v0/postings/{encoded_account}?mode=json")
    jobs: list[dict[str, str]] = []
    for job in root:
        categories = job.get("categories") or {}
        all_locations = categories.get("allLocations") or []
        location = "; ".join(all_locations) or categories.get("location") or "Location not specified"
        if job.get("workplaceType") == "remote" and not is_remote_location(location):
            location = f"Remote — {location}"
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["text"].strip(),
            "location": location,
            "team": categories.get("team") or categories.get("department") or "Other",
            "url": job["hostedUrl"],
        })
    return jobs


def fetch_teamtailor(
    company_id: str, company_name: str, account: str
) -> list[dict[str, str]]:
    encoded_account = urllib.parse.quote(account)
    root = get_json(f"https://{encoded_account}.teamtailor.com/jobs.json")
    jobs: list[dict[str, str]] = []
    for job in root["items"]:
        posting = job.get("_jobposting") or {}
        raw_locations = posting.get("jobLocation") or []
        if isinstance(raw_locations, dict):
            raw_locations = [raw_locations]
        locations = []
        for raw_location in raw_locations:
            address = raw_location.get("address") or {}
            location = ", ".join(
                str(part)
                for part in (
                    address.get("addressLocality"),
                    address.get("addressRegion"),
                    address.get("addressCountry"),
                )
                if part
            )
            if location and location not in locations:
                locations.append(location)
        location = "; ".join(locations) or "Location not specified"
        if posting.get("jobLocationType") == "TELECOMMUTE":
            location = f"Remote — {location}"
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["title"].strip(),
            "location": location,
            "team": "Other",
            "url": job["url"],
        })
    return jobs


def fetch_workday(
    company_id: str,
    company_name: str,
    tenant: str,
    data_center: str,
    site: str,
) -> list[dict[str, str]]:
    encoded_tenant = urllib.parse.quote(tenant)
    encoded_site = urllib.parse.quote(site)
    host = f"https://{tenant}.{data_center}.myworkdayjobs.com"
    endpoint = f"{host}/wday/cxs/{encoded_tenant}/{encoded_site}/jobs"
    jobs: list[dict[str, str]] = []
    offset = 0
    limit = 20
    total: int | None = None
    while True:
        root = post_json(endpoint, {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "",
        })
        if total is None:
            total = root.get("total", 0)
        postings = root.get("jobPostings") or []
        for job in postings:
            external_path = job["externalPath"]
            jobs.append({
                "id": f"{company_id}:{external_path}",
                "companyName": company_name,
                "title": job["title"].strip(),
                "location": job.get("locationsText") or "Location not specified",
                "team": "Other",
                "url": f"{host}/en-US/{encoded_site}{external_path}",
            })
        offset += len(postings)
        if not postings or offset >= total:
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
    ] + [
        (name, fetch_ashby, source)
        for source in ASHBY_SOURCES
        for name in [source[1]]
    ] + [
        (name, fetch_workable, source)
        for source in WORKABLE_SOURCES
        for name in [source[1]]
    ] + [
        (name, fetch_lever, source)
        for source in LEVER_SOURCES
        for name in [source[1]]
    ] + [
        (name, fetch_teamtailor, source)
        for source in TEAMTAILOR_SOURCES
        for name in [source[1]]
    ] + [
        (name, fetch_workday, source)
        for source in WORKDAY_SOURCES
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
    return sorted(
        unique.values(),
        key=lambda job: (job["companyName"].casefold(), job["title"].casefold(), job["id"]),
    )


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


def send_job(job: dict[str, str]) -> None:
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
    initialized_sources = set(state["initializedSources"])
    current_sources = {job["id"].partition(":")[0] for job in jobs}
    post_existing = "--post-existing" in sys.argv
    if not state["initialized"] and not post_existing:
        save_state([job["id"] for job in jobs], current_sources)
        print(f"Initial seed complete: {len(jobs)} existing jobs recorded; no messages sent.")
        return

    new_sources = current_sources - initialized_sources
    if new_sources:
        seeded_jobs = [
            job for job in jobs if job["id"].partition(":")[0] in new_sources
        ]
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
        save_state(seen, initialized_sources)
        print(
            f"Marked {len(excluded_jobs)} excluded-location openings as seen; "
            "none were sent.",
            flush=True,
        )
    found_at = datetime.now(FOUND_TIMEZONE).date().isoformat()
    new_jobs = [dict(job, foundAt=found_at) for job in candidate_jobs]
    total = len(new_jobs)
    for index, job in enumerate(new_jobs, start=1):
        send_job(job)
        seen.add(job["id"])
        save_state(seen, initialized_sources)
        print(f"Posted {index}/{total}: {job['companyName']} — {job['title']}", flush=True)
        time.sleep(1.1)
    print(
        f"Checked {len(jobs)} jobs; posted {len(new_jobs)} new openings; "
        f"filtered {len(excluded_jobs)} by location."
    )


if __name__ == "__main__":
    main()
