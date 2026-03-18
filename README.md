# LinkedIn Job Scraper

Scrape LinkedIn job listings without an API key. Search by job title, location, experience level, workplace type, and more — results are saved directly to your Apify dataset.

---

## What it does

- Searches LinkedIn's public job listings for one or more job titles
- Runs all titles **concurrently** for fast results
- Optionally fetches full job detail pages for rich metadata (description, skills, applicant count, hiring manager)
- Optionally fetches company pages to enrich results with **follower count** and **employee count**
- Filters results by applicant count, workplace type, experience level, industry, and more
- No LinkedIn account or API key required

---

## Output

Each job result is a JSON object with the following fields:

| Field | Description |
|---|---|
| `job_id` | LinkedIn internal job ID |
| `title` | Job title |
| `company` | Company name |
| `company_linkedin_url` | Company LinkedIn profile URL |
| `location` | Job location text |
| `job_url` | Direct link to the LinkedIn job posting |
| `posted_date` | ISO date when the job was posted |
| `posted_text` | Human-readable posting time (e.g. "2 days ago") |
| `salary` | Salary range if listed |
| `easy_apply` | Whether LinkedIn Easy Apply is available |
| `search_title` | Which input title matched this job |
| `description` | Full job description *(requires `fetch_details: true`)* |
| `experience_required` | Extracted years of experience requirement (e.g. `"3-5 years"`) |
| `seniority_level` | e.g. `"Mid-Senior level"` |
| `employment_type` | e.g. `"Full-time"` |
| `job_function` | e.g. `"Engineering"` |
| `industries` | Industry category from LinkedIn |
| `workplace_type` | `"Remote"`, `"Hybrid"`, or `"On-site"` |
| `applicant_count` | Number of applicants (if shown by LinkedIn) |
| `skills` | List of skills extracted from the job description |
| `job_poster` | Object with `name`, `title`, and `linkedin_url` of the hiring manager |
| `company_followers` | LinkedIn follower count of the hiring company (e.g. `"1,234,567"`) *(requires `fetch_company_details: true`)* |
| `company_employee_count` | Number of employees on LinkedIn (e.g. `"10,001+"` or `"51-200"`) *(requires `fetch_company_details: true`)* |

> Fields from `description` onwards are only populated when **Fetch Full Job Details** is enabled.
> `company_followers` and `company_employee_count` are only populated when **Fetch Company Details** is enabled.

---

## Input parameters

### Job Search

| Parameter | Type | Default | Description |
|---|---|---|---|
| `titles` | `string[]` | `["Software Engineer"]` | One or more job titles to search. Each title runs as a separate search. |
| `location` | `string` | `"United States"` | Country or city. Use `"Worldwide"` or `"Remote"` for global results. |
| `count` | `integer` | `25` | Number of jobs to return **per title**. Max ~500. |
| `date_posted` | `string` | `"week"` | Recency filter: `"24h"`, `"week"`, `"month"`, or `"any"` |
| `sort_by` | `string` | `"recent"` | Sort order: `"recent"` (newest first) or `"relevant"` |

### Filters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `job_type` | `string[]` | `[]` | Workplace type: `"remote"`, `"hybrid"`, `"onsite"`. Leave empty for all. |
| `experience_level` | `string[]` | `[]` | Seniority: `"internship"`, `"entry"`, `"mid"`, `"senior"`, `"director"`, `"executive"`. Leave empty for all. |
| `easy_apply` | `boolean` | `false` | Only return jobs with LinkedIn Easy Apply. |
| `under_10_applicants` | `boolean` | `false` | Only return jobs with fewer than 10 applicants. |
| `company_ids` | `string[]` | `[]` | Filter by specific LinkedIn company IDs (found in the company URL). |
| `industry` | `string` | `""` | Filter by industry: `"technology"`, `"finance"`, `"healthcare"`, `"education"`, `"retail"`, `"manufacturing"`, `"consulting"`, `"media"`, `"government"`. Leave empty for all. |

### Post-Fetch Filters

These filters are applied **after** scraping, based on data from the job detail page.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `min_applicants` | `integer` | `null` | Only keep jobs with at least this many applicants. |
| `max_applicants` | `integer` | `null` | Only keep jobs with at most this many applicants. |

### Advanced

| Parameter | Type | Default | Description |
|---|---|---|---|
| `fetch_details` | `boolean` | `true` | Fetch individual job pages for full description, skills, applicant count, and hiring manager info. Slower but much richer output. |
| `fetch_company_details` | `boolean` | `false` | Fetch each unique company's LinkedIn page to get follower count and employee count. Adds one extra request per unique company in the results. |
| `proxy` | `string` | `null` | Optional proxy URL. Format: `http://user:pass@host:port` |

---

## Example input

```json
{
    "titles": ["AI Engineer", "ML Engineer"],
    "location": "India",
    "job_type": ["remote", "hybrid"],
    "experience_level": ["mid", "senior"],
    "date_posted": "week",
    "sort_by": "recent",
    "easy_apply": false,
    "under_10_applicants": false,
    "count": 50,
    "fetch_details": true,
    "fetch_company_details": false,
    "min_applicants": null,
    "max_applicants": 300,
    "company_ids": [],
    "industry": "technology",
    "proxy": null
}
```

---

## Supported locations

Common location values and their behavior:

| Input | Resolves to |
|---|---|
| `"India"` | India |
| `"United States"` | United States |
| `"United Kingdom"` | United Kingdom |
| `"Canada"` | Canada |
| `"Australia"` | Australia |
| `"Germany"` | Germany |
| `"Singapore"` | Singapore |
| `"UAE"` or `"Dubai"` | UAE / Dubai |
| `"Remote"` | LinkedIn Remote geo filter |
| `"Worldwide"` or `"Anywhere"` | Global (no geo filter) |

Any other city or country name can be typed freely — it will be passed as a text search to LinkedIn.

---

## Tips

- **Multiple titles**: Add several titles (e.g. `["Data Scientist", "ML Engineer", "AI Engineer"]`) to cast a wider net in one run.
- **Finding low-competition jobs**: Enable `under_10_applicants` or set `max_applicants` to a small number like `50`.
- **Speed vs. richness**: Disable `fetch_details` to run much faster with basic card data only. Enable it to get descriptions, skills, and hiring manager info.
- **Company insights**: Enable `fetch_company_details` to enrich results with follower count and employee count. Only one request is made per unique company across all results, so the overhead is low when jobs span a small set of companies.
- **Company filter**: To find jobs only at specific companies, look up their LinkedIn company ID from the URL (e.g. `linkedin.com/company/google/` → search for Google's numeric ID) and pass it in `company_ids`.
- **Rate limits**: The scraper includes built-in jitter delays and retry logic to avoid LinkedIn rate limits. If you hit persistent 429 errors, try adding a proxy.

---

## Limitations

- LinkedIn's public job API returns a maximum of ~500 jobs per search query.
- Applicant counts, salary, and hiring manager info are only shown when LinkedIn includes them — not all job postings have this data.
- LinkedIn may occasionally return fewer results than requested for niche searches.
- This actor uses LinkedIn's public guest API and does not require login. It does not scrape private or authenticated content.
