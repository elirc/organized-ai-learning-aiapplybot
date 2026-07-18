# User Stories

## Story 1: Show Apply Readiness In Status Output

**Difficulty:** Easy

**Estimated Time:** 1 hour

**Skills You'll Practice:** reading CLI output, SQLite stats, small display change

**The Story:** As a job seeker, I want `applypilot status` to clearly show how many jobs are ready for auto-apply so that I know whether Stage 6 can run.

**Why This Story Matters:** The CLI already calculates `ready_to_apply`, but improving wording and placement helps users understand the workflow state before launching automation.

**Acceptance Criteria:**
- [ ] `applypilot status` includes a clear "Ready for auto-apply" row.
- [ ] The count comes from existing stats, not a duplicate SQL query in `cli.py`.
- [ ] No production behavior changes outside status display.

**Files You'll Likely Touch:**
- `src/applypilot/cli.py`: status table display is built in `status()`.

**Relevant Existing Patterns:**
- `src/applypilot/cli.py:362-425` builds Rich tables from `get_stats()`.
- `src/applypilot/database.py:222-320` computes stats.

**High-Level Implementation Plan:**
1. Open `src/applypilot/cli.py:373-390`.
2. Rename or add a display row using `stats["ready_to_apply"]`.
3. Keep table construction style consistent with existing `summary.add_row(...)`.
4. Run `applypilot status` against a test/local database if available.

**Testing and Verification Plan:** Manual verification is enough if only label text changes. If you alter `get_stats()`, add a DB-focused test.

**Tips:**
- Do not add SQL to `cli.py`; stats ownership belongs in `database.py`.
- Keep Rich markup consistent with nearby rows.
- Use exact stat keys already returned by `get_stats()`.

**What Could Go Wrong:**
- A typo in the stats key causes a runtime `KeyError`.
- A display-only change accidentally alters DB logic.
- The new label is ambiguous with "Applied."

**Stretch Goal:** Add a second row for "Blocked/manual apply" if stats already expose enough data.

**Connects To:** Story 4, because both improve operational visibility.

## Story 2: Make Unknown Agent Output Easier To Diagnose

**Difficulty:** Easy

**Estimated Time:** 1.5 hours

**Skills You'll Practice:** parser tests, failure reasons, small behavior change

**The Story:** As a developer, I want unknown agent output to include a short diagnostic reason so that I can debug failed apply runs faster.

**Why This Story Matters:** Agent output is an external boundary. Better parse reasons reduce mystery when automation fails.

**Acceptance Criteria:**
- [ ] Empty output still returns `NEEDS_REVIEW` with `empty_output`.
- [ ] Output without markers returns `NEEDS_REVIEW` with a useful reason.
- [ ] Existing parser tests still pass.
- [ ] Add one parser test for noisy text with no final marker.

**Files You'll Likely Touch:**
- `src/applypilot/apply/agents/parsing.py`: parser logic.
- `tests/test_agent_parsing.py`: parser tests.

**Relevant Existing Patterns:**
- `src/applypilot/apply/agents/parsing.py:74-87`.
- `tests/test_agent_parsing.py:4-24`.

**High-Level Implementation Plan:**
1. Read `parse_agent_result()` in `src/applypilot/apply/agents/parsing.py:74-87`.
2. Decide whether the current `no_result_marker` reason is enough or should include a safe prefix.
3. Add a focused test in `tests/test_agent_parsing.py`.
4. Run `python -m pytest tests/test_agent_parsing.py -q`.

**Testing and Verification Plan:** Parser unit tests only.

**Tips:**
- Do not include raw personal prompt data in reasons.
- Keep valid status vocabulary unchanged.
- Prefer deterministic assertions over matching whole logs.

**What Could Go Wrong:**
- Parser starts treating random text as success.
- Reason leaks too much agent output.
- Existing `NEEDS_REVIEW` semantics change unexpectedly.

**Stretch Goal:** Add a max-length cap to diagnostic reasons.

**Connects To:** Story 6, where result parsing affects apply behavior.

## Story 3: Validate Search Config Location Defaults More Clearly

**Difficulty:** Easy

**Estimated Time:** 2 hours

**Skills You'll Practice:** config normalization, pytest, backward compatibility

**The Story:** As a user configuring searches, I want location defaults to be normalized predictably so that discovery does not miss relevant local jobs.

**Why This Story Matters:** Search config is one of the first user-owned inputs. Small normalization bugs can silently reduce job discovery quality.

**Acceptance Criteria:**
- [ ] Existing alias behavior remains: `boards` becomes `sites`.
- [ ] Country normalization still maps USA variants to `usa`.
- [ ] Derived location accept patterns are documented by tests.
- [ ] No existing config files are modified.

**Files You'll Likely Touch:**
- `src/applypilot/config.py`: normalization helpers.
- `tests/test_config_normalization.py`: existing tests.

**Relevant Existing Patterns:**
- `src/applypilot/config.py:181-238`.
- `tests/test_config_normalization.py:44-100`.

**High-Level Implementation Plan:**
1. Read `_normalize_search_config()`.
2. Identify one missing edge case, such as empty location list or remote-only location.
3. Add a test first.
4. Implement only the normalization needed by that test.

**Testing and Verification Plan:** Run `python -m pytest tests/test_config_normalization.py -q`.

**Tips:**
- Keep `_normalize_search_config()` backward compatible.
- Do not mutate input dictionaries unexpectedly.
- Use tests with temporary `searches.yaml` files like existing tests.

**What Could Go Wrong:**
- Remote-only locations become restrictive.
- User-provided accept patterns get overwritten.
- Tests accidentally read real `~/.applypilot/searches.yaml`.

**Stretch Goal:** Add a short warning when config is empty.

**Connects To:** Story 7, because discovery quality depends on config quality.

## Story 4: Add A Dashboard Filter For Apply Status

**Difficulty:** Medium

**Estimated Time:** 3 hours

**Skills You'll Practice:** generated HTML, SQL query fields, UI filtering

**The Story:** As a job seeker, I want the HTML dashboard to filter by apply status so that I can inspect failed, applied, and pending jobs separately.

**Why This Story Matters:** The generated dashboard is the user's inspection surface after pipeline runs.

**Acceptance Criteria:**
- [ ] Dashboard query includes `apply_status`.
- [ ] Each job card stores status in a data attribute.
- [ ] UI filter can show all, pending, applied, failed, manual, and in-progress jobs.
- [ ] Existing score/text filters still work.

**Files You'll Likely Touch:**
- `src/applypilot/view.py`: dashboard SQL, HTML, JS filtering.

**Relevant Existing Patterns:**
- `src/applypilot/view.py:25-82` queries dashboard data.
- `src/applypilot/view.py:360-385` applies client-side filters.

**High-Level Implementation Plan:**
1. Add `apply_status` to the jobs SELECT in `generate_dashboard()`.
2. Add a visual status label on each job card.
3. Add a select/filter control in the generated HTML.
4. Extend `applyFilters()` to check card status.
5. Generate dashboard and verify filtering manually.

**Testing and Verification Plan:** Manual browser verification. Consider a unit-style smoke test later if dashboard generation gets templated.

**Tips:**
- Escape status values before injecting into HTML.
- Keep filter logic near existing score/text logic.
- Avoid changing database schema; the column already exists in `database.py`.

**What Could Go Wrong:**
- Cards without status disappear unintentionally.
- JS filter logic conflicts with score filtering.
- HTML injection risk if unescaped values are displayed.

**Stretch Goal:** Add a count per apply status.

**Connects To:** Story 5, because both improve visibility.

## Story 5: Add A Doctor Check For Writable Runtime Directories

**Difficulty:** Medium

**Estimated Time:** 3 hours

**Skills You'll Practice:** diagnostics, filesystem checks, CLI UX

**The Story:** As a user, I want `applypilot doctor` to tell me if runtime directories are writable so that pipeline failures are easier to diagnose.

**Why This Story Matters:** This app writes profile files, SQLite DBs, logs, generated resumes, worker dirs, and dashboard files.

**Acceptance Criteria:**
- [ ] `doctor` checks `APP_DIR`, `LOG_DIR`, `TAILORED_DIR`, and `APPLY_WORKER_DIR`.
- [ ] The check does not leave unnecessary files behind.
- [ ] Output uses the existing Rich table style.
- [ ] Permission failures do not crash the command.

**Files You'll Likely Touch:**
- `src/applypilot/cli.py`: `doctor()` output.
- Possibly `src/applypilot/config.py`: helper if reused.

**Relevant Existing Patterns:**
- `src/applypilot/cli.py:295-359`.
- `src/applypilot/config.py:300-303`.

**High-Level Implementation Plan:**
1. Read `doctor()`.
2. Import runtime paths from `config`.
3. Create a small helper to check directory existence/writability using a temporary probe file.
4. Add rows to the doctor table.
5. Test manually with normal permissions.

**Testing and Verification Plan:** Add a test only if CLI runner utilities already exist; otherwise manually verify. Do not alter real user files in tests.

**Tips:**
- Use a unique temporary filename and delete it.
- Catch `OSError`.
- Keep diagnostics read-only except for the temporary probe.

**What Could Go Wrong:**
- The check creates files in user directories and leaves them.
- `doctor` fails before printing useful diagnostics.
- Windows path permissions behave differently than expected.

**Stretch Goal:** Show `APPLYPILOT_DIR` override in doctor output.

**Connects To:** Story 8, because durable storage depends on writable runtime paths.

## Story 6: Add A Retryable Apply Failure Reason Test

**Difficulty:** Medium

**Estimated Time:** 4 hours

**Skills You'll Practice:** failure classification, DB tests, apply state

**The Story:** As a developer, I want retryable and permanent apply failures to be tested so that failed jobs do not get retried incorrectly.

**Why This Story Matters:** Wrong retry classification can either spam a site or abandon valid applications.

**Acceptance Criteria:**
- [ ] Add tests for at least one permanent failure and one retryable failure.
- [ ] Permanent failures set attempts high enough to prevent normal retry.
- [ ] Retryable failures increment attempts once.
- [ ] Existing launcher tests still pass.

**Files You'll Likely Touch:**
- `tests/test_apply_launcher.py`: add tests.
- Possibly `src/applypilot/apply/launcher.py`: only if behavior is wrong.

**Relevant Existing Patterns:**
- `src/applypilot/apply/launcher.py:277-298`.
- `src/applypilot/apply/launcher.py:575-585`.
- `tests/test_apply_launcher.py:8-122`.

**High-Level Implementation Plan:**
1. Study `_setup_db()` in tests.
2. Seed a job row.
3. Call `mark_result()` with permanent and non-permanent values.
4. Query `apply_attempts` and `apply_status`.
5. Only change production code if the test reveals incorrect behavior.

**Testing and Verification Plan:** Run `python -m pytest tests/test_apply_launcher.py -q`.

**Tips:**
- Keep tests DB-local using `tmp_path`.
- Avoid launching Chrome.
- Test state transitions, not internal implementation details.

**What Could Go Wrong:**
- Tests accidentally use the real DB path.
- Permanent failure list changes without tests.
- Retryable failures become permanently blocked.

**Stretch Goal:** Add a test for `domain_not_allowed`.

**Connects To:** Story 8.

## Story 7: Add Discovery Summary By Source

**Difficulty:** Medium

**Estimated Time:** 4 hours

**Skills You'll Practice:** discovery flow, database aggregation, CLI reporting

**The Story:** As a user, I want discovery results summarized by source so that I know which job boards produced useful leads.

**Why This Story Matters:** Discovery can use several sources. Source-level feedback helps tune searches.

**Acceptance Criteria:**
- [ ] Discovery summary includes new and existing counts by source when available.
- [ ] Does not break current `run_discovery()` return shape.
- [ ] Existing status/dashboard behavior remains unchanged.
- [ ] Add or update focused tests if logic is extracted.

**Files You'll Likely Touch:**
- `src/applypilot/discovery/jobspy.py`: source insert stats.
- `src/applypilot/pipeline.py`: display summary if returned.

**Relevant Existing Patterns:**
- `src/applypilot/discovery/jobspy.py:131-192`.
- `src/applypilot/discovery/jobspy.py:454-485`.
- `src/applypilot/pipeline.py:62-99`.

**High-Level Implementation Plan:**
1. Read how JobSpy results are stored.
2. Determine whether per-source stats are already available deeper in `_full_crawl()`.
3. Return additional summary data without removing old keys.
4. Update pipeline display only if it can handle missing summary data.

**Testing and Verification Plan:** Use unit tests around any extracted summary helper. Manual discovery may be slow and network-dependent.

**Tips:**
- Preserve backward compatibility of return dict keys.
- Do not make live network calls in tests.
- Source labels should match `site` values in DB.

**What Could Go Wrong:**
- Summary double-counts duplicates.
- Pipeline assumes summary exists for every discovery backend.
- Tests become dependent on JobSpy installation.

**Stretch Goal:** Add dashboard source quality metrics.

**Connects To:** Story 9.

## Story 8: Add An Apply Safety Preview Command

**Difficulty:** Hard

**Estimated Time:** 6 hours

**Skills You'll Practice:** CLI design, DB querying, safety review, tests

**The Story:** As a cautious job seeker, I want to preview the exact jobs that auto-apply would attempt before launching browsers so that I can approve the queue mentally.

**Why This Story Matters:** Auto-apply is high stakes. Previewing eligible jobs reduces accidental submissions.

**Acceptance Criteria:**
- [ ] New command or option shows eligible jobs without claiming them.
- [ ] Preview respects `min_score`, blocked sites, manual ATS, and target URL rules as much as practical.
- [ ] Preview does not set `apply_status`.
- [ ] Tests prove preview is read-only.

**Files You'll Likely Touch:**
- `src/applypilot/cli.py`: new option or subcommand.
- `src/applypilot/apply/launcher.py`: read-only eligibility helper.
- `tests/test_apply_launcher.py`: read-only preview tests.

**Relevant Existing Patterns:**
- `src/applypilot/cli.py:127-220`.
- `src/applypilot/apply/launcher.py:174-271`.
- `tests/test_apply_launcher.py:17-108`.

**High-Level Implementation Plan:**
1. Extract eligibility query logic carefully from `acquire_job()` into a read helper.
2. Keep claiming behavior unchanged.
3. Add CLI mode such as `apply --preview`.
4. Display URL, title, site, score, and apply URL.
5. Add test proving preview does not mark rows `in_progress`.

**Testing and Verification Plan:** Run launcher tests and manually run preview on a non-production `APPLYPILOT_DIR`.

**Tips:**
- Do not call `BEGIN IMMEDIATE` for preview unless needed.
- Avoid copying all of `acquire_job()` into a divergent query.
- Think carefully about manual ATS filtering.

**What Could Go Wrong:**
- Preview and real apply eligibility drift apart.
- Preview accidentally claims jobs.
- Users assume preview is exhaustive when target URL rules differ.

**Stretch Goal:** Add `--json` output for preview.

**Connects To:** Story 10.

## Story 9: Add A Failed-Apply Report

**Difficulty:** Hard

**Estimated Time:** 7 hours

**Skills You'll Practice:** SQL aggregation, CLI reporting, failure taxonomy

**The Story:** As a user, I want a report of failed applications grouped by reason so that I know what to fix first.

**Why This Story Matters:** Auto-apply failures can come from CAPTCHA, expired jobs, login issues, blocked domains, parser failures, and unknown states.

**Acceptance Criteria:**
- [ ] New CLI command or status section groups `apply_error` values.
- [ ] Report includes count, example job title, and example URL.
- [ ] Does not expose personal profile data.
- [ ] Tests cover aggregation with seeded rows.

**Files You'll Likely Touch:**
- `src/applypilot/database.py`: aggregation helper.
- `src/applypilot/cli.py`: display command/section.
- `tests/`: new or existing DB-focused test file.

**Relevant Existing Patterns:**
- `src/applypilot/database.py:222-320`.
- `src/applypilot/cli.py:362-425`.
- `src/applypilot/apply/launcher.py:277-298`.

**High-Level Implementation Plan:**
1. Add `get_apply_failure_report(conn=None)` in `database.py`.
2. Use parameter-free SQL grouping by normalized `apply_error`.
3. Add a CLI display table.
4. Seed rows in a test database and assert grouped output shape.

**Testing and Verification Plan:** Add tests for aggregation helper; manually inspect CLI formatting.

**Tips:**
- Keep database logic out of `cli.py`.
- Cap example strings for display.
- Treat `NULL` and empty strings consistently.

**What Could Go Wrong:**
- Grouping by full error strings creates too many buckets.
- Report leaks long URLs or personal fields.
- CLI output becomes too noisy.

**Stretch Goal:** Export report as JSON.

**Connects To:** Story 10.

## Story 10: Add An Audit Log For Auto-Apply Decisions

**Difficulty:** Expert

**Estimated Time:** 12 hours

**Skills You'll Practice:** architecture, persistence, privacy, testing, operational safety

**The Story:** As a user, I want an audit log of auto-apply decisions so that I can understand why each job was applied, skipped, failed, or sent to review.

**Why This Story Matters:** Automated job submissions are high stakes. An audit trail builds trust and helps debug failures.

**Acceptance Criteria:**
- [ ] Every apply decision records job URL, timestamp, worker, decision, reason, agent, and dry-run flag.
- [ ] Audit log avoids storing full profile, resume text, or secrets.
- [ ] Durable storage is local and survives process exit.
- [ ] Tests cover applied, skipped, failed, and dry-run paths.
- [ ] Existing `jobs` status behavior remains unchanged.

**Files You'll Likely Touch:**
- `src/applypilot/database.py`: schema or new audit table helper.
- `src/applypilot/apply/launcher.py`: write audit events at decision points.
- `src/applypilot/cli.py`: optional report command.
- `tests/test_apply_launcher.py`: state/audit tests.

**Relevant Existing Patterns:**
- `src/applypilot/database.py:62-219` for schema/migration style.
- `src/applypilot/apply/launcher.py:467-500` for outcome mapping.
- `src/applypilot/apply/launcher.py:690-702` for final persistence.
- `tests/test_apply_launcher.py:8-122` for isolated DB setup.

**High-Level Implementation Plan:**
1. Decide whether to use a new table or log file. Prefer a SQLite table for queryability.
2. Add idempotent table creation in `init_db()`.
3. Add helper `record_apply_audit(...)`.
4. Call it when jobs are applied, skipped, failed, blocked by domain, or released after dry-run.
5. Add tests that do not launch Chrome or agents.
6. Add a CLI report only after storage is stable.

**Testing and Verification Plan:** Unit tests for audit helper and launcher paths. Manual check with `--dry-run` in a safe test directory.

**Tips:**
- Do not store full prompt text.
- Keep audit writes best-effort only if failure should not block status updates, or transactional if audit must be guaranteed. Choose intentionally.
- Preserve old databases with additive migration.
- Keep reasons short and normalized.

**What Could Go Wrong:**
- Audit records leak personal data.
- Audit writes fail and break apply flow.
- Duplicate records appear on retry without clear semantics.

**Stretch Goal:** Add `applypilot audit --url <job>` to show one job's decision timeline.

**Connects To:** Senior ownership work: observability, trust, and safe automation.
