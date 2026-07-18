# Technology Map

## Python Packaging

**Role in This Project:** Defines installable package metadata, dependencies, optional dev tools, build backend, and console script.

**Where It Appears:** `pyproject.toml:1-54`.

**Why It Matters:** If packaging breaks, `applypilot` cannot be installed or invoked reliably.

**What to Study First:** `pyproject.toml:20-35`, `src/applypilot/__main__.py:1-5`.

**Related Technologies:** Typer, pytest, hatchling.

**Learning Priority:** High, because it explains how the CLI starts.

## Typer

**Role in This Project:** Exposes user commands: `init`, `run`, `apply`, `doctor`, `status`, `dashboard`.

**Where It Appears:** `src/applypilot/cli.py`.

**Why It Matters:** Most user stories begin at the CLI boundary.

**What to Study First:** `src/applypilot/cli.py:22-45`, `src/applypilot/cli.py:78-124`, `src/applypilot/cli.py:127-220`.

**Related Technologies:** Rich, config, pipeline, apply launcher.

**Learning Priority:** High.

## SQLite

**Role in This Project:** Stores job rows, stage progress, retry state, apply outcomes, and dashboard stats.

**Where It Appears:** `src/applypilot/database.py`, plus SQL in stage modules.

**Why It Matters:** It is the durable state machine.

**What to Study First:** `src/applypilot/database.py:20-49`, `src/applypilot/database.py:90-133`, `src/applypilot/database.py:365-427`.

**Related Technologies:** pipeline, apply launcher, dashboard, tests.

**Learning Priority:** High.

## Pipeline Orchestration

**Role in This Project:** Coordinates six stages sequentially or concurrently.

**Where It Appears:** `src/applypilot/pipeline.py`.

**Why It Matters:** It is the product workflow in code.

**What to Study First:** `src/applypilot/pipeline.py:35-55`, `src/applypilot/pipeline.py:62-165`, `src/applypilot/pipeline.py:376-480`.

**Related Technologies:** SQLite, discovery, enrichment, scoring, apply.

**Learning Priority:** High.

## Playwright And Browser Automation

**Role in This Project:** Scrapes detail pages, renders PDFs, and connects agents to Chrome via MCP/CDP.

**Where It Appears:** `src/applypilot/enrichment/detail.py`, `src/applypilot/scoring/pdf.py`, `src/applypilot/apply/chrome.py`, `src/applypilot/apply/launcher.py`.

**Why It Matters:** Browser automation is powerful, flaky, and safety-sensitive.

**What to Study First:** `src/applypilot/enrichment/detail.py:529-675`, `src/applypilot/apply/launcher.py:66-115`, `src/applypilot/apply/launcher.py:671-721`.

**Related Technologies:** subprocess, MCP, Chrome, tests.

**Learning Priority:** High for Stage 6 work, Medium otherwise.

## LLM Client And Prompting

**Role in This Project:** Scores jobs, tailors resumes, generates cover letters, and instructs apply agents.

**Where It Appears:** `src/applypilot/llm.py`, `src/applypilot/scoring/`, `src/applypilot/apply/prompt.py`.

**Why It Matters:** LLM output is untrusted and must be constrained.

**What to Study First:** `src/applypilot/llm.py:22-126`, `src/applypilot/scoring/scorer.py:72-100`, `src/applypilot/apply/prompt.py:419-565`.

**Related Technologies:** httpx, dotenv, validators, parser.

**Learning Priority:** High.

## pytest

**Role in This Project:** Tests parser, config normalization, DB/launcher behavior, PDF behavior, and optional integrations.

**Where It Appears:** `tests/`.

**Why It Matters:** Tests are how this repo makes Python's implicit contracts visible.

**What to Study First:** `tests/test_agent_parsing.py:4-24`, `tests/test_apply_launcher.py:8-122`, `tests/test_config_normalization.py:8-109`.

**Related Technologies:** monkeypatch, tmp_path, pytest markers.

**Learning Priority:** High.

## YAML And dotenv Configuration

**Role in This Project:** Loads user search preferences, site registries, env vars, and optional external service keys.

**Where It Appears:** `src/applypilot/config.py`, `src/applypilot/config/*.yaml`, `.env.example`.

**Why It Matters:** Most runtime behavior depends on local config.

**What to Study First:** `src/applypilot/config.py:129-238`, `src/applypilot/config.py:319-394`.

**Related Technologies:** wizard, discovery, apply prompt.

**Learning Priority:** Medium-High.

## subprocess Agent Runners

**Role in This Project:** Runs Claude and Codex CLIs as external processes and normalizes their output.

**Where It Appears:** `src/applypilot/apply/agents/claude_runner.py`, `src/applypilot/apply/agents/codex_runner.py`.

**Why It Matters:** This is a high-risk boundary between local code and autonomous CLI agents.

**What to Study First:** `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/apply/agents/claude_runner.py:48-149`, `src/applypilot/apply/agents/codex_runner.py:58-145`.

**Related Technologies:** parser, prompt, MCP config, logs.

**Learning Priority:** High for Stage 6 work.
