# Stories 18-25

## Story 18: Add SQLite Audit Log For Apply Decisions

**Difficulty:** Hard

**Estimated Time:** 10 hours

**User Story:** As a user, I want a durable audit log of auto-apply decisions so that I can understand what the app attempted, skipped, failed, or submitted.

**Product Value:** Auto-apply needs trust and traceability.

**Acceptance Criteria:**
- [ ] New audit table records timestamp, job URL, worker ID, agent, dry-run flag, decision, reason, and duration.
- [ ] Audit log does not store full prompt, resume text, profile data, or secrets.
- [ ] Audit write occurs for applied, skipped, failed, domain-blocked, and needs-review outcomes.
- [ ] Tests cover at least three audit event types.
- [ ] Existing `jobs` status behavior remains unchanged.

**Files You Will Likely Touch:**
- `src/applypilot/database.py`: add table creation and helper.
- `src/applypilot/apply/launcher.py`: record events.
- `tests/test_apply_launcher.py`: audit tests.
- Optional `src/applypilot/cli.py`: later audit display command.

**Relevant Code To Study First:**
- `src/applypilot/database.py:62-219`
- `src/applypilot/apply/launcher.py:416-568`
- `src/applypilot/apply/launcher.py:690-702`
- `tests/test_apply_launcher.py:8-257`

**Detailed Implementation Plan:**
1. In `database.py`, add `CREATE TABLE IF NOT EXISTS apply_audit`.
2. Columns:
   - `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - `created_at TEXT`
   - `url TEXT`
   - `worker_id INTEGER`
   - `agent TEXT`
   - `dry_run INTEGER`
   - `decision TEXT`
   - `reason TEXT`
   - `duration_ms INTEGER`
3. Add helper `record_apply_audit(...)`.
4. Keep helper small and parameterized.
5. In `launcher.run_job()`, record domain-blocked decisions before returning.
6. In `worker_loop()`, record final decisions after `run_job()`.
7. Avoid storing raw prompt or resume.
8. Add tests:
   - domain block creates audit row
   - applied creates audit row
   - skipped dry-run creates audit row
9. Run launcher tests.

**Testing And Verification:**
- `python -m pytest tests/test_apply_launcher.py -q`.
- Manual DB inspection in a throwaway `APPLYPILOT_DIR`.

**Tips:**
- Keep audit write failure behavior intentional. Decide whether audit failure should fail apply or log warning.
- Prefer transactional consistency if audit is part of the same DB connection.
- Keep reasons short.

**What Could Go Wrong:**
- Audit stores sensitive data.
- Audit write crashes apply flow.
- Duplicate audit rows make timelines confusing.

**Review Checklist:**
- [ ] No personal data or prompts stored.
- [ ] Tests prove audit rows.
- [ ] Existing job status tests still pass.

**Connects To:** Story 21 and Story 25.

## Story 19: Recover Stale In-Progress Apply Locks

**Difficulty:** Hard

**Estimated Time:** 8 hours

**User Story:** As a user, I want stale `in_progress` jobs to be recoverable so that a crashed browser or killed process does not permanently block the queue.

**Product Value:** Automation can crash. Recovery must be explicit and safe.

**Acceptance Criteria:**
- [ ] Add helper to identify `in_progress` rows older than a configurable threshold.
- [ ] Add command to preview stale locks.
- [ ] Add command option to release stale locks.
- [ ] Releasing stale locks records a clear `apply_error` or audit event if Story 18 exists.
- [ ] Tests cover stale and non-stale rows.

**Files You Will Likely Touch:**
- `src/applypilot/apply/launcher.py`: stale lock helper.
- `src/applypilot/cli.py`: command or option.
- `tests/test_apply_launcher.py`: DB tests.

**Relevant Code To Study First:**
- `src/applypilot/apply/launcher.py:174-271`
- `src/applypilot/apply/launcher.py:301-308`
- `src/applypilot/database.py:123-132`

**Detailed Implementation Plan:**
1. Define stale threshold default, such as 2 hours.
2. Add helper `find_stale_locks(older_than_minutes: int)`.
3. Query `apply_status = 'in_progress'` and compare `last_attempted_at`.
4. Add helper `release_stale_locks(...)`.
5. Update rows:
   - `apply_status = NULL`
   - `agent_id = NULL`
   - optionally `apply_error = 'released_stale_lock'`
6. Add CLI option under `apply`, such as `--release-stale-locks`.
7. Add preview mode first, or require `--yes` for mutation.
8. Tests:
   - old in-progress row is released
   - recent in-progress row remains
   - failed row remains unchanged

**Testing And Verification:**
- `python -m pytest tests/test_apply_launcher.py -q`.

**Tips:**
- Date parsing must handle ISO strings.
- Mutating recovery commands should be very explicit.
- Do not release active workers accidentally.

**What Could Go Wrong:**
- Active job lock is released while worker is still applying.
- Bad timestamp parsing crashes command.

**Review Checklist:**
- [ ] Preview exists or mutation is explicit.
- [ ] Tests cover age threshold.

**Connects To:** Story 22.

## Story 20: Add Structured Log Redaction

**Difficulty:** Hard

**Estimated Time:** 9 hours

**User Story:** As a user, I want logs to avoid exposing email, phone, API keys, and full prompt content so that local debugging does not create unnecessary privacy risk.

**Product Value:** ApplyPilot handles personal application data. Logs must be useful but restrained.

**Acceptance Criteria:**
- [ ] Add redaction helper for emails, phone-like strings, and known API key env vars.
- [ ] Apply helper before writing high-risk log lines.
- [ ] Do not redact job URLs or non-sensitive status fields.
- [ ] Tests cover redaction patterns.

**Files You Will Likely Touch:**
- New module `src/applypilot/redaction.py` or helper in config/logging area.
- `src/applypilot/apply/launcher.py`: worker logs.
- `src/applypilot/apply/agents/claude_runner.py`: raw command/log boundary if appropriate.
- `src/applypilot/apply/agents/codex_runner.py`: raw command/log boundary if appropriate.
- `tests/`: redaction tests.

**Relevant Code To Study First:**
- `src/applypilot/apply/launcher.py:455-475`
- `src/applypilot/apply/agents/claude_runner.py:94-120`
- `src/applypilot/apply/agents/codex_runner.py:95-135`
- `src/applypilot/apply/prompt.py:419-565`

**Detailed Implementation Plan:**
1. Create redaction helper:
   - `redact_sensitive(text: str) -> str`
2. Redact:
   - emails
   - phone-like digit groups
   - values of `GEMINI_API_KEY`, `OPENAI_API_KEY`, `CAPSOLVER_API_KEY` if present
3. Add tests for helper.
4. Identify log writes that may include sensitive content.
5. Apply redaction before writing those lines.
6. Be careful with raw agent logs: decide whether full raw logs are required for debugging. If retained, document privacy behavior clearly.
7. Run tests.

**Testing And Verification:**
- Unit redaction tests.
- Manual log inspection in dry-run.

**Tips:**
- Do not over-redact URLs.
- Keep helper deterministic.
- Avoid logging full prompts unless intentionally debug-only.

**What Could Go Wrong:**
- Redaction hides useful debugging data.
- Redaction misses common phone formats.
- Raw logs still contain prompt content.

**Review Checklist:**
- [ ] Tests include realistic personal-data examples.
- [ ] Logging policy is clear.

**Connects To:** Story 21.

## Story 21: Add Dry-Run Session Report

**Difficulty:** Hard

**Estimated Time:** 8 hours

**User Story:** As a user, I want a report after dry-run apply sessions showing which jobs were previewed and why they were not submitted so that I can review before real submission.

**Product Value:** Dry-run should produce confidence, not just temporary console output.

**Acceptance Criteria:**
- [ ] Dry-run session writes a summary artifact under `~/.applypilot/logs` or a reports directory.
- [ ] Report includes job title, site, URL, agent, result, reason, and timestamp.
- [ ] Report does not include full profile or resume text.
- [ ] Tests cover report builder without launching browser.

**Files You Will Likely Touch:**
- `src/applypilot/apply/launcher.py`: collect dry-run results.
- Possible new helper module `src/applypilot/apply/reports.py`.
- `tests/`: report builder tests.

**Relevant Code To Study First:**
- `src/applypilot/apply/launcher.py:484-487`
- `src/applypilot/apply/launcher.py:690-692`
- `src/applypilot/config.py:22-29`

**Detailed Implementation Plan:**
1. Add pure helper `build_dry_run_report(entries: list[dict]) -> str`.
2. Each entry should be small and non-sensitive.
3. Add tests for report text.
4. In `worker_loop()`, when result is `skipped` due to dry-run, append entry to session collection.
5. At end of run, write report file.
6. Name file with timestamp.
7. Keep report path visible in console output.
8. If multi-worker, decide whether each worker writes its own report or main aggregates. Prefer simple per-worker first.

**Testing And Verification:**
- Unit report helper.
- Manual dry-run with one job in safe environment.

**Tips:**
- Start with Markdown or JSON, not complex HTML.
- Do not write full prompt.
- Keep report generation separate from browser code.

**What Could Go Wrong:**
- Multi-worker reports collide.
- Report accidentally includes resume text.

**Review Checklist:**
- [ ] Report builder is testable.
- [ ] No sensitive content.

**Connects To:** Story 18 and Story 20.

## Story 22: Add Pipeline Checkpoint/Resume Command

**Difficulty:** Hard

**Estimated Time:** 10 hours

**User Story:** As a user, I want to resume pipeline work from the next incomplete stage so that interrupted runs are easier to continue.

**Product Value:** Long scraping and LLM workflows can be interrupted. Resume lowers frustration.

**Acceptance Criteria:**
- [ ] New command or option determines which stages have pending work.
- [ ] User can run `applypilot run --resume` to continue from the earliest incomplete stage.
- [ ] Uses existing DB state, not separate checkpoint files.
- [ ] Dry-run shows planned stages.
- [ ] Tests cover stage resolution logic.

**Files You Will Likely Touch:**
- `src/applypilot/pipeline.py`: stage pending logic.
- `src/applypilot/cli.py`: CLI option.
- `tests/`: pipeline resolution tests.

**Relevant Code To Study First:**
- `src/applypilot/pipeline.py:222-255`
- `src/applypilot/pipeline.py:439-480`
- `src/applypilot/database.py:222-320`

**Detailed Implementation Plan:**
1. Add helper `resolve_resume_stages(min_score: int) -> list[str]`.
2. Use `_count_pending()` for stages that have pending SQL.
3. Determine behavior for `discover`, which does not have pending SQL.
4. Recommended first version:
   - if enrichment pending, start at `enrich`
   - else if score pending, start at `score`
   - else if tailor pending, start at `tailor`
   - else if cover pending, start at `cover`
   - else if pdf pending, start at `pdf`
5. Add `resume: bool = typer.Option(False, "--resume")` to CLI run.
6. If `--resume`, ignore explicit stages or reject combining with explicit stages. Pick one rule and document it.
7. Add dry-run display of resolved stages.
8. Test helper with monkeypatched `_count_pending`.

**Testing And Verification:**
- Unit tests for stage resolution.
- Manual dry-run.

**Tips:**
- Keep resume stage resolution pure and testable.
- Avoid running discovery unexpectedly.
- Make CLI conflict behavior clear.

**What Could Go Wrong:**
- Resume skips a needed stage.
- Combining explicit stages and resume creates confusing behavior.

**Review Checklist:**
- [ ] Helper tested.
- [ ] CLI behavior clear.

**Connects To:** Story 16.

## Story 23: Add Source Quality Score

**Difficulty:** Expert

**Estimated Time:** 12 hours

**User Story:** As a user, I want each job source to receive a quality score so that I can prioritize boards that produce high-fit, apply-ready roles.

**Product Value:** Search strategy improves when source quality is measured over time.

**Acceptance Criteria:**
- [ ] Source quality score uses existing DB data.
- [ ] Formula is documented and testable.
- [ ] Dashboard displays quality score by source.
- [ ] No external calls are added.
- [ ] Tests cover score calculation.

**Files You Will Likely Touch:**
- `src/applypilot/database.py`: source quality aggregation helper.
- `src/applypilot/view.py`: dashboard display.
- `tests/`: helper tests.

**Relevant Code To Study First:**
- `src/applypilot/view.py:62-72`
- `src/applypilot/database.py:222-320`
- `src/applypilot/database.py:90-133`

**Detailed Implementation Plan:**
1. Define source quality formula:
   - example: `(high_fit * 3 + apply_ready * 5 + applied * 8) / total`
2. Add pure helper `calculate_source_quality(row_or_counts)`.
3. Add unit tests for formula.
4. Add DB helper `get_source_quality_stats(conn=None)`.
5. Query totals by `site`.
6. Display in dashboard.
7. Add explanation tooltip or label in dashboard.
8. Keep formula stable and documented.

**Testing And Verification:**
- Unit formula tests.
- DB aggregation test.
- Manual dashboard check.

**Tips:**
- Do not overfit formula.
- Handle small sample sizes.
- Make unscored jobs affect confidence.

**What Could Go Wrong:**
- Score appears precise but is based on tiny data.
- Formula punishes new sources unfairly.

**Review Checklist:**
- [ ] Formula documented.
- [ ] Tests cover edge cases.

**Connects To:** Story 25.

## Story 24: Add Fake Agent Runner For Local Tests

**Difficulty:** Expert

**Estimated Time:** 10 hours

**User Story:** As a maintainer, I want a fake agent runner for tests so that auto-apply behavior can be tested without Claude, Codex, Chrome, or network dependencies.

**Product Value:** Faster, safer tests for high-risk automation logic.

**Acceptance Criteria:**
- [ ] Fake runner implements same contract as real runners.
- [ ] Tests can inject fake runner into `run_job()` or lower-level helper.
- [ ] Covers applied, failed, dry-run, and needs-review outcomes.
- [ ] Does not affect production CLI behavior.

**Files You Will Likely Touch:**
- `src/applypilot/apply/launcher.py`: dependency injection seam.
- `src/applypilot/apply/agents/base.py`: shared contract stays same.
- `tests/test_apply_launcher.py`: fake runner tests.

**Relevant Code To Study First:**
- `src/applypilot/apply/agents/base.py:10-36`
- `src/applypilot/apply/launcher.py:502-568`
- `tests/test_apply_launcher.py:226-252`

**Detailed Implementation Plan:**
1. Identify where `run_job()` constructs `ClaudeRunner` and `CodexRunner`.
2. Add optional internal parameter to `run_job()` such as `runner_factory=None`, or extract `_run_engine()` to a testable helper.
3. Keep CLI call sites unchanged.
4. In tests, create `FakeRunner` returning `AgentRunResult`.
5. Use `ParsedOutcome` for each scenario.
6. Avoid launching Chrome by testing only `run_job()` with monkeypatched file/prompt setup or an even smaller extracted helper.
7. Add tests:
   - APPLIED maps to `"applied"`
   - DRY_RUN maps to `"skipped"`
   - NEEDS_REVIEW triggers auto fallback if testing auto mode
8. Run launcher tests.

**Testing And Verification:**
- `python -m pytest tests/test_apply_launcher.py -q`.

**Tips:**
- Keep dependency injection private if you do not want to expose API.
- Do not add a fake agent option to production CLI.
- Preserve real runner construction behavior.

**What Could Go Wrong:**
- Test seam complicates production code.
- Fake runner diverges from real contract.

**Review Checklist:**
- [ ] Production CLI unchanged.
- [ ] Fake uses real `AgentRunResult`.

**Connects To:** Story 18 and Story 19.

## Story 25: Add Search Campaigns As A New Domain Concept

**Difficulty:** Expert

**Estimated Time:** 16+ hours

**User Story:** As a job seeker running different job-search strategies, I want to group searches and results into campaigns so that I can compare outcomes across roles, locations, or resume strategies.

**Product Value:** ApplyPilot becomes a campaign-based job search tool rather than one undifferentiated queue.

**Acceptance Criteria:**
- [ ] User can define campaign name in search config.
- [ ] Discovered jobs store campaign name or ID.
- [ ] Status/dashboard can filter or group by campaign.
- [ ] Existing users without campaigns continue to work.
- [ ] Tests cover config normalization, DB migration, and campaign grouping.

**Files You Will Likely Touch:**
- `src/applypilot/config.py`: normalize campaign config.
- `src/applypilot/database.py`: add `campaign` column or new table.
- `src/applypilot/discovery/jobspy.py`: store campaign on discovered jobs.
- `src/applypilot/discovery/workday.py`: store campaign on discovered jobs.
- `src/applypilot/discovery/smartextract.py`: store campaign on discovered jobs.
- `src/applypilot/cli.py`: status/display options.
- `src/applypilot/view.py`: dashboard grouping/filtering.
- `tests/test_config_normalization.py`, new DB/discovery tests.

**Relevant Code To Study First:**
- `src/applypilot/config.py:209-238`
- `src/applypilot/database.py:143-219`
- `src/applypilot/database.py:329-362`
- `src/applypilot/discovery/jobspy.py:131-192`
- `src/applypilot/view.py:25-115`

**Detailed Implementation Plan:**
1. Product design first:
   - Decide whether campaign is a simple string column or a separate table.
   - For first version, prefer simple `campaign TEXT` column for lower risk.
2. Config:
   - Add optional `campaign` field to search config normalization.
   - Default to `"default"` or `NULL`. Pick one and document it.
3. Database:
   - Add `campaign` to `_ALL_COLUMNS`.
   - Add column to `CREATE TABLE`.
   - Ensure old DBs migrate through `ensure_columns()`.
4. Discovery:
   - Pass campaign from config into discovery storage.
   - Update inserts in JobSpy, Workday, and smart extract.
   - If a path cannot identify campaign yet, default consistently.
5. Status:
   - Add campaign grouping stats helper.
   - Display campaign counts in `applypilot status` or new command.
6. Dashboard:
   - Add campaign field to SELECT.
   - Add campaign filter.
7. Tests:
   - Config normalization with campaign.
   - DB migration includes campaign.
   - Insert stores campaign.
   - Dashboard generated HTML includes campaign filter.
8. Rollout:
   - Keep old configs working.
   - Avoid requiring campaign for existing users.

**Testing And Verification:**
- `python -m pytest tests/test_config_normalization.py -q`
- DB migration test.
- Discovery storage test with fake rows.
- Manual dashboard generation.

**Tips:**
- This is architectural. Write a short design note before coding.
- Keep first version simple.
- Avoid changing every function signature if one storage helper can carry campaign.
- Make backward compatibility non-negotiable.

**What Could Go Wrong:**
- Old databases fail migration.
- Some discovery paths do not store campaign.
- Dashboard filters hide uncategorized jobs.
- Campaign becomes a vague string with inconsistent spelling.

**Review Checklist:**
- [ ] Backward compatibility proven.
- [ ] Tests cover all discovery paths touched.
- [ ] UI handles missing campaign.
- [ ] Product behavior documented.

**Connects To:** Long-term product strategy: campaign comparison, source quality, and tailored resume experiments.

