"""
LinkedIn Job Scraper
====================
Standalone usage:
    python main.py

Apify usage:
    Reads INPUT from Apify key-value store automatically.

Input schema:
    {
        "titles":              ["AI Engineer", "ML Engineer"],
        "location":            "India",
        "job_type":            ["remote", "hybrid"],
        "experience_level":    ["mid", "senior"],
        "date_posted":         "week",       // "24h" | "week" | "month" | "any"
        "sort_by":             "recent",     // "recent" | "relevant"
        "easy_apply":          false,
        "under_10_applicants": false,
        "count":               50,           // total jobs per title
        "fetch_details":         true,
        "fetch_company_details": false,      // fetch follower + employee count per company
        "max_applicants":        null,       // post-filter: only jobs with <= N applicants
        "min_applicants":        null,
        "proxy":                 null,       // "http://user:pass@host:port"
        "company_ids":           [],         // LinkedIn company IDs
        "industry":              ""
    }
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

from filters import SearchParams
from scraper import scrape_jobs, filter_by_applicants, scrape_company_details

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Apify detection ───────────────────────────────────────────────────────────

def is_apify() -> bool:
    return os.environ.get("APIFY_IS_AT_HOME") == "1"


def read_local_input() -> dict:
    """Fall back to local input.json or hardcoded defaults."""
    if os.path.exists("input.json"):
        with open("input.json") as f:
            return json.load(f)
    return {
        "titles":           ["AI Engineer"],
        "location":         "India",
        "job_type":         ["remote"],
        "experience_level": ["mid", "senior"],
        "date_posted":      "week",
        "sort_by":          "recent",
        "easy_apply":       False,
        "count":            25,
        "fetch_details":    True,
    }


def build_params(inp: dict, title: str) -> SearchParams:
    return SearchParams(
        title=title,
        location=inp.get("location", "Worldwide"),
        job_type=inp.get("job_type", []),
        experience_level=inp.get("experience_level", []),
        date_posted=inp.get("date_posted", "any"),
        sort_by=inp.get("sort_by", "recent"),
        easy_apply=inp.get("easy_apply", False),
        under_10_applicants=inp.get("under_10_applicants", False),
        has_verifications=inp.get("has_verifications", False),
        count=inp.get("count", 25),
        company_ids=inp.get("company_ids", []),
        industry=inp.get("industry", ""),
        max_applicants=inp.get("max_applicants"),
        min_applicants=inp.get("min_applicants"),
    )


async def run():
    if is_apify():
        from apify import Actor
        async with Actor:
            inp = await Actor.get_input() or {}
            all_jobs = await _scrape(inp)
            await Actor.push_data(all_jobs)
            logger.info("Pushed to Apify dataset.")
    else:
        inp = read_local_input()
        all_jobs = await _scrape(inp)
        out_path = "output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_jobs, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Saved to {out_path}")

    return all_jobs


async def _scrape(inp: dict) -> list:
    titles: list[str] = inp.get("titles", ["Software Engineer"])
    fetch_details: bool = inp.get("fetch_details", True)
    fetch_company: bool = inp.get("fetch_company_details", False)
    proxy: str | None = inp.get("proxy")
    min_app = inp.get("min_applicants")
    max_app = inp.get("max_applicants")

    logger.info(f"Starting scrape for {len(titles)} title(s): {titles}")
    logger.info(f"Config: location={inp.get('location')} | type={inp.get('job_type')} | "
                f"exp={inp.get('experience_level')} | posted={inp.get('date_posted')} | "
                f"count={inp.get('count')} per title | company_details={fetch_company}")

    start_time = datetime.now()

    tasks = [
        scrape_jobs(build_params(inp, title), fetch_details=fetch_details, proxy=proxy)
        for title in titles
    ]
    results_per_title = await asyncio.gather(*tasks)

    all_jobs = []
    for title, jobs in zip(titles, results_per_title):
        for job in jobs:
            job["search_title"] = title
        jobs = filter_by_applicants(jobs, min_app, max_app)
        all_jobs.extend(jobs)
        logger.info(f"[{title}] → {len(jobs)} jobs after applicant filter")

    # Optional: enrich jobs with company follower + employee counts
    if fetch_company and all_jobs:
        unique_urls = list({
            j["company_linkedin_url"]
            for j in all_jobs
            if j.get("company_linkedin_url")
        })
        logger.info(f"Fetching company details for {len(unique_urls)} unique companies...")
        company_data = await scrape_company_details(unique_urls, proxy=proxy)
        for job in all_jobs:
            details = company_data.get(job.get("company_linkedin_url"), {})
            job["company_followers"] = details.get("company_followers")
            job["company_employee_count"] = details.get("company_employee_count")
    else:
        for job in all_jobs:
            job["company_followers"] = None
            job["company_employee_count"] = None

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Done. Total jobs: {len(all_jobs)} in {elapsed:.1f}s")

    return all_jobs


if __name__ == "__main__":
    asyncio.run(run())
