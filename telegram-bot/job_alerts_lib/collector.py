"""Source orchestration and cross-source deduplication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import sys
from typing import Callable

from job_alerts_lib.connectors import (
    fetch_ashby,
    fetch_eightfold,
    fetch_greenhouse,
    fetch_lever,
    fetch_oracle_recruiting,
    fetch_smartrecruiters,
    fetch_successfactors,
    fetch_teamtailor,
    fetch_workable,
    fetch_workday,
    fetch_zoho_recruit,
)
from job_alerts_lib.sources import (
    ASHBY_SOURCES,
    EIGHTFOLD_SOURCES,
    GREENHOUSE_SOURCES,
    LEVER_SOURCES,
    ORACLE_RECRUITING_SOURCES,
    SMARTRECRUITERS_SOURCES,
    SUCCESSFACTORS_SOURCES,
    TEAMTAILOR_SOURCES,
    WORKABLE_SOURCES,
    WORKDAY_SOURCES,
    ZOHO_RECRUIT_SOURCES,
)

Job = dict[str, str]
Fetcher = Callable[..., list[Job]]


@dataclass(frozen=True)
class Feed:
    source_id: str
    company_name: str
    fetcher: Fetcher
    arguments: tuple[str, ...]


@dataclass
class SourceResult:
    source_id: str
    company_name: str
    jobs: list[Job]
    error: Exception | None = None


def _feeds_for(fetcher: Fetcher, sources: list[tuple[str, ...]]) -> list[Feed]:
    return [Feed(source[0], source[1], fetcher, source) for source in sources]


def configured_feeds() -> list[Feed]:
    return (
        _feeds_for(fetch_greenhouse, GREENHOUSE_SOURCES)
        + _feeds_for(fetch_smartrecruiters, SMARTRECRUITERS_SOURCES)
        + _feeds_for(fetch_ashby, ASHBY_SOURCES)
        + _feeds_for(fetch_workable, WORKABLE_SOURCES)
        + _feeds_for(fetch_lever, LEVER_SOURCES)
        + _feeds_for(fetch_teamtailor, TEAMTAILOR_SOURCES)
        + _feeds_for(fetch_workday, WORKDAY_SOURCES)
        + _feeds_for(fetch_eightfold, EIGHTFOLD_SOURCES)
        + _feeds_for(fetch_successfactors, SUCCESSFACTORS_SOURCES)
        + _feeds_for(fetch_oracle_recruiting, ORACLE_RECRUITING_SOURCES)
        + _feeds_for(fetch_zoho_recruit, ZOHO_RECRUIT_SOURCES)
    )

def collect_source_results() -> list[SourceResult]:
    feeds = configured_feeds()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(feed.fetcher, *feed.arguments): feed
            for feed in feeds
        }
        for future in as_completed(futures):
            feed = futures[future]
            try:
                jobs = future.result()
                results.append(SourceResult(feed.source_id, feed.company_name, jobs))
            except Exception as error:
                results.append(SourceResult(feed.source_id, feed.company_name, [], error))
    return sorted(results, key=lambda result: result.company_name.casefold())


def collect_jobs() -> list[Job]:
    results = collect_source_results()
    jobs = []
    for result in results:
        if result.error:
            print(f"{result.company_name} failed: {result.error}", file=sys.stderr)
        else:
            jobs.extend(result.jobs)
    if not jobs:
        raise RuntimeError("All company feeds failed")
    unique = {job["id"]: job for job in jobs}
    return sorted(
        unique.values(),
        key=lambda job: (job["companyName"].casefold(), job["title"].casefold(), job["id"]),
    )
