# Architecture and System Design (Junior Engineer Guide)

This document explains how ApplyBot is structured, with special focus on Stage 6 (Auto-Apply), where the system now supports both Claude CLI and Codex CLI through a shared abstraction.

If you are new to the codebase, start with this doc and then read files in the order listed in [Reading Order](#reading-order).

---

## 1) High-Level Architecture

ApplyBot is a pipeline application with six stages:

1. Discover jobs
2. Enrich job details
3. Score jobs with AI
4. Tailor resume per job
5. Generate cover letters
6. Auto-apply using browser automation + agent CLI

The first five stages are data preparation. Stage 6 is execution.

### Main Architectural Layers

- **CLI layer**: command parsing and user-facing control (`src/applypilot/cli.py`)
- **Pipeline orchestration**: stage sequencing and control (`src/applypilot/pipeline.py`)
- **Persistence layer**: SQLite schema and DB helpers (`src/applypilot/database.py`)
- **Stage modules**: stage-specific logic (`src/applypilot/discovery/*`, `enrichment/*`, `scoring/*`, `apply/*`)
- **Configuration layer**: paths, defaults, feature checks (`src/applypilot/config.py`)

---

## 2) Stage 6 Core Problem

Originally, Stage 6 directly spawned Claude CLI from one monolithic launcher path.

That design made it hard to:

- support a second CLI backend (Codex)
- keep parsing logic consistent
- add fallback strategies
- test backend behavior in a backend-agnostic way

The refactor introduces a backend abstraction so Stage 6 can switch engines with minimal branching.

---

## 3) New Stage 6 Design

### 3.1 Agent Backend Abstraction

New module:

- `src/applypilot/apply/agents/`

Key files:

- `base.py`
- `parsing.py`
- `claude_runner.py`
- `codex_runner.py`

#### `ParsedOutcome`

Represents normalized final state from any backend.

Fields:

- `status`: one of `APPLIED | FAILED | CAPTCHA | NEEDS_REVIEW | DRY_RUN`
- `reason`: short machine-readable explanation
- `submitted`: whether a submission actually occurred

#### `AgentRunResult`

Represents full execution result for one backend invocation.

Fields:

- `engine`: `claude` or `codex`
- `exit_code`
- `final_text`
- `events_path` (Codex JSONL path when available)
- `raw_log_path`
- `duration_ms`
- `parsed` (the `ParsedOutcome`)

### 3.2 Parsing Strategy (`parsing.py`)

Parsing supports two output formats:

1. RESULT-line format (legacy and still supported)
2. JSON object output (preferred for Codex when schema mode is used)

Algorithm:

1. try JSON-object parse from last valid JSON-like lines
2. else parse `RESULT:` lines (case-insensitive)
3. else return `NEEDS_REVIEW`

Why this matters:

- CLI outputs are not perfectly stable across tool versions
- robust fallback reduces false negatives

---

## 4) Backend Implementations

### 4.1 Claude Runner

File:

- `src/applypilot/apply/agents/claude_runner.py`

Responsibilities:

- build Claude CLI command with expected flags
- pass per-worker MCP config via `--mcp-config`
- stream and collect output
- extract assistant text from stream-json events
- write raw log
- parse outcome via shared parser

Implementation notes:

- keeps existing behavior patterns (permission mode, no session persistence)
- supports process registration callbacks so Ctrl+C logic can terminate active agents

### 4.2 Codex Runner

File:

- `src/applypilot/apply/agents/codex_runner.py`

Responsibilities:

- run `codex exec` non-interactively
- use `--json` event stream
- optionally use `--output-schema`
- capture JSONL event file + raw log
- extract best-effort final assistant text from events
- parse outcome via shared parser

Implementation notes:

- uses per-worker working directory
- captures both structured and unstructured output pathways
- also supports process registration callbacks for centralized interrupt handling

---

## 5) Shared MCP Wiring Strategy

### Claude MCP

- launcher generates worker JSON config
- path pattern: `~/.applypilot/.mcp-apply-<worker>.json`
- includes Playwright server
- includes Gmail server only when `--enable-gmail`

### Codex MCP

- launcher generates worker-local `.codex/config.toml`
- same MCP server intent as Claude:
  - Playwright MCP with worker-specific CDP endpoint
  - optional Gmail MCP when enabled

### Why worker-local config matters

Each worker has a different Chrome CDP port (`BASE_CDP_PORT + worker_id`), so each worker needs independent MCP wiring.

---

## 6) Launcher Refactor (`apply/launcher.py`)

This is the most important integration file for Stage 6.

### 6.1 New Controls Added

- `agent` backend selector (`claude|codex|auto`)
- `enable_gmail` toggle
- `domain_allowlist`
- `max_applies`
- `min_delay_seconds`

### 6.2 `run_job` flow

`run_job` now:

1. validates allowlist vs job URL host
2. builds one shared prompt
3. configures backend-specific MCP/runtime files
4. runs selected backend or fallback chain (`auto`)
5. maps parsed outcomes to existing job status semantics

### 6.3 `auto` mode fallback behavior

`auto` flow:

1. try Claude
2. if missing/error/non-zero/needs_review, try Codex
3. if both fail, return clear combined fallback reason

### 6.4 Status mapping

The launcher maps normalized parsed outcomes back into existing DB states.

Examples:

- `APPLIED` -> `applied`
- `DRY_RUN` -> skip/lock release path
- `CAPTCHA` -> failed with captcha reason
- `FAILED` -> failed with specific reason
- `NEEDS_REVIEW` -> failed with review reason

This preserves legacy downstream behavior while modernizing backend internals.

---

## 7) Prompt Contract Design (`apply/prompt.py`)

The prompt remains mostly legacy-compatible but now explicitly encodes shared guardrails.

### 7.1 New explicit guardrails

- dry-run behavior: do not submit, end with dry-run result
- domain allowlist policy: abort outside allowed domains
- throttling instruction: minimum delay between applications

### 7.2 Final output contract

Two supported terminal formats:

- RESULT line:
  - `RESULT: <STATUS> - <reason>`
- JSON object (for schema-backed runs):
  - `{"result":"...","reason":"...","submitted":...}`

The parser supports both to reduce brittleness.

---

## 8) CLI Integration (`cli.py`)

### 8.1 New apply options

Added:

- `--agent claude|codex|auto`
- `--claude-model`
- `--codex-model`
- `--enable-gmail`
- `--domain-allowlist`
- `--max-applies`
- `--min-delay-seconds`

Retained compatibility:

- `--model` still accepted as deprecated Claude alias

### 8.2 `doctor` command

`applypilot doctor` checks:

- Claude binary presence
- Codex binary presence
- Chrome availability
- Codex trust guidance for project config usage

`doctor` is intentionally advisory, not a hard failure command.

---

## 9) Concurrency and Worker Model

Stage 6 workers use thread-based concurrency (`ThreadPoolExecutor`).

For each worker:

1. acquire job DB lock (`in_progress`)
2. launch isolated Chrome with worker-specific profile + CDP port
3. run backend agent process with MCP config for that worker
4. parse outcome and update DB
5. cleanup Chrome and release resources

Ctrl+C behavior:

- first Ctrl+C skips active job(s) by killing active agent processes
- second Ctrl+C requests stop and terminates all workers/chrome

---

## 10) Database State Transitions

Relevant fields include:

- `apply_status`
- `apply_error`
- `apply_attempts`
- `apply_duration_ms`
- `apply_task_id`

Typical state lifecycle:

1. `NULL/failed` -> acquired -> `in_progress`
2. final result:
   - success -> `applied`
   - otherwise -> `failed` with reason + attempts increment
3. permanent failure classification avoids pointless retries for known terminal causes

---

## 11) Logging and Observability

Stage 6 writes detailed logs for troubleshooting.

Important files:

- worker log stream (`worker-<id>.log`)
- backend raw logs (`agent_claude_...`, `agent_codex_...`)
- Codex JSONL events (`agent_codex_...jsonl`)

Why this is useful:

- debug parser misses
- inspect model terminal outputs
- inspect backend exit codes and timing

---

## 12) Testing Strategy

### 12.1 Unit tests

- parser-focused tests in `tests/test_agent_parsing.py`

### 12.2 Integration tests

- `tests/test_agent_runners_integration.py`
- local HTML fixture (`tests/fixtures/fake_job_form.html`)
- local HTTP server + Chrome CDP + MCP wiring
- tests are marked `integration`
- auto-skip when required binaries are missing

Goal:

- validate runner plumbing and parse behavior without touching real job boards

---

## 13) Extension Guide (For Junior Engineers)

If you want to add a new backend (for example another CLI agent), do this:

1. Create `<new>_runner.py` in `apply/agents/`
2. Return `AgentRunResult` from `run(...)`
3. Reuse `parse_agent_result(...)`
4. Add backend selection branch in `launcher.run_job`
5. Add CLI option in `cli.apply`
6. Add docs + integration test skip logic

### Design principle to keep

Always keep:

- one shared prompt contract
- one shared outcome parser
- one shared launcher status mapping

Backends should differ only in:

- command invocation
- event/log extraction
- backend-specific config files

---

## 14) Reading Order

For onboarding, read in this sequence:

1. `src/applypilot/cli.py`
2. `src/applypilot/apply/launcher.py`
3. `src/applypilot/apply/agents/base.py`
4. `src/applypilot/apply/agents/parsing.py`
5. `src/applypilot/apply/agents/claude_runner.py`
6. `src/applypilot/apply/agents/codex_runner.py`
7. `src/applypilot/apply/prompt.py`
8. `tests/test_agent_parsing.py`
9. `tests/test_agent_runners_integration.py`

---

## 15) Mental Model Summary

Think of Stage 6 as three layers:

1. **Orchestration layer** (`launcher.py`)
   - chooses jobs
   - starts browser
   - chooses backend
   - commits DB outcomes

2. **Execution layer** (`agents/*_runner.py`)
   - executes one CLI tool
   - captures structured/unstructured output

3. **Normalization layer** (`parsing.py`)
   - translates backend-specific text into stable statuses

That separation is what makes Claude/Codex coexist cleanly while keeping existing pipeline behavior predictable.

---

## 16) Hands-On Exercises

> Snapshot note: sections 16–17 come from the refined `ARCHITECTURE.md` in `elirc/applybot`. This snapshot's code is newer: it has five more test files and changes in `launcher.py`, `database.py` and other modules. So the line numbers, E4 and review point 4 were re-checked against the code here and adjusted.

Ordered easy → hard. Each has a check you can run.

### E1 — Drive the parser by hand (15 min)

The normalization layer is pure. Its only project import is the
`ParsedOutcome` dataclass from the sibling `base.py`, so you can poke it
directly:

```bash
python -c "import sys; sys.path.insert(0, 'src'); from applypilot.apply.agents.parsing import parse_agent_result; print(parse_agent_result('RESULT: APPLIED - submitted ok')); print(parse_agent_result('')); print(parse_agent_result('blah'))"
```

**Check**: you get `APPLIED/submitted ok/True`, then
`NEEDS_REVIEW/empty_output/False`, then `NEEDS_REVIEW/no_result_marker/False`.
Now explain why `NEEDS_REVIEW` (not `FAILED`) is the right default for
unparseable output from an agent that may or may not have submitted a form.

### E2 — Pin the precedence rule with a test (30 min)

Read `parse_agent_result()` in `src/applypilot/apply/agents/parsing.py`:
JSON lines are tried **before** `RESULT:` lines, and that priority is
position-independent — output containing `RESULT: APPLIED` followed later
by `{"status": "FAILED"}` parses as `FAILED`. That is a real behavioural
contract and nothing currently documents it except the code.

Add a test to `tests/test_agent_parsing.py` that fixes this precedence
(both orders: JSON-then-RESULT and RESULT-then-JSON).
**Check**: `python -m pytest tests/test_agent_parsing.py -q` passes, and
deliberately swapping the two `_try_parse_*` calls makes your test fail.

### E3 — Trace auto-fallback and name its gaps (45 min)

Read the `auto` branch in `src/applypilot/apply/launcher.py` (the
`for engine in ("claude", "codex")` loop, ~L548–568). Write down, from the
code alone: which outcomes cause the loop to try Codex after Claude, and
what the final status string is when both fail.
**Check**: your answer ends with `auto_fallback_exhausted`, and you can say
what a `CAPTCHA` outcome from Claude does (does Codex get a turn? should
it?).

### E4 — First direct test for the database layer (1–2 h)

`database.py` has no test file of its own. It is only exercised indirectly:
the `_setup_db` fixture in `tests/test_apply_launcher.py` calls `init_db`
once on a `tmp_path` DB so the launcher tests have a `jobs` table. It was
built for direct tests: `get_connection(db_path=...)` and
`init_db(db_path=...)` accept an override path ("Useful for testing" is in
the docstring), and `init_db` claims to be idempotent. Nothing checks that
claim. Write a test (a new `tests/test_database.py`) that creates a DB in
`tmp_path`, inserts a job, and asserts `init_db` is idempotent (call it
twice, data survives). Copy the `close_connection` setup and teardown from
`_setup_db`.
**Check**: `python -m pytest -q` stays green; deleting the
`CREATE TABLE IF NOT EXISTS` guard's `IF NOT EXISTS` makes your idempotence
test fail (undo that!).

---

## 17) What a Senior Reviewer Would Push Back On

All four are real properties of today's code — verify each before taking
the review position.

1. **The job's identity is its URL** (`url TEXT PRIMARY KEY` in
   `database.py`). Natural keys are tidy until the same posting appears
   with `?utm_source=...` appended (two rows, two applications to one job)
   or a board reposts the same role at a new URL (history lost). A
   reviewer would ask for URL canonicalization at insert time, and
   eventually a surrogate id + unique index. Where would you normalize —
   discovery, or the DB layer?
2. **One wide table for all six stages.** Deliberate, and the docstring
   says why (any stage can run independently, no migration ordering). The
   cost: every stage's writer can clobber any column, and NULL means both
   "not yet" and "not applicable". Fine for a single-user CLI; the moment
   two processes share the DB you want per-stage tables or at least
   `CHECK` constraints on `apply_status`.
3. **Status vocabulary is stringly-typed at the edges.** `EXPIRED` and
   `LOGIN_ISSUE` from an agent collapse into `FAILED` with a
   `expired:`/`login_issue:` reason prefix (`parsing.py`,
   `_normalize_status`). Downstream code that wants to treat login issues
   as retryable has to parse strings. The `Literal[...]` on
   `ParsedOutcome.status` is the right instinct — a reviewer would push to
   either widen it or document the reason-prefix contract where it's
   consumed.
4. **Seven test files for 32 source files.** What exists is well-aimed:
   the parser (pure, highest churn), an integration harness that skips
   cleanly when CLIs are missing, and `test_apply_launcher.py` (job
   claiming, retry/permanent-failure bookkeeping, lock release, the domain
   allowlist), plus config normalization, JobSpy discovery, the LLM client
   and PDF generation. The gaps are the persistence layer's own contract
   (it is only touched through the launcher fixture) and
   `_normalize_status`'s mapping table: no test feeds it `EXPIRED` or
   `LOGIN_ISSUE`. E2/E4 above are the first two PRs a reviewer would
   actually ask for. Both are small, high-value and need no mocking.
