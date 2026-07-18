# Intern Training Pack

This folder contains training docs for the **top 40% most important core code files** in the project.

## Selection Method

- Total core Python implementation files considered: `25` (`src/applypilot/**/*.py`, excluding `__init__.py` files).
- Target requested by you: top `30-40%`.
- Selected for this pack: `10` files (`40%`) + `1` system architecture overview.

Selection criteria:

1. Runtime control/orchestration importance
2. Cross-file dependency centrality
3. Failure surface area (where bugs are most expensive)
4. New Stage-6 dual-agent complexity (Claude + Codex)

## Included File Walkthroughs

Each walkthrough explains:

- What the file is responsible for
- How key functions/classes work
- Line-by-line explanation of the **most important 20-30% of code paths**
- Common edge cases and junior-level gotchas

### 1) CLI and orchestration entrypoints

- `01_cli.py.md` -> `src/applypilot/cli.py`
- `03_pipeline.py.md` -> `src/applypilot/pipeline.py`
- `02_database.py.md` -> `src/applypilot/database.py`
- `10_config.py.md` -> `src/applypilot/config.py`

### 2) Stage 6 auto-apply core

- `04_apply_launcher.py.md` -> `src/applypilot/apply/launcher.py`
- `08_apply_prompt.py.md` -> `src/applypilot/apply/prompt.py`
- `09_apply_chrome.py.md` -> `src/applypilot/apply/chrome.py`

### 3) Stage 6 backend abstraction

- `05_agents_parsing.py.md` -> `src/applypilot/apply/agents/parsing.py`
- `06_agents_claude_runner.py.md` -> `src/applypilot/apply/agents/claude_runner.py`
- `07_agents_codex_runner.py.md` -> `src/applypilot/apply/agents/codex_runner.py`

## System Architecture Summary

- `00_SYSTEM_ARCHITECTURE.md`

This file explains how all major modules fit together and how data flows end-to-end.

## Suggested Reading Order for an Intern

1. `00_SYSTEM_ARCHITECTURE.md`
2. `01_cli.py.md`
3. `10_config.py.md`
4. `02_database.py.md`
5. `03_pipeline.py.md`
6. `04_apply_launcher.py.md`
7. `09_apply_chrome.py.md`
8. `08_apply_prompt.py.md`
9. `05_agents_parsing.py.md`
10. `06_agents_claude_runner.py.md`
11. `07_agents_codex_runner.py.md`
