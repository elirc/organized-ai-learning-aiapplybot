# Mid-Level Engineer Guide

## Architecture Diagram

```text
User
  |
  v
Typer CLI
  |-- init -> wizard -> profile/search/env files under ~/.applypilot
  |-- run  -> pipeline -> discovery/enrichment/scoring/tailor/cover/pdf
  |-- apply -> launcher -> Chrome worker -> Claude/Codex runner -> result parser
  |-- status/dashboard -> SQLite stats -> Rich/HTML display
  |
  v
SQLite jobs table
  |-- discovery columns
  |-- enrichment columns
  |-- scoring columns
  |-- artifact columns
  |-- apply status columns
```

The center of gravity is not a server. It is the local `jobs` table plus filesystem artifacts under `~/.applypilot`.

## Type System Deep Dive

This is Python, not TypeScript. The type discipline is partial but useful.

Good contract example:

```python
# src/applypilot/apply/agents/base.py:10-36
@dataclass
class ParsedOutcome:
    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool

class AgentRunner(Protocol):
    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ...
```

Inline lesson: `ParsedOutcome` is a small stable vocabulary between messy external agent output and the rest of the app. A junior might see a dataclass; a mid-level engineer sees a boundary that prevents backend-specific strings from leaking through the launcher.

Weakness: many core job records are plain `dict`. For example `run_job(job: dict, ...)` in `src/applypilot/apply/launcher.py:416-428` assumes keys like `url`, `title`, `application_url`, and `tailored_resume_path`. A future improvement could introduce a typed `JobRow` dataclass or `TypedDict`.

## State Management Deep Dive

There is no Redux/Zustand/React Query. State lives in three places:

- SQLite rows: durable stage state.
- Files under `~/.applypilot`: user profile, resume, generated artifacts, logs.
- In-memory dashboard worker state: `src/applypilot/apply/dashboard.py:41-88`.

Important durable state example:

`acquire_job()` uses SQLite as a queue:

```python
# src/applypilot/apply/launcher.py:186-271
conn.execute("BEGIN IMMEDIATE")        # Lock early so workers do not double-claim.
...
row = conn.execute(...).fetchone()     # Select eligible job.
...
conn.execute("""
    UPDATE jobs SET apply_status = 'in_progress',
                   agent_id = ?,
                   last_attempted_at = ?
    WHERE url = ?
""", (f"worker-{worker_id}", now, row["url"]))
conn.commit()
return dict(row)
```

This is a local queue pattern. It is acceptable for a single-machine CLI, but a senior engineer would revisit it if the app became multi-host or cloud-based.

## API Contract Map

No internal REST/GraphQL/tRPC API exists. The main contracts are function and data contracts:

| Boundary | Contract | Evidence |
| --- | --- | --- |
| CLI to pipeline | stage names and options | `src/applypilot/cli.py:78-124`, `src/applypilot/pipeline.py:172-180` |
| Pipeline to stage modules | each runner returns a `dict` status | `src/applypilot/pipeline.py:62-165` |
| Stage modules to DB | `jobs` columns | `src/applypilot/database.py:90-133` |
| LLM client to scoring | OpenAI-compatible chat response | `src/applypilot/llm.py:69-126` |
| Agent CLI to launcher | `ParsedOutcome` | `src/applypilot/apply/agents/parsing.py:74-87` |
| Browser automation to agent | MCP config and prompt instructions | `src/applypilot/apply/launcher.py:66-115`, `src/applypilot/apply/prompt.py:419-565` |

## Component Interaction Map

For CLI/Rich UI:

`cli.apply()` validates dependencies -> `apply.launcher.main()` starts workers -> each worker calls `dashboard.update_state()` and `dashboard.add_event()` -> Rich dashboard renders via `render_full()`.

Evidence: `src/applypilot/cli.py:127-220`, `src/applypilot/apply/launcher.py:602-731`, `src/applypilot/apply/dashboard.py:58-88`, `src/applypilot/apply/dashboard.py:169-190`.

## Full-Stack Feature Trace

Closest full-stack equivalent: applying to one job.

1. UI/command: User runs `applypilot apply --agent auto --dry-run`. `cli.apply()` declares options in `src/applypilot/cli.py:127-153`.
2. Validation: CLI checks Chrome, selected agent CLI, profile existence, and tailored resumes in `src/applypilot/cli.py:182-218`.
3. State/data fetching: worker calls `acquire_job()`, which selects an eligible row in `src/applypilot/apply/launcher.py:196-238`.
4. Validation/middleware equivalent: manual ATS and blocked site checks happen before claiming in `src/applypilot/apply/launcher.py:247-258`.
5. Persistence: claimed row is updated to `in_progress` in `src/applypilot/apply/launcher.py:260-271`.
6. Browser boundary: `worker_loop()` launches Chrome in `src/applypilot/apply/launcher.py:671-675`.
7. Business logic: `run_job()` builds prompt sections, creates MCP config, chooses runner, and handles auto fallback in `src/applypilot/apply/launcher.py:502-568`.
8. External process: `CodexRunner.run()` executes `codex exec --json` in `src/applypilot/apply/agents/codex_runner.py:63-118`.
9. Response parsing: `parse_agent_result()` normalizes JSON or `RESULT:` output in `src/applypilot/apply/agents/parsing.py:35-87`.
10. UI update: `run_job()` maps outcome into dashboard state in `src/applypilot/apply/launcher.py:467-500`.
11. Final persistence: `worker_loop()` calls `mark_result()` or `release_lock()` in `src/applypilot/apply/launcher.py:690-702`.

## Diff Reading Exercise

Hypothetical change: add a new agent backend called `browserless`.

Read the diff in this order:

1. Does `src/applypilot/cli.py:133` extend the accepted Literal safely?
2. Does a new runner return `AgentRunResult` like `claude_runner.py:141-149` and `codex_runner.py:137-145`?
3. Does `run_job()` choose the runner without duplicating prompt logic from `src/applypilot/apply/launcher.py:502-535`?
4. Does output parsing reuse `parse_agent_result()` instead of inventing another status vocabulary?
5. Do tests cover success, timeout, and parse failure?

Strong review comment: "This adds a third backend but keeps the normalized agent contract intact. The risky part is not the CLI option; it is whether backend-specific failures map to durable statuses consistently."

## Non-Obvious Architectural Patterns

- Lazy imports in stage runners reduce startup coupling and keep optional dependency failures localized. See `src/applypilot/pipeline.py:62-165`.
- SQLite is used as both data store and work queue. This is simple and appropriate for local automation, but it limits distributed scaling.
- LLM output is constrained through both prompting and post-processing. See prompt final-output requirements in `src/applypilot/apply/prompt.py:552-565` and parser fallback in `src/applypilot/apply/agents/parsing.py:74-87`.
- Config normalization supports older wizard schemas. See `src/applypilot/config.py:129-178` and tests in `tests/test_config_normalization.py:8-42`.

## Mid-Level Socratic Checkpoint

1. Why is SQLite a reasonable queue for this app today?
2. What would break if two workers selected the same row?
3. Which columns define "ready to apply"?
4. Why does the app parse both JSON and `RESULT:` lines?
5. Where is the boundary between browser automation setup and agent execution?
6. What makes `run_job()` a high-risk function?
7. How would you add a new pipeline stage?
8. What test would you write before changing apply failure classification?

## How To Self-Grade

Strong answers use line citations from `database.py`, `pipeline.py`, `launcher.py`, and `agents/parsing.py`. They separate "state transition" from "side effect." They also name at least one trade-off, such as SQLite simplicity versus distributed coordination.
