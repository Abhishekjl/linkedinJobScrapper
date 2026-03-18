import asyncio
import random
import logging

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from anti_detect import get_headers, get_api_headers, build_client
from filters import SearchParams, build_search_url, build_job_detail_url, pages_needed
from parser import parse_job_cards, parse_job_detail, parse_company_page

logger = logging.getLogger(__name__)

# ── Concurrency limits ────────────────────────────────────────────────────────
SEARCH_CONCURRENCY = 2    # parallel search page fetches
DETAIL_CONCURRENCY = 2    # keep LOW — detail pages 429 very fast if burst
MIN_DELAY        = 1.5    # jitter delay for search pages (seconds)
MAX_DELAY        = 3.5
DETAIL_MIN_DELAY = 2.5    # longer jitter for detail pages
DETAIL_MAX_DELAY = 5.0


# ── Low-level fetch ───────────────────────────────────────────────────────────

async def _fetch(
    client: httpx.AsyncClient,
    url: str,
    is_api: bool = True,
    is_detail: bool = False,
) -> str:
    """Fetch a URL with anti-detect headers and human-like jitter delay."""
    if is_detail:
        await asyncio.sleep(random.uniform(DETAIL_MIN_DELAY, DETAIL_MAX_DELAY))
    else:
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    headers = get_api_headers() if is_api else get_headers()
    response = await client.get(url, headers=headers)

    # Handle 429
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 20))
        sleep_time = retry_after + random.uniform(3, 8)
        logger.warning(f"Rate limited. Sleeping {sleep_time:.0f}s then retrying...")
        await asyncio.sleep(sleep_time)
        headers = get_api_headers() if is_api else get_headers()
        response = await client.get(url, headers=headers)

    # Handle 403
    if response.status_code == 403:
        logger.warning(f"403 on {url} — backing off and retrying with fresh headers")
        await asyncio.sleep(random.uniform(8, 15))
        response = await client.get(url, headers=get_headers())

    response.raise_for_status()
    return response.text


# ── Search page fetcher ───────────────────────────────────────────────────────

async def _fetch_search_page(
    client: httpx.AsyncClient,
    params: SearchParams,
    start: int,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    params_copy = SearchParams(**params.__dict__)
    params_copy.start = start
    url = build_search_url(params_copy)
    logger.debug(f"Search page start={start}: {url}")

    async with semaphore:
        try:
            html = await _fetch(client, url, is_api=True, is_detail=False)
            jobs = parse_job_cards(html)
            logger.info(f"  start={start} → {len(jobs)} cards parsed")
            return jobs
        except httpx.HTTPStatusError as e:
            logger.warning(f"  start={start} → HTTP {e.response.status_code}, skipping")
            return []
        except Exception as e:
            logger.warning(f"  start={start} → Error: {e}, skipping")
            return []


# ── Detail page fetcher ───────────────────────────────────────────────────────

async def _fetch_job_detail(
    client: httpx.AsyncClient,
    job: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    url = build_job_detail_url(job["job_id"])
    async with semaphore:
        try:
            html = await _fetch(client, url, is_api=False, is_detail=True)
            detail = parse_job_detail(html, job["job_id"])
            return {**job, **detail}
        except httpx.HTTPStatusError as e:
            logger.warning(f"  detail {job['job_id']} → HTTP {e.response.status_code}, using card data only")
            return job
        except Exception as e:
            logger.warning(f"  detail {job['job_id']} → Error: {e}")
            return job


# ── Main scraper ──────────────────────────────────────────────────────────────

async def scrape_jobs(
    params: SearchParams,
    fetch_details: bool = True,
    proxy: str | None = None,
) -> list[dict]:
    offsets = pages_needed(params.count)
    search_sem = asyncio.Semaphore(SEARCH_CONCURRENCY)
    detail_sem  = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async with build_client(proxies=proxy) as client:

        # 1. Fetch all search pages
        logger.info(f"[{params.title}] Fetching {len(offsets)} page(s)...")
        search_tasks = [
            _fetch_search_page(client, params, offset, search_sem)
            for offset in offsets
        ]
        pages = await asyncio.gather(*search_tasks)

        # 2. Flatten + dedupe + trim
        all_jobs: list[dict] = []
        seen_ids: set[str] = set()
        for page in pages:
            for job in page:
                jid = job.get("job_id")
                if jid and jid not in seen_ids:
                    seen_ids.add(jid)
                    all_jobs.append(job)
                    if len(all_jobs) >= params.count:
                        break
            if len(all_jobs) >= params.count:
                break

        all_jobs = all_jobs[: params.count]
        logger.info(f"[{params.title}] {len(all_jobs)} unique cards collected")

        # 3. Fetch detail pages
        if fetch_details and all_jobs:
            logger.info(f"[{params.title}] Fetching details for {len(all_jobs)} jobs...")
            detail_tasks = [
                _fetch_job_detail(client, job, detail_sem)
                for job in all_jobs
            ]
            all_jobs = list(await asyncio.gather(*detail_tasks))

    return all_jobs


# ── Company details fetcher ───────────────────────────────────────────────────

COMPANY_CONCURRENCY = 2
COMPANY_MIN_DELAY   = 3.0
COMPANY_MAX_DELAY   = 6.0


async def _fetch_company(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, dict]:
    async with semaphore:
        try:
            html = await _fetch(client, url, is_api=False, is_detail=True)
            return url, parse_company_page(html)
        except Exception as e:
            logger.warning(f"  company {url} → Error: {e}")
            return url, {"company_followers": None, "company_employee_count": None}


async def scrape_company_details(
    company_urls: list[str],
    proxy: str | None = None,
) -> dict[str, dict]:
    """
    Fetch follower count and employee count for each company URL.
    Returns a dict mapping company_url → {company_followers, company_employee_count}.
    """
    sem = asyncio.Semaphore(COMPANY_CONCURRENCY)
    async with build_client(proxies=proxy) as client:
        tasks = [_fetch_company(client, url, sem) for url in company_urls]
        results = await asyncio.gather(*tasks)
    return dict(results)


# ── Applicant count post-filter ───────────────────────────────────────────────

def filter_by_applicants(
    jobs: list[dict],
    min_applicants: int | None,
    max_applicants: int | None,
) -> list[dict]:
    if min_applicants is None and max_applicants is None:
        return jobs
    filtered = []
    for job in jobs:
        count = job.get("applicant_count")
        if count is None:
            filtered.append(job)
            continue
        if min_applicants is not None and count < min_applicants:
            continue
        if max_applicants is not None and count > max_applicants:
            continue
        filtered.append(job)
    return filtered
