# Production Review

## Goal

Move the codebase closer to a production-ready state for unattended job application runs, with special attention to configuration correctness, Stage-6 apply reliability, and test coverage.

## Review Findings

### Fixed in this pass

1. Profile contract drift
The setup wizard was writing a profile shape that did not match what the prompt builder and auto-apply logic expected. That meant important fields like work authorization, sponsorship, EEO data, and current role could silently degrade to fallback values.

2. Search-config contract drift
`searches.yaml` examples and wizard output used keys like `boards`, `country`, and nested `location.accept_patterns`, while discovery code expected `sites`, `defaults.country_indeed`, and flat location lists. That made discovery behavior inconsistent across fresh setups.

3. Targeted apply bug
`acquire_job(target_url=...)` excluded rows with `NULL` `apply_status`, which prevented `--url` and `--gen` from reliably selecting unattempted jobs.

4. Parallel worker race on upload files
Prompt generation copied resumes and cover letters into a shared `apply-workers/current` directory. Multiple workers could overwrite one another's upload files mid-run.

5. Cover-letter PDF generation used the wrong renderer
Cover letters were being rendered through the resume formatter, producing the wrong output structure for uploaded documents.

6. LLM provider detection was static at import time
LLM environment variables were captured once when the module imported, which made testability worse and could lead to stale provider selection if env loading order changed.

7. Tier detection lagged behind supported Stage-6 backends
The setup and tier system treated Claude as the only Stage-6 backend, even though the repo supports Codex too.

8. Thin unit coverage around production-critical seams
The existing tests mostly covered result parsing and optional integration runners, but not config normalization, targeted apply acquisition, cover-letter PDF behavior, or dynamic LLM setup.

9. Manual-only ATS queue stall
If the top queued job routed through a manual-only ATS, the worker could mark it as manual and then stop as if the queue were empty, leaving other valid jobs untouched.

10. Multi-worker limit distribution bug
When `max_applies` or `limit` was smaller than the worker count, extra workers received `limit=0`, interpreted that as continuous mode, and could poll forever.

11. Targeted apply concurrency risk
Running `--url` with multiple workers offered no upside and created duplicate-claim risk, so targeted runs now collapse to a single worker.

12. Hard import on optional JobSpy dependency
The JobSpy discovery module imported `jobspy` at module import time. If that package was missing, the module crashed immediately instead of failing with a useful runtime message.

13. SQLite compatibility edge
One query path used `NULLS LAST`, which is not the safest cross-version SQLite choice for production environments.

### Remaining important work

1. Add a true end-to-end dry-run harness
Mocking the external CLIs is good, but the next production step is a repeatable local harness that exercises `applypilot apply --dry-run` against a fake ATS flow and verifies DB state transitions.

2. Add discovery/enrichment smoke tests
The discovery stack still depends on multiple external boards and scraping heuristics. A small fixture-based smoke suite would catch schema drift earlier.

3. Tighten packaging for optional discovery dependencies
The repo still relies on extra installation steps for JobSpy-related tooling. That is workable, but it is not ideal for reproducible deployment.

4. Expand operational safeguards
A production deployment should eventually add stronger secrets handling, richer audit logging, safer defaults for domain allowlisting, and resumable per-job run artifacts.

## Implemented Changes

### Runtime contracts

- Added profile normalization in `src/applypilot/config.py` so older wizard output and hand-written profiles are upgraded to the shape expected by the runtime.
- Added search-config normalization in `src/applypilot/config.py` so `boards`, `country`, and nested location filters map cleanly onto discovery expectations.
- Updated tier detection to treat either Claude or Codex as a valid Stage-6 backend when Chrome is present.

### Apply reliability

- Fixed targeted job acquisition in `src/applypilot/apply/launcher.py` so jobs with no prior apply status can still be selected with `--url`.
- Updated `src/applypilot/apply/prompt.py` and `src/applypilot/apply/launcher.py` so each worker uses its own upload workspace instead of a shared directory.
- Fixed queue acquisition in `src/applypilot/apply/launcher.py` so manual-only ATS jobs are marked and skipped without stopping the rest of the run.
- Fixed worker scheduling in `src/applypilot/apply/launcher.py` so zero-share workers do not enter unintended continuous mode.
- Added a single-worker safeguard for targeted `--url` runs.

### Document generation

- Reworked `src/applypilot/scoring/pdf.py` to keep resume rendering separate from cover-letter rendering.
- Updated `src/applypilot/scoring/cover_letter.py` to prefer the tailored resume text for letter generation and to use the dedicated cover-letter PDF renderer.

### Setup flow

- Rebuilt `src/applypilot/wizard/init.py` so new setups collect data in the shape the runtime actually consumes.
- Updated the wizard to recognize both Claude and Codex as supported auto-apply backends.

### Discovery and diagnostics

- Made `src/applypilot/discovery/jobspy.py` import `python-jobspy` lazily and fail with an actionable error message instead of a hard module import crash.
- Improved `applypilot doctor` to report Python Playwright package availability and `python-jobspy` presence.
- Replaced the `NULLS LAST` ordering pattern in `src/applypilot/database.py` with a more SQLite-compatible ordering expression.
- Fixed a small dashboard filtering bug in `src/applypilot/view.py` so score filters do not depend on a browser-global `event` object.

### Codebase hygiene

- Cleaned repo-wide dead imports, dead locals, and no-op f-strings so the full repository now passes `ruff check .`, not just targeted file linting.

### Testing

Added unit tests for:

- legacy profile normalization
- search-config alias normalization
- Codex-aware tier detection
- dynamic LLM provider detection
- targeted apply acquisition for unattempted jobs
- manual ATS skip-through behavior in the apply queue
- zero-limit worker exit behavior
- cover-letter HTML/PDF generation path
- batch conversion skipping cover-letter files
- lazy JobSpy dependency failure reporting

## Verification

Executed locally in a fresh `.venv`:

- `python -m compileall src tests`
- `.venv\Scripts\python.exe -m pip install -e .[dev]`
- `.venv\Scripts\python.exe -m pytest -q`
- `.venv\Scripts\python.exe -m applypilot --help`
- `.venv\Scripts\python.exe -m applypilot doctor`
- `.venv\Scripts\ruff.exe check .`

Result:

- 17 tests passed
- CLI help loaded successfully
- `applypilot doctor` reported the expected environment state
- full-repo lint passed

## Recommended Next Step

Before using unattended real submissions at scale, run:

1. `applypilot init`
2. `applypilot doctor`
3. `applypilot run discover enrich score tailor cover pdf`
4. `applypilot apply --agent auto --dry-run --workers 1 --domain-allowlist "your-approved-domains"`

Then inspect generated logs under `~/.applypilot/logs/` and confirm file uploads, prompt output, and final DB transitions match expectations.
