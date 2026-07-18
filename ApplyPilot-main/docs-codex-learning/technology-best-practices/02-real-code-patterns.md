# Real Code Patterns

## Technology: Typer CLI

### Where It Is Used

`src/applypilot/cli.py` defines the command interface.

### Important Files

- `src/applypilot/cli.py`: commands and preflight checks.
- `pyproject.toml`: console script.

### Best-Practice Example 1: Shared Bootstrap

- File: `src/applypilot/cli.py`
- Line range: `38-45`
- Name: `_bootstrap`

```python
def _bootstrap() -> None:
    # One common startup path means commands do not forget env/dir/db setup.
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()
```

What it does: prepares local runtime state before commands touch the app.

Why it is good: centralizes repeated startup invariants.

Junior miss: they may think it is boilerplate.

Senior notice: this is also where expensive or destructive startup work must not creep in.

### Best-Practice Example 2: Validated Stage Names

- File: `src/applypilot/cli.py`
- Line range: `78-124`
- Name: `run`

The command validates stage names before calling `run_pipeline()`, preventing deeper modules from receiving unknown workflow names.

### Weak or Risky Pattern, If Present

`apply()` is long and mixes utility modes, dependency checks, and launch handoff in `src/applypilot/cli.py:127-220`. This is manageable today but should be split if more modes are added.

### Anti-Patterns to Avoid

- Adding SQL directly in CLI commands.
- Adding real side effects before `_bootstrap()`.
- Adding new commands without tests or doctor guidance.

### Interview Talking Points

- "Typer gives this repo a typed command boundary."
- "The CLI gates dangerous apply behavior before launching browsers."

### Mini Practice Tasks

- Add a display-only row to `status()`.
- Add a dry-run-only diagnostic option.

## Technology: SQLite

### Where It Is Used

SQLite appears in `src/applypilot/database.py` and stage modules that persist job progress.

### Important Files

- `src/applypilot/database.py`
- `src/applypilot/apply/launcher.py`
- `src/applypilot/pipeline.py`

### Best-Practice Example 1: Thread-Local Connections

- File: `src/applypilot/database.py`
- Line range: `20-49`
- Name: `get_connection`

```python
def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    # Each thread gets a cached connection, important for parallel workers.
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
```

Why good: parallel stages/workers need SQLite safety settings and row dictionaries.

Senior notice: local concurrency is supported, distributed concurrency is not.

### Best-Practice Example 2: Additive Migration Registry

- File: `src/applypilot/database.py`
- Line range: `143-219`
- Name: `_ALL_COLUMNS`, `ensure_columns`

This pattern keeps old local DBs compatible by adding missing columns on startup.

### Weak or Risky Pattern, If Present

Some dynamic SQL uses f-strings around internally built clauses. Example: `src/applypilot/apply/launcher.py:227-238`. Values are parameterized, but reviewers should stay alert.

### Anti-Patterns to Avoid

- Writing schema columns outside `database.py`.
- Querying real user DBs in tests.
- Changing primary keys in local-user databases without migration planning.

### Interview Talking Points

- "SQLite is both storage and workflow queue."
- "The schema mirrors the product pipeline."

### Mini Practice Tasks

- Add a read-only aggregation helper.
- Write a test with `tmp_path` DB isolation.

## Technology: Pipeline Orchestration

### Where It Is Used

`src/applypilot/pipeline.py` runs stages sequentially or streaming.

### Important Files

- `src/applypilot/pipeline.py`
- Stage modules in `discovery/`, `enrichment/`, `scoring/`

### Best-Practice Example 1: Stage Registry

- File: `src/applypilot/pipeline.py`
- Line range: `35-55`, `157-165`
- Name: `STAGE_ORDER`, `_STAGE_RUNNERS`

The stage order and runner map give the workflow a single readable source.

### Best-Practice Example 2: Pending SQL For Streaming

- File: `src/applypilot/pipeline.py`
- Line range: `222-255`
- Name: `_PENDING_SQL`, `_count_pending`

```python
_PENDING_SQL = {
    "score": "SELECT COUNT(*) FROM jobs WHERE full_description IS NOT NULL AND fit_score IS NULL",
}
```

Why good: downstream stages decide work availability from durable DB state.

### Weak or Risky Pattern, If Present

Stage runner return shapes are informal dicts. Typed result objects would improve maintainability.

### Mini Practice Tasks

- Add a dry-run summary for selected stages.
- Trace why `tailor` waits for `score`.

## Technology: LLM Client And Validation

### Where It Is Used

`src/applypilot/llm.py`, `src/applypilot/scoring/scorer.py`, `src/applypilot/scoring/tailor.py`, `src/applypilot/scoring/validator.py`, and `src/applypilot/apply/prompt.py`.

### Important Files

- `src/applypilot/llm.py`
- `src/applypilot/scoring/scorer.py`
- `src/applypilot/scoring/tailor.py`
- `src/applypilot/scoring/validator.py`

### Best-Practice Example 1: Provider Detection

- File: `src/applypilot/llm.py`
- Line range: `22-53`
- Name: `_detect_provider`

It supports Gemini, OpenAI, or local OpenAI-compatible endpoints using env vars.

### Best-Practice Example 2: Retry On Transient LLM Failures

- File: `src/applypilot/llm.py`
- Line range: `92-126`
- Name: `LLMClient.chat`

Retries 429, 503, and timeouts with backoff.

### Best-Practice Example 3: Programmatic Validation

- File: `src/applypilot/scoring/validator.py`
- Line range: `93-165`
- Name: `validate_json_fields`

The code treats LLM output as untrusted and checks missing fields, fabricated skills, banned words, and leaks.

### Weak or Risky Pattern, If Present

Scoring parses a text protocol with `SCORE:`, `KEYWORDS:`, `REASONING:` in `src/applypilot/scoring/scorer.py:43-69`. It works, but structured JSON would be easier to validate.

### Mini Practice Tasks

- Add a parser test for malformed score output.
- Add a validator test for one banned phrase.

## Technology: Agent Runners And subprocess

### Where It Is Used

Stage 6 uses external Claude/Codex CLI processes.

### Important Files

- `src/applypilot/apply/agents/base.py`
- `src/applypilot/apply/agents/claude_runner.py`
- `src/applypilot/apply/agents/codex_runner.py`
- `src/applypilot/apply/agents/parsing.py`

### Best-Practice Example 1: Normalized Runner Result

- File: `src/applypilot/apply/agents/base.py`
- Line range: `10-36`
- Name: `AgentRunResult`, `AgentRunner`

One launcher can work with multiple backends.

### Best-Practice Example 2: Codex JSONL Parsing

- File: `src/applypilot/apply/agents/codex_runner.py`
- Line range: `95-135`
- Name: `CodexRunner.run`

It writes raw logs, writes parsed JSONL events, extracts text, handles non-JSON warnings, and falls back to raw log text.

### Weak or Risky Pattern, If Present

`CodexRunner` uses `--dangerously-bypass-approvals-and-sandbox` in `src/applypilot/apply/agents/codex_runner.py:63-74`. This is a major trust decision.

### Mini Practice Tasks

- Add parser tests for JSON object output.
- Add a fake runner test for auto fallback without launching real CLIs.

## Technology: pytest

### Where It Is Used

Tests live under `tests/`.

### Important Files

- `tests/test_agent_parsing.py`
- `tests/test_apply_launcher.py`
- `tests/test_config_normalization.py`

### Best-Practice Example 1: Isolated DB Setup

- File: `tests/test_apply_launcher.py`
- Line range: `8-14`
- Name: `_setup_db`

```python
def _setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "applypilot.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(app_config, "DB_PATH", db_path)
    database.init_db(db_path)
```

Why good: tests do not touch the user's real database.

### Best-Practice Example 2: Behavior-Oriented Parser Tests

- File: `tests/test_agent_parsing.py`
- Line range: `4-24`

Tests assert normalized outcomes, not internal regex details.

### Weak or Risky Pattern, If Present

Integration tests depend on local CLIs and browser tooling, so they may skip. This is acceptable, but critical logic should still have unit tests.

### Mini Practice Tasks

- Add one test for domain allowlist blocking.
- Add one test for config edge cases.
