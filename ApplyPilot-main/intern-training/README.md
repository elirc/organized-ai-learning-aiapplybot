# Intern Training Pack

> **Read this first:** the eleven walkthroughs in this folder are
> byte-identical copies of files in [`code-explained/`](../code-explained/),
> which is the canonical, larger set (it adds `05_agents_base.md`,
> `12_llm.md`, `13_jobspy.md`, `14_scorer.md` and `15_tailor.md`).
> Use `code-explained/` so you only ever read one version; this folder is
> kept for link stability. The one thing that exists only here is the
> suggested reading order below.

## Suggested reading order (maps into `code-explained/`)

1. `code-explained/00_SYSTEM_DESIGN.md` — how the six stages fit together
2. `code-explained/01_cli.md` → `src/applypilot/cli.py`
3. `code-explained/11_config.md` → `src/applypilot/config.py`
4. `code-explained/02_database.md` → `src/applypilot/database.py`
5. `code-explained/03_pipeline.md` → `src/applypilot/pipeline.py`
6. `code-explained/04_launcher.md` → `src/applypilot/apply/launcher.py`
7. `code-explained/10_chrome.md` → `src/applypilot/apply/chrome.py`
8. `code-explained/09_prompt.md` → `src/applypilot/apply/prompt.py`
9. `code-explained/06_agents_parsing.md` → `src/applypilot/apply/agents/parsing.py`
10. `code-explained/07_claude_runner.md` → `src/applypilot/apply/agents/claude_runner.py`
11. `code-explained/08_codex_runner.md` → `src/applypilot/apply/agents/codex_runner.py`

These ten files were picked (of 25 implementation files under
`src/applypilot/`, ignoring `__init__.py`) for orchestration importance,
dependency centrality, and failure surface — the places where bugs are
most expensive. After them, the remaining `code-explained/` files cover
the LLM client, discovery, scoring and tailoring stages.

When you finish reading, continue with the exercises at the end of
[`ARCHITECTURE.md`](../ARCHITECTURE.md).
