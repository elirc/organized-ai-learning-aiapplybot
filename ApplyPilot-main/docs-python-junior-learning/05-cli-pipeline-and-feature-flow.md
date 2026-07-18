# 05 - CLI, Pipeline, And Feature Flow

This file teaches how user actions become code execution.

## Entry Point: How The Command Starts

The shell command is declared in `pyproject.toml:34-35`:

```toml
[project.scripts]
applypilot = "applypilot.cli:app"
```

Read it as:

"When the user runs `applypilot`, load `app` from `applypilot/cli.py`."

## The CLI App

```python
# src/applypilot/cli.py:22-31
app = typer.Typer(
    name="applypilot",
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)

VALID_STAGES = ("discover", "enrich", "score", "tailor", "cover", "pdf")
```

Inline lesson:

- `app` is the CLI router.
- `VALID_STAGES` is the allowed stage vocabulary.

Fake comparison:

```python
commands = {
    "run": run_pipeline,
    "status": show_status,
}
```

Typer does this in a cleaner real framework.

## Command: `applypilot run`

```python
# src/applypilot/cli.py:78-124
@app.command()
def run(
    stages: Optional[list[str]] = typer.Argument(None, ...),
    min_score: int = typer.Option(7, "--min-score", ...),
    workers: int = typer.Option(1, "--workers", "-w", ...),
    stream: bool = typer.Option(False, "--stream", ...),
    dry_run: bool = typer.Option(False, "--dry-run", ...),
) -> None:
    _bootstrap()

    from applypilot.pipeline import run_pipeline

    stage_list = stages if stages else ["all"]

    for s in stage_list:
        if s != "all" and s not in VALID_STAGES:
            raise typer.Exit(code=1)

    result = run_pipeline(
        stages=stage_list,
        min_score=min_score,
        dry_run=dry_run,
        stream=stream,
        workers=workers,
    )
```

Inline lesson:

- CLI options become Python parameters.
- `_bootstrap()` prepares env, folders, and DB.
- Stage names are validated.
- `run_pipeline()` does the real orchestration.

Fake beginner version:

```python
def run(command_stages=None):
    prepare_app()

    if command_stages is None:
        command_stages = ["all"]

    for stage in command_stages:
        if stage not in ["all", "discover", "score"]:
            print("Bad stage")
            return

    run_pipeline(command_stages)
```

## Pipeline Stage Map

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

Think of this as an application assembly line:

```text
raw job lead -> detailed posting -> scored job -> resume package -> cover package -> PDF package
```

## Stage Runner Functions

```python
# src/applypilot/pipeline.py:62-99
def _run_discover(workers: int = 1) -> dict:
    stats: dict = {"jobspy": None, "workday": None, "smartextract": None}

    try:
        from applypilot.discovery.jobspy import run_discovery
        run_discovery()
        stats["jobspy"] = "ok"
    except Exception as e:
        stats["jobspy"] = f"error: {e}"

    try:
        from applypilot.discovery.workday import run_workday_discovery
        run_workday_discovery(workers=workers)
        stats["workday"] = "ok"
    except Exception as e:
        stats["workday"] = f"error: {e}"

    try:
        from applypilot.discovery.smartextract import run_smart_extract
        run_smart_extract(workers=workers)
        stats["smartextract"] = "ok"
    except Exception as e:
        stats["smartextract"] = f"error: {e}"

    return stats
```

Inline lesson:

- Discovery is made of three sub-scrapers.
- Each sub-scraper can fail independently.
- The function returns partial status instead of crashing the whole app immediately.

Fake pattern:

```python
def run_all_sources():
    results = {}
    for source in ["source_a", "source_b", "source_c"]:
        try:
            run_source(source)
            results[source] = "ok"
        except Exception as error:
            results[source] = f"error: {error}"
    return results
```

## Sequential Pipeline

```python
# src/applypilot/pipeline.py:324-373
def _run_sequential(ordered: list[str], min_score: int, workers: int = 1) -> dict:
    results: list[dict] = []
    errors: dict[str, str] = {}

    for name in ordered:
        runner = _STAGE_RUNNERS[name]

        try:
            kwargs: dict = {}
            if name in ("tailor", "cover"):
                kwargs["min_score"] = min_score
            if name in ("discover", "enrich"):
                kwargs["workers"] = workers
            result = runner(**kwargs)
            status = result.get("status", "ok") if isinstance(result, dict) else "ok"
        except Exception as e:
            status = f"error: {e}"

        results.append({"stage": name, "status": status, "elapsed": elapsed})
```

Inline lesson:

- Loop through stages in order.
- Pick the right runner function.
- Build keyword arguments based on stage.
- Record status.

## Full Feature Trace: Status Command

This is a simpler feature than auto-apply and a good beginner trace.

### User action

```text
applypilot status
```

### CLI command

```python
# src/applypilot/cli.py:362-369
@app.command()
def status() -> None:
    """Show pipeline statistics from the database."""
    _bootstrap()

    from applypilot.database import get_stats

    stats = get_stats()
```

Inline lesson:

- Register `status` command.
- Prepare app.
- Load `get_stats`.
- Query stats.

### Database logic

```python
# src/applypilot/database.py:222-320
def get_stats(conn: sqlite3.Connection | None = None) -> dict:
    if conn is None:
        conn = get_connection()

    stats["total"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    stats["scored"] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE fit_score IS NOT NULL"
    ).fetchone()[0]
```

Inline lesson:

- Use a DB connection.
- Run SQL counts.
- Return a dictionary of stats.

### UI output

```python
# src/applypilot/cli.py:373-390
summary = Table(title="Pipeline Overview", show_header=True, header_style="bold cyan")
summary.add_column("Metric", style="bold")
summary.add_column("Count", justify="right")

summary.add_row("Total jobs discovered", str(stats["total"]))
summary.add_row("Scored by LLM", str(stats["scored"]))
summary.add_row("Ready to apply", str(stats["ready_to_apply"]))
summary.add_row("Applied", str(stats["applied"]))
```

Inline lesson:

- Rich `Table` is the terminal UI.
- DB stats become display rows.

## Full Feature Trace: Apply One Job

This is the advanced flow.

```text
applypilot apply --agent codex --dry-run
```

### CLI validates inputs

Evidence: `src/applypilot/cli.py:127-220`

Key responsibilities:

- parse CLI options
- check Chrome
- check Claude/Codex CLI
- check profile exists
- check tailored resumes exist

### Worker claims job

Evidence: `src/applypilot/apply/launcher.py:174-271`

Important idea:

- A job becomes `in_progress` before browser automation starts.

### Browser launches

Evidence: `src/applypilot/apply/launcher.py:671-675`

```python
chrome_proc = launch_chrome(worker_id, port=port, headless=headless)
```

### Agent runs

Evidence: `src/applypilot/apply/launcher.py:502-535`

```python
if engine == "claude":
    runner = ClaudeRunner(...)
else:
    runner = CodexRunner(...)
return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)
```

### Result gets parsed and saved

Evidence:

- Parse result: `src/applypilot/apply/agents/parsing.py:74-87`
- Mark result: `src/applypilot/apply/launcher.py:277-298`
- Worker save path: `src/applypilot/apply/launcher.py:690-702`

## Practice: Trace A New Feature

Pretend you want to add:

"Show the number of failed applications in the HTML dashboard."

Trace it:

1. UI surface: `src/applypilot/view.py:25-407`
2. Data source: `jobs.apply_status` and `jobs.apply_error` from `src/applypilot/database.py:123-132`
3. Query location: `src/applypilot/view.py:38-82`
4. Display location: generated HTML in `src/applypilot/view.py`
5. Test idea: seed rows and call `generate_dashboard()` with temp DB path.

Self-grade:

- Strong trace names files, data columns, and verification.
- Weak trace says "change dashboard" without knowing where data comes from.

