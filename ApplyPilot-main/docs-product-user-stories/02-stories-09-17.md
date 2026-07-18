# Stories 9-17

## Story 9: Add Source Quality Summary To Dashboard

**Difficulty:** Medium

**Estimated Time:** 4 hours

**User Story:** As a job seeker, I want the dashboard to summarize which job sources produce the most high-fit roles so that I can tune my search strategy.

**Product Value:** Discovery quality matters more than raw volume. This helps users focus on sources that produce useful jobs.

**Acceptance Criteria:**
- [ ] Dashboard includes a source summary section.
- [ ] Summary shows total jobs, high-fit jobs, unscored jobs, and average score by source.
- [ ] Uses existing `jobs.site` and `jobs.fit_score`.
- [ ] Does not require new database columns.

**Files You Will Likely Touch:**
- `src/applypilot/view.py`: dashboard SQL and HTML.

**Relevant Code To Study First:**
- `src/applypilot/view.py:62-72`
- `src/applypilot/view.py:110-115`
- `src/applypilot/database.py:91-133`

**Detailed Implementation Plan:**
1. Open `src/applypilot/view.py`.
2. Study existing `site_stats` query around `src/applypilot/view.py:62-72`.
3. Confirm whether it already calculates the needed fields.
4. If fields exist, improve the display rather than adding new SQL.
5. Add a clear section title like `Source Quality`.
6. Display count, high-fit count, unscored count, average score.
7. Use existing color map if appropriate.
8. Generate dashboard and inspect layout.

**Testing And Verification:**
- Manual dashboard inspection.
- Optional smoke test: generated HTML contains `Source Quality`.

**Tips:**
- Prefer reusing existing query output.
- Do not over-style; data should be scannable.
- Handle `site` being null.

**What Could Go Wrong:**
- Average score treats unscored jobs incorrectly.
- Long source names break layout.

**Review Checklist:**
- [ ] No duplicate query if existing query is enough.
- [ ] Null site handled.

**Connects To:** Story 23.

## Story 10: Add Apply Queue Preview

**Difficulty:** Medium

**Estimated Time:** 5 hours

**User Story:** As a cautious user, I want to preview jobs that auto-apply would attempt before launching browsers so that I can catch unsafe or unwanted applications.

**Product Value:** Preview reduces risk before a high-stakes automation action.

**Acceptance Criteria:**
- [ ] Preview lists eligible jobs without marking them `in_progress`.
- [ ] Preview respects `min_score`.
- [ ] Preview excludes blocked/manual ATS jobs where practical.
- [ ] Preview displays title, site, score, URL, and apply URL.
- [ ] Add a test proving preview is read-only.

**Files You Will Likely Touch:**
- `src/applypilot/apply/launcher.py`: add read-only eligibility helper.
- `src/applypilot/cli.py`: add `apply --preview` or a new command.
- `tests/test_apply_launcher.py`: DB read-only test.

**Relevant Code To Study First:**
- `src/applypilot/apply/launcher.py:174-271`
- `src/applypilot/cli.py:127-220`
- `tests/test_apply_launcher.py:8-122`

**Detailed Implementation Plan:**
1. Study `acquire_job()`. Do not copy it blindly.
2. Extract or create a helper like `preview_jobs(min_score, limit, target_url=None)`.
3. The helper should SELECT eligible rows but not UPDATE them.
4. Reuse blocked site/manual ATS logic as much as possible.
5. Add CLI option:
   - `preview: bool = typer.Option(False, "--preview", help="...")`
6. In `cli.apply()`, after basic bootstrap but before launching Chrome, call preview helper when `preview=True`.
7. Render a Rich table with title, site, score, URL.
8. Return without launching workers.
9. Add test:
   - seed eligible job
   - call preview helper
   - assert returned job exists
   - assert DB row `apply_status` remains null
10. Run `python -m pytest tests/test_apply_launcher.py -q`.

**Testing And Verification:**
- Unit test helper.
- Manual: `applypilot apply --preview --min-score 7`.

**Tips:**
- Preview must be read-only.
- Do not call `launch_chrome`.
- Do not call `acquire_job`.

**What Could Go Wrong:**
- Preview and real apply eligibility drift.
- Preview accidentally claims jobs.
- Preview hides manual ATS behavior incorrectly.

**Review Checklist:**
- [ ] Read-only test exists.
- [ ] No browser/agent side effects.

**Connects To:** Story 18.

## Story 11: Add Reset Failed By Reason

**Difficulty:** Medium

**Estimated Time:** 4 hours

**User Story:** As a user, I want to reset only failed jobs matching a reason so that I can retry temporary failures without retrying permanent failures.

**Product Value:** Users need controlled retry, especially when failures include both transient network errors and permanent blocked domains.

**Acceptance Criteria:**
- [ ] CLI supports resetting failed jobs by reason prefix.
- [ ] Example: reset only `codex_exit_1` or only `timeout`.
- [ ] Permanent failures are not reset unless explicitly requested.
- [ ] Test covers reason-filtered reset.

**Files You Will Likely Touch:**
- `src/applypilot/apply/launcher.py`: reset logic.
- `src/applypilot/cli.py`: CLI option.
- `tests/test_apply_launcher.py`: reset tests.

**Relevant Code To Study First:**
- `src/applypilot/apply/launcher.py:394-414`
- `src/applypilot/cli.py:149-177`
- `src/applypilot/apply/launcher.py:575-588`

**Detailed Implementation Plan:**
1. Open `reset_failed()` in `launcher.py`.
2. Add optional parameters:
   - `reason_prefix: str | None = None`
   - `include_permanent: bool = False`
3. Build SQL conditions:
   - base: `apply_status = 'failed'`
   - if prefix: `apply_error LIKE ?`
   - if not include permanent: avoid rows with `apply_attempts >= max_apply_attempts` or `99`
4. Keep parameterized SQL.
5. In `cli.apply()`, add options:
   - `--reset-failed-reason`
   - `--include-permanent`
6. Display count reset.
7. Test with three rows:
   - timeout
   - domain_not_allowed permanent
   - codex_exit
8. Assert only intended rows reset.

**Testing And Verification:**
- `python -m pytest tests/test_apply_launcher.py -q`.

**Tips:**
- Be careful with permanent failures.
- Keep old `--reset-failed` behavior backward compatible.
- Use `LIKE "prefix%"`, not raw string concatenation.

**What Could Go Wrong:**
- Permanent failures become retryable accidentally.
- SQL matches too broadly.

**Review Checklist:**
- [ ] Backward compatibility preserved.
- [ ] Permanent handling explicit.

**Connects To:** Story 19.

## Story 12: Add Domain Allowlist Presets In Search Config

**Difficulty:** Medium

**Estimated Time:** 5 hours

**User Story:** As a user, I want to define trusted application domains in my config so that I do not have to pass `--domain-allowlist` every time.

**Product Value:** Safety defaults should be easy to reuse.

**Acceptance Criteria:**
- [ ] Search config can include a domain allowlist.
- [ ] CLI `--domain-allowlist` overrides or extends config behavior according to a documented rule.
- [ ] Prompt builder receives the effective allowlist.
- [ ] Tests cover config normalization for allowlist.

**Files You Will Likely Touch:**
- `src/applypilot/config.py`: normalize config.
- `src/applypilot/cli.py`: compute effective allowlist.
- `src/applypilot/apply/launcher.py`: pass list through.
- `tests/test_config_normalization.py`: config test.

**Relevant Code To Study First:**
- `src/applypilot/config.py:209-238`
- `src/applypilot/cli.py:140-146`
- `src/applypilot/apply/launcher.py:416-568`
- `src/applypilot/apply/prompt.py:534-544`

**Detailed Implementation Plan:**
1. Decide config key name, such as `apply_domain_allowlist`.
2. Add default normalization in `_normalize_search_config()`.
3. Add test with a temporary `searches.yaml`.
4. In `cli.apply()`, load search config when apply starts.
5. Parse CLI allowlist into a list.
6. Define rule:
   - recommended: CLI list overrides config list when provided
   - config list used when CLI is absent
7. Pass effective list to launcher `main()` or worker options.
8. Ensure prompt builder still receives list.
9. Run config and launcher tests.

**Testing And Verification:**
- `python -m pytest tests/test_config_normalization.py tests/test_apply_launcher.py -q`.

**Tips:**
- Make precedence explicit in docs/help text.
- Strip whitespace and lowercase domains.
- Do not silently ignore invalid empty entries.

**What Could Go Wrong:**
- CLI and config allowlists combine unexpectedly.
- Empty config disables safety.

**Review Checklist:**
- [ ] Precedence documented.
- [ ] Test covers normalization.

**Connects To:** Story 18.

## Story 13: Add Profile Sanity Report

**Difficulty:** Medium

**Estimated Time:** 5 hours

**User Story:** As a user, I want a profile sanity report so that I can catch missing email, phone, work authorization, or resume facts before generating applications.

**Product Value:** Bad profile data can lead to bad applications. Users need safe preflight visibility.

**Acceptance Criteria:**
- [ ] New command reports missing or suspicious profile fields.
- [ ] Does not print sensitive values like password.
- [ ] Reuses normalized profile from `load_profile()`.
- [ ] Test covers at least one missing required field.

**Files You Will Likely Touch:**
- `src/applypilot/config.py`: optional helper for profile checks.
- `src/applypilot/cli.py`: new command.
- `tests/test_config_normalization.py` or new test file.

**Relevant Code To Study First:**
- `src/applypilot/config.py:36-80`
- `src/applypilot/config.py:129-178`
- `src/applypilot/config.py:306-316`
- `src/applypilot/apply/prompt.py:188-213`

**Detailed Implementation Plan:**
1. Define required fields:
   - `personal.full_name`
   - `personal.email`
   - `personal.phone`
   - `work_authorization.legally_authorized_to_work`
2. Add helper `validate_profile_completeness(profile: dict) -> list[dict]`.
3. Each issue should include `field`, `severity`, `message`.
4. Do not include actual sensitive values.
5. Add CLI command `profile-check`.
6. Render Rich table.
7. Add tests for missing email and missing work authorization.

**Testing And Verification:**
- Unit test helper.
- Manual: run `applypilot profile-check`.

**Tips:**
- Keep this read-only.
- Use normalized profile, not raw JSON.
- Do not print password or full sensitive payload.

**What Could Go Wrong:**
- Report leaks sensitive fields.
- Check duplicates prompt-builder rules.

**Review Checklist:**
- [ ] No sensitive values displayed.
- [ ] Helper testable without CLI.

**Connects To:** Story 21.

## Story 14: Add Tailored Artifact Manifest

**Difficulty:** Medium

**Estimated Time:** 5 hours

**User Story:** As a user, I want each tailored resume to have a manifest describing the job, score, generated files, and validation result so that I can audit what was created.

**Product Value:** Generated application artifacts need traceability.

**Acceptance Criteria:**
- [ ] For each tailored resume, write a manifest JSON file.
- [ ] Manifest includes job URL, title, site, score, text path, PDF path if available, report path, and status.
- [ ] Manifest does not include full resume text.
- [ ] Tests cover manifest creation with fake job data.

**Files You Will Likely Touch:**
- `src/applypilot/scoring/tailor.py`: artifact writing.
- `tests/`: add or update tailoring artifact test if feasible.

**Relevant Code To Study First:**
- `src/applypilot/scoring/tailor.py:430-548`
- `src/applypilot/scoring/pdf.py:362-407`

**Detailed Implementation Plan:**
1. Open `run_tailoring()`.
2. Locate where `txt_path`, `job_path`, and `report_path` are written.
3. After PDF attempt, build a manifest dictionary.
4. Include paths as strings.
5. Write `prefix_MANIFEST.json`.
6. Keep full resume text out of manifest.
7. Add helper function if this makes testing easier:
   - `build_tailor_manifest(job, result, paths)`.
8. Unit test helper with fake data.
9. Manual run with one job in a safe test DB.

**Testing And Verification:**
- Unit test helper.
- Manual artifact inspection.

**Tips:**
- Avoid testing real LLM calls.
- Keep manifest generation pure if possible.
- Include enough data to trace without leaking content.

**What Could Go Wrong:**
- Manifest stores sensitive resume text.
- PDF path is missing but code assumes it exists.

**Review Checklist:**
- [ ] No full resume content.
- [ ] Paths and status accurate.

**Connects To:** Story 18.

## Story 15: Add Cover Letter Validation Summary To Status

**Difficulty:** Medium

**Estimated Time:** 4 hours

**User Story:** As a user, I want status output to show how many cover letters failed validation so that I can review content issues before applying.

**Product Value:** Cover letter quality affects application quality. Validation failures should be visible.

**Acceptance Criteria:**
- [ ] Status includes count of cover-letter generation errors or missing eligible cover letters.
- [ ] Uses existing DB columns where possible.
- [ ] Does not parse cover letter files during status.
- [ ] Tests cover stat helper if DB logic changes.

**Files You Will Likely Touch:**
- `src/applypilot/database.py`: stats helper if needed.
- `src/applypilot/cli.py`: display.
- `src/applypilot/scoring/cover_letter.py`: understand existing writes.

**Relevant Code To Study First:**
- `src/applypilot/database.py:222-320`
- `src/applypilot/cli.py:378-390`
- `src/applypilot/scoring/cover_letter.py:179-282`

**Detailed Implementation Plan:**
1. Read existing `get_stats()`.
2. Determine what it already reports for cover letters.
3. If needed, add a new stat:
   - eligible tailored jobs without cover letters
   - cover attempts over threshold
4. Add display row to `status()`.
5. Add DB test if you add new stat logic.
6. Avoid reading files from disk during status.

**Testing And Verification:**
- DB helper test.
- Manual status output.

**Tips:**
- Status should stay fast.
- Use DB columns like `cover_letter_path` and `cover_attempts`.

**What Could Go Wrong:**
- Status becomes slow by scanning files.
- Count definition is unclear.

**Review Checklist:**
- [ ] Count meaning documented in label.
- [ ] Query uses existing columns.

**Connects To:** Story 16.

## Story 16: Add Per-Stage Limit Option To Run Command

**Difficulty:** Medium

**Estimated Time:** 6 hours

**User Story:** As a user, I want to limit how many jobs a stage processes so that I can test pipeline behavior on a small batch.

**Product Value:** Safer experimentation and debugging.

**Acceptance Criteria:**
- [ ] `applypilot run score --limit 5` limits scoring to 5 jobs.
- [ ] Limit is passed only to stages that support it.
- [ ] Unsupported stages either ignore with clear message or fail clearly.
- [ ] Existing behavior is unchanged when no limit is provided.

**Files You Will Likely Touch:**
- `src/applypilot/cli.py`: add option.
- `src/applypilot/pipeline.py`: pass limit through.
- Stage modules that already accept limits.
- Tests around pipeline argument passing if feasible.

**Relevant Code To Study First:**
- `src/applypilot/cli.py:78-124`
- `src/applypilot/pipeline.py:62-165`
- `src/applypilot/scoring/scorer.py:103-126`
- `src/applypilot/scoring/tailor.py:430-448`

**Detailed Implementation Plan:**
1. Inventory stage function signatures:
   - `run_scoring(limit=0, rescore=False)`
   - `run_tailoring(min_score=7, limit=20)`
   - `run_cover_letters(min_score=7, limit=20)`
   - `batch_convert(limit=50)`
   - `run_enrichment(limit=100, workers=1)`
2. Add `limit: Optional[int]` to CLI `run()`.
3. Add `limit` parameter to `run_pipeline()`.
4. Update `_run_score`, `_run_tailor`, `_run_cover`, `_run_pdf`, `_run_enrich` to accept/pass limit where supported.
5. Decide behavior for `discover`, which may not support simple limit.
6. Keep default behavior identical by passing `None` and using existing defaults.
7. Add tests around stage runner call behavior with monkeypatch if practical.

**Testing And Verification:**
- Targeted unit tests if runner monkeypatching is easy.
- Manual safe run: `applypilot run score --limit 1`.

**Tips:**
- This touches orchestration; keep changes small.
- Avoid changing defaults accidentally.
- Update help text clearly.

**What Could Go Wrong:**
- Limit changes default production behavior.
- Unsupported stages silently do surprising things.

**Review Checklist:**
- [ ] Defaults preserved.
- [ ] Stage support documented.

**Connects To:** Story 22.

## Story 17: Add A Safe "Explain Queue" Command

**Difficulty:** Medium

**Estimated Time:** 5 hours

**User Story:** As a user, I want a command that explains why jobs are or are not eligible for auto-apply so that I can fix missing artifacts or low scores.

**Product Value:** Users need reasons, not just counts.

**Acceptance Criteria:**
- [ ] Command shows sample jobs grouped by eligibility reason.
- [ ] Reasons include low score, missing tailored resume, missing application URL, already applied, failed permanent.
- [ ] Read-only; no rows updated.
- [ ] Test covers grouping logic.

**Files You Will Likely Touch:**
- `src/applypilot/database.py`: grouping helper.
- `src/applypilot/cli.py`: display command.
- `tests/`: DB helper tests.

**Relevant Code To Study First:**
- `src/applypilot/database.py:365-427`
- `src/applypilot/apply/launcher.py:174-271`
- `src/applypilot/cli.py:362-425`

**Detailed Implementation Plan:**
1. Define reasons in a helper:
   - `already_applied`
   - `missing_application_url`
   - `missing_tailored_resume`
   - `below_min_score`
   - `retry_limit_reached`
   - `eligible`
2. Write SQL or Python grouping over selected job rows.
3. Return count and up to 3 examples per group.
4. Add CLI command `explain-queue` or `apply --explain-queue`.
5. Render Rich table.
6. Add tests with seeded rows for at least three groups.

**Testing And Verification:**
- Unit tests for grouping helper.
- Manual command output.

**Tips:**
- Keep it read-only.
- Use the same eligibility concepts as `acquire_job()`.
- Do not call `acquire_job()`.

**What Could Go Wrong:**
- Explanation logic drifts from real apply selection.
- Too much output overwhelms user.

**Review Checklist:**
- [ ] Read-only.
- [ ] Clear reason names.

**Connects To:** Story 10 and Story 18.

