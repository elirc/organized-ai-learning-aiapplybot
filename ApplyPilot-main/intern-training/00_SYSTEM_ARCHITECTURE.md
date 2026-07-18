# ApplyPilot — System Design Overview

**From a Senior SWE to a Junior SWE / Intern**

---

## What Is This System?

ApplyPilot is an **AI-powered autonomous job application pipeline**. Think of it as a robot that finds jobs, evaluates them, customizes your resume for each one, and then actually opens a browser and fills out the application form — all automatically.

It runs as a command-line tool (`applypilot`) and has **six stages**, each building on the previous one:

```
Stage 1: DISCOVER  →  Find jobs from multiple websites
Stage 2: ENRICH    →  Get full job descriptions and apply URLs
Stage 3: SCORE     →  AI evaluates how well you fit each job (1-10)
Stage 4: TAILOR    →  AI rewrites your resume for high-scoring jobs
Stage 5: COVER     →  AI generates a cover letter
Stage 6: APPLY     →  AI agent opens a browser and submits the application
```

---

## The Architecture Pattern: Pipeline + Pluggable Backends

### Why a Pipeline?

Each stage transforms data and passes it to the next. This is the **pipeline pattern** — the same pattern used in data engineering (ETL), CI/CD systems, and Unix shell pipes.

**Why this works well here:**
1. **Each stage is independent.** You can run `applypilot run discover` without running anything else. Or run `applypilot run score tailor` to only do the AI stages.
2. **Resumable.** If your computer crashes during scoring, you restart and it picks up where it left off — the database tracks what's been done.
3. **Debuggable.** If a tailored resume looks wrong, you check Stage 4 logs without touching Stages 1-3.

### Why SQLite as the "Conveyor Belt"?

Every stage reads from and writes to a single SQLite database (`applypilot.db`). This is the **shared state** that ties the whole pipeline together.

**Why SQLite instead of PostgreSQL, Redis, or files?**
- **Zero setup.** No server to install. The DB is a single file.
- **Thread-safe with WAL mode.** Multiple workers can read/write concurrently without locks (Write-Ahead Logging).
- **Atomic operations.** The `BEGIN IMMEDIATE` transaction in `acquire_job()` prevents two workers from grabbing the same job.
- **Portable.** The entire state fits in one file you can copy or back up.

**Trade-off:** SQLite doesn't scale to hundreds of concurrent writers. But this app typically runs 1-4 workers, so it's perfect.

### Why Pluggable Backends for Stage 6?

Stage 6 (auto-apply) can use **Claude Code CLI** or **OpenAI Codex CLI** as the AI agent that fills out forms. The system abstracts this behind a shared interface:

```python
class AgentRunner(Protocol):
    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ...
```

Both `ClaudeRunner` and `CodexRunner` implement this protocol. The launcher doesn't care which one it's talking to — it just calls `.run()` and gets back a `ParsedOutcome`.

**Why this design?**
- **Redundancy.** If Claude is down, Codex can take over (`--agent auto` mode).
- **Experimentation.** You can A/B test which agent fills out forms better.
- **Future-proofing.** Adding a new backend (e.g., Gemini agent) means writing one new class, not rewriting the whole system.

---

## The Data Model: One Table, 30+ Columns

The entire system runs on a single `jobs` table with columns grouped by stage:

```
Discovery:   url (PK), title, salary, description, location, site, strategy, discovered_at
Enrichment:  full_description, application_url, detail_scraped_at, detail_error
Scoring:     fit_score, score_reasoning, scored_at
Tailoring:   tailored_resume_path, tailored_at, tailor_attempts
Cover Letter: cover_letter_path, cover_letter_at, cover_attempts
Application: applied_at, apply_status, apply_error, apply_attempts, agent_id, ...
```

**Why one wide table instead of normalized tables?**
- **Simplicity.** One `SELECT *` gives you everything about a job. No JOINs.
- **Stage queries are simple.** "Give me jobs that need scoring" = `WHERE full_description IS NOT NULL AND fit_score IS NULL`.
- **Forward migration is trivial.** New column? `ALTER TABLE ADD COLUMN`. That's it.

**Trade-off:** This doesn't follow relational normalization rules. If you needed to track multiple resumes per job or multiple applications per job, you'd need separate tables. But for this use case, 1 job = 1 row works perfectly.

---

## The Tech Stack — Why Each Choice

### Python 3.11+
The entire application is Python. Why?
- **Ecosystem.** Libraries for web scraping (BeautifulSoup, Playwright), data (pandas), LLM APIs (httpx), and CLI (Typer) are all best-in-class in Python.
- **subprocess control.** Stage 6 needs to launch Chrome and AI CLI tools as subprocesses. Python's `subprocess` module handles this well.
- **Accessible.** Most engineers know Python. Lower barrier for contributors.

### Typer (CLI Framework)
Typer gives you a polished CLI with type hints and auto-generated help:
```bash
applypilot run --min-score 8 --workers 2 --stream
applypilot apply --agent claude --dry-run --limit 5
```
**Why not argparse?** Typer is less boilerplate and produces better `--help` output.

### Rich (Terminal UI)
Rich gives you colored output, tables, progress bars, and live dashboards in the terminal. The `status` command shows a beautiful table with score distributions. The `apply` command shows a live worker dashboard.

### httpx (HTTP Client)
Used for the LLM API calls (Gemini, OpenAI, local). **Why not `requests`?** httpx has native timeout support and a cleaner async API (though we use the sync client here).

### Playwright (Browser Automation)
Used in two places:
1. **Enrichment stage** — Opens job posting pages to scrape full descriptions.
2. **Apply stage** — Launched as an MCP server that the AI agent controls via Chrome DevTools Protocol (CDP).

### SQLite + WAL Mode
WAL (Write-Ahead Logging) allows concurrent readers and one writer without blocking. The `busy_timeout=10000` setting means SQLite will wait up to 10 seconds for a lock rather than failing immediately.

---

## Key Design Decisions Explained

### 1. Lazy Imports
Throughout the codebase, you'll see imports inside functions:
```python
def _bootstrap() -> None:
    from applypilot.config import load_env, ensure_dirs  # imported here, not at top
```
**Why?** Startup speed. If you run `applypilot --version`, you don't want to import Playwright, pandas, and the entire LLM stack. Lazy imports mean only the code you need gets loaded.

### 2. Thread-Local Database Connections
```python
_local = threading.local()
```
SQLite connections cannot be shared across threads. Each worker thread gets its own connection, cached in a `threading.local()` object. This is the standard pattern for thread-safe SQLite in Python.

### 3. Profile-Driven (Zero Hardcoded Personal Data)
Every piece of personal information — name, email, skills, companies worked at — comes from `~/.applypilot/profile.json`. Nothing is hardcoded anywhere in the source code.

**Why this matters:**
- **Security.** No one's personal data in the git repo.
- **Multi-user.** Different people can use the same codebase.
- **Testability.** You can swap in a test profile without touching code.

### 4. Fresh LLM Conversations on Retry
When resume tailoring fails validation, the system retries with a **new conversation** rather than continuing the old one:
```python
for attempt in range(max_retries + 1):
    messages = [  # fresh messages each time
        {"role": "system", "content": prompt},
        {"role": "user", "content": ...},
    ]
```
**Why?** LLMs develop "apologetic spirals" — if you tell them they made a mistake, they over-correct and make different mistakes. Starting fresh avoids this.

### 5. Two-Layer Resume Validation
Tailored resumes go through two independent checks:
1. **Programmatic validator** — checks banned words, fabricated skills, metric inflation.
2. **LLM judge** — a separate LLM call that evaluates the tailored resume against the original.

**Why two layers?** The programmatic checker catches obvious problems (banned phrases, skills not in the boundary list). The LLM judge catches subtle fabrication (inventing work that sounds plausible but never happened). Neither alone is sufficient.

### 6. Atomic Job Acquisition
```python
conn.execute("BEGIN IMMEDIATE")
# ... SELECT the next job ...
# ... UPDATE it to 'in_progress' ...
conn.commit()
```
`BEGIN IMMEDIATE` takes a write lock immediately, preventing race conditions where two workers grab the same job. This is critical for multi-worker mode.

### 7. Double Ctrl+C Pattern
First Ctrl+C = skip the current job (kill the agent process, move to next job).
Second Ctrl+C = full stop (kill everything, shut down).

This UX pattern is common in long-running CLI tools. It gives you a way to skip a stuck job without killing the entire pipeline.

---

## How Data Flows Through the System

```
User runs: applypilot run

CLI (cli.py)
  ├── Parses flags (--min-score 7, --workers 2, etc.)
  ├── Calls _bootstrap() → loads .env, creates dirs, initializes DB
  └── Calls pipeline.run_pipeline()

Pipeline (pipeline.py)
  ├── Resolves stages ("all" → ["discover", "enrich", "score", "tailor", "cover", "pdf"])
  ├── Sequential mode: runs each stage one at a time
  └── Streaming mode: runs all stages as threads, polling DB for work

Stage 1: Discovery
  ├── jobspy.py → Searches Indeed, LinkedIn, Glassdoor via python-jobspy
  ├── workday.py → Queries Workday corporate career APIs
  └── smartextract.py → AI-powered scraping for custom sites
  All → INSERT INTO jobs (url, title, salary, ...)

Stage 2: Enrichment
  └── detail.py → For each job without full_description:
      ├── Opens the URL with Playwright
      ├── Tries JSON-LD structured data first (free)
      ├── Falls back to CSS selectors (free)
      └── Falls back to LLM extraction (1 API call)
      UPDATE jobs SET full_description=..., application_url=...

Stage 3: Scoring
  └── scorer.py → For each enriched but unscored job:
      ├── Sends resume + job description to LLM
      ├── Gets score (1-10), keywords, reasoning
      └── UPDATE jobs SET fit_score=..., score_reasoning=...

Stage 4: Tailoring
  └── tailor.py → For each job with score >= 7:
      ├── Sends resume + job description to LLM
      ├── Gets JSON with tailored sections
      ├── Code assembles resume (header from profile, body from LLM)
      ├── Validates with programmatic checker + LLM judge
      ├── Saves .txt file
      ├── Converts to PDF
      └── UPDATE jobs SET tailored_resume_path=...

Stage 5: Cover Letter
  └── cover_letter.py → Similar LLM generation + validation

Stage 6: PDF
  └── pdf.py → Converts any remaining .txt files to PDF via Playwright HTML rendering
```

```
User runs: applypilot apply --agent claude --workers 2

CLI (cli.py)
  ├── Checks: Chrome installed? Claude CLI installed? Profile exists? Tailored resumes ready?
  └── Calls launcher.main()

Launcher (launcher.py)
  ├── Creates ThreadPoolExecutor with N workers
  └── Each worker runs worker_loop():

      worker_loop():
        ├── acquire_job() → SELECT + UPDATE in one transaction (atomic lock)
        ├── launch_chrome() → Chrome with remote debugging on port 9222+worker_id
        ├── run_job():
        │   ├── Builds prompt (prompt.py) with profile data + resume + job info
        │   ├── Creates MCP config (Playwright server pointing to Chrome)
        │   ├── Launches AI agent (ClaudeRunner or CodexRunner)
        │   │   ├── Subprocess: claude -p --mcp-config ... < prompt
        │   │   ├── Streams output, logs everything
        │   │   └── Returns AgentRunResult
        │   └── Parses outcome (parsing.py) → ParsedOutcome
        ├── mark_result() → UPDATE jobs SET apply_status=...
        └── cleanup_worker() → Kill Chrome
```

---

## Module Dependency Map

```
cli.py ─────────────────────────────┐
  ├── config.py (paths, env, profile)│
  ├── database.py (schema, queries)  │
  ├── pipeline.py ───────────────────┤
  │     ├── discovery/               │
  │     │   ├── jobspy.py            │
  │     │   ├── workday.py           │
  │     │   └── smartextract.py      │
  │     ├── enrichment/              │
  │     │   └── detail.py            │
  │     └── scoring/                 │
  │         ├── scorer.py            │
  │         ├── tailor.py            │
  │         ├── cover_letter.py      │
  │         ├── validator.py         │
  │         └── pdf.py               │
  └── apply/                         │
      ├── launcher.py ◄──────────────┘
      ├── prompt.py
      ├── chrome.py
      ├── dashboard.py
      └── agents/
          ├── base.py (protocol + models)
          ├── parsing.py (outcome parser)
          ├── claude_runner.py
          └── codex_runner.py

Shared services (used by many modules):
  config.py ← paths, profile loading, env vars
  database.py ← SQLite connections, queries
  llm.py ← LLM API client (Gemini/OpenAI/local)
```

---

## Concurrency Model

**Stages 1-5:** Can run sequentially or in streaming mode (threads polling the DB).
**Stage 6:** ThreadPoolExecutor with N workers, each with its own:
- Chrome instance (separate profile directory, separate CDP port)
- Worker directory (isolated file space for resume PDFs)
- Database connection (thread-local)
- AI agent subprocess

**Why threads instead of async?**
- The main bottleneck is I/O (LLM API calls, browser waiting). Python threads release the GIL during I/O.
- Worker count is typically 1-4. Thread overhead is negligible at this scale.
- `subprocess.Popen` works naturally with threads. An async approach would need `asyncio.create_subprocess_exec`, which adds complexity.

---

## Configuration Layers

1. **Environment variables** (`.env` file): API keys, Chrome path overrides
2. **Profile JSON** (`profile.json`): Personal data, skills boundary, work authorization
3. **Search config YAML** (`searches.yaml`): Job queries, locations, site selection
4. **Site registries** (`sites.yaml`, `employers.yaml`): Per-site scraping configs
5. **CLI flags**: Runtime overrides (--min-score, --workers, --dry-run)

Priority: CLI flags > env vars > profile > YAML defaults

---

## Error Handling Philosophy

1. **Fail gracefully, don't crash the pipeline.** If one JobSpy search fails, the others still run.
2. **Track attempts.** `tailor_attempts` and `apply_attempts` columns prevent infinite retries.
3. **Permanent vs. transient failures.** The system distinguishes between "job expired" (permanent, never retry) and "timeout" (transient, retry later).
4. **Log everything.** Every agent session gets a timestamped log file in `~/.applypilot/logs/`.

---

## Security Considerations

1. **No secrets in code.** API keys live in `.env`, personal data in `profile.json`.
2. **Chrome permission blocking.** The browser launches with `--deny-permission-prompts` and fake media devices.
3. **Agent guardrails.** The prompt explicitly forbids granting camera/mic permissions, entering payment info, or doing biometric verification.
4. **Domain allowlisting.** `--domain-allowlist` restricts which websites the agent can navigate to.
5. **SSO blocking.** The prompt tells the agent to stop if redirected to Google/Microsoft SSO pages.

---

## How to Read This Codebase

If you're new to this codebase, read the files in this order:

1. **`config.py`** — Understand where everything lives on disk
2. **`database.py`** — Understand the data model (the `jobs` table schema)
3. **`cli.py`** — Understand the user interface and command routing
4. **`pipeline.py`** — Understand how stages are orchestrated
5. **`apply/agents/base.py`** — Understand the backend abstraction
6. **`apply/agents/parsing.py`** — Understand how results are normalized
7. **`apply/launcher.py`** — Understand the apply orchestration (the most complex file)
8. **`apply/prompt.py`** — Understand what the AI agent is told to do

Then explore the stage implementations (scorer.py, tailor.py, etc.) as needed.
