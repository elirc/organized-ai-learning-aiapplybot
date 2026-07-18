# Junior Engineer Guide

## How To Set Up And Run Locally

The repo has a complete README setup path, so this procedure is reconstructed from `README.md:57-139`, `.env.example`, and `pyproject.toml:20-35`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .

# Optional JobSpy support, from README.md:97-99
pip install --no-deps python-jobspy
pip install pydantic tls-client requests markdownify regex

# Optional browser/runtime checks for Stage 6
applypilot doctor

# First-time user config
applypilot init

# Core pipeline
applypilot run

# Tests
python -m pytest -q
```

Environment variables are documented in `.env.example`: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_URL`, `LLM_MODEL`, `CAPSOLVER_API_KEY`, and optional `PROXY`. User runtime files live in `~/.applypilot` unless `APPLYPILOT_DIR` is set, as shown in `src/applypilot/config.py:11-29`.

Database setup is automatic. `_bootstrap()` calls `load_env()`, `ensure_dirs()`, and `init_db()` in `src/applypilot/cli.py:38-45`.

## Project Type

- Type: Python CLI/package.
- Package manager: `pip`/editable install via `pyproject.toml`.
- Frontend: no React/browser SPA. There is terminal UI via Rich and generated HTML dashboard.
- Backend: no HTTP server/controllers. The "backend" is local Python modules plus SQLite.
- API layer: external APIs only, including LLM chat completions, JobSpy, Workday endpoints, Playwright CDP/MCP.
- State: SQLite plus local files in `~/.applypilot`.
- Tests: pytest.

## Folder Orientation

| Path | Responsibility |
| --- | --- |
| `src/applypilot/cli.py` | CLI commands and runtime preflight checks. |
| `src/applypilot/config.py` | Local paths, env loading, profile/search normalization, tier detection. |
| `src/applypilot/database.py` | SQLite connection, schema, migration, stats, stage queries. |
| `src/applypilot/pipeline.py` | Stage orchestration. |
| `src/applypilot/discovery/` | Job discovery via JobSpy, Workday, and smart extraction. |
| `src/applypilot/enrichment/` | Detail-page scraping and apply URL extraction. |
| `src/applypilot/scoring/` | LLM scoring, tailoring, validation, cover letters, PDFs. |
| `src/applypilot/apply/` | Stage 6 auto-apply, Chrome workers, prompts, agent runners, live dashboard. |
| `src/applypilot/wizard/` | First-time setup wizard. |
| `tests/` | Unit and integration tests. |

## Three Important "Frontend" Folders Or UI Surfaces

This repo has no React frontend. The UI surfaces are:

- `src/applypilot/cli.py`: command-line interface.
- `src/applypilot/apply/dashboard.py`: live Rich terminal dashboard.
- `src/applypilot/view.py`: generated HTML dashboard.

## Three Important Backend/Core Folders

- `src/applypilot/discovery/`: brings jobs into the system.
- `src/applypilot/scoring/`: turns job rows into scored and tailored artifacts.
- `src/applypilot/apply/`: applies to jobs using browser automation and CLI agents.

## Front Door Walkthrough

```python
# src/applypilot/cli.py:22-45
app = typer.Typer(
    name="applypilot",        # This is the CLI name users see.
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)

VALID_STAGES = ("discover", "enrich", "score", "tailor", "cover", "pdf")

def _bootstrap() -> None:
    # Every command that touches runtime state should load env, create dirs,
    # and initialize SQLite before doing real work.
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()
```

The key junior lesson: entry points are not just "where code starts." They are where the app promises the user what workflows exist.

## Pipeline Entry Walkthrough

```python
# src/applypilot/pipeline.py:35-44
STAGE_ORDER = ("discover", "enrich", "score", "tailor", "cover", "pdf")

STAGE_META: dict[str, dict] = {
    "discover": {"desc": "Job discovery (JobSpy + Workday + smart extract)"},
    "enrich":   {"desc": "Detail enrichment (full descriptions + apply URLs)"},
    "score":    {"desc": "LLM scoring (fit 1-10)"},
    "tailor":   {"desc": "Resume tailoring (LLM + validation)"},
    "cover":    {"desc": "Cover letter generation"},
    "pdf":      {"desc": "PDF conversion (tailored resumes + cover letters)"},
}
```

The stage names are a contract. CLI validation uses the same list in `src/applypilot/cli.py:30-31` and `src/applypilot/cli.py:100-107`.

## Database Anatomy

```python
# src/applypilot/database.py:90-133
conn.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        url TEXT PRIMARY KEY,             # One row per discovered job.
        title TEXT,
        salary TEXT,
        description TEXT,
        location TEXT,
        site TEXT,
        strategy TEXT,
        discovered_at TEXT,

        full_description TEXT,            # Enrichment output.
        application_url TEXT,
        detail_scraped_at TEXT,
        detail_error TEXT,

        fit_score INTEGER,                # Scoring output.
        score_reasoning TEXT,
        scored_at TEXT,

        tailored_resume_path TEXT,        # Tailoring/PDF/apply readiness.
        tailored_at TEXT,
        tailor_attempts INTEGER DEFAULT 0,

        applied_at TEXT,                  # Stage 6 output.
        apply_status TEXT,
        apply_error TEXT,
        apply_attempts INTEGER DEFAULT 0,
        agent_id TEXT
    )
""")
```

The key junior lesson: the schema tells the product story. Each group of columns is a milestone in the workflow.

## Three UI Anatomies

### CLI Command

`run()` receives CLI arguments, validates stage names, gates LLM stages behind tier checks, and calls `run_pipeline()`. See `src/applypilot/cli.py:78-124`.

### Live Terminal Dashboard

`WorkerState` is a dataclass that models the current state of each apply worker in `src/applypilot/apply/dashboard.py:22-39`. `update_state()` safely mutates it under a lock in `src/applypilot/apply/dashboard.py:58-69`. `render_dashboard()` transforms state into a Rich table in `src/applypilot/apply/dashboard.py:109-166`.

### HTML Dashboard

`generate_dashboard()` queries stats and scored jobs in `src/applypilot/view.py:25-82`, builds HTML/JS strings, writes the dashboard, and optionally opens it in `src/applypilot/view.py:391-407`.

## Three Backend/Core Anatomies

### Discovery Route Equivalent

There is no web route. The equivalent command path is:

`applypilot run discover -> cli.run() -> pipeline._run_discover() -> jobspy.run_discovery()`

Evidence: `src/applypilot/cli.py:78-124`, `src/applypilot/pipeline.py:62-99`, `src/applypilot/discovery/jobspy.py:454-485`.

### Scoring Function

`score_job()` builds a job prompt, calls the LLM client, parses the response, and returns a structured score in `src/applypilot/scoring/scorer.py:72-100`.

### Apply Job Function

`run_job()` checks domain safety, prepares artifacts, builds prompts, chooses Claude or Codex, parses the result, and returns status in `src/applypilot/apply/launcher.py:416-568`.

## Beginner-Relevant Python Type Patterns

- `Literal["claude", "codex", "auto"]` restricts valid CLI agent values in `src/applypilot/cli.py:133`.
- `dataclass` makes small data models readable in `src/applypilot/apply/agents/base.py:10-29`.
- `Protocol` defines a behavior contract for agent runners in `src/applypilot/apply/agents/base.py:32-36`.
- `dict | None` and `list[str]` are common modern Python type hints throughout `src/applypilot/pipeline.py:37-55`.

## Domain Glossary

Technical terms:

- CLI: Command-line interface.
- Stage: One pipeline step that reads/writes job state.
- SQLite: Local file database used as the durable state machine.
- WAL: SQLite write-ahead logging, enabled in `src/applypilot/database.py:45-48`.
- MCP: Tool-server protocol used to let agents drive browser automation.
- CDP: Chrome DevTools Protocol, used to connect Playwright MCP to a browser.
- Idempotent: Safe to call repeatedly without corrupting state, like `init_db()`.

Domain terms:

- Discovery: Finding job postings.
- Enrichment: Fetching full job descriptions and apply URLs.
- Fit score: LLM-assigned job/resume match from 1-10.
- Tailored resume: A generated resume artifact for one job.
- Manual ATS: Application system the automation should skip.
- Dry run: Fill/review workflow without final submission.
- Apply worker: One isolated browser/agent process pair.

## Junior Socratic Checkpoint

1. Why does `_bootstrap()` run before most commands?
2. Which file proves this is a CLI package?
3. Which database column means a job has been enriched?
4. Which database column means a job has been claimed by a worker?
5. Why does `acquire_job()` use `BEGIN IMMEDIATE`?
6. Why are Claude and Codex runners separate files?
7. What is the difference between `description` and `full_description`?

## How To Self-Grade

Strong answers cite `pyproject.toml:34-35`, `src/applypilot/cli.py:38-45`, `src/applypilot/database.py:90-133`, and `src/applypilot/apply/launcher.py:186-271`. They explain state transitions, not just function names. They also notice that the app has no React/Express layer and should not be studied as if it did.
