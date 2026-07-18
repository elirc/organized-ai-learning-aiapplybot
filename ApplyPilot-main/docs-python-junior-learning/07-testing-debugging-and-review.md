# 07 - Testing, Debugging, And Review

This file teaches how to prove code works and how to debug when it does not.

## What Is A Test?

A test is a small program that checks another program.

Fake example:

```python
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
```

If `add(2, 3)` returns anything other than `5`, the test fails.

## Real Parser Tests

```python
# tests/test_agent_parsing.py:4-18
def test_parse_result_line_applied() -> None:
    parsed = parse_agent_result("RESULT: APPLIED - submitted")
    assert parsed.status == "APPLIED"
    assert parsed.submitted is True

def test_parse_json_output() -> None:
    parsed = parse_agent_result('{"result":"DRY_RUN","reason":"preview","submitted":false}')
    assert parsed.status == "DRY_RUN"
    assert parsed.submitted is False
```

Inline lesson:

- Call the function with a known input.
- Check the returned object.
- The test does not care how regex works internally.
- It cares about behavior.

## Testing Database Code Safely

Never let tests touch real user data.

Real helper:

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

- `tmp_path` creates a temporary location.
- `monkeypatch.setattr(...)` redirects production constants.
- `init_db(db_path)` creates a test DB.

Fake equivalent:

```python
def test_uses_fake_database(tmp_path):
    fake_db = tmp_path / "test.db"
    app.database_path = fake_db
    run_test()
```

## Arrange, Act, Assert

Most tests should have three parts.

Fake example:

```python
def test_high_score_is_eligible():
    # Arrange
    job = {"fit_score": 9}

    # Act
    eligible = job["fit_score"] >= 7

    # Assert
    assert eligible is True
```

Real example:

```python
# tests/test_apply_launcher.py:41-75
def test_acquire_job_target_url_selects_unattempted_job(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    conn.execute(...)
    conn.commit()

    job = launcher.acquire_job(target_url="https://example.com/jobs/123", worker_id=4)

    assert job is not None
    assert job["url"] == "https://example.com/jobs/123"
    row = conn.execute(...).fetchone()
    assert row["apply_status"] == "in_progress"
    assert row["agent_id"] == "worker-4"
```

Inline lesson:

- Arrange: create DB row.
- Act: call `acquire_job()`.
- Assert: returned job and DB state are correct.

## Debugging Method

When something fails, do not jump randomly.

Use this sequence:

1. Reproduce the problem.
2. Name the expected behavior.
3. Find the entry point.
4. Find the state change.
5. Check logs/errors.
6. Write a focused test or temporary print.
7. Fix the smallest owning function.

## Example Debug: `applypilot status` Looks Wrong

Question: "Why does status say 0 ready to apply?"

Trace:

1. Entry point: `src/applypilot/cli.py:362-425`
2. Stats function: `src/applypilot/database.py:222-320`
3. Apply-ready columns: `tailored_resume_path`, `applied_at`, `application_url` from `src/applypilot/database.py:113-132`
4. Query logic likely in `get_stats()`

Fake debugging SQL:

```sql
SELECT url, tailored_resume_path, application_url, applied_at
FROM jobs
WHERE tailored_resume_path IS NOT NULL;
```

What you are asking:

"Are jobs really ready, or is the display wrong?"

## Example Debug: Agent Output Not Recognized

Trace:

1. Runner writes output: `src/applypilot/apply/agents/codex_runner.py:95-135`
2. Parser reads text: `src/applypilot/apply/agents/parsing.py:74-87`
3. Launcher maps parsed status: `src/applypilot/apply/launcher.py:467-500`
4. Tests show expected parser behavior: `tests/test_agent_parsing.py:4-55`

Fake failing output:

```text
Done. I submitted it.
```

Parser result:

```python
ParsedOutcome(status="NEEDS_REVIEW", reason="no_result_marker", submitted=False)
```

Why:

The output lacks JSON or `RESULT:` marker. That is safer than assuming submission.

## Code Review Checklist

When reviewing a change, ask:

1. What user behavior changes?
2. What file owns this behavior?
3. What database columns are read/written?
4. Does it touch external boundaries?
5. What happens on failure?
6. Is there a test?
7. Does it touch unrelated files?

## Review Example: Changing Apply Failure Logic

Relevant code:

- `src/applypilot/apply/launcher.py:575-588` classifies permanent failures.
- `src/applypilot/apply/launcher.py:690-702` marks final worker results.
- `tests/test_apply_launcher.py:149-201` tests retryable and permanent failures.

Fake diff:

```python
PERMANENT_FAILURES = {
    "expired",
    "captcha",
    # removed "domain_not_allowed"
}
```

Review comment:

"Removing `domain_not_allowed` from permanent failures may cause blocked domains to be retried repeatedly. Please add or update a test proving the desired retry behavior."

## How To Write A Good Test

Good test names say behavior:

```python
def test_run_job_blocks_disallowed_domain_before_side_effects():
    ...
```

Weak test name:

```python
def test_run_job_1():
    ...
```

Good tests check outcomes:

```python
assert result == "failed:domain_not_allowed:blocked.example"
assert duration_ms == 0
```

Weak tests check implementation details:

```python
assert internal_counter == 3  # unless that counter is the behavior
```

## Practice

Design a test for:

"When agent output is empty, the parser returns `NEEDS_REVIEW` with reason `empty_output`."

Write the shape:

```python
def test_empty_agent_output_needs_review():
    parsed = parse_agent_result("")
    assert parsed.status == "NEEDS_REVIEW"
    assert parsed.reason == "empty_output"
    assert parsed.submitted is False
```

Compare with real test coverage in `tests/test_agent_parsing.py:27-32`.

Self-grade:

- Strong test has one behavior, clear input, clear assertions.
- Weak test mixes unrelated parser cases.

