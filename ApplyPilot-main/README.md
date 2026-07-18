# ApplyBot (ApplyPilot Stage-6 Refactor)

ApplyBot is a production-oriented fork of ApplyPilot that keeps the original 6-stage job pipeline and significantly upgrades Stage 6 (Auto-Apply) so you can run autonomous applications with either:

- Claude Code CLI (subscription)
- OpenAI Codex CLI (subscription)
- Automatic fallback mode (`--agent auto`): Claude first, then Codex

The project supports end-to-end job workflows:

1. Discover jobs
2. Enrich job details
3. Score fit with AI
4. Tailor resume per role
5. Generate cover letter
6. Auto-apply with browser automation + MCP

## What Is New In This Fork

The core Stage-6 changes implemented in this repository:

- New agent backend abstraction in `src/applypilot/apply/agents/`
- Dual backend support (`claude` and `codex`) with shared prompt + shared browser tooling model
- `--agent claude|codex|auto` selection
- Codex non-interactive execution via `codex exec --json`
- Per-worker Codex MCP configuration via `.codex/config.toml`
- Robust outcome parsing:
  - `RESULT: ...` line parsing
  - JSON object parsing fallback
- Safety/controls:
  - `--dry-run`
  - `--domain-allowlist`
  - `--max-applies`
  - `--min-delay-seconds`
  - Gmail MCP disabled by default (`--enable-gmail` to opt in)
- New diagnostics command: `applypilot doctor`
- Integration fixture tests for local form automation

---

## Table of Contents

- [1) Prerequisites](#1-prerequisites)
- [2) Installation](#2-installation)
- [3) First-Time Setup](#3-first-time-setup)
- [4) Verify Environment](#4-verify-environment)
- [5) Run Stages 1-5](#5-run-stages-1-5)
- [6) Run Stage 6 Auto-Apply](#6-run-stage-6-auto-apply)
- [7) CLI Reference (Auto-Apply)](#7-cli-reference-auto-apply)
- [8) Logs, Outputs, and Runtime Files](#8-logs-outputs-and-runtime-files)
- [9) Testing](#9-testing)
- [10) Troubleshooting](#10-troubleshooting)
- [11) Security and Safety Notes](#11-security-and-safety-notes)

---

## 1) Prerequisites

### Required

- Python 3.11+
- Node.js 18+ (for `npx` MCP server execution)
- Chrome/Chromium
- An LLM setup for stages 3-5:
  - `GEMINI_API_KEY` (most common in this codebase), or
  - `OPENAI_API_KEY`, or
  - custom `LLM_URL`

### Required for Stage 6 (Auto-Apply)

At least one of:

- Claude Code CLI (`claude`)
- Codex CLI (`codex`) with authenticated subscription login

### Optional

- `CAPSOLVER_API_KEY` for CAPTCHA solving workflows
- Gmail MCP (enabled only when `--enable-gmail` is passed)

---

## 2) Installation

From repo root:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -U pip
pip install -e .

# JobSpy install pattern used by this project:
pip install --no-deps python-jobspy
pip install pydantic tls-client requests markdownify regex
```

If you will run Stage 6, confirm these are available in PATH:

```bash
claude --version
codex --version
node --version
npx --version
```

---

## 3) First-Time Setup

Run the setup wizard:

```bash
applypilot init
```

This creates user data in `~/.applypilot` (or `APPLYPILOT_DIR` if set), including:

- `profile.json`
- `searches.yaml`
- `.env`
- local SQLite DB

Then run core pipeline stages:

```bash
applypilot run
```

Or specific stages:

```bash
applypilot run discover enrich
applypilot run score tailor cover pdf
```

---

## 4) Verify Environment

Use the diagnostic command:

```bash
applypilot doctor
```

`doctor` reports:

- Claude CLI present/missing
- Codex CLI present/missing
- Chrome present/missing
- Codex trust guidance for project MCP config usage

If Codex indicates the project is not trusted, follow the printed trust instructions and rerun `doctor`.

---

## 5) Run Stages 1-5

Typical workflow:

```bash
# Discover/enrich/score/tailor/cover/pdf
applypilot run

# View pipeline counts
applypilot status

# Open HTML dashboard
applypilot dashboard
```

---

## 6) Run Stage 6 Auto-Apply

### A) Claude backend

```bash
applypilot apply --agent claude --claude-model haiku --dry-run
```

### B) Codex backend

```bash
applypilot apply --agent codex --codex-model gpt-5.3-codex --dry-run
```

### C) Auto fallback backend

```bash
applypilot apply --agent auto --dry-run
```

Behavior in `auto` mode:

1. Try Claude runner
2. If Claude missing/fails/returns no reliable parse, try Codex
3. If both fail, mark job as `needs_review`-style failure reason

### D) Real submission mode

Remove `--dry-run` when ready:

```bash
applypilot apply --agent auto --workers 2 --max-applies 25 --min-delay-seconds 10
```

### E) Domain safety

Restrict where submissions are allowed:

```bash
applypilot apply --agent codex --domain-allowlist "greenhouse.io,boards.greenhouse.io"
```

If agent navigates outside allowlist, run halts for that job with review/failure reason.

### F) Gmail MCP (opt-in only)

Default is disabled for safety.

```bash
applypilot apply --agent claude --enable-gmail
```

---

## 7) CLI Reference (Auto-Apply)

Command:

```bash
applypilot apply [OPTIONS]
```

High-value options:

- `--agent claude|codex|auto`
- `--claude-model TEXT`
- `--codex-model TEXT`
- `--dry-run`
- `--enable-gmail`
- `--domain-allowlist A,B,C`
- `--max-applies INTEGER` (default `25`)
- `--min-delay-seconds INTEGER` (default `10`)
- `--workers INTEGER`
- `--continuous`
- `--headless`
- `--url TEXT` (target one job)
- Utility modes:
  - `--mark-applied URL`
  - `--mark-failed URL`
  - `--fail-reason TEXT`
  - `--reset-failed`
  - `--gen --url URL`

Notes:

- `--model` is retained as deprecated alias for `--claude-model` compatibility.
- Gmail MCP tools are disabled unless explicitly enabled.

---

## 8) Logs, Outputs, and Runtime Files

By default, runtime files live under `~/.applypilot`.

Important paths:

- Logs: `~/.applypilot/logs/`
- Worker browser data: `~/.applypilot/chrome-workers/`
- Apply worker dirs: `~/.applypilot/apply-workers/`
- Claude MCP config per worker: `~/.applypilot/.mcp-apply-<worker>.json`
- Codex project MCP config per worker: `<worker_dir>/.codex/config.toml`

Per-job run artifacts include:

- raw runner logs (`agent_claude_...log`, `agent_codex_...log`)
- Codex event JSONL (`agent_codex_...jsonl`) when `--json` stream is active

---

## 9) Testing

### Unit parser tests

```bash
python -m pytest tests/test_agent_parsing.py -q
```

### Integration tests

```bash
python -m pytest -m integration -q
```

Integration tests include:

- Local static multi-step form fixture
- Local HTTP server
- Chrome CDP launch
- Backend runner invocation in dry-run mode

If `claude`, `codex`, `npx`, or Chrome is unavailable, tests skip with explicit messages.

---

## 10) Troubleshooting

### `Codex CLI not found`

Install Codex CLI and authenticate:

```bash
codex login
```

Then rerun:

```bash
applypilot doctor
```

### `Claude CLI not found`

Install from:

- https://claude.ai/code

### Chrome not detected

Set `CHROME_PATH` in your environment or install Chrome/Chromium.

### Codex MCP not loading

- Confirm project trust (use `applypilot doctor` guidance)
- Ensure worker `.codex/config.toml` exists during run

### No jobs are applied

Check:

- Tailored resume availability (`applypilot run score tailor`)
- `--min-score` threshold
- `--domain-allowlist` not overly restrictive
- worker logs in `~/.applypilot/logs/`

---

## 11) Security and Safety Notes

- Use `--dry-run` first on any new setup.
- Keep Gmail MCP disabled unless you explicitly need email verification assistance.
- Keep a strict `--domain-allowlist` in production runs.
- Use conservative `--max-applies` and non-zero `--min-delay-seconds` to avoid aggressive behavior.
- Review logs regularly to catch site changes and parser drift.

---

## Architecture Document

A separate deep-dive architecture guide for junior engineers is included at:

- `ARCHITECTURE.md`
- `PRODUCTION_REVIEW.md`

These documents cover system design, data flow, Stage-6 backend abstraction, production-hardening changes, failure handling, and extension patterns.
