#!/usr/bin/env python3
"""Fetch every configured source and print one representative live job."""

from __future__ import annotations

import sys

from job_alerts_lib.collector import collect_source_results


def main() -> None:
    results = collect_source_results()
    failures = 0
    live_sources = 0
    total_jobs = 0
    for result in results:
        if result.error:
            failures += 1
            print(f"FAIL  {result.company_name}: {result.error}")
        elif not result.jobs:
            print(f"EMPTY {result.company_name}: no current openings")
        else:
            live_sources += 1
            total_jobs += len(result.jobs)
            job = sorted(result.jobs, key=lambda item: (item["title"].casefold(), item["id"]))[0]
            print(f"OK    {result.company_name}: {job['title']} | {job['location']} | {job['url']}")

    print(
        f"Validated {len(results)} sources: {live_sources} with live jobs, "
        f"{len(results) - live_sources - failures} empty, {failures} failed; "
        f"{total_jobs} jobs total."
    )
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
