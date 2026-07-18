# 01 - Python Basics With ApplyPilot Examples

This file teaches Python using fake examples first, then connects each idea to real ApplyPilot code.

## 1. Variables

A variable is a name for a value.

Fake example:

```python
job_title = "Platform Engineer"
fit_score = 9
is_remote = True
```

Read it in English:

- `job_title` holds text.
- `fit_score` holds a number.
- `is_remote` holds true/false.

Real ApplyPilot example:

```python
# src/applypilot/config.py:11-20
APP_DIR = Path(os.environ.get("APPLYPILOT_DIR", Path.home() / ".applypilot"))
DB_PATH = APP_DIR / "applypilot.db"
PROFILE_PATH = APP_DIR / "profile.json"
SEARCH_CONFIG_PATH = APP_DIR / "searches.yaml"
ENV_PATH = APP_DIR / ".env"
```

Inline lesson:

- `APP_DIR` is the root folder for user-specific files.
- `DB_PATH` is built from `APP_DIR`, so changing `APPLYPILOT_DIR` changes where the DB lives.
- These names are uppercase because they behave like constants.

Practice:

```python
# Fake practice
app_dir = "C:/Users/Owner/.applypilot"
db_path = app_dir + "/applypilot.db"
print(db_path)
```

Self-grade:

- Strong answer: you can explain why `DB_PATH` depends on `APP_DIR`.
- Weak answer: you only say "it stores a string."

## 2. Strings

Strings are text.

Fake example:

```python
company = "Example Corp"
message = f"Applying to {company}"
```

`f"..."` is an f-string. It lets Python put variable values inside text.

Real ApplyPilot example:

```python
# src/applypilot/apply/launcher.py:430-433
apply_url = job.get("application_url") or job["url"]
if not _is_domain_allowed(apply_url, domain_allowlist):
    host = _url_host(apply_url) or "unknown-domain"
    return f"failed:domain_not_allowed:{host}", 0
```

Inline lesson:

- `apply_url` chooses `application_url` if it exists; otherwise it falls back to `url`.
- The returned string includes the blocked host.
- This is a status string, not an exception.

Fake reinforcement:

```python
host = "blocked.example"
result = f"failed:domain_not_allowed:{host}"
print(result)  # failed:domain_not_allowed:blocked.example
```

## 3. Lists

A list is an ordered group of values.

Fake example:

```python
stages = ["discover", "enrich", "score"]
first_stage = stages[0]  # "discover"
```

Real ApplyPilot example:

```python
# src/applypilot/pipeline.py:35
STAGE_ORDER = ("discover", "enrich", "score", "tailor", "cover", "pdf")
```

This is a tuple, not a list. A tuple is like a list that is usually treated as fixed.

Why it matters:

- The stage order is the app's workflow.
- You should not casually reorder it.
- `tailor` depends on `score`; `score` depends on `enrich`.

Fake reinforcement:

```python
stage_order = ("discover", "enrich", "score")

for stage in stage_order:
    print(f"Running {stage}")
```

## 4. Dictionaries

A dictionary maps keys to values.

Fake example:

```python
job = {
    "title": "Platform Engineer",
    "site": "Example Corp",
    "fit_score": 9,
}

print(job["title"])       # required access
print(job.get("salary"))  # optional access, returns None if missing
```

Real ApplyPilot example:

```python
# src/applypilot/apply/launcher.py:435-439
resume_path = job.get("tailored_resume_path")
txt_path = Path(resume_path).with_suffix(".txt") if resume_path else None
resume_text = ""
if txt_path and txt_path.exists():
    resume_text = txt_path.read_text(encoding="utf-8")
```

Inline lesson:

- `job` is a dictionary representing one DB row.
- `.get("tailored_resume_path")` avoids crashing if the key is missing.
- The code only reads the resume text if the path exists.

Junior trap:

```python
# This can crash if "tailored_resume_path" is missing.
resume_path = job["tailored_resume_path"]
```

Senior habit:

- Use `job["field"]` when the field is required.
- Use `job.get("field")` when the field is optional.
- If many fields are required, consider a typed object or `TypedDict`.

## 5. Functions

A function packages reusable behavior.

Fake example:

```python
def is_high_fit(score: int) -> bool:
    # Return True when the score is 7 or higher.
    return score >= 7

print(is_high_fit(9))  # True
print(is_high_fit(4))  # False
```

Real ApplyPilot example:

```python
# src/applypilot/apply/launcher.py:155-167
def _is_domain_allowed(url: str, allowlist: list[str] | None) -> bool:
    if not allowlist:
        return True
    host = _url_host(url)
    if not host:
        return False
    for allowed in allowlist:
        a = allowed.strip().lower()
        if not a:
            continue
        if host == a or host.endswith(f".{a}"):
            return True
    return False
```

Inline lesson:

- Inputs: a URL and an optional allowlist.
- Output: `True` or `False`.
- Early return: if there is no allowlist, all domains are allowed.
- Loop: checks each allowed domain.
- Subdomain rule: `careers.example.com` is allowed when `example.com` is allowed.

Fake reinforcement:

```python
def is_allowed_email_domain(email: str, allowed_domains: list[str]) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in allowed_domains

print(is_allowed_email_domain("ada@example.com", ["example.com"]))  # True
```

## 6. If Statements

An `if` statement chooses behavior.

Fake example:

```python
score = 8

if score >= 7:
    print("Tailor resume")
else:
    print("Skip for now")
```

Real ApplyPilot example:

```python
# src/applypilot/apply/launcher.py:476-500
if parsed.status == "APPLIED":
    return "applied", run_result.duration_ms
if parsed.status == "CAPTCHA":
    return "captcha", run_result.duration_ms
if parsed.status == "DRY_RUN":
    return "skipped", run_result.duration_ms
if parsed.status == "FAILED":
    reason = parsed.reason or "unknown"
    return f"failed:{reason}", run_result.duration_ms

reason = parsed.reason or "needs_review"
return f"failed:needs_review:{reason}", run_result.duration_ms
```

Inline lesson:

- Each status maps to a durable apply result.
- `DRY_RUN` becomes `skipped`, so the app does not treat preview as submission.
- Unknown statuses fall through to `needs_review`.

## 7. Loops

A loop repeats behavior.

Fake example:

```python
jobs = ["job-1", "job-2", "job-3"]

for job in jobs:
    print(f"Processing {job}")
```

Real ApplyPilot example:

```python
# src/applypilot/scoring/scorer.py:139-161
for job in jobs:
    result = score_job(resume_text, job)
    result["url"] = job["url"]
    results.append(result)

now = datetime.now(timezone.utc).isoformat()
for r in results:
    conn.execute(
        "UPDATE jobs SET fit_score = ?, score_reasoning = ?, scored_at = ? WHERE url = ?",
        (r["score"], f"{r['keywords']}\n{r['reasoning']}", now, r["url"]),
    )
conn.commit()
```

Inline lesson:

- First loop does LLM scoring and collects results.
- Second loop writes results to SQLite.
- `conn.commit()` saves all updates.

Why this matters:

- If scoring crashes before commit, DB state may not change.
- If you parallelize this later, you must think about rate limits and DB writes.

## 8. Exceptions

Exceptions represent errors.

Fake example:

```python
try:
    number = int("not a number")
except ValueError:
    number = 0
```

Real ApplyPilot example:

```python
# src/applypilot/discovery/jobspy.py:21-30
def _get_scrape_jobs():
    try:
        from jobspy import scrape_jobs
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "python-jobspy is not installed. Install the discovery extras from the README "
            "before running the JobSpy discovery stage."
        ) from exc
    return scrape_jobs
```

Inline lesson:

- JobSpy is optional.
- Import happens lazily so other app features can still work without JobSpy.
- A low-level `ModuleNotFoundError` becomes a user-friendly `RuntimeError`.

Fake reinforcement:

```python
def load_optional_tool():
    try:
        import imaginary_tool
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install imaginary_tool before using this feature") from exc
```

## 9. Classes

A class groups data and behavior.

Fake example:

```python
class Job:
    def __init__(self, title: str, score: int) -> None:
        self.title = title
        self.score = score

    def is_high_fit(self) -> bool:
        return self.score >= 7
```

Real ApplyPilot example:

```python
# src/applypilot/llm.py:60-74
class LLMClient:
    """Thin OpenAI-compatible chat completions client using httpx."""

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=_TIMEOUT)
```

Inline lesson:

- `LLMClient` stores connection settings.
- `self.base_url`, `self.model`, and `self.api_key` are instance attributes.
- `_client` is an `httpx.Client`, reused for requests.

## 10. Dataclasses

A dataclass is a concise way to create a data object.

Fake example:

```python
from dataclasses import dataclass

@dataclass
class JobScore:
    score: int
    reason: str
```

Real ApplyPilot example:

```python
# src/applypilot/apply/agents/base.py:10-29
@dataclass
class ParsedOutcome:
    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool

@dataclass
class AgentRunResult:
    engine: str
    exit_code: int
    final_text: str
    events_path: Path | None
    raw_log_path: Path
    duration_ms: int
    parsed: ParsedOutcome
```

Inline lesson:

- `ParsedOutcome` is the small final result from an agent.
- `AgentRunResult` wraps process details plus parsed outcome.
- This lets Claude and Codex return the same shape.

## 11. Type Hints

Type hints describe expected shapes.

Fake example:

```python
def double(number: int) -> int:
    return number * 2
```

Real ApplyPilot example:

```python
# src/applypilot/database.py:365-368
def get_jobs_by_stage(
    conn: sqlite3.Connection | None = None,
    stage: str = "discovered",
    min_score: int | None = None,
    limit: int = 100,
) -> list[dict]:
```

Inline lesson:

- `conn` may be a SQLite connection or `None`.
- `stage` is a string.
- `min_score` may be an integer or `None`.
- The function returns a list of dictionaries.

Junior habit:

- Read type hints before reading the body.
- They tell you what the function expects and promises.

## 12. Imports

Imports bring code from another file or package.

Fake example:

```python
from pathlib import Path

path = Path("resume.txt")
```

Real ApplyPilot example:

```python
# src/applypilot/cli.py:38-45
def _bootstrap() -> None:
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()
```

Inline lesson:

- Imports happen inside the function.
- This can reduce startup cost or avoid import cycles.
- `_bootstrap()` coordinates config and database setup.

## Mini Quiz

1. What is the difference between `job["url"]` and `job.get("url")`?
2. Why does `_is_domain_allowed()` return `True` when there is no allowlist?
3. What does `conn.commit()` do?
4. Why is `ParsedOutcome` a useful dataclass?
5. What does `Path(...).with_suffix(".txt")` probably do?

## How To Self-Grade

Strong answers connect Python syntax to product behavior. For example, `conn.commit()` is not just "saving"; it is the moment scored jobs become durable in the pipeline state.

