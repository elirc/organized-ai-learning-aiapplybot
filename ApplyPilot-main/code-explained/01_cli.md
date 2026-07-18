# cli.py — The Front Door of ApplyPilot

**File:** `src/applypilot/cli.py` (426 lines)
**Role:** CLI entry point — parses user commands and routes them to the right subsystem.

---

## What This File Does

This is the file that runs when a user types `applypilot` in their terminal. It defines every command the user can run, validates their inputs, checks prerequisites, and hands off to the appropriate subsystem.

Think of it as a **receptionist** — it doesn't do the work itself, but it makes sure the right department gets the right request with the right information.

---

## The Framework: Typer

```python
app = typer.Typer(
    name="applypilot",
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)
```

[Typer](https://typer.tiangolo.com/) is a CLI framework built on top of Click. The key thing to understand: **each function decorated with `@app.command()` becomes a CLI command.** The function parameters become command-line flags automatically.

For example:
```python
@app.command()
def run(
    stages: Optional[list[str]] = typer.Argument(None, help="Pipeline stages to run."),
    min_score: int = typer.Option(7, "--min-score", help="Minimum fit score."),
):
```
This automatically generates:
```
$ applypilot run --help
Usage: applypilot run [STAGES] [OPTIONS]
  --min-score INTEGER  Minimum fit score. [default: 7]
```

**Why `no_args_is_help=True`?** If someone types just `applypilot` with no command, show the help text instead of an error. Better UX.

---

## The Bootstrap Pattern

```python
def _bootstrap() -> None:
    """Common setup: load env, create dirs, init DB."""
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()
```

Every command that touches data calls `_bootstrap()` first. This does three things:
1. **Load .env** — reads API keys from `~/.applypilot/.env`
2. **Create directories** — ensures `~/.applypilot/`, `logs/`, `tailored_resumes/`, etc. exist
3. **Init DB** — creates the SQLite database and runs migrations if needed

**Why lazy imports?** Notice the imports are *inside* the function, not at the top of the file. This is intentional:
```python
def _bootstrap() -> None:
    from applypilot.config import load_env, ensure_dirs  # lazy import
```
If someone runs `applypilot --version`, they shouldn't have to wait for the entire dependency tree (Playwright, pandas, LLM clients) to load. Lazy imports keep startup fast for simple commands.

---

## Command: `run` (Stages 1-5)

```python
@app.command()
def run(stages, min_score, workers, stream, dry_run):
```

This command runs the pipeline stages. Key behaviors:

### Stage Validation
```python
VALID_STAGES = ("discover", "enrich", "score", "tailor", "cover", "pdf")

for s in stage_list:
    if s != "all" and s not in VALID_STAGES:
        console.print(f"[red]Unknown stage:[/red] '{s}'.")
        raise typer.Exit(code=1)
```
If someone types `applypilot run discovr` (typo), they get a clear error instead of a confusing crash.

### Tier Gating
```python
llm_stages = {"score", "tailor", "cover"}
if any(s in stage_list for s in llm_stages) or "all" in stage_list:
    from applypilot.config import check_tier
    check_tier(2, "AI scoring/tailoring")
```
The system has a **tier model**: Tier 1 (discovery only), Tier 2 (+ AI scoring), Tier 3 (+ auto-apply). If you try to run `score` without an LLM API key configured, `check_tier()` gives you a helpful error message telling you what to set up.

**Why this design?** It prevents confusing runtime errors. Instead of crashing with `RuntimeError: No LLM provider configured` 10 minutes into a run, you get a clear message *before anything starts*.

---

## Command: `apply` (Stage 6)

This is the most complex command (lines 127-292). It has many flags because Stage 6 is the most configurable:

```python
@app.command()
def apply(
    limit, workers, min_score, model, agent, claude_model, codex_model,
    continuous, dry_run, headless, enable_gmail, domain_allowlist,
    max_applies, min_delay_seconds, url, gen, mark_applied, mark_failed,
    fail_reason, reset_failed,
):
```

### Utility Modes (Quick Exits)
The first thing `apply` does is check for "utility mode" flags that don't need Chrome or AI:

```python
if mark_applied:
    mark_job(mark_applied, "applied")
    return

if mark_failed:
    mark_job(mark_failed, "failed", reason=fail_reason)
    return

if reset_failed:
    count = do_reset()
    return
```

**Why?** Sometimes you manually applied to a job and want to mark it in the database. Or you want to retry all failed jobs. These operations are quick database updates that shouldn't require Chrome to be installed.

### Pre-flight Checks
Before launching the full apply pipeline, the command validates:

1. **Chrome is installed:**
```python
try:
    get_chrome_path()
except FileNotFoundError as e:
    console.print(f"[red]{e}[/red]")
    raise typer.Exit(code=1)
```

2. **Agent CLI is installed:**
```python
if agent == "claude" and not shutil.which("claude"):
    console.print("[red]Claude CLI not found.[/red]")
    raise typer.Exit(code=1)
```

3. **Profile exists:**
```python
if not _profile_path.exists():
    console.print("[red]Profile not found.[/red]\n"
                  "Run [bold]applypilot init[/bold] to create your profile first.")
```

4. **Tailored resumes are ready:**
```python
ready = conn.execute(
    "SELECT COUNT(*) FROM jobs WHERE tailored_resume_path IS NOT NULL AND applied_at IS NULL"
).fetchone()[0]
if ready == 0:
    console.print("[red]No tailored resumes ready.[/red]")
```

**Why all these checks?** Launching Chrome + an AI agent is expensive (takes seconds, uses resources). If we know it's going to fail, fail fast with a clear message.

### The `--gen` Flag (Debug Mode)
```python
if gen:
    prompt_file = gen_prompt(target_url, ...)
    console.print(f"[green]Wrote prompt to:[/green] {prompt_file}")
    console.print(f"  claude --model {model} -p --mcp-config {mcp_path} < {prompt_file}")
    return
```
This writes the prompt to a file and prints the exact command you'd run manually. It's a **debugging escape hatch** — if auto-apply is behaving weirdly, you can see exactly what instructions the AI agent receives and run it yourself.

---

## Command: `doctor` (Health Check)

```python
@app.command()
def doctor():
```

Prints a table showing whether Chrome, Claude CLI, and Codex CLI are installed. Also checks Codex project trust configuration. This is a **diagnostic tool** — when something doesn't work, `applypilot doctor` is the first thing to run.

---

## Command: `status` (Dashboard)

```python
@app.command()
def status():
```

Queries the database and displays:
- Job counts by stage (total, enriched, scored, tailored, applied)
- Score distribution histogram
- Jobs by source site

This uses Rich tables for pretty formatting. The score histogram uses `=` characters with color coding (green for 7+, yellow for 5-6, red for 1-4).

---

## Design Patterns to Notice

### 1. Fail Fast, Fail Clear
Every command validates its preconditions *before* doing any work. Error messages tell you exactly what's wrong and how to fix it.

### 2. Separation of Concerns
`cli.py` never does business logic. It validates, configures, and delegates:
- `applypilot run` → `pipeline.run_pipeline()`
- `applypilot apply` → `launcher.main()`
- `applypilot init` → `wizard.run_wizard()`

### 3. Progressive Disclosure
Simple commands (`status`, `doctor`) have few or no options. Complex commands (`apply`) have many, but with sensible defaults so you can start simple: `applypilot apply` works with zero flags.

### 4. Exit Codes
```python
if result.get("errors"):
    raise typer.Exit(code=1)
```
Non-zero exit codes allow shell scripts to detect failures: `applypilot run && echo "Success"`.
