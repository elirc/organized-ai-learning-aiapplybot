# Tier 3 Senior Missions

### Mission 18: Reverse-Engineer The Architecture Decisions

**Tier:** Senior

**Time Estimate:** 75 minutes

**Goal:** Infer why the current architecture exists.

**The Concept:** Senior reading is archaeology. You infer the decisions from the structures left behind.

**Design Intent Before You Read the Code:** Local automation favors simple packaging, local files, SQLite, direct subprocesses, and explicit safety flags.

**Find It In The Code:** Open `README.md:1-37`, `src/applypilot/database.py:15-49`, `src/applypilot/pipeline.py:376-436`, and `src/applypilot/apply/agents/base.py:10-36`.

```text
Decision clues:
- SQLite instead of server DB: local-first tool.
- Typer instead of web UI: command workflows.
- Agent Protocol: multiple backends expected.
- Streaming threads instead of queue service: simple local concurrency.
```

**The Aha Moment:** Architecture is shaped by product constraints.

**Socratic Checkpoint:** Why Typer? Why SQLite? Why runner Protocol? Why local artifacts? Why not a hosted service?

**How to Self-Grade:** Strong answers explain trade-offs honestly, not as universal best practices.

**Connects To:** Mission 19 and Mission 24.

### Mission 19: Find The Bugs Before They Happen

**Tier:** Senior

**Time Estimate:** 70 minutes

**Goal:** Predict failure modes from code shape.

**The Concept:** Senior debugging starts before the bug report. Risk clusters around side effects, concurrency, external services, and weak contracts.

**Design Intent Before You Read the Code:** A safe auto-apply flow must protect against duplicate claims, bad domains, missing artifacts, external timeouts, and parse failures.

**Find It In The Code:** Open `src/applypilot/apply/launcher.py:174-271`, `src/applypilot/apply/prompt.py:452-468`, `src/applypilot/apply/agents/codex_runner.py:120-135`, and `src/applypilot/apply/agents/parsing.py:74-87`.

```python
# src/applypilot/apply/agents/parsing.py:74-87
if not text.strip():
    return ParsedOutcome(status="NEEDS_REVIEW", reason="empty_output", submitted=False)
...
return ParsedOutcome(status="NEEDS_REVIEW", reason="no_result_marker", submitted=False)
```

**The Aha Moment:** Good fallback states turn unknowns into reviewable outcomes.

**Socratic Checkpoint:** What happens on empty agent output? What happens when the PDF is missing? What happens if domain allowlist rejects a host? What happens on timeout? What can still be double-submitted?

**How to Self-Grade:** Strong answers list symptoms, owning files, and test ideas.

**Connects To:** Mission 20.

### Mission 20: The Bug Injection Challenge

**Tier:** Senior

**Time Estimate:** 60 minutes

**Goal:** Practice thinking from symptom to code path.

**The Concept:** A bug report is a shadow. Your job is to infer the object casting it.

**Design Intent Before You Read the Code:** Do not modify production code. Write test scenarios or notes only.

**Find It In The Code:** Use `tests/test_apply_launcher.py:17-122`, `tests/test_agent_parsing.py:4-24`, and `src/applypilot/apply/launcher.py:690-702`.

```text
Bug 1: Dry runs disappear from the queue.
Bug 2: Manual ATS jobs are retried forever.
Bug 3: A timeout leaves Chrome open.
Bug 4: Valid Codex JSON is ignored.
Bug 5: A high-score row is never picked because application_url is null.
```

**The Aha Moment:** You can design a failing test before knowing the fix.

**Socratic Checkpoint:** Which bug is a parser bug? Which is a DB state bug? Which is a cleanup bug? Which is a data eligibility bug? Which existing test is closest?

**How to Self-Grade:** Strong answers map each symptom to one file and one assertion.

**Connects To:** Mission 23.

### Mission 21: Performance X-Ray

**Tier:** Senior

**Time Estimate:** 60 minutes

**Goal:** Identify throughput bottlenecks.

**The Concept:** Performance is queue math. Which station is slow, and can the next station work while it waits?

**Design Intent Before You Read the Code:** Improve throughput without sacrificing application safety.

**Find It In The Code:** Open `src/applypilot/pipeline.py:376-436`, `src/applypilot/scoring/scorer.py:139-161`, and `src/applypilot/apply/launcher.py:671-727`.

```python
# src/applypilot/scoring/scorer.py:139-161
for job in jobs:
    result = score_job(resume_text, job)
...
conn.commit()
```

**The Aha Moment:** Some slow paths are intentionally simple because external side effects are risky.

**Socratic Checkpoint:** Which stages parallelize? Which are sequential? What is the cost of Chrome per job? What rate limit might LLM scoring hit? What should be measured before optimizing?

**How to Self-Grade:** Strong answers separate measurement, bottleneck, and risk.

**Connects To:** Mission 22.

### Mission 22: The Security Audit

**Tier:** Senior

**Time Estimate:** 80 minutes

**Goal:** Audit personal-data and automation risk.

**The Concept:** This app handles someone's identity and submits forms. Security is not abstract here; it is about preventing wrong submissions, leaks, and unsafe automation.

**Design Intent Before You Read the Code:** Sensitive data should have explicit boundaries and logs should be treated with caution.

**Find It In The Code:** Open `src/applypilot/config.py:36-80`, `src/applypilot/apply/prompt.py:188-235`, `src/applypilot/apply/prompt.py:520-565`, and `src/applypilot/apply/agents/codex_runner.py:63-74`.

```python
# src/applypilot/apply/prompt.py:520-531
if dry_run:
    submit_instruction = "Do NOT click..."
else:
    submit_instruction = "BEFORE clicking Submit/Apply, take a snapshot..."
```

**The Aha Moment:** The dangerous moment is not filling the form; it is deciding to submit.

**Socratic Checkpoint:** Which fields are sensitive? Where is CAPTCHA API key inserted? What does dry-run protect? Why is sandbox bypass risky? What should never be logged?

**How to Self-Grade:** Strong answers name concrete code paths and realistic mitigations.

**Connects To:** Mission 23.

### Mission 23: Write The Test That Doesn't Exist

**Tier:** Senior

**Time Estimate:** 70 minutes

**Goal:** Design a missing test without changing production code.

**The Concept:** Good tests pin behavior at the boundary where a regression would hurt users.

**Design Intent Before You Read the Code:** Choose a behavior with high consequence and controllable dependencies.

**Find It In The Code:** Open `tests/test_apply_launcher.py:17-122`, `src/applypilot/apply/launcher.py:430-433`, and `src/applypilot/apply/launcher.py:537-568`.

```text
Candidate test:
"run_job blocks non-allowlisted domains before building prompt or launching any agent."
```

**The Aha Moment:** The best test is often the smallest test around the most dangerous boundary.

**Socratic Checkpoint:** What dependency would you monkeypatch? What assertion proves no agent ran? What fake job fields are required? Where should the test live? What failure would this catch?

**How to Self-Grade:** Strong answers include setup, action, assertions, and why the test is stable.

**Connects To:** Mission 24.

### Mission 24: The Git History Tells A Story

**Tier:** Senior

**Time Estimate:** 45 minutes

**Goal:** Use git history to infer product evolution.

**The Concept:** Commits are fossils of decisions. They tell you what changed recently and where risk may cluster.

**Design Intent Before You Read the Code:** Recent refactors deserve extra review because they often contain new boundaries and compatibility layers.

**Find It In The Code:** Run `git log --oneline -n 8`. At inspection time, visible commits included `1383292 Add intern training docs and code walkthrough materials` and `ac7cbc5 Refactor auto-apply with Claude/Codex runners, guardrails, tests, and docs`.

```text
Read commit themes:
- training material added
- Stage 6 refactored
- agent abstraction introduced
- guardrails added
- tests added around runner behavior
```

**The Aha Moment:** Recent change areas are where your review attention should concentrate.

**Socratic Checkpoint:** What changed most recently? Which modules are likely newer? Which tests were added with the refactor? What would you inspect before modifying Stage 6? What architectural direction does history imply?

**How to Self-Grade:** Strong answers use history to prioritize review, not to blame code.

**Connects To:** Mission 25.
