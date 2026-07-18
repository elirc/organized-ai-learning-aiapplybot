# database.py — The Single Source of Truth

**File:** `src/applypilot/database.py` (425 lines)
**Role:** SQLite schema definition, thread-safe connections, queries, and migrations.

---

## What This File Does

This file manages **all database operations** for ApplyPilot. Every pipeline stage reads from and writes to the same SQLite database through this module. It defines:

1. The schema (what columns the `jobs` table has)
2. Thread-safe connection management
3. Forward-only migrations (adding new columns safely)
4. Reusable queries for each pipeline stage
5. Statistics for dashboards

---

## Thread-Local Connection Pool

```python
_local = threading.local()

def get_connection(db_path=None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)

    if not hasattr(_local, 'connections'):
        _local.connections = {}

    conn = _local.connections.get(path)
    if conn is not None:
        try:
            conn.execute("SELECT 1")  # health check
            return conn
        except sqlite3.ProgrammingError:
            pass  # connection is closed/broken

    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    _local.connections[path] = conn
    return conn
```

### Why `threading.local()`?

**The problem:** SQLite connections are NOT thread-safe. If two threads use the same connection object, you get crashes or data corruption.

**The solution:** `threading.local()` gives each thread its own namespace. When Thread A calls `get_connection()`, it gets Thread A's connection. When Thread B calls it, it gets a completely separate connection. They never interfere.

```
Thread 1: _local.connections = {"path": Connection_A}
Thread 2: _local.connections = {"path": Connection_B}  # completely separate
```

### Why Cache Connections?

Creating a new SQLite connection for every query is wasteful (file open, WAL setup, etc.). By caching in `_local.connections`, each thread reuses its connection across all queries in that thread's lifetime.

### The Health Check

```python
try:
    conn.execute("SELECT 1")
    return conn
except sqlite3.ProgrammingError:
    pass  # connection is broken, create a new one
```

Sometimes a cached connection becomes invalid (e.g., the file was deleted, or the connection was closed elsewhere). `SELECT 1` is the cheapest possible query to verify the connection is alive. If it fails, we silently create a new one.

### WAL Mode and Busy Timeout

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=10000")
```

**WAL (Write-Ahead Logging):** The default SQLite journal mode locks the entire database for writes. WAL allows concurrent reads + one writer. This is essential for multi-worker mode.

**busy_timeout=10000:** If a connection tries to write while another is writing, instead of immediately failing with `SQLITE_BUSY`, it waits up to 10 seconds. This handles brief contention gracefully.

### Row Factory

```python
conn.row_factory = sqlite3.Row
```

Without this, `SELECT` returns tuples: `(url, title, salary, ...)`. With `sqlite3.Row`, you get dict-like objects: `row["title"]`, `row["salary"]`. This makes the code much more readable.

---

## Schema Design

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        -- Discovery stage
        url                   TEXT PRIMARY KEY,
        title                 TEXT,
        salary                TEXT,
        description           TEXT,
        location              TEXT,
        site                  TEXT,
        strategy              TEXT,
        discovered_at         TEXT,

        -- Enrichment stage
        full_description      TEXT,
        application_url       TEXT,
        detail_scraped_at     TEXT,
        detail_error          TEXT,

        -- Scoring stage
        fit_score             INTEGER,
        score_reasoning       TEXT,
        scored_at             TEXT,

        -- Tailoring stage
        tailored_resume_path  TEXT,
        tailored_at           TEXT,
        tailor_attempts       INTEGER DEFAULT 0,

        -- Cover letter stage
        cover_letter_path     TEXT,
        cover_letter_at       TEXT,
        cover_attempts        INTEGER DEFAULT 0,

        -- Application stage
        applied_at            TEXT,
        apply_status          TEXT,
        apply_error           TEXT,
        apply_attempts        INTEGER DEFAULT 0,
        agent_id              TEXT,
        last_attempted_at     TEXT,
        apply_duration_ms     INTEGER,
        apply_task_id         TEXT,
        verification_confidence TEXT
    )
""")
```

### Why URL as Primary Key?

The `url` is the natural unique identifier for a job. Two scrapers might find the same job — deduplication happens automatically because `INSERT` into a duplicate URL raises `IntegrityError`.

**Trade-off:** URLs can be long (500+ chars), making the index larger. An auto-increment ID would be smaller, but then you'd need a separate unique constraint on URL anyway.

### Why TEXT for Dates?

```python
discovered_at TEXT,  -- not DATETIME
```

SQLite doesn't have a native datetime type. All dates are stored as ISO 8601 strings (`2024-03-15T14:30:00+00:00`). Python's `datetime.isoformat()` produces these, and they sort correctly as strings.

### Why Attempt Counters?

```python
tailor_attempts INTEGER DEFAULT 0,
apply_attempts  INTEGER DEFAULT 0,
```

These prevent infinite retry loops. If tailoring fails 5 times (LLM keeps producing bad output), the job is skipped on future runs. If applying fails 3 times, the job is marked as permanently failed.

### Why `strategy` Column?

```python
strategy TEXT,  -- e.g., "jobspy", "workday_cxs", "json_ld", "css_selectors"
```

This tracks *how* a job was discovered. Useful for debugging ("all Workday jobs are failing enrichment") and analytics ("which scraper finds the most jobs?").

---

## Forward Migration System

```python
_ALL_COLUMNS: dict[str, str] = {
    "url": "TEXT PRIMARY KEY",
    "title": "TEXT",
    # ... every column listed here ...
}

def ensure_columns(conn=None) -> list[str]:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    added = []
    for col, dtype in _ALL_COLUMNS.items():
        if col not in existing:
            if "PRIMARY KEY" in dtype:
                continue
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {dtype}")
            added.append(col)
    if added:
        conn.commit()
    return added
```

### How It Works

1. `PRAGMA table_info(jobs)` returns the current schema — what columns actually exist in the database.
2. Compare against `_ALL_COLUMNS` — the **desired** schema.
3. Any missing columns get added via `ALTER TABLE ADD COLUMN`.

### Why This Design?

**The problem:** Users upgrade ApplyPilot over time. Version 1.0 might have 20 columns. Version 2.0 adds `apply_duration_ms`. How do you update existing databases?

**The solution:** `_ALL_COLUMNS` is the single source of truth. On startup, `ensure_columns()` compares the actual schema to the desired schema and adds anything missing. This is:

- **Idempotent** — safe to run 100 times (already-existing columns are skipped)
- **Forward-only** — columns are only added, never removed (no data loss)
- **Automatic** — happens on every startup, no manual migration commands

**Why not use a migration framework like Alembic?** Overkill for a single-table app. `ALTER TABLE ADD COLUMN` is the only migration operation needed.

---

## Query Functions

### `store_jobs()` — Deduplication on Insert

```python
def store_jobs(conn, jobs, site, strategy) -> tuple[int, int]:
    for job in jobs:
        try:
            conn.execute("INSERT INTO jobs (...) VALUES (...)", (...))
            new += 1
        except sqlite3.IntegrityError:
            existing += 1
    conn.commit()
    return new, existing
```

The `url` is the primary key. If a job already exists, the INSERT fails with `IntegrityError`, and we count it as "existing" instead of crashing. This is the **insert-or-ignore** pattern.

**Why not `INSERT OR IGNORE`?** We want to *count* duplicates (for reporting), not silently skip them.

### `get_jobs_by_stage()` — Stage-Aware Queries

```python
conditions = {
    "discovered": "1=1",
    "pending_detail": "detail_scraped_at IS NULL",
    "enriched": "full_description IS NOT NULL",
    "pending_score": "full_description IS NOT NULL AND fit_score IS NULL",
    "pending_tailor": "fit_score >= ? AND tailored_resume_path IS NULL AND ...",
    "pending_apply": "tailored_resume_path IS NOT NULL AND applied_at IS NULL AND ...",
}
```

Each stage needs "give me the jobs that I should work on." This function maps stage names to SQL WHERE clauses.

**The `pending_tailor` query is interesting:**
```sql
WHERE fit_score >= ?
  AND full_description IS NOT NULL
  AND tailored_resume_path IS NULL
  AND COALESCE(tailor_attempts, 0) < 5
```

This says: "Give me jobs that scored high enough, have a description, haven't been tailored yet, AND haven't already failed 5 times." The `COALESCE` handles NULL (never attempted) by treating it as 0.

### `get_stats()` — Dashboard Data

This function runs ~15 separate COUNT queries to produce a snapshot of the entire pipeline. It's used by the `status` command and the HTML dashboard.

```python
stats["pending_detail"] = conn.execute(
    "SELECT COUNT(*) FROM jobs WHERE detail_scraped_at IS NULL"
).fetchone()[0]
```

**Why so many separate queries instead of one complex query?** Readability and maintainability. Each stat is independent and clearly labeled. A single mega-query would be harder to debug.

---

## Design Patterns to Notice

### 1. Single Table, Many Stages
All 30+ columns live in one table. This is a **wide table** design. It violates normalization but massively simplifies queries — no JOINs needed.

### 2. NULL as "Not Yet Done"
The pattern `WHERE column IS NULL` means "this stage hasn't run yet." This is how the pipeline knows what work remains:
- `fit_score IS NULL` → needs scoring
- `tailored_resume_path IS NULL` → needs tailoring
- `applied_at IS NULL` → needs applying

### 3. Defensive Programming
The `close_connection()` function uses `.pop(path, None)` which returns `None` if the key doesn't exist, instead of raising `KeyError`. The health check in `get_connection()` catches `ProgrammingError`. These are examples of defensive coding — assuming things might be in an unexpected state.

### 4. Schema as Code
The `_ALL_COLUMNS` dict serves as both documentation AND the migration source. If you want to add a column, you add it to this dict — that's it. The migration system picks it up automatically.
