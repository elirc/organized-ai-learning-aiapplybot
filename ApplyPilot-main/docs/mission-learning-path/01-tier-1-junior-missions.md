# Tier 1 Junior Missions

### Mission 1: The App's Heartbeat

**Tier:** Junior

**Time Estimate:** 35 minutes

**Goal:** Explain how a terminal command enters the application.

**The Concept:** A CLI app's heartbeat is its command registry. In this app, `applypilot` is like the front desk of a recruiting operations center: every request starts there before moving to a specialist station.

**Design Intent Before You Read the Code:** `pyproject.toml` owns package metadata and the console script. `cli.py` owns command names, options, dependency checks, and handoff to deeper modules. Poor implementation here would make the system hard to run, hard to diagnose, or unsafe to invoke.

**Find It In The Code:** Open `pyproject.toml:20-35`, then `src/applypilot/cli.py:22-45`, then `src/applypilot/cli.py:78-124`.

```python
# pyproject.toml:34-35
# This maps the shell command to the Typer app object.
applypilot = "applypilot.cli:app"

# src/applypilot/cli.py:22-31
app = typer.Typer(...)        # Command registry.
VALID_STAGES = (...)          # Shared vocabulary for pipeline stages.

# src/applypilot/cli.py:38-45
def _bootstrap():
    load_env()                # Bring local .env values into process env.
    ensure_dirs()             # Create ~/.applypilot folders.
    init_db()                 # Make sure SQLite schema exists.
```

**The Aha Moment:** The CLI is not a thin wrapper; it is the first safety boundary.

**Socratic Checkpoint:** What creates the `applypilot` command? Why is `_bootstrap()` shared? Which command starts the pipeline? Which command checks dependencies? What happens if the user passes an invalid stage?

**How to Self-Grade:** Strong answers cite `pyproject.toml:34-35`, `src/applypilot/cli.py:38-45`, and `src/applypilot/cli.py:100-107`. They explain user behavior and safety, not just syntax.

**Connects To:** Mission 2, because entry points only make sense after you know the folder map.

### Mission 2: The Folder Mental Map

**Tier:** Junior

**Time Estimate:** 40 minutes

**Goal:** Build a mental map of top-level responsibilities.

**The Concept:** A codebase folder map is like sorting job applications into trays: discovery, screening, resume prep, and final submission should not all be in one pile.

**Design Intent Before You Read the Code:** Each folder should own one part of the workflow. Confusion appears when a folder both orchestrates and performs domain work.

**Find It In The Code:** Open `src/applypilot/cli.py`, `src/applypilot/pipeline.py:35-165`, `src/applypilot/database.py:90-133`, and directory names under `src/applypilot/`.

```text
cli.py          -> command front door
pipeline.py     -> stage orchestration
database.py     -> durable state
discovery/      -> find jobs
enrichment/     -> enrich rows with details
scoring/        -> LLM scoring and artifacts
apply/          -> browser/agent auto-apply
wizard/         -> first-time setup
```

**The Aha Moment:** The folders mirror the product workflow.

**Socratic Checkpoint:** Which folder owns browser-based applying? Which owns generated PDFs? Which file owns schema? Which module decides stage order? Where would you look for first-time setup?

**How to Self-Grade:** Strong answers connect folders to user-facing stages from `src/applypilot/pipeline.py:35-44`.

**Connects To:** Mission 3, because folder boundaries become meaningful when you study contracts.

### Mission 3: TypeScript Is a Contract

**Tier:** Junior

**Time Estimate:** 45 minutes

**Goal:** Recognize type-like contracts in a Python codebase.

**The Concept:** TypeScript contracts say "this shape is allowed." Python can do the same through dataclasses, Literals, Protocols, tests, and disciplined dictionaries.

**Design Intent Before You Read the Code:** The agent result contract must hide messy CLI output from the launcher. If every runner returned arbitrary strings, Stage 6 would become fragile.

**Find It In The Code:** Open `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/cli.py:133`, and `src/applypilot/apply/agents/parsing.py:13-87`.

```python
# src/applypilot/apply/agents/base.py:10-29
@dataclass
class ParsedOutcome:
    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool

# This makes every backend report the same outcome vocabulary.
```

**The Aha Moment:** A good contract lets you swap implementation without rewriting the caller.

**Socratic Checkpoint:** What statuses are legal? Where are unknown outputs sent? Why is `submitted` separate from `status`? What does `Protocol` enforce conceptually? Which parts are still plain dicts?

**How to Self-Grade:** Strong answers cite `src/applypilot/apply/agents/base.py:10-36` and notice the weakness of `job: dict` in `src/applypilot/apply/launcher.py:416-428`.

**Connects To:** Mission 6 and Mission 17.

### Mission 4: Your First React Component

**Tier:** Junior

**Time Estimate:** 35 minutes

**Goal:** Understand the repo's UI equivalent and why there is no React component layer here.

**The Concept:** This repo has terminal and generated-file UI, not React. Rich tables are the CLI version of components: data goes in, visual representation comes out.

**Design Intent Before You Read the Code:** `WorkerState` should be easy to update from worker code and easy to render. Poor design would mix display formatting into job execution.

**Find It In The Code:** Open `src/applypilot/apply/dashboard.py:22-88`, then `src/applypilot/apply/dashboard.py:109-190`.

```python
# src/applypilot/apply/dashboard.py:22-39
@dataclass
class WorkerState:
    worker_id: int = 0
    status: str = "starting"
    job_title: str = ""

# src/applypilot/apply/dashboard.py:58-69
def update_state(worker_id: int = 0, **kwargs) -> None:
    # Thread-safe mutation for worker UI state.
    with _lock:
        ...
```

**The Aha Moment:** UI state should be shaped for the screen that renders it.

**Socratic Checkpoint:** Why use a lock? What does `render_dashboard()` return? Which fields are display-only? What would happen if worker threads mutated `_worker_states` directly? How is this different from React state?

**How to Self-Grade:** Strong answers cite the dataclass, lock, and render function line ranges.

**Connects To:** Mission 9, because state needs a home.

### Mission 5: Your First Node.js Route

**Tier:** Junior

**Time Estimate:** 45 minutes

**Goal:** Trace the repo's route-equivalent core function and understand why there is no Node.js route layer.

**The Concept:** There are no HTTP routes. `acquire_job()` is route-like because it receives intent, checks rules, mutates state, and returns a response.

**Design Intent Before You Read the Code:** Job claiming must be atomic. If implemented poorly, multiple workers could submit the same application.

**Find It In The Code:** Open `src/applypilot/apply/launcher.py:174-271`.

```python
# src/applypilot/apply/launcher.py:186-188
conn = get_connection()
conn.execute("BEGIN IMMEDIATE")   # Claiming starts with a DB write lock.

# src/applypilot/apply/launcher.py:260-271
conn.execute("""
    UPDATE jobs SET apply_status = 'in_progress',
                   agent_id = ?,
                   last_attempted_at = ?
    WHERE url = ?
""", ...)
conn.commit()
return dict(row)
```

**The Aha Moment:** The database row is the queue item, lock, and audit record.

**Socratic Checkpoint:** Why begin a transaction before selecting? Which rows are eligible? Why skip manual ATS? What is returned? What state is committed?

**How to Self-Grade:** Strong answers include concurrency and durable state.

**Connects To:** Mission 14, the end-to-end trace.

### Mission 6: Props Are a Typed Contract

**Tier:** Junior

**Time Estimate:** 30 minutes

**Goal:** Read function parameters as promises.

**The Concept:** In React, props are a component contract. In this repo, function parameters play that role.

**Design Intent Before You Read the Code:** `run_job()` needs a complete job row, a browser port, agent selection, dry-run flag, and safety settings. Missing any piece changes behavior.

**Find It In The Code:** Open `src/applypilot/apply/launcher.py:416-428` and `src/applypilot/apply/prompt.py:419-447`.

```python
# src/applypilot/apply/prompt.py:419-428
def build_prompt(
    job: dict,                 # Must include job and artifact fields.
    tailored_resume: str,
    dry_run: bool = False,
    domain_allowlist: list[str] | None = None,
    ...
) -> str:
```

**The Aha Moment:** A parameter list tells you what the caller must know.

**Socratic Checkpoint:** Which parameters are safety controls? Which are artifact controls? Which are backend controls? What would you type more strongly? Which defaults are risky?

**How to Self-Grade:** Strong answers name `dry_run`, `domain_allowlist`, `timeout_s`, and `agent`.

**Connects To:** Mission 12.

### Mission 7: Following Data Into The App

**Tier:** Junior

**Time Estimate:** 45 minutes

**Goal:** Trace data from search config into stored jobs.

**The Concept:** The search config is a sourcing brief. Discovery reads it, job boards return leads, and the database records leads for later screening.

**Design Intent Before You Read the Code:** Config must be normalized before discovery uses it. Job data must be deduplicated by URL.

**Find It In The Code:** Open `src/applypilot/config.py:209-238`, `src/applypilot/discovery/jobspy.py:454-485`, and `src/applypilot/discovery/jobspy.py:131-192`.

```python
# src/applypilot/discovery/jobspy.py:179-191
try:
    conn.execute("INSERT INTO jobs (...)", (...))
    new += 1
except sqlite3.IntegrityError:
    existing += 1       # Duplicate URLs are expected, not fatal.
```

**The Aha Moment:** Data quality starts before the first insert.

**Socratic Checkpoint:** Where do `sites` come from? How are aliases normalized? Why is URL the primary key? Which fields may arrive incomplete? Why keep duplicates count?

**How to Self-Grade:** Strong answers connect config normalization, external data, and DB uniqueness.

**Connects To:** Mission 11.

### Mission 8: Navigation, Routing, Or Execution Flow Is The App's Skeleton

**Tier:** Junior

**Time Estimate:** 45 minutes

**Goal:** Explain the app's execution skeleton.

**The Concept:** In web apps, routing maps URLs to pages. Here, stage routing maps command intent to ordered work.

**Design Intent Before You Read the Code:** Stage resolution must preserve order even when the user names only some stages.

**Find It In The Code:** Open `src/applypilot/pipeline.py:172-180`, `src/applypilot/pipeline.py:324-373`, and `src/applypilot/pipeline.py:439-480`.

```python
# src/applypilot/pipeline.py:172-180
def _resolve_stages(stage_names: list[str]) -> list[str]:
    if "all" in stage_names:
        return list(STAGE_ORDER)
    ...
```

**The Aha Moment:** Stage order is this app's routing table.

**Socratic Checkpoint:** What does `all` resolve to? Where are unknown stages rejected? What is the difference between sequential and streaming mode? Why does pipeline bootstrap again? What gets returned?

**How to Self-Grade:** Strong answers cite both CLI validation and pipeline resolution.

**Connects To:** Mission 13 and Mission 14.
