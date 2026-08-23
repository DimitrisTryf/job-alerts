"""Connectors for enterprise and server-rendered recruitment platforms."""

from __future__ import annotations

from html.parser import HTMLParser
import re
import time
import urllib.error
import urllib.parse
from typing import Any

from job_alerts_lib.http import get_json, get_text, post_json
from job_alerts_lib.locations import is_remote_location


def workday_location(locations_text: str, external_path: str) -> str:
    """Replace an opaque Workday location count with its URL's primary location."""
    match = re.fullmatch(r"\s*(\d+)\s+Locations?\s*", locations_text, re.IGNORECASE)
    if not match or int(match.group(1)) < 2:
        return locations_text
    path_parts = urllib.parse.unquote(external_path).strip("/").split("/")
    try:
        location_slug = path_parts[path_parts.index("job") + 1]
    except (ValueError, IndexError):
        return locations_text
    words = [word for word in location_slug.split("-") if word]
    if len(words) >= 4:
        primary = ", ".join((" ".join(words[:-2]), words[-2], words[-1]))
    elif len(words) == 3 and words[0].casefold() == "remote":
        primary = ", ".join(words)
    elif len(words) >= 2:
        primary = ", ".join((" ".join(words[:-1]), words[-1]))
    else:
        return locations_text
    additional_count = int(match.group(1)) - 1
    noun = "location" if additional_count == 1 else "locations"
    return f"{primary} (+{additional_count} additional {noun})"


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
    jobs = []
    offset = 0
    limit = 20
    total = None
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
            external_path = job.get("externalPath")
            title = job.get("title")
            if not external_path or not title:
                continue
            location = job.get("locationsText") or "Location not specified"
            jobs.append({
                "id": f"{company_id}:{external_path}",
                "companyName": company_name,
                "title": title.strip(),
                "location": workday_location(location, external_path),
                "team": "Other",
                "url": f"{host}/en-US/{encoded_site}{external_path}",
            })
        offset += len(postings)
        if not postings or offset >= total:
            break
    return jobs


def fetch_eightfold(
    company_id: str,
    company_name: str,
    portal_url: str,
    employer_domain: str,
) -> list[dict[str, str]]:
    def fetch_page(start: int) -> dict[str, Any]:
        query = urllib.parse.urlencode({
            "domain": employer_domain,
            "query": "",
            "location": "",
            "start": start,
        })
        url = f"{portal_url}/api/pcsx/search?{query}"
        for attempt in range(8):
            try:
                return get_json(url)["data"]
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt == 7:
                    raise
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
                time.sleep(delay)
        raise RuntimeError("Eightfold pagination retries exhausted")

    first_page = fetch_page(0)
    page_size = len(first_page.get("positions") or [])
    if not page_size:
        return []
    pages = [first_page]
    starts = range(page_size, first_page.get("count", 0), page_size)
    pages.extend(fetch_page(start) for start in starts)

    jobs = {}
    for page in pages:
        for job in page.get("positions") or []:
            job_id = str(job.get("atsJobId") or job["id"])
            raw_locations = job.get("locations") or job.get("standardizedLocations") or []
            location = "; ".join(dict.fromkeys(str(value) for value in raw_locations if value))
            work_option = str(job.get("workLocationOption") or "")
            if "remote" in work_option.casefold() and not is_remote_location(location):
                location = f"Remote — {location}" if location else "Remote"
            jobs[job_id] = {
                "id": f"{company_id}:{job_id}",
                "companyName": company_name,
                "title": job["name"].strip(),
                "location": location or "Location not specified",
                "team": job.get("department") or "Other",
                "url": urllib.parse.urljoin(portal_url, job["positionUrl"]),
            }
    return list(jobs.values())


class SuccessFactorsSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs = []
        self.current = None
        self.capture = None
        self.capture_parts = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "tr" and "data-row" in classes:
            self.current = {}
        elif self.current is not None and tag == "a" and "jobTitle-link" in classes:
            if "url" not in self.current:
                self.current["url"] = attributes.get("href") or ""
                self.capture = "title"
                self.capture_parts = []
        elif self.current is not None and tag == "td" and "colLocation" in classes:
            self.capture = "location"
            self.capture_parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if tag == "a" and self.capture == "title":
            self.current["title"] = " ".join("".join(self.capture_parts).split())
            self.capture = None
        elif tag == "td" and self.capture == "location":
            self.current["location"] = " ".join("".join(self.capture_parts).split())
            self.capture = None
        elif tag == "tr":
            if self.current.get("url") and self.current.get("title"):
                self.jobs.append(self.current)
            self.current = None
            self.capture = None


def fetch_successfactors(
    company_id: str, company_name: str, base_url: str
) -> list[dict[str, str]]:
    jobs = {}
    offset = 0
    page_size = 50
    while True:
        query = urllib.parse.urlencode({
            "q": "",
            "sortColumn": "referencedate",
            "sortDirection": "desc",
            "startrow": offset,
        })
        parser = SuccessFactorsSearchParser()
        parser.feed(get_text(f"{base_url}/search/?{query}"))
        for job in parser.jobs:
            path = urllib.parse.urlsplit(job["url"]).path
            jobs[path] = {
                "id": f"{company_id}:{path}",
                "companyName": company_name,
                "title": job["title"],
                "location": job.get("location") or "Location not specified",
                "team": "Other",
                "url": urllib.parse.urljoin(base_url, job["url"]),
            }
        if len(parser.jobs) < page_size:
            break
        offset += page_size
    return list(jobs.values())


def fetch_oracle_recruiting(
    company_id: str,
    company_name: str,
    api_base_url: str,
    site_number: str,
    public_job_base_url: str,
) -> list[dict[str, str]]:
    jobs = {}
    offset = 0
    limit = 200
    while True:
        finder = (
            f"findReqs;siteNumber={site_number},limit={limit},offset={offset},"
            "sortBy=POSTING_DATES_DESC"
        )
        query = urllib.parse.urlencode({
            "onlyData": "true",
            "expand": "requisitionList",
            "finder": finder,
        })
        root = get_json(
            f"{api_base_url}/hcmRestApi/resources/latest/"
            f"recruitingCEJobRequisitions?{query}"
        )
        search = root["items"][0]
        requisitions = search.get("requisitionList") or []
        for job in requisitions:
            job_id = str(job["Id"])
            jobs[job_id] = {
                "id": f"{company_id}:{job_id}",
                "companyName": company_name,
                "title": job["Title"].strip(),
                "location": job.get("PrimaryLocation") or "Location not specified",
                "team": job.get("JobFunction") or job.get("JobFamily") or "Other",
                "url": f"{public_job_base_url}{urllib.parse.quote(job_id)}",
            }
        offset += len(requisitions)
        if not requisitions or offset >= search.get("TotalJobsCount", 0):
            break
    return list(jobs.values())


class ZohoRecruitParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs = []
        self.current = None
        self.capture_title = False
        self.title_parts = []
        self.td_index = -1
        self.td_parts = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "tr" and "jobDetailRow" in classes:
            self.current = {"id": attributes.get("data-rowid") or ""}
            self.td_index = -1
        elif self.current is not None and tag == "td":
            self.td_index += 1
            self.td_parts = []
        elif self.current is not None and tag == "a" and "jobdetail" in classes:
            self.current["url"] = attributes.get("href") or ""
            self.capture_title = True
            self.title_parts = []

    def handle_data(self, data: str) -> None:
        if self.capture_title:
            self.title_parts.append(data)
        if self.current is not None and self.td_index >= 0:
            self.td_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if tag == "a" and self.capture_title:
            self.current["title"] = " ".join("".join(self.title_parts).split())
            self.capture_title = False
        elif tag == "td":
            if self.td_index == 3:
                self.current["location"] = " ".join("".join(self.td_parts).split())
            self.td_parts = []
        elif tag == "tr":
            if self.current.get("id") and self.current.get("title"):
                self.jobs.append(self.current)
            self.current = None


def fetch_zoho_recruit(
    company_id: str, company_name: str, careers_url: str
) -> list[dict[str, str]]:
    parser = ZohoRecruitParser()
    parser.feed(get_text(careers_url))
    jobs = []
    for job in parser.jobs:
        location = job.get("location") or "Location not specified"
        if location == "Location not specified" and "remote" in job["title"].casefold():
            location = "Remote"
        jobs.append({
            "id": f"{company_id}:{job['id']}",
            "companyName": company_name,
            "title": job["title"],
            "location": location,
            "team": "Other",
            "url": urllib.parse.urljoin(careers_url, job["url"]),
        })
    return jobs
