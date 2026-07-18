# Senior Engineer Guide

## Architectural Critique

| Area | Score | Rationale |
| --- | ---: | --- |
| Scalability | 3 | Good for local single-machine automation. SQLite plus threads is simple, but not distributed. See `src/applypilot/database.py:15-49` and `src/applypilot/pipeline.py:376-436`. |
| Type discipline | 3 | Helpful dataclasses and Protocols exist, but many job rows are untyped dicts. See `src/applypilot/apply/agents/base.py:10-36` and `src/applypilot/apply/launcher.py:416-428`. |
| Separation of concerns | 4 | CLI, config, DB, pipeline, scoring, and agent runners are mostly separated. `run_job()` still carries many responsibilities. |
| Testability | 3 | Pytest covers parsing, config, launcher selection, and PDFs. External browser/LLM paths are harder to test. |
| Maintainability | 3 | The stage model is clear; some large modules such as `smartextract.py` and `launcher.py` need careful ownership. |
| Security posture | 2 | There are meaningful guardrails, but local personal data, browser automation, CAPTCHA, and bypassed agent sandboxing are high-risk. |
| Performance | 3 | Threading and retry patterns exist. Polling, sequential LLM stages, and browser startup per job are natural bottlenecks. |
| Developer experience | 4 | README setup, `doctor`, pytest tests, and clear stage names help. |

## Performance Audit

Finding 1: Browser startup per job is expensive. `worker_loop()` launches Chrome for each acquired job in `src/applypilot/apply/launcher.py:671-675` and cleans it up in `src/applypilot/apply/launcher.py:719-721`.

Suggested direction:

```python
# Documentation-only sketch.
# Keep a browser per worker for a bounded batch, but reset context per job.
chrome_proc = launch_chrome(worker_id, port=port, headless=headless)
try:
    while has_work:
        run_job(...)
finally:
    cleanup_worker(worker_id, chrome_proc)
```

Trade-off: reusing Chrome improves throughput but increases session leakage risk. Because job applications contain personal data, safety may be worth the slower startup.

Finding 2: Scoring is sequential. `run_scoring()` loops one job at a time in `src/applypilot/scoring/scorer.py:139-161`. Parallel LLM calls could improve throughput but would need rate-limit controls.

Finding 3: Streaming mode polls every 10 seconds in `src/applypilot/pipeline.py:243-255`. This is simple but may lag. Fine for local use.

## Security Audit

Finding 1: Codex runner bypasses approvals and sandbox.

```python
# src/applypilot/apply/agents/codex_runner.py:63-74
cmd = [
    "codex",
    "exec",
    "--json",
    "--skip-git-repo-check",
    "--dangerously-bypass-approvals-and-sandbox",
]
```

Suggested corrected snippet:

```python
# Documentation-only sketch.
if not explicit_trust_confirmed:
    raise RuntimeError("Codex sandbox bypass requires explicit user trust.")
```

The app already has `doctor` trust guidance in `src/applypilot/cli.py:334-359`, but the risk deserves runtime visibility too.

Finding 2: Prompt contains personal data and CAPTCHA key material. `_build_captcha_section()` inserts `CAPSOLVER_API_KEY` into prompt text in `src/applypilot/apply/prompt.py:216-235`. Logs should be reviewed to ensure prompt contents are not written wholesale.

Finding 3: Domain allowlist is optional. `run_job()` enforces it only when passed in `src/applypilot/apply/launcher.py:430-433` and `src/applypilot/apply/prompt.py:534-544`.

Suggested policy: default to a configured allowlist for real submissions, or require explicit confirmation when no allowlist is provided.

## Type Discipline Review

Strong:

- `ParsedOutcome` and `AgentRunResult` make process outputs explicit: `src/applypilot/apply/agents/base.py:10-29`.
- CLI agent selection uses `Literal` in `src/applypilot/cli.py:133`.

Weak:

- `job: dict` appears across critical flows. A `TypedDict` could document expected columns for `run_job()`, `score_job()`, and `tailor_resume()`.
- Stage runner return values are loose `dict`s in `src/applypilot/pipeline.py:62-165`.

## Custom Abstractions Inventory

- Stage registry: `_STAGE_RUNNERS` in `src/applypilot/pipeline.py:157-165`.
- Stage tracker: `_StageTracker` in `src/applypilot/pipeline.py:196-219`.
- DB schema registry: `_ALL_COLUMNS` in `src/applypilot/database.py:143-183`.
- Agent backend contract: `AgentRunner` in `src/applypilot/apply/agents/base.py:32-36`.
- Agent result parser: `parse_agent_result()` in `src/applypilot/apply/agents/parsing.py:74-87`.
- Config normalization: `_normalize_profile()` and `_normalize_search_config()` in `src/applypilot/config.py:129-238`.

## Testing Assessment

Good coverage anchors:

- Result parsing: `tests/test_agent_parsing.py:4-24`.
- Job claiming and manual ATS skip: `tests/test_apply_launcher.py:17-122`.
- Config compatibility: `tests/test_config_normalization.py:8-109`.
- LLM provider detection: `tests/test_llm.py`.
- JobSpy missing dependency behavior: `tests/test_jobspy_discovery.py`.

Gaps:

- No broad unit tests for `run_job()` auto fallback.
- Limited tests around domain allowlist behavior.
- External browser and agent tests are integration-only and skip when local tools are absent.

## Example Test For Risky Untested Behavior

Do not add this directly without checking current test style.

```python
def test_run_job_blocks_domain_before_prompt_or_agent(monkeypatch, tmp_path):
    from applypilot.apply import launcher

    called = {"prompt": False}

    def fail_build_prompt(*args, **kwargs):
        called["prompt"] = True
        raise AssertionError("prompt should not be built for blocked domains")

    monkeypatch.setattr(launcher.prompt_mod, "build_prompt", fail_build_prompt)

    job = {
        "url": "https://safe.example/job",
        "application_url": "https://evil.example/apply",
        "title": "Engineer",
        "site": "Example",
        "tailored_resume_path": str(tmp_path / "resume.txt"),
    }

    result, duration = launcher.run_job(
        job,
        port=9222,
        domain_allowlist=["safe.example"],
    )

    assert result == "failed:domain_not_allowed:evil.example"
    assert duration == 0
    assert called["prompt"] is False
```

## Bug Injection Exercise

1. Symptom: two workers try the same job. Test scenario: seed two eligible jobs and run two acquire calls in parallel; assert unique URLs.
2. Symptom: dry-run permanently consumes a job. Test scenario: agent returns `DRY_RUN`; assert `apply_status` is released or retryable.
3. Symptom: Codex emits valid JSON plus warnings and parser ignores result. Test scenario: JSONL stream includes non-JSON warning lines and final event text.
4. Symptom: high-fit job never gets tailored. Test scenario: `fit_score >= 7`, `tailor_attempts < 5`, `full_description` present; assert `get_jobs_by_stage(... pending_tailor ...)` includes it.
5. Symptom: manual ATS job blocks queue progress. Test scenario: first row is manual ATS, second is valid; assert valid row is claimed. This is already covered in `tests/test_apply_launcher.py:54-108`.

## Git History Learning Exercise

The repo inspection found two visible commits:

- `1383292 Add intern training docs and code walkthrough materials`: implies this codebase has already been used for learning/onboarding.
- `ac7cbc5 Refactor auto-apply with Claude/Codex runners, guardrails, tests, and docs`: implies Stage 6 was recently refactored around backend abstraction and safety.

Realistic commit themes to study from the current code:

1. "Introduce agent runner Protocol": teaches boundary extraction.
2. "Add Codex JSON output parsing": teaches external process normalization.
3. "Add manual ATS skip logic": teaches product safety.
4. "Normalize legacy config": teaches backward compatibility.
5. "Add integration fixture for local form": teaches testing browser automation without hitting real sites.

## If I Owned This Codebase

| Item | Effort | Impact | Risk | Why It Matters |
| --- | --- | --- | --- | --- |
| Add `TypedDict`/dataclass for job rows | M | High | Low | Makes critical dict contracts explicit. |
| Add domain allowlist tests | S | High | Low | Protects Stage 6 safety behavior. |
| Add structured logging/redaction review | M | High | Medium | Personal data and secrets flow through prompts. |
| Split `run_job()` into smaller services | M | Medium | Medium | Easier tests and safer backend additions. |
| Add migration metadata table | M | Medium | Medium | Current additive migration is simple but opaque. |
| Template generated HTML dashboard | M | Medium | Low | Improves maintainability of `view.py`. |
| Add more integration fixtures for apply failures | L | High | Medium | Catches real browser/agent regressions. |
