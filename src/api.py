"""
LinkedIn Scraper API Server
===========================
Run locally:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Docker:
    docker build -t linkedin-scraper .
    docker run -p 8000:8000 linkedin-scraper

Endpoints:
    GET  /health             — liveness check
    POST /scrape-jobs        — scrape LinkedIn jobs by title/location/filters
    POST /company-details    — fetch follower count + employee count for companies
"""

import asyncio
import logging
import sys
import os

# Allow running from src/ directly
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from filters import SearchParams
from scraper import scrape_jobs, filter_by_applicants, scrape_company_details

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="LinkedIn Scraper API", version="1.0.0")


# ── Request models ────────────────────────────────────────────────────────────

class ScrapeJobsRequest(BaseModel):
    titles: list[str] = Field(..., min_length=1, example=["AI Engineer", "ML Engineer"])
    location: str = "United States"
    job_type: list[str] = []            # ["remote", "hybrid", "onsite"]
    employment_type: list[str] = []     # ["contract", "part-time", "temporary"]
    experience_level: list[str] = []    # ["mid", "senior"]
    date_posted: str = "week"           # "24h" | "week" | "month" | "any"
    sort_by: str = "recent"             # "recent" | "relevant"
    easy_apply: bool = False
    under_10_applicants: bool = False
    count: int = Field(default=25, ge=1, le=500)
    fetch_details: bool = True
    fetch_company_details: bool = False
    min_applicants: Optional[int] = None
    max_applicants: Optional[int] = None
    company_ids: list[str] = []
    industry: str = ""
    proxy: Optional[str] = None


class CompanyDetailsRequest(BaseModel):
    company_urls: list[str] = Field(
        ...,
        min_length=1,
        example=["https://www.linkedin.com/company/google"],
    )
    proxy: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/scrape-jobs")
async def api_scrape_jobs(req: ScrapeJobsRequest):
    if not req.titles:
        raise HTTPException(status_code=400, detail="titles cannot be empty")

    tasks = [
        scrape_jobs(
            SearchParams(
                title=title,
                location=req.location,
                job_type=req.job_type,
                employment_type=req.employment_type,
                experience_level=req.experience_level,
                date_posted=req.date_posted,
                sort_by=req.sort_by,
                easy_apply=req.easy_apply,
                under_10_applicants=req.under_10_applicants,
                count=req.count,
                company_ids=req.company_ids,
                industry=req.industry,
                min_applicants=req.min_applicants,
                max_applicants=req.max_applicants,
            ),
            fetch_details=req.fetch_details,
            proxy=req.proxy,
        )
        for title in req.titles
    ]

    results_per_title = await asyncio.gather(*tasks)

    all_jobs = []
    for title, jobs in zip(req.titles, results_per_title):
        for job in jobs:
            job["search_title"] = title
        jobs = filter_by_applicants(jobs, req.min_applicants, req.max_applicants)
        all_jobs.extend(jobs)

    # Optional: enrich jobs with company follower + employee counts (same as main.py)
    if req.fetch_company_details and all_jobs:
        unique_urls = list({
            j["company_linkedin_url"]
            for j in all_jobs
            if j.get("company_linkedin_url")
        })
        company_data = await scrape_company_details(unique_urls, proxy=req.proxy)
        for job in all_jobs:
            details = company_data.get(job.get("company_linkedin_url"), {})
            job["company_followers"] = details.get("company_followers")
            job["company_employee_count"] = details.get("company_employee_count")
    else:
        for job in all_jobs:
            job["company_followers"] = None
            job["company_employee_count"] = None

    return {"count": len(all_jobs), "jobs": all_jobs}


@app.post("/company-details")
async def api_company_details(req: CompanyDetailsRequest):
    if not req.company_urls:
        raise HTTPException(status_code=400, detail="company_urls cannot be empty")

    results = await scrape_company_details(req.company_urls, proxy=req.proxy)
    return {"count": len(results), "companies": results}
