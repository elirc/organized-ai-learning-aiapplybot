# 08 - Practice Labs

These labs are designed for learning. Do them in scratch branches. Do not paste solutions blindly.

## Lab 1: Explain A Function Out Loud

Function:

- `src/applypilot/apply/launcher.py:155-167`

Task:

Explain `_is_domain_allowed()` line by line.

Use this template:

```text
This function receives...
First it checks...
Then it extracts...
The loop means...
It returns False when...
The product reason this matters is...
```

Fake warm-up:

```python
def is_score_allowed(score: int, minimum: int) -> bool:
    if score < minimum:
        return False
    return True
```

Self-grade:

- Strong answer connects allowlist to safe auto-apply.
- Weak answer only says "it checks domains."

## Lab 2: Trace A Job Row

Files:

- `src/applypilot/database.py:90-133`
- `src/applypilot/scoring/scorer.py:154-161`
- `src/applypilot/scoring/tailor.py:526-540`
- `src/applypilot/apply/launcher.py:277-298`

Task:

Create a table with columns:

```text
stage | function | columns read | columns written | failure mode
```

Fill it for:

- scoring
- tailoring
- applying

Fake example:

```text
stage: scoring
function: run_scoring
columns read: full_description, url
columns written: fit_score, score_reasoning, scored_at
failure mode: LLM error produces score 0
```

Self-grade:

- Strong answer includes both read and write columns.
- Weak answer only lists function names.

## Lab 3: Write Fake Python Before Real Python

Feature idea:

"Add a preview of jobs that would be auto-applied."

Before touching code, write fake Python:

```python
def preview_apply_queue(min_score):
    jobs = find_jobs_ready_to_apply(min_score)
    for job in jobs:
        print(job["title"], job["site"], job["fit_score"])
```

Then map fake functions to real files:

- `find_jobs_ready_to_apply` might belong near `src/applypilot/apply/launcher.py:174-271`
- Display might belong in `src/applypilot/cli.py:127-220`
- DB state comes from `src/applypilot/database.py:90-133`

Self-grade:

- Strong plan separates selection from display.
- Weak plan puts everything directly inside a CLI command.

## Lab 4: Add One Test In Your Head

Existing test style:

- `tests/test_apply_launcher.py:8-14`
- `tests/test_apply_launcher.py:149-201`

Task:

Design a test for:

"A failed job with `apply_attempts` already at max should not be acquired again."

Fake test outline:

```python
def test_max_attempts_job_is_not_acquired(tmp_path, monkeypatch):
    # Arrange: create temp DB
    # Arrange: insert apply-ready job with apply_attempts = max
    # Act: call acquire_job()
    # Assert: result is None
```

Questions:

1. Which DB columns must be set?
2. Which function should be called?
3. What should the assertion be?
4. Should this launch Chrome?

Answer:

It should not launch Chrome. This is a database selection test.

## Lab 5: Learn Type Hints By Designing A Job Contract

Real weak point:

- `run_job(job: dict, ...)` in `src/applypilot/apply/launcher.py:416-428`

Task:

Write a fake `TypedDict` for an apply-ready job.

```python
from typing import TypedDict

class ApplyReadyJob(TypedDict, total=False):
    url: str
    title: str
    site: str
    application_url: str | None
    tailored_resume_path: str
    fit_score: int
    full_description: str
    cover_letter_path: str | None
```

Discussion:

- `url`, `title`, and `tailored_resume_path` are required in practice.
- Some values can be optional.
- This makes invisible dictionary contracts visible.

Self-grade:

- Strong contract distinguishes required from optional fields.
- Weak contract marks everything as `str`.

## Lab 6: Debug A Fake Bug Report

Bug:

"I ran `applypilot apply --dry-run`, and now my job disappeared from the queue."

Trace:

1. CLI command: `src/applypilot/cli.py:127-220`
2. Job claim: `src/applypilot/apply/launcher.py:174-271`
3. Dry-run mapping: `src/applypilot/apply/launcher.py:484-487`
4. Worker handling for skipped: `src/applypilot/apply/launcher.py:690-692`
5. Lock release: `src/applypilot/apply/launcher.py:301-308`

Expected reasoning:

- Dry-run should map to `skipped`.
- Worker should call `release_lock()`.
- `release_lock()` should clear `apply_status` only when it is `in_progress`.

Self-grade:

- Strong answer identifies the expected state after dry-run.
- Weak answer says "check logs" without tracing state.

## Lab 7: Review A Fake Diff

Fake diff:

```python
def parse_agent_result(text: str) -> ParsedOutcome:
    if "submitted" in text.lower():
        return ParsedOutcome(status="APPLIED", reason="submitted", submitted=True)
```

Review it against:

- `src/applypilot/apply/agents/parsing.py:74-87`
- `tests/test_agent_parsing.py:4-55`

Problems:

- It trusts vague text.
- It could mark a job applied when the agent merely said "not submitted."
- It bypasses JSON and `RESULT:` contracts.

Better review comment:

"This makes apply detection too loose. Please keep explicit JSON or `RESULT:` markers and add a parser test for ambiguous text like `not submitted`."

## Lab 8: Build A Reading Habit

Every time you open a file, write:

```text
Owner:
Inputs:
Outputs:
State read:
State written:
External systems:
Tests:
Risk:
```

Example for `src/applypilot/llm.py`:

```text
Owner: LLM API client
Inputs: messages, env vars, model settings
Outputs: assistant text
State read: environment variables
State written: none, except client singleton
External systems: Gemini/OpenAI/local LLM endpoint
Tests: tests/test_llm.py:6-24
Risk: timeout, rate limit, wrong provider, cost
```

## Lab 9: First Safe Real Change

Suggested beginner change:

"Improve a label in `applypilot status`."

Why this is safe:

- It is display-only.
- It touches `src/applypilot/cli.py:373-390`.
- It does not change DB state.

Checklist:

1. Read `status()`.
2. Identify the exact table row.
3. Change label only.
4. Run targeted command or test.
5. Review diff for unrelated changes.

## Lab 10: First Deeper Real Change

Suggested intermediate change:

"Add a test for a new apply failure reason."

Files:

- `src/applypilot/apply/launcher.py:575-588`
- `tests/test_apply_launcher.py:149-201`

Plan:

1. Decide whether the failure should be permanent.
2. Add test first.
3. Update classification if test exposes missing behavior.
4. Run `python -m pytest tests/test_apply_launcher.py -q`.

Self-grade:

- Strong work explains user harm of retrying or not retrying.
- Weak work changes constants without a test.

