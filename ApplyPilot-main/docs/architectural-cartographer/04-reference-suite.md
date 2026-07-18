# Reference Suite

## Doc 1: Junior Onboarding Guide

Start with `pyproject.toml:20-35`, `README.md:83-139`, and `src/applypilot/cli.py:22-45`. Your first goal is to understand how a shell command becomes Python execution.

Day-one orientation:

- Run `applypilot doctor` after install.
- Read the six stages in `src/applypilot/pipeline.py:35-44`.
- Read the schema in `src/applypilot/database.py:90-133`.
- Trace one CLI command only: `applypilot run score`.

First explanation to practice:

"ApplyPilot is a local Python CLI. It stores job workflow state in SQLite, uses LLMs for scoring/tailoring, uses Playwright/browser tooling for scraping and applying, and writes artifacts under `~/.applypilot`."

## Doc 2: Mid-Level Architecture Guide

System design:

- CLI boundary: `src/applypilot/cli.py`.
- Config boundary: `src/applypilot/config.py`.
- Durable state: `src/applypilot/database.py`.
- Orchestration: `src/applypilot/pipeline.py`.
- Domain stages: `discovery/`, `enrichment/`, `scoring/`, `apply/`.

Data flow:

`jobs.url` is the primary key. Each stage fills more columns. If a bug appears, ask: "Which column should have changed, and which function owns that transition?"

Component contracts:

- Stage functions return dict summaries.
- Agent runners return `AgentRunResult`.
- Parser returns `ParsedOutcome`.
- Config loaders return normalized dicts.

API boundaries:

No internal HTTP API. External boundaries are LLM chat completions (`src/applypilot/llm.py:69-126`), job board scraping, Playwright browser sessions, and local CLI processes.

## Doc 3: Senior Ownership Guide

Technical debt register:

- Untyped job dicts in critical paths.
- Large modules with multiple responsibilities.
- Optional domain allowlist for real auto-apply.
- Custom additive migration without migration history.
- Generated HTML assembled as strings.

Upgrade path:

1. Add tests around safety rules.
2. Add typed job row contracts.
3. Split `run_job()` around prompt preparation, runner selection, and outcome mapping.
4. Add redaction review for prompt/log content.
5. Improve dashboard template structure.

## Doc 4: Code Review Guide

Review order:

1. Entry point: does the CLI option or stage name match existing patterns?
2. State: does it read/write the right `jobs` columns?
3. Idempotency: can it retry safely?
4. External effects: browser, LLM, filesystem, subprocess, network.
5. Tests: does it cover success and failure?
6. Safety: does it protect personal data and application submission behavior?

Repo examples:

- Job claiming review: `src/applypilot/apply/launcher.py:174-271`.
- Parser review: `src/applypilot/apply/agents/parsing.py:35-87`.
- Config compatibility review: `tests/test_config_normalization.py:8-109`.

## Doc 5: Debugging Guide

For a pipeline bug:

1. Run `applypilot status`.
2. Inspect which DB columns are missing.
3. Open the stage runner in `src/applypilot/pipeline.py:62-165`.
4. Open the module that owns that stage.
5. Check logs under `~/.applypilot/logs/`.

Likely failure points:

- Missing profile: `src/applypilot/config.py:306-316`.
- Missing LLM provider: `src/applypilot/llm.py:22-53`.
- Missing Chrome/CLI: `src/applypilot/cli.py:182-197`.
- Agent output lacks final marker: `src/applypilot/apply/agents/parsing.py:74-87`.
- Resume PDF missing before apply: `src/applypilot/apply/prompt.py:452-468`.

## Doc 6: Change Playbook

To add a feature safely:

1. Define user behavior.
2. Identify the owning command or stage.
3. Identify DB columns or files affected.
4. Add or update tests first when the behavior is risky.
5. Keep external calls behind small boundaries.
6. Run targeted pytest.
7. Review generated artifacts/logs for privacy.

To remove a feature:

1. Find CLI entry and user docs.
2. Find DB fields and status values.
3. Remove tests or adjust them intentionally.
4. Keep migration compatibility if user DBs may already have columns.

## Doc 7: Interview Walkthrough

Concise answer:

"I worked on a local Python CLI automation system for job applications. It uses Typer for commands, SQLite as a durable workflow ledger, Playwright and job-board integrations for discovery/enrichment, LLM calls for scoring and resume tailoring, and a Stage 6 agent abstraction so Claude and Codex CLIs can drive browser-based application flows through one normalized result contract."

Deeper follow-up:

- Trade-off: SQLite is simple and reliable locally, but it is not a distributed queue.
- Safety: auto-apply is gated by dry-run, domain allowlist, manual ATS detection, max applies, and result parsing.
- Testing: parser/config/launcher behavior is covered with pytest; browser/agent paths need integration fixtures.
- Improvement: introduce typed job row contracts and more safety tests around domain and fallback behavior.
