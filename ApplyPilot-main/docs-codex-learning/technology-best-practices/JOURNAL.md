# Technology Journal

## Technologies Identified

- Python package metadata and console scripts in `pyproject.toml:1-54`.
- Typer CLI in `src/applypilot/cli.py:22-220`.
- Rich tables/panels in `src/applypilot/cli.py:315-332`, `src/applypilot/apply/dashboard.py:109-190`.
- SQLite via `sqlite3` in `src/applypilot/database.py:20-219`.
- YAML/dotenv config in `src/applypilot/config.py:319-394`.
- Playwright in enrichment/PDF/apply flows: `src/applypilot/enrichment/detail.py:633-639`, `src/applypilot/scoring/pdf.py:345-350`, MCP setup in `src/applypilot/apply/launcher.py:66-115`.
- httpx LLM client in `src/applypilot/llm.py:60-126`.
- subprocess runners in `src/applypilot/apply/agents/claude_runner.py:48-149` and `src/applypilot/apply/agents/codex_runner.py:58-145`.
- pytest tests in `tests/test_agent_parsing.py`, `tests/test_apply_launcher.py`, and `tests/test_config_normalization.py`.

## Prioritization

Highest priority:

1. SQLite state model.
2. CLI command flow.
3. Apply launcher and agent runner contract.
4. Config normalization.
5. pytest patterns.

These are highest priority because most real changes will touch them.

## Strong Patterns

- Stage vocabulary is centralized: `src/applypilot/pipeline.py:35-44`.
- DB schema is idempotent and additive: `src/applypilot/database.py:62-219`.
- Agent runner outputs are normalized: `src/applypilot/apply/agents/base.py:10-36`.
- Config compatibility is tested: `tests/test_config_normalization.py:8-109`.

## Weak Or Inconsistent Patterns

- Critical job rows are mostly `dict`, not typed records.
- Generated HTML dashboard is string-built in `src/applypilot/view.py`.
- Some modules are very large and mix several responsibilities.
- Security posture depends heavily on local trust and user discipline.

## What Junior Developers Might Misunderstand

- The browser automation does not mean this is a web app.
- SQLite is not just storage; it is workflow state.
- The prompt builder is business logic because it controls safety behavior.
- Tests that monkeypatch paths are protecting real user files.

## What Mid-Level Or Senior Engineers Should Notice

- `BEGIN IMMEDIATE` in `acquire_job()` is a concurrency decision.
- `--dangerously-bypass-approvals-and-sandbox` is a serious trust decision.
- Parser fallbacks are a safety feature, not just convenience.
- The absence of REST/auth/ORM is acceptable for local CLI scope but would change in a hosted product.
