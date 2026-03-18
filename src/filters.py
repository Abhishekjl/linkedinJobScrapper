from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlencode, quote_plus


# ── LinkedIn filter constants ────────────────────────────────────────────────

JOB_TYPE_MAP = {
    "remote":  "2",
    "onsite":  "1",
    "on-site": "1",
    "hybrid":  "3",
}

EXPERIENCE_MAP = {
    "internship": "1",
    "intern":     "1",
    "entry":      "2",
    "entry-level":"2",
    "junior":     "2",
    "associate":  "2",
    "mid":        "3",
    "mid-level":  "3",
    "senior":     "4",
    "sr":         "4",
    "lead":       "4",
    "director":   "5",
    "executive":  "6",
}

DATE_POSTED_MAP = {
    "24h":    "r86400",
    "day":    "r86400",
    "week":   "r604800",
    "7d":     "r604800",
    "month":  "r2592000",
    "30d":    "r2592000",
    "any":    "",
}

SORT_BY_MAP = {
    "relevant":  "R",   # LinkedIn default
    "recent":    "DD",  # Most recent first
}

INDUSTRY_MAP = {
    "technology":   "96",
    "tech":         "96",
    "finance":      "43",
    "healthcare":   "14",
    "education":    "69",
    "retail":       "27",
    "manufacturing":"22",
    "consulting":   "104",
    "media":        "28",
    "government":   "75",
}


@dataclass
class SearchParams:
    # Required
    title: str

    # Location
    location: str = "Worldwide"               # e.g. "India", "United States", "Remote"
    geo_id: str = ""                           # LinkedIn geoId (auto-resolved if blank)

    # Job filters
    job_type: list[str] = field(default_factory=list)        # ["remote","hybrid"]
    experience_level: list[str] = field(default_factory=list) # ["mid","senior"]
    date_posted: str = "any"                   # "24h","week","month","any"
    easy_apply: bool = False

    # Sorting
    sort_by: Literal["relevant", "recent"] = "recent"

    # Applicant count filter (post-filter, not LinkedIn native)
    max_applicants: int | None = None          # only return jobs with <= N applicants
    min_applicants: int | None = None

    # Pagination
    count: int = 25                            # how many jobs to return total
    start: int = 0                             # offset (LinkedIn uses 0,25,50...)

    # Optional advanced
    company_ids: list[str] = field(default_factory=list)     # LinkedIn company IDs
    industry: str = ""                         # e.g. "technology"
    under_10_applicants: bool = False          # LinkedIn native "Under 10 applicants"
    has_verifications: bool = False            # LinkedIn verified jobs
    salary_base: int | None = None             # base salary filter (USD)


# ── GEO ID lookup (most common) ─────────────────────────────────────────────

GEO_IDS = {
    "india":          "102713980",
    "in":             "102713980",
    "united states":  "103644278",
    "usa":            "103644278",
    "us":             "103644278",
    "united kingdom": "101165590",
    "uk":             "101165590",
    "canada":         "101174742",
    "ca":             "101174742",
    "australia":      "101452733",
    "au":             "101452733",
    "germany":        "101282230",
    "de":             "101282230",
    "singapore":      "102454443",
    "sg":             "102454443",
    "uae":            "104305776",
    "dubai":          "106204383",
    "remote":         "90000070",   # LinkedIn "Remote" geo
    "worldwide":      "92000000",
    "anywhere":       "92000000",
}


def resolve_geo_id(location: str) -> tuple[str, str]:
    """Return (geoId, display_location) for a given location string."""
    key = location.strip().lower()
    geo_id = GEO_IDS.get(key, "")
    return geo_id, location


def build_search_url(params: SearchParams) -> str:
    """
    Build the LinkedIn Jobs search URL from SearchParams.
    Uses the public guest API endpoint (no auth required).
    """
    geo_id, location = resolve_geo_id(params.location)
    if params.geo_id:
        geo_id = params.geo_id  # override if explicitly provided

    qs: dict = {
        "keywords":  params.title,
        "location":  location,
        "start":     params.start,
        "pageSize":  min(25, params.count),   # LinkedIn max per page is 25
        "sortBy":    SORT_BY_MAP.get(params.sort_by, "DD"),
    }

    if geo_id:
        qs["geoId"] = geo_id

    # ── Job type (f_WT) ──────────────────────────────────────────────────────
    wt_codes = []
    for jt in params.job_type:
        code = JOB_TYPE_MAP.get(jt.lower().strip())
        if code:
            wt_codes.append(code)
    if wt_codes:
        qs["f_WT"] = ",".join(wt_codes)

    # ── Experience level (f_E) ───────────────────────────────────────────────
    exp_codes = []
    for exp in params.experience_level:
        code = EXPERIENCE_MAP.get(exp.lower().strip())
        if code:
            exp_codes.append(code)
    if exp_codes:
        qs["f_E"] = ",".join(exp_codes)

    # ── Date posted (f_TPR) ──────────────────────────────────────────────────
    tpr = DATE_POSTED_MAP.get(params.date_posted.lower(), "")
    if tpr:
        qs["f_TPR"] = tpr

    # ── Easy apply ───────────────────────────────────────────────────────────
    if params.easy_apply:
        qs["f_LF"] = "f_AL"

    # ── Under 10 applicants ──────────────────────────────────────────────────
    if params.under_10_applicants:
        qs["f_JIYN"] = "true"

    # ── Verified jobs ────────────────────────────────────────────────────────
    if params.has_verifications:
        qs["f_VJ"] = "true"

    # ── Company filter ───────────────────────────────────────────────────────
    if params.company_ids:
        qs["f_C"] = ",".join(params.company_ids)

    # ── Industry ─────────────────────────────────────────────────────────────
    if params.industry:
        ind_code = INDUSTRY_MAP.get(params.industry.lower(), "")
        if ind_code:
            qs["f_I"] = ind_code

    base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    return f"{base}?{urlencode(qs)}"


def build_job_detail_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


def pages_needed(total_wanted: int) -> list[int]:
    """Return list of start offsets needed to collect total_wanted jobs."""
    offsets = []
    start = 0
    while start < total_wanted:
        offsets.append(start)
        start += 25
    return offsets
