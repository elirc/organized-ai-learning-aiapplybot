# discovery/jobspy.py — Multi-Site Job Scraper

**File:** `src/applypilot/discovery/jobspy.py` (479 lines)
**Role:** Searches Indeed, LinkedIn, Glassdoor, and ZipRecruiter for jobs using the python-jobspy library.

---

## What This File Does

This is Stage 1's primary scraper. It takes search queries from the user's config (title + location combinations) and scrapes multiple job boards simultaneously. Results are deduplicated and stored in SQLite.

---

## The Retry Wrapper

```python
def _scrape_with_retry(kwargs, max_retries=2, backoff=5.0):
    for attempt in range(max_retries + 1):
        try:
            return scrape_jobs(**kwargs)
        except Exception as e:
            err = str(e).lower()
            transient = any(k in err for k in ("timeout", "429", "proxy", "connection", "reset"))
            if transient and attempt < max_retries:
                wait = backoff * (attempt + 1)
                time.sleep(wait)
            else:
                raise
```

### Why Retry Only Transient Errors?

Job board scraping is inherently flaky — sites rate-limit, proxies disconnect, connections time out. The retry wrapper catches these transient errors and retries with linear backoff (5s, 10s, 15s).

Non-transient errors (authentication failures, invalid parameters) are re-raised immediately — retrying them would be pointless.

**The error classification is string-based** (`"timeout" in err`). This is pragmatic — python-jobspy raises generic exceptions, not typed ones. String matching is the simplest way to classify them.

---

## Location Filtering

```python
def _location_ok(location, accept, reject):
    if not location:
        return True  # unknown → keep, let scorer decide

    loc = location.lower()
    if any(r in loc for r in ("remote", "anywhere", "work from home")):
        return True  # remote always OK

    for r in reject:
        if r.lower() in loc:
            return False  # explicitly rejected

    for a in accept:
        if a.lower() in loc:
            return True  # explicitly accepted

    return False  # unknown → reject
```

### The Three-Tier Filter

1. **Remote?** → Always keep. The user accepts remote work regardless of the city.
2. **In reject list?** → Drop. E.g., "India", "Philippines" — the user can't work there.
3. **In accept list?** → Keep. E.g., "Toronto", "Remote" — the user can work there.
4. **Unknown?** → Drop. Better to miss a job than waste time on a bad location.

**Why filter here instead of in scoring?** Filtering at discovery saves LLM tokens. If there are 500 jobs from India and the user is in Toronto, scoring all 500 wastes money. Filtering first reduces the scoring workload.

---

## JobSpy DataFrame → SQLite

```python
def store_jobspy_results(conn, df, source_label):
    for _, row in df.iterrows():
        url = str(row.get("job_url", ""))
        title = str(row.get("title", ""))
        salary = None
        min_amt = row.get("min_amount")
        max_amt = row.get("max_amount")
        if min_amt and str(min_amt) != "nan":
            salary = f"${int(float(min_amt)):,}-${int(float(max_amt)):,}"

        # If description is long enough, promote it directly
        if description and len(description) > 200:
            full_description = description
            detail_scraped_at = now
```

### The `nan` Problem

Pandas uses `NaN` (Not a Number) for missing values. When converted to string, it becomes `"nan"`. Every field must be checked:
```python
title = str(row.get("title", "")) if str(row.get("title", "")) != "nan" else None
```

This is ugly but necessary. Without it, your database fills up with literal `"nan"` strings.

### Description Promotion

```python
if description and len(description) > 200:
    full_description = description
    detail_scraped_at = now
```

If JobSpy already provides a full description (200+ characters), we promote it to `full_description` and mark enrichment as done. This saves Stage 2 from re-scraping a page we already have data for.

### Salary Parsing

```python
salary = f"{currency}{int(float(min_amt)):,}-{currency}{int(float(max_amt)):,}"
if interval:
    salary += f"/{interval}"
# Result: "$85,000-$120,000/yearly"
```

JobSpy provides raw numbers (`min_amount`, `max_amount`, `interval`, `currency`). We format them into a human-readable string with comma separators.

---

## The Full Crawl — Combinatorial Search

```python
def _full_crawl(search_cfg, ...):
    queries = search_cfg.get("queries", [])
    locs = search_cfg.get("locations", [])

    searches = []
    for q in queries:
        for loc in locs:
            searches.append({
                "query": q["query"],
                "location": loc["location"],
                "remote": loc.get("remote", False),
            })
```

### Cartesian Product

If the user has 5 queries and 3 locations, the full crawl runs 5 × 3 = 15 search combinations. Each combination queries all configured sites (Indeed, LinkedIn, etc.), so 15 × 3 = 45 API calls.

### Glassdoor Special Handling

```python
# Glassdoor needs simplified location
gd_location = glassdoor_map.get(s["location"], s["location"].split(",")[0])
has_glassdoor = "glassdoor" in sites
other_sites = [si for si in sites if si != "glassdoor"]
```

Glassdoor's search doesn't handle full addresses well. "Toronto, ON, Canada" returns nothing, but "Toronto" works. The `glassdoor_location_map` in the config maps full locations to Glassdoor-friendly versions.

Non-Glassdoor sites run with the full location string. Glassdoor runs separately with the simplified version.

---

## Design Patterns to Notice

### 1. Config-Driven Scraping
No hardcoded queries or locations. Everything comes from `searches.yaml`. Adding a new search query is a YAML edit, not a code change.

### 2. Resilient Batch Processing
Each search combination is independent. If one fails, the rest continue. The final stats report includes error counts.

### 3. Deduplication via Primary Key
Jobs with the same URL are silently skipped (`IntegrityError` caught). Running the full crawl twice adds zero duplicates.
