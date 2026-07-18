# Stories 1-8

## Story 1: Rename Status Row To "Ready For Auto-Apply"

**Difficulty:** Easy

**Estimated Time:** 45 minutes

**User Story:** As a job seeker, I want the status command to clearly show how many jobs are ready for auto-apply so that I do not start Stage 6 before the queue is prepared.

**Product Value:** The existing status output already includes readiness information, but clearer language reduces user confusion before a high-stakes automation step.

**Acceptance Criteria:**
- [ ] `applypilot status` shows a row labeled `Ready for auto-apply`.
- [ ] The value uses the existing `ready_to_apply` stat.
- [ ] No SQL is added to `src/applypilot/cli.py`.
- [ ] No production behavior changes outside display text.

**Files You Will Likely Touch:**
- `src/applypilot/cli.py`: the Rich status table is assembled in `status()`.

**Relevant Code To Study First:**
- `src/applypilot/cli.py:362-425`
- `src/applypilot/database.py:222-320`

**Detailed Implementation Plan:**
1. Open `src/applypilot/cli.py`.
2. Find `def status()` around `src/applypilot/cli.py:362`.
3. Find the `summary.add_row(...)` calls around `src/applypilot/cli.py:378-389`.
4. Locate the row that uses `stats["ready_to_apply"]`.
5. Change only the display label to `Ready for auto-apply`.
6. Do not change the stat key.
7. Run `applypilot status` in a safe local environment, or run the existing test suite if one covers CLI output later.

**Testing And Verification:**
- Manual: run `applypilot status` and inspect the label.
- Optional future test: add a Typer CLI runner test if CLI testing infrastructure is introduced.

**Tips:**
- Keep DB logic in `database.py`; keep display logic in `cli.py`.
- If a value already exists in `stats`, reuse it.
- Display-only changes should have tiny diffs.

**What Could Go Wrong:**
- A typo like `stats["ready_for_apply"]` causes a `KeyError`.
- Adding SQL to `cli.py` duplicates `database.py`.

**Review Checklist:**
- [ ] Diff touches only `src/applypilot/cli.py`.
- [ ] No behavior or schema changes.

**Connects To:** Story 6, where you add more dashboard visibility.

## Story 2: Add A Help Note For Missing LLM Provider

**Difficulty:** Easy

**Estimated Time:** 1 hour

**User Story:** As a new user, I want a clearer error when no LLM provider is configured so that I know which environment variable to set.

**Product Value:** Stages `score`, `tailor`, and `cover` depend on LLM configuration. Better guidance reduces setup friction.

**Acceptance Criteria:**
- [ ] The missing-provider error names `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `LLM_URL`.
- [ ] The message points users to `~/.applypilot/.env` or `.env.example`.
- [ ] Existing provider detection behavior remains unchanged.
- [ ] Existing LLM tests still pass.

**Files You Will Likely Touch:**
- `src/applypilot/llm.py`: provider detection and error message.
- `tests/test_llm.py`: add or update test for missing provider if needed.

**Relevant Code To Study First:**
- `src/applypilot/llm.py:22-53`
- `tests/test_llm.py:6-24`
- `.env.example`

**Detailed Implementation Plan:**
1. Open `src/applypilot/llm.py`.
2. Read `_detect_provider()`.
3. Find the final `raise RuntimeError(...)` branch.
4. Change only the error message text.
5. Keep the provider selection order unchanged.
6. Open `tests/test_llm.py`.
7. If no test covers missing provider, add one that clears `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `LLM_URL`, calls `_detect_provider()`, and asserts the error message includes the three setup options.
8. Run `python -m pytest tests/test_llm.py -q`.

**Testing And Verification:**
- Unit: `tests/test_llm.py`.
- Manual: temporarily run a scoring command without LLM env vars in a throwaway shell.

**Tips:**
- Do not print API keys.
- Keep the message helpful but short.
- Use `monkeypatch.delenv(..., raising=False)` in tests.

**What Could Go Wrong:**
- Changing detection order could break users who set multiple env vars.
- Test leaks a real environment variable if not cleared.

**Review Checklist:**
- [ ] Message only, no provider behavior change.
- [ ] Test isolates environment.

**Connects To:** Story 5, where setup validation becomes more complete.

## Story 3: Add Parser Test For Ambiguous Agent Output

**Difficulty:** Easy

**Estimated Time:** 1 hour

**User Story:** As a maintainer, I want ambiguous agent output to remain `NEEDS_REVIEW` so that the app never marks a job as submitted based on vague text.

**Product Value:** Auto-apply safety depends on explicit final output contracts.

**Acceptance Criteria:**
- [ ] Add a test using ambiguous text like `I think it submitted, but not sure`.
- [ ] Parser returns `NEEDS_REVIEW`.
- [ ] Parser does not set `submitted=True`.
- [ ] No production code changes unless the test reveals a bug.

**Files You Will Likely Touch:**
- `tests/test_agent_parsing.py`: parser behavior tests.
- Possibly `src/applypilot/apply/agents/parsing.py`: only if the new test fails.

**Relevant Code To Study First:**
- `src/applypilot/apply/agents/parsing.py:13-87`
- `tests/test_agent_parsing.py:4-55`

**Detailed Implementation Plan:**
1. Open `tests/test_agent_parsing.py`.
2. Add a test named `test_parse_ambiguous_submission_text_needs_review`.
3. Call `parse_agent_result("I think it submitted, but not sure")`.
4. Assert `parsed.status == "NEEDS_REVIEW"`.
5. Assert `parsed.submitted is False`.
6. Assert the reason is `no_result_marker`, unless parser behavior intentionally changes.
7. Run `python -m pytest tests/test_agent_parsing.py -q`.

**Testing And Verification:**
- Unit only: parser tests.

**Tips:**
- Good parser tests check behavior, not regex internals.
- Keep the test focused on one input and one expected result.

**What Could Go Wrong:**
- A future parser change may trust vague text and produce false positives.
- The test becomes too broad if it includes multiple unrelated cases.

**Review Checklist:**
- [ ] No external CLI or browser launched.
- [ ] Test asserts safe fallback.

**Connects To:** Story 18, where audit logging records final decisions.

## Story 4: Show APPLYPILOT_DIR In Doctor Output

**Difficulty:** Easy

**Estimated Time:** 1.5 hours

**User Story:** As a user, I want `applypilot doctor` to show which runtime directory it is checking so that I know where profile, logs, and database files live.

**Product Value:** Many confusing local issues come from looking in the wrong directory.

**Acceptance Criteria:**
- [ ] `applypilot doctor` prints the resolved `APP_DIR`.
- [ ] Output shows whether it came from default home path or `APPLYPILOT_DIR`.
- [ ] Does not create or modify user files beyond normal bootstrap.
- [ ] Existing doctor checks still display.

**Files You Will Likely Touch:**
- `src/applypilot/cli.py`: `doctor()` output.
- `src/applypilot/config.py`: read `APP_DIR`, possibly env var.

**Relevant Code To Study First:**
- `src/applypilot/cli.py:295-359`
- `src/applypilot/config.py:11-29`

**Detailed Implementation Plan:**
1. Open `src/applypilot/cli.py`.
2. Find `def doctor()`.
3. Import `APP_DIR` from `applypilot.config` near the existing `get_chrome_path` import.
4. Determine whether `os.environ.get("APPLYPILOT_DIR")` is set.
5. Add a Rich table row or short section showing the resolved path.
6. Keep the style consistent with existing doctor output.
7. Run `applypilot doctor` manually.

**Testing And Verification:**
- Manual: run with and without `APPLYPILOT_DIR`.
- Optional test later: use Typer runner and `monkeypatch.setenv`.

**Tips:**
- Avoid expanding this story into directory writability checks; that is Story 5.
- Use `str(APP_DIR)` for display.

**What Could Go Wrong:**
- Importing config before env loading could show stale values if env is expected to change at runtime.
- Output becomes too noisy.

**Review Checklist:**
- [ ] Clear path display.
- [ ] No unrelated doctor behavior changes.

**Connects To:** Story 5.

## Story 5: Add Runtime Directory Writability Checks To Doctor

**Difficulty:** Easy-Medium

**Estimated Time:** 2.5 hours

**User Story:** As a user, I want `applypilot doctor` to tell me whether runtime directories are writable so that I can fix permissions before running the pipeline.

**Product Value:** ApplyPilot writes SQLite DBs, logs, tailored resumes, cover letters, Chrome worker data, and agent artifacts. Permission failures can otherwise appear later in confusing places.

**Acceptance Criteria:**
- [ ] Doctor checks `APP_DIR`, `LOG_DIR`, `TAILORED_DIR`, `COVER_LETTER_DIR`, and `APPLY_WORKER_DIR`.
- [ ] Each check reports OK or error.
- [ ] Probe files are cleaned up.
- [ ] Permission failure does not crash `doctor`.

**Files You Will Likely Touch:**
- `src/applypilot/cli.py`: add doctor output.
- `src/applypilot/config.py`: directory constants already live here.

**Relevant Code To Study First:**
- `src/applypilot/cli.py:295-359`
- `src/applypilot/config.py:22-29`
- `src/applypilot/config.py:300-303`

**Detailed Implementation Plan:**
1. Open `src/applypilot/cli.py`.
2. Inside `doctor()`, import directory constants from `applypilot.config`.
3. Write a small helper inside `doctor()` or near helpers:
   - receives a `Path`
   - ensures directory exists or checks existing path
   - writes a small probe file like `.applypilot-write-test`
   - deletes the probe file in a `finally` block
   - returns `(ok, detail)`
4. Add rows to the existing Rich doctor table.
5. Catch `OSError` and display the exception message.
6. Manually run `applypilot doctor`.
7. If you add a helper function, consider a unit test with `tmp_path`.

**Testing And Verification:**
- Manual doctor run.
- Unit test for helper if extracted.

**Tips:**
- Do not leave probe files behind.
- Do not write inside real user directories in automated tests.
- Keep checks fast.

**What Could Go Wrong:**
- Probe file cleanup fails.
- A permission error stops the whole command.
- The helper modifies real data.

**Review Checklist:**
- [ ] Uses `try/finally`.
- [ ] Safe around `OSError`.
- [ ] No secrets displayed.

**Connects To:** Story 14, where artifact manifests depend on reliable runtime paths.

## Story 6: Add Apply Status Filter To HTML Dashboard

**Difficulty:** Medium-Easy

**Estimated Time:** 3 hours

**User Story:** As a job seeker, I want to filter the HTML dashboard by apply status so that I can quickly inspect failed, applied, manual, and pending applications.

**Product Value:** The dashboard becomes an operations console, not just a score list.

**Acceptance Criteria:**
- [ ] Dashboard query includes `apply_status`.
- [ ] Each job card includes a status data attribute.
- [ ] UI filter supports all, pending, applied, failed, manual, and in-progress.
- [ ] Existing score and text filters still work.

**Files You Will Likely Touch:**
- `src/applypilot/view.py`: generated HTML dashboard.

**Relevant Code To Study First:**
- `src/applypilot/view.py:25-82`
- `src/applypilot/view.py:360-385`
- `src/applypilot/database.py:123-132`

**Detailed Implementation Plan:**
1. Open `src/applypilot/view.py`.
2. Find the SQL query selecting jobs for dashboard cards.
3. Add `apply_status` to the SELECT list.
4. Find the code that builds each job card.
5. Add `data-apply-status="{status}"`, using `pending` when status is empty.
6. Add a filter control near existing score/search controls.
7. Extend `applyFilters()`:
   - read selected apply status
   - compare against `card.dataset.applyStatus`
   - combine with score and text matches
8. Generate the dashboard manually.
9. Test cards with no status, failed status, and applied status.

**Testing And Verification:**
- Manual: call `applypilot dashboard`, open generated HTML, test filters.
- Optional: add a smoke test that generated HTML contains `data-apply-status`.

**Tips:**
- Escape text before inserting into HTML.
- Keep default behavior as "show all."
- Treat missing status as `pending`.

**What Could Go Wrong:**
- Existing search filter stops working.
- Empty statuses are hidden accidentally.
- HTML string changes break layout.

**Review Checklist:**
- [ ] Dashboard still loads.
- [ ] Filter combinations work.
- [ ] No schema change.

**Connects To:** Story 9.

## Story 7: Add JSON Output To Status Command

**Difficulty:** Medium-Easy

**Estimated Time:** 3 hours

**User Story:** As a power user, I want `applypilot status --json` so that I can script or save pipeline health snapshots.

**Product Value:** JSON output makes status useful in automation, debugging, and future monitoring.

**Acceptance Criteria:**
- [ ] `applypilot status --json` prints valid JSON.
- [ ] JSON includes the same stats returned by `get_stats()`.
- [ ] Rich tables are not printed when `--json` is used.
- [ ] Default `applypilot status` remains unchanged.

**Files You Will Likely Touch:**
- `src/applypilot/cli.py`: add option to `status()`.
- Possibly `tests/`: add CLI or function-level test if infrastructure exists.

**Relevant Code To Study First:**
- `src/applypilot/cli.py:362-425`
- `src/applypilot/database.py:222-320`

**Detailed Implementation Plan:**
1. Open `src/applypilot/cli.py`.
2. Add a parameter to `status()`:
   - `json_output: bool = typer.Option(False, "--json", help="...")`
3. After `stats = get_stats()`, add an early branch:
   - if `json_output`, use `json.dumps(stats, indent=2, default=str)`
   - print to console or standard output
   - return
4. Ensure Rich table code only runs when JSON is false.
5. Add `import json` inside the branch or at top.
6. Manually run `applypilot status --json`.
7. Validate output with `python -m json.tool` if desired.

**Testing And Verification:**
- Manual JSON parse.
- Optional Typer runner test later.

**Tips:**
- Do not mutate stats for display.
- Watch for tuples in `score_distribution` or `by_site`; JSON converts tuples to arrays.
- Avoid printing Rich markup in JSON mode.

**What Could Go Wrong:**
- JSON output includes Rich formatting.
- Non-serializable objects sneak into stats later.

**Review Checklist:**
- [ ] Default output unchanged.
- [ ] JSON is parseable.

**Connects To:** Story 8.

## Story 8: Add Failed Apply Report Command

**Difficulty:** Medium-Easy

**Estimated Time:** 4 hours

**User Story:** As a job seeker, I want a failed-apply report grouped by reason so that I know whether failures are caused by CAPTCHA, expired jobs, blocked domains, or login issues.

**Product Value:** Users need actionable failure categories, not a pile of failed rows.

**Acceptance Criteria:**
- [ ] New command or `status` section groups failed applications by `apply_error`.
- [ ] Each group includes count and one example URL/title.
- [ ] Does not display profile data, resume text, or prompts.
- [ ] Aggregation logic lives outside CLI display code.

**Files You Will Likely Touch:**
- `src/applypilot/database.py`: add report helper.
- `src/applypilot/cli.py`: display report.
- `tests/`: add DB helper test.

**Relevant Code To Study First:**
- `src/applypilot/database.py:222-320`
- `src/applypilot/cli.py:362-425`
- `src/applypilot/apply/launcher.py:277-298`

**Detailed Implementation Plan:**
1. In `database.py`, add `get_apply_failure_report(conn=None) -> list[dict]`.
2. Query rows where `apply_status = 'failed'` or `apply_error IS NOT NULL`.
3. Group by normalized reason:
   - start simple: use first segment before `:` from `apply_error`
   - example: `domain_not_allowed:foo.com` becomes `domain_not_allowed`
4. Return list of dictionaries:
   - `reason`
   - `count`
   - `example_title`
   - `example_url`
5. In `cli.py`, add command `apply-failures` or option under `status`.
6. Render a Rich table.
7. Add a test using temporary DB rows.
8. Run targeted DB tests.

**Testing And Verification:**
- Unit: seed failed rows and assert grouped output.
- Manual: run command against local DB.

**Tips:**
- Keep raw long errors out of table columns.
- Do not include personal fields.
- Keep grouping logic testable in `database.py`.

**What Could Go Wrong:**
- Grouping by exact full error creates too many categories.
- Display leaks long URLs or sensitive text.
- CLI grows too much if report logic is placed there.

**Review Checklist:**
- [ ] Aggregation tested.
- [ ] Display safe and short.

**Connects To:** Story 18.

