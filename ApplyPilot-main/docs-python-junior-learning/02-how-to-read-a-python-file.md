# 02 - How To Read A Python File

Most beginners read code from line 1 downward. That works for small scripts, but real codebases need a better method.

Use this reading order:

1. File name and folder.
2. Top docstring.
3. Imports.
4. Constants.
5. Public functions/classes.
6. Private helpers.
7. Side effects.
8. Tests.

## Example 1: Reading `cli.py`

File: `src/applypilot/cli.py`

### Step 1: File Name And Folder

`cli.py` lives at `src/applypilot/cli.py`. That usually means "command-line interface."

### Step 2: Imports And App Creation

```python
# src/applypilot/cli.py:22-31
app = typer.Typer(
    name="applypilot",
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)
console = Console()
log = logging.getLogger(__name__)

VALID_STAGES = ("discover", "enrich", "score", "tailor", "cover", "pdf")
```

Inline reading:

- `typer.Typer(...)` creates the CLI app.
- `Console()` is Rich's pretty terminal output object.
- `VALID_STAGES` is a tuple of allowed pipeline stages.

Read like an engineer:

- This file owns user commands.
- It should validate user input.
- It should not contain deep scraping or LLM logic.

### Step 3: Shared Setup

```python
# src/applypilot/cli.py:38-45
def _bootstrap() -> None:
    """Common setup: load env, create dirs, init DB."""
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()
```

Inline reading:

- Load environment variables.
- Create local directories.
- Initialize the database.

Fake simplified version:

```python
def prepare_app():
    load_settings()
    create_folders()
    create_database()
```

The idea is the same: every command gets a safe starting point.

### Step 4: Commands

```python
# src/applypilot/cli.py:70-75
@app.command()
def init() -> None:
    """Run the first-time setup wizard (profile, resume, search config)."""
    from applypilot.wizard.init import run_wizard

    run_wizard()
```

Inline reading:

- `@app.command()` registers a command.
- The command is named after the function: `init`.
- It delegates to the wizard module.

Practice:

If you saw this fake code:

```python
@app.command()
def clean() -> None:
    run_cleanup()
```

You should predict a user can run:

```text
applypilot clean
```

## Example 2: Reading `database.py`

File: `src/applypilot/database.py`

### Step 1: Top Docstring

```python
# src/applypilot/database.py:1-6
"""ApplyPilot database layer: schema, migrations, stats, and connection helpers.

Single source of truth for the jobs table schema. All columns from every
pipeline stage are created up front so any stage can run independently
without migration ordering issues.
"""
```

Inline reading:

- This file owns schema.
- This file owns migrations.
- This file is a single source of truth.

Senior note:

When a file says "single source of truth," be skeptical of code elsewhere that duplicates schema knowledge.

### Step 2: Connection Helper

```python
# src/applypilot/database.py:20-49
def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)

    if not hasattr(_local, 'connections'):
        _local.connections = {}

    conn = _local.connections.get(path)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            pass

    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    _local.connections[path] = conn
    return conn
```

Inline reading:

- Choose a DB path.
- Create a per-thread connection cache if missing.
- Reuse an existing connection if it still works.
- Otherwise create a new SQLite connection.
- Configure SQLite for local concurrency.
- Return rows that behave like dictionaries.

Fake simplified version:

```python
connections = {}

def get_fake_connection(name):
    if name in connections:
        return connections[name]

    conn = open_connection(name)
    connections[name] = conn
    return conn
```

The real version is more careful because SQLite and threads need care.

## Example 3: Reading `pipeline.py`

File: `src/applypilot/pipeline.py`

Start with constants:

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

Inline reading:

- `STAGE_ORDER` is the order of the assembly line.
- `STAGE_META` is display metadata.
- Stages are not random; each stage prepares data for later stages.

Then read runner map:

```python
# src/applypilot/pipeline.py:157-165
_STAGE_RUNNERS: dict[str, callable] = {
    "discover": _run_discover,
    "enrich":   _run_enrich,
    "score":    _run_score,
    "tailor":   _run_tailor,
    "cover":    _run_cover,
    "pdf":      _run_pdf,
}
```

Inline reading:

- Stage name maps to function.
- This is like a routing table for pipeline stages.

Fake simplified version:

```python
handlers = {
    "hello": say_hello,
    "goodbye": say_goodbye,
}

command = "hello"
handlers[command]()
```

## Reading Checklist For Any ApplyPilot File

Use this table:

| Question | Example Answer |
| --- | --- |
| What does the file own? | `database.py` owns SQLite schema and query helpers. |
| Who calls it? | CLI, pipeline, apply launcher, tests. |
| What does it read? | User DB, env vars, YAML, profile, external APIs. |
| What does it write? | SQLite rows, generated files, logs, dashboard HTML. |
| What can fail? | Missing files, missing packages, network, browser, LLM, SQL. |
| What tests cover it? | `tests/test_apply_launcher.py`, `tests/test_config_normalization.py`, etc. |

## Practice Exercise

Open `src/applypilot/apply/agents/parsing.py:1-87`.

Answer:

1. What is the input to `parse_agent_result()`?
2. What is its output?
3. Why does it check JSON before `RESULT:` lines?
4. Why does unknown output become `NEEDS_REVIEW` instead of crashing?

Self-grade:

- Strong answer: you connect parser behavior to safe auto-apply outcomes.
- Weak answer: you only describe the regex.

