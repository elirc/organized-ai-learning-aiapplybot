# 04 - Data, State, And SQLite

This app's most important state is the `jobs` table.

## What Is State?

State is information the app remembers.

Fake examples:

```python
current_score = 9                  # temporary state in memory
job["apply_status"] = "applied"    # durable state if saved to DB
resume_path = "resume.pdf"         # file path state
```

In ApplyPilot, state lives in three places:

1. SQLite database: `src/applypilot/database.py:90-133`
2. Local files under `APP_DIR`: `src/applypilot/config.py:11-29`
3. Temporary in-memory worker dashboard state: `src/applypilot/apply/dashboard.py:41-88`

## SQLite In Plain English

SQLite is a database stored in a file. In this app, that file is:

```python
# src/applypilot/config.py:11-20
APP_DIR = Path(os.environ.get("APPLYPILOT_DIR", Path.home() / ".applypilot"))
DB_PATH = APP_DIR / "applypilot.db"
```

So by default:

```text
~/.applypilot/applypilot.db
```

## The Jobs Table As A Workflow Ledger

Real schema excerpt:

```python
# src/applypilot/database.py:90-133
conn.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        url                   TEXT PRIMARY KEY,
        title                 TEXT,
        salary                TEXT,
        description           TEXT,
        location              TEXT,
        site                  TEXT,
        strategy              TEXT,
        discovered_at         TEXT,

        full_description      TEXT,
        application_url       TEXT,
        detail_scraped_at     TEXT,
        detail_error          TEXT,

        fit_score             INTEGER,
        score_reasoning       TEXT,
        scored_at             TEXT,

        tailored_resume_path  TEXT,
        tailored_at           TEXT,
        tailor_attempts       INTEGER DEFAULT 0,

        cover_letter_path     TEXT,
        cover_letter_at       TEXT,
        cover_attempts        INTEGER DEFAULT 0,

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

Annotated meaning:

- `url`: unique identity of a job.
- `full_description`: enrichment succeeded enough to score.
- `fit_score`: scoring stage ran.
- `tailored_resume_path`: resume artifact exists.
- `apply_status`: auto-apply state.
- `apply_error`: why apply failed or needs review.

## Fake Database Example

Imagine the DB as a spreadsheet:

| url | title | full_description | fit_score | tailored_resume_path | apply_status |
| --- | --- | --- | --- | --- | --- |
| job-1 | Backend Engineer | null | null | null | null |
| job-2 | Python Engineer | long text | 9 | resume.txt | null |
| job-3 | Data Engineer | long text | 6 | null | null |

What this tells you:

- `job-1` needs enrichment.
- `job-2` is likely ready for apply.
- `job-3` was scored but may be below tailoring threshold.

## Reading SQL

SQL asks the database questions.

Fake SQL:

```sql
SELECT * FROM jobs WHERE fit_score >= 7
```

Read it as:

"Give me all job rows where the fit score is 7 or higher."

Real ApplyPilot example:

```python
# src/applypilot/database.py:383-399
conditions = {
    "pending_detail": "detail_scraped_at IS NULL",
    "enriched": "full_description IS NOT NULL",
    "pending_score": "full_description IS NOT NULL AND fit_score IS NULL",
    "scored": "fit_score IS NOT NULL",
    "pending_tailor": (
        "fit_score >= ? AND full_description IS NOT NULL "
        "AND tailored_resume_path IS NULL AND COALESCE(tailor_attempts, 0) < 5"
    ),
    "tailored": "tailored_resume_path IS NOT NULL",
    "pending_apply": (
        "tailored_resume_path IS NOT NULL AND applied_at IS NULL "
        "AND application_url IS NOT NULL"
    ),
    "applied": "applied_at IS NOT NULL",
}
```

Inline lesson:

- `IS NULL` means missing.
- `IS NOT NULL` means present.
- `fit_score >= ?` uses a parameter.
- `COALESCE(tailor_attempts, 0)` treats missing attempts as 0.

## Parameters Protect SQL

Fake bad example:

```python
# Risky fake code. Do not copy.
query = f"SELECT * FROM jobs WHERE title = '{user_input}'"
```

Why risky:

- If `user_input` contains SQL syntax, it can break or change the query.

Fake better example:

```python
query = "SELECT * FROM jobs WHERE title = ?"
rows = conn.execute(query, (user_input,)).fetchall()
```

Real ApplyPilot example:

```python
# src/applypilot/database.py:413-421
query = (
    f"SELECT * FROM jobs WHERE {where} "
    "ORDER BY (fit_score IS NULL), fit_score DESC, discovered_at DESC"
)
if limit > 0:
    query += " LIMIT ?"
    params.append(limit)

rows = conn.execute(query, params).fetchall()
```

Senior note:

- The `where` string is chosen from internal known conditions.
- Values go through `params`.
- This is safer than putting user values directly into SQL.

## Transactions

A transaction groups DB actions.

Fake example:

```python
conn.execute("BEGIN")
try:
    conn.execute("UPDATE account SET balance = balance - 10 WHERE id = 1")
    conn.execute("UPDATE account SET balance = balance + 10 WHERE id = 2")
    conn.commit()
except Exception:
    conn.rollback()
```

Real ApplyPilot example:

```python
# src/applypilot/apply/launcher.py:186-274
conn = get_connection()
try:
    conn.execute("BEGIN IMMEDIATE")
    ...
    conn.execute(
        """
        UPDATE jobs SET apply_status = 'in_progress',
                       agent_id = ?,
                       last_attempted_at = ?
        WHERE url = ?
        """,
        (f"worker-{worker_id}", now, row["url"]),
    )
    conn.commit()
    return dict(row)
except Exception:
    conn.rollback()
    raise
```

Inline lesson:

- `BEGIN IMMEDIATE` claims a write lock early.
- The worker selects a job and marks it `in_progress`.
- `commit()` makes the claim durable.
- `rollback()` undoes the claim if an error occurs.

Why this matters:

Without this, two workers might apply to the same job.

## Migrations

A migration changes the database schema safely.

Real ApplyPilot pattern:

```python
# src/applypilot/database.py:143-183
_ALL_COLUMNS: dict[str, str] = {
    "url": "TEXT PRIMARY KEY",
    "title": "TEXT",
    ...
    "verification_confidence": "TEXT",
}
```

```python
# src/applypilot/database.py:186-219
def ensure_columns(conn: sqlite3.Connection | None = None) -> list[str]:
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

Inline lesson:

- Read existing columns.
- Compare with expected columns.
- Add missing columns.
- Never remove or rename columns here.

Fake migration exercise:

```python
# You want to add this fake column:
"reviewed_by_user": "INTEGER DEFAULT 0"

# You would add it to the column registry.
# Then init_db() would call ensure_columns().
```

## Tests For Database Code

Tests should not touch the real user's database.

Real test helper:

```python
# tests/test_apply_launcher.py:8-14
def _setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "applypilot.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(app_config, "DB_PATH", db_path)
    database.close_connection(db_path)
    database.init_db(db_path)
    return db_path, database.get_connection(db_path)
```

Inline lesson:

- `tmp_path` gives a temporary folder.
- `monkeypatch` redirects the app's DB path.
- Tests create a fresh DB.
- Real user data is safe.

## Practice

Write a fake test plan:

"When a job is marked as permanent failure, `apply_attempts` should become high enough that normal queue selection will not pick it again."

Use real anchors:

- Permanent marking: `src/applypilot/apply/launcher.py:277-298`
- Permanent failure list: `src/applypilot/apply/launcher.py:575-585`
- Existing tests: `tests/test_apply_launcher.py:149-201`

Self-grade:

- Strong answer includes setup, action, assertion.
- Weak answer says only "test failure handling."

