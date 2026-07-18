# Architectural Cartographer Journal

## First-Pass Mental Model

ApplyPilot is a Python CLI package with a stage-based job application pipeline. It is not a React, Next.js, Express, NestJS, Prisma, TypeORM, GraphQL, or REST API application. The user interface is primarily terminal commands and Rich terminal output, plus generated HTML dashboards. The durable "application state" is a local SQLite `jobs` table.

The system behaves like a recruiting operations conveyor belt:

1. Discovery adds raw job rows.
2. Enrichment fills full descriptions and application URLs.
3. Scoring assigns fit scores.
4. Tailoring creates customized resume artifacts.
5. Cover-letter and PDF stages create uploadable files.
6. Auto-apply claims eligible jobs, launches isolated Chrome workers, delegates form filling to Claude or Codex CLI, parses the result, and updates the row.

Evidence: `README.md:9-16`, `src/applypilot/pipeline.py:35-44`, `src/applypilot/database.py:68-76`, `src/applypilot/apply/launcher.py:602-731`.

## Important Discoveries

- The package entry point is declared in `pyproject.toml:34-35` and routes to `applypilot.cli:app`.
- CLI startup bootstraps env, directories, and DB through `_bootstrap()` in `src/applypilot/cli.py:38-45`.
- The pipeline is explicitly ordered in `src/applypilot/pipeline.py:35-44`.
- SQLite is treated as a stage-progress ledger. The schema columns map directly to stage outputs in `src/applypilot/database.py:90-133`.
- Streaming mode uses threads plus DB polling, not a message queue. See `_StageTracker` and `_PENDING_SQL` in `src/applypilot/pipeline.py:196-255`.
- Stage 6 has a real agent abstraction: dataclasses and a Protocol in `src/applypilot/apply/agents/base.py:10-36`.
- Claude and Codex differ at the process boundary but return the same `AgentRunResult`, shown in `src/applypilot/apply/agents/claude_runner.py:141-149` and `src/applypilot/apply/agents/codex_runner.py:137-145`.
- Tests focus heavily on new Stage 6 and config behavior: `tests/test_apply_launcher.py:17-122`, `tests/test_agent_parsing.py:4-24`, `tests/test_config_normalization.py:8-109`.

## Why These Files Were Chosen As Anchors

`cli.py` is the front door. If you do not understand its commands, you cannot predict how a user invokes the system.

`pipeline.py` is the orchestration center. It shows the product's six-stage model and the difference between sequential and streaming execution.

`database.py` is the state contract. Most features eventually read or update `jobs`.

`apply/launcher.py` is the most senior-level file. It mixes transactions, worker loops, process management, browser lifecycle, prompt building, fallback behavior, and durable status updates.

`apply/agents/*` shows a clean boundary: backend-specific process code is hidden behind a shared result model.

`config.py` matters because this app depends on local profile data, search YAML, env vars, Chrome, and optional external CLIs.

## Where A Junior Might Get Confused

- They may look for a web server or API routes because the product uses browser automation. There are no HTTP controllers in the app itself.
- They may confuse `description`, `full_description`, and `application_url`. These columns represent different pipeline maturity levels in `src/applypilot/database.py:91-133`.
- They may see `run_pipeline()` and miss that each stage runner imports its implementation lazily in `src/applypilot/pipeline.py:62-165`.
- They may see tests using `monkeypatch` and not understand that they are replacing paths and dependencies to avoid touching real user data, as in `tests/test_apply_launcher.py:8-14`.

## Where A Mid-Level Engineer Should Slow Down

- Transaction boundaries in `acquire_job()` matter. `BEGIN IMMEDIATE` plus `apply_status = 'in_progress'` prevents workers from claiming the same row, but only inside SQLite's limits. See `src/applypilot/apply/launcher.py:186-271`.
- Streaming mode uses polling and threads. It is simpler than a queue, but error propagation and idempotency need careful thought. See `src/applypilot/pipeline.py:258-317`.
- LLM outputs are treated as untrusted text and normalized through parsers and validators. See `src/applypilot/apply/agents/parsing.py:35-87` and `src/applypilot/scoring/validator.py:93-165`.

## Where A Senior Engineer Should Be Skeptical

- `CodexRunner` launches `codex exec` with `--dangerously-bypass-approvals-and-sandbox` in `src/applypilot/apply/agents/codex_runner.py:63-74`. This may be acceptable for local automation but deserves very explicit user trust boundaries.
- Some SQL is assembled dynamically. Most values are parameterized, but review every f-string SQL site carefully, for example `src/applypilot/apply/launcher.py:212-238` and `src/applypilot/enrichment/detail.py:815-820`.
- Profile data includes sensitive personal fields in `src/applypilot/config.py:36-80`, and prompts can include that data. Logging and artifact paths must be reviewed with privacy in mind.
- The repo has many modified files in the working tree at inspection time. I did not treat those as safe to revert or normalize.

## Missing Or Weak Patterns

- No centralized ORM or migration tool. SQLite schema migration is custom and additive only: `src/applypilot/database.py:186-219`.
- No web API/auth layer exists, so REST/GraphQL/auth learning has to be framed as an absence.
- Tests exist, but many high-risk external paths are difficult to cover without integration fixtures.
- Generated HTML dashboard uses string assembly rather than templates: `src/applypilot/view.py:25-115` and `src/applypilot/view.py:391-407`.
- Secrets and profile data are local files, so operational security depends heavily on file-system discipline.

## How To Use Checkpoints

For each checkpoint, answer from memory first. Then cite the relevant file. Then say what could go wrong if that part failed. That third step is where junior reading starts becoming engineering judgment.
