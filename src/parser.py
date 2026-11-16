import re
from bs4 import BeautifulSoup


# ── Workplace type normalizer ─────────────────────────────────────────────────

def normalize_workplace_type(raw: str) -> str:
    """
    Extract clean workplace type from any text — even full paragraphs.
    Returns: "Remote" | "Hybrid" | "On-site"
    Defaults to "On-site" if no keyword found.
    """
    if not raw:
        return "On-site"
    text = re.sub(r"\b(?:not|no|non)[\s\-]+(?:a\s+)?remote\b", " ", raw.lower())
    if re.search(r"\bremote\b", text):
        return "Remote"
    if re.search(r"\bhybrid\b", text):
        return "Hybrid"
    if re.search(r"\bon[\s\-]?site\b|\bonsite\b|\bin[\s\-]?office\b|\bat[\s\-]?office\b|\bin[\s\-]person\b|\boffice[\s\-]based\b", text):
        return "On-site"
    return "On-site"  # default assumption when no keyword found


# ── Years of experience extractor ─────────────────────────────────────────────

def extract_experience(text: str) -> str:
    """
    Extract years of experience requirement from job description.
    Handles patterns like:
      - "3-5 years"        → "3-5 years"
      - "5+ years"         → "5+ years"
      - "at least 3 years" → "3+ years"
      - "minimum 5 years"  → "5+ years"
      - "3 to 7 years"     → "3-7 years"
      - "10+ years"        → "10+ years"
    Returns empty string if not found.
    """
    if not text:
        return ""

    # Pattern 1: "X-Y years" or "X–Y years" or "X to Y years"
    m = re.search(r"(\d+)\s*(?:–|-|to)\s*(\d+)\s*\+?\s*years?", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)} years"

    # Pattern 2: "X+ years" or "X years+"
    m = re.search(r"(\d+)\s*\+\s*years?|(\d+)\s*years?\s*\+", text, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2)
        return f"{val}+ years"

    # Pattern 3: "at least X years" / "minimum X years" / "over X years"
    m = re.search(r"(?:at\s+least|minimum|over|more\s+than)\s+(\d+)\s*years?", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}+ years"

    # Pattern 4: plain "X years of experience"
    m = re.search(r"(\d+)\s*years?\s+(?:of\s+)?(?:work\s+)?experience", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} years"

    return ""


# ── Job Card Parser (search results page) ────────────────────────────────────

def parse_job_cards(html: str) -> list[dict]:
    """Parse job listing cards from LinkedIn search results HTML."""
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for card in soup.find_all("li"):
        try:
            job = _parse_single_card(card)
            if job and job.get("job_id"):
                jobs.append(job)
        except Exception:
            continue
    return jobs


def _parse_single_card(card) -> dict | None:
    job = {}

    # ── Job ID ───────────────────────────────────────────────────────────────
    base_card = card.find("div", {"data-entity-urn": True})
    if not base_card:
        base_card = card.find(attrs={"data-entity-urn": True})
    if base_card:
        urn = base_card.get("data-entity-urn", "")
        job["job_id"] = urn.split(":")[-1]
    else:
        link = card.find("a", href=re.compile(r"/jobs/view/(\d+)"))
        if link:
            m = re.search(r"/jobs/view/(\d+)", link["href"])
            job["job_id"] = m.group(1) if m else None
        if not job.get("job_id"):
            return None

    # ── Title ─────────────────────────────────────────────────────────────────
    title_el = (
        card.find("h3", class_=re.compile(r"base-search-card__title|job-search-card__title")) or
        card.find("span", class_=re.compile(r"sr-only")) or
        card.find("h3")
    )
    job["title"] = title_el.get_text(strip=True) if title_el else ""

    # ── Company ───────────────────────────────────────────────────────────────
    company_el = (
        card.find("h4", class_=re.compile(r"base-search-card__subtitle|job-search-card__company")) or
        card.find("a", class_=re.compile(r"hidden-nested-link")) or
        card.find("h4")
    )
    job["company"] = company_el.get_text(strip=True) if company_el else ""

    # ── Company URL ───────────────────────────────────────────────────────────
    company_link = card.find("a", class_=re.compile(r"hidden-nested-link"))
    job["company_linkedin_url"] = company_link["href"].split("?")[0] if company_link and company_link.get("href") else ""

    # ── Location ──────────────────────────────────────────────────────────────
    loc_el = (
        card.find("span", class_=re.compile(r"job-search-card__location|base-search-card__metadata")) or
        card.find("span", class_=re.compile(r"location"))
    )
    job["location"] = loc_el.get_text(strip=True) if loc_el else ""

    # ── Job URL ───────────────────────────────────────────────────────────────
    link_el = card.find("a", class_=re.compile(r"base-card__full-link|job-search-card__title-link"))
    if not link_el:
        link_el = card.find("a", href=re.compile(r"/jobs/view/"))
    job["job_url"] = link_el["href"].split("?")[0] if link_el and link_el.get("href") else \
        f"https://www.linkedin.com/jobs/view/{job['job_id']}"

    # ── Posted Date ───────────────────────────────────────────────────────────
    date_el = card.find("time")
    if date_el:
        job["posted_date"] = date_el.get("datetime", date_el.get_text(strip=True))
        job["posted_text"] = date_el.get_text(strip=True)
    else:
        date_span = card.find("span", class_=re.compile(r"date|listed"))
        job["posted_date"] = date_span.get_text(strip=True) if date_span else ""
        job["posted_text"] = job["posted_date"]

    # ── Salary ────────────────────────────────────────────────────────────────
    salary_el = card.find("span", class_=re.compile(r"salary|compensation"))
    job["salary"] = salary_el.get_text(strip=True) if salary_el else ""

    # ── Easy Apply ────────────────────────────────────────────────────────────
    job["easy_apply"] = bool(card.find(string=re.compile(r"Easy Apply", re.I)))

    return job


# ── Job Detail Parser (individual job page) ──────────────────────────────────

def parse_job_detail(html: str, job_id: str) -> dict:
    """Parse full job detail page for rich metadata."""
    soup = BeautifulSoup(html, "lxml")
    detail = {"job_id": job_id}

    # ── Description ───────────────────────────────────────────────────────────
    desc_el = (
        soup.find("div", class_=re.compile(r"description__text|show-more-less-html")) or
        soup.find("section", class_=re.compile(r"description"))
    )
    description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""
    detail["description"] = description

    # ── Years of experience (from description) ────────────────────────────────
    detail["experience_required"] = extract_experience(description)

    # ── Job criteria items ────────────────────────────────────────────────────
    criteria = soup.find_all("li", class_=re.compile(r"description__job-criteria-item"))
    for item in criteria:
        header = item.find("h3")
        value  = item.find("span")
        if not header or not value:
            continue
        htext = header.get_text(strip=True).lower()
        vtext = value.get_text(strip=True)
        if "seniority" in htext:
            detail["seniority_level"] = vtext
        elif "employment" in htext:
            detail["employment_type"] = vtext
        elif "function" in htext:
            detail["job_function"] = vtext
        elif "industry" in htext or "industries" in htext:
            detail["industries"] = vtext

    # ── Workplace type — normalized ───────────────────────────────────────────
    raw_wtype = ""
    wtype_el = soup.find(string=re.compile(r"\b(Remote|Hybrid|On-site|Onsite)\b", re.I))
    if wtype_el:
        raw_wtype = wtype_el.strip()
    # Try dedicated element first, fall back to scanning full description
    detail["workplace_type"] = normalize_workplace_type(raw_wtype) if raw_wtype else \
                                normalize_workplace_type(description)

    # ── Applicant Count ───────────────────────────────────────────────────────
    applicant_el = soup.find(string=re.compile(r"\d+\s*(applicant|people clicked Apply)", re.I))
    if applicant_el:
        m = re.search(r"([\d,]+)", applicant_el)
        detail["applicant_count"] = int(m.group(1).replace(",", "")) if m else None
    else:
        detail["applicant_count"] = None

    # ── Skills ────────────────────────────────────────────────────────────────
    skills_section = soup.find("div", class_=re.compile(r"skills-section|job-details-skill"))
    if skills_section:
        skills = skills_section.find_all("span", class_=re.compile(r"skill"))
        detail["skills"] = [s.get_text(strip=True) for s in skills if s.get_text(strip=True)]
    else:
        detail["skills"] = _extract_skills_from_text(description)

    # ── Job Poster / Hiring Manager ───────────────────────────────────────────
    poster_section = soup.find("div", class_=re.compile(r"hirer-card|message-the-recruiter|job-poster"))
    if poster_section:
        poster_name  = poster_section.find("span", class_=re.compile(r"name|actor-name"))
        poster_title = poster_section.find("span", class_=re.compile(r"subtitle|title|headline"))
        poster_link  = poster_section.find("a", href=re.compile(r"/in/"))
        detail["job_poster"] = {
            "name":         poster_name.get_text(strip=True) if poster_name else "",
            "title":        poster_title.get_text(strip=True) if poster_title else "",
            "linkedin_url": poster_link["href"].split("?")[0] if poster_link and poster_link.get("href") else "",
        }
    else:
        detail["job_poster"] = {}

    return detail


# ── Company Page Parser ───────────────────────────────────────────────────────

def parse_company_page(html: str) -> dict:
    """Parse follower count and employee count from a LinkedIn company public page."""
    soup = BeautifulSoup(html, "lxml")
    result = {"company_followers": None, "company_employee_count": None}

    text = soup.get_text(" ", strip=True)

    # Followers — e.g. "1,234,567 followers" or "12K followers"
    m = re.search(r"([\d,]+(?:\.\d+)?[KkMm]?)\s*followers", text)
    if m:
        result["company_followers"] = m.group(1).strip()

    # Employee count — e.g. "10,001+ employees" or "51-200 employees"
    m = re.search(r"([\d,]+(?:\+|-[\d,]+)?)\s*employees", text, re.IGNORECASE)
    if m:
        result["company_employee_count"] = m.group(1).strip()

    return result


# ── Skill Extraction from Description ────────────────────────────────────────

COMMON_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "React", "Angular", "Vue", "Node.js", "Django", "FastAPI", "Flask",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "BigQuery", "Snowflake",
    "Machine Learning", "Deep Learning", "NLP", "LLM", "PyTorch", "TensorFlow",
    "Spark", "Kafka", "Airflow", "dbt", "MLflow",
    "REST", "GraphQL", "gRPC", "Microservices", "CI/CD", "Git",
    "SQL", "NoSQL", "Linux", "Agile", "Scrum",
    "LangChain", "RAG", "Hugging Face", "Scikit-learn",
]


def _extract_skills_from_text(text: str) -> list[str]:
    found = []
    for skill in COMMON_SKILLS:
        if re.search(r"\b" + re.escape(skill) + r"\b", text, re.IGNORECASE):
            found.append(skill)
    return found
