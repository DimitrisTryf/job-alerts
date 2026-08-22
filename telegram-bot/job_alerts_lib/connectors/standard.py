"""Connectors for ATS platforms with public JSON job-board APIs."""

from __future__ import annotations

import re
import urllib.parse

from job_alerts_lib.http import get_json
from job_alerts_lib.locations import is_remote_location


def fetch_greenhouse(company_id: str, company_name: str, board: str) -> list[dict[str, str]]:
    listing = get_json(
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{urllib.parse.quote(board)}/jobs?content=true"
    )
    jobs = []
    for job in listing["jobs"]:
        departments = job.get("departments") or []
        location = (job.get("location") or {}).get("name") or ""
        office_names = [
            str(office.get("name") or "").strip()
            for office in job.get("offices") or []
        ]
        if location.strip().casefold() in {"location", "n/a", "not specified"}:
            location = "; ".join(dict.fromkeys(name for name in office_names if name))
        elif len(office_names) > 1:
            locations = [location, *office_names]
            location = "; ".join(dict.fromkeys(name for name in locations if name))
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["title"],
            "location": location or "Location not specified",
            "team": departments[0].get("name", "Other") if departments else "Other",
            "url": job["absolute_url"],
        })
    return jobs

def fetch_smartrecruiters(
    company_id: str, company_name: str, tenant: str
) -> list[dict[str, str]]:
    jobs = []
    offset = 0
    while True:
        root = get_json(
            "https://api.smartrecruiters.com/v1/companies/"
            f"{urllib.parse.quote(tenant)}/postings?limit=100&offset={offset}"
            "&destination=PUBLIC"
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
    root = get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(board)}"
    )
    jobs = []
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
    root = get_json(
        "https://apply.workable.com/api/v1/widget/accounts/"
        f"{urllib.parse.quote(account)}?details=true"
    )
    jobs = []
    for job in root["jobs"]:
        locations = []
        for raw_location in job.get("locations") or []:
            location = ", ".join(
                str(part)
                for part in (
                    raw_location.get("city"),
                    raw_location.get("region"),
                    raw_location.get("country"),
                )
                if part
            )
            if location and location not in locations:
                locations.append(location)
        location = "; ".join(locations) or "Location not specified"
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
    root = get_json(
        f"https://api.lever.co/v0/postings/{urllib.parse.quote(account)}?mode=json"
    )
    jobs = []
    for job in root:
        categories = job.get("categories") or {}
        location = "; ".join(categories.get("allLocations") or [])
        location = location or categories.get("location") or "Location not specified"
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
    feed_url = account if account.startswith("https://") else (
        f"https://{urllib.parse.quote(account)}.teamtailor.com/jobs.json"
    )
    root = get_json(feed_url)
    jobs = []
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
