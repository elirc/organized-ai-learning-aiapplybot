# Reference Artifacts

### Mission 25: Write The Docs That Don't Exist

**Tier:** Senior

**Time Estimate:** 90 minutes

**Goal:** Practice creating documentation that teaches ownership, not just usage.

**The Concept:** Documentation is an engineering tool. In a job-application pipeline, a good doc is like a handoff note between recruiters: it explains state, next action, risk, and evidence.

**Design Intent Before You Read the Code:** The best docs cite the code and help a future engineer make safe decisions.

**Find It In The Code:** Use `src/applypilot/cli.py:22-220`, `src/applypilot/database.py:90-133`, `src/applypilot/pipeline.py:35-165`, and `src/applypilot/apply/launcher.py:174-731`.

```text
Write a one-page guide that answers:
1. What command starts this flow?
2. Which rows are affected?
3. Which external systems are touched?
4. What can fail?
5. What test proves the behavior?
```

**The Aha Moment:** A useful doc teaches the next engineer how to think.

**Socratic Checkpoint:** What is the audience? What code evidence matters? What risk should be visible? What is intentionally omitted? How would you know the doc worked?

**How to Self-Grade:** Strong answers are specific, cited, and actionable.

**Connects To:** Your first real PR.

## Doc 1: Junior Onboarding Checklist

Day 1 actions:

- Install with `pip install -e .`.
- Run `applypilot doctor`.
- Read `pyproject.toml:20-35`.
- Read `src/applypilot/cli.py:22-45`.
- Read `src/applypilot/database.py:90-133`.

First PR checklist:

- Name the owning command or stage.
- Identify DB columns touched.
- Add or update a focused test.
- Avoid real `~/.applypilot` data in tests.
- Run targeted pytest.

Questions to ask:

- Which stage owns this behavior?
- Is this safe to retry?
- Does this touch personal data?

## Doc 2: Architecture Guide For New Engineers

Navigate from user action inward:

`CLI command -> pipeline or launcher -> domain module -> SQLite/files -> display/logs`

Do not get lost by reading `smartextract.py` first. Start with stage definitions in `src/applypilot/pipeline.py:35-44`, then read the schema.

## Doc 3: Code Review Checklist

Check first:

- CLI and stage contract.
- DB state transition.
- External side effects.
- Safety controls.

Check last:

- Logs and user-visible messages.
- Test coverage.
- Backward compatibility with existing local DBs and config files.

## Doc 4: Debugging Playbook

For "nothing happened":

1. Run `applypilot status`.
2. Check if rows match the stage's pending SQL in `src/applypilot/pipeline.py:222-241`.
3. Check logs under `~/.applypilot/logs`.
4. Check env/provider setup in `src/applypilot/llm.py:22-53`.

For "apply failed":

1. Inspect `apply_status` and `apply_error`.
2. Read worker log.
3. Read agent raw log.
4. Check parser fallback in `src/applypilot/apply/agents/parsing.py:74-87`.

## Doc 5: Change Playbook

Workflow:

1. Branch.
2. Write a small plan.
3. Find owning files.
4. Add a test for the risky behavior.
5. Implement narrowly.
6. Run targeted tests.
7. Review diff for unrelated changes.
8. Explain state transitions in PR.

## Doc 6: Senior Ownership Notes

Monitor:

- Apply success/failure categories.
- Parser fallbacks to `NEEDS_REVIEW`.
- LLM timeout and retry behavior.
- Browser cleanup failures.
- User data in logs.

Improve:

- Typed job rows.
- More safety tests.
- Redaction policy.
- Smaller `run_job()` units.

Leave alone:

- The simple stage vocabulary unless product workflow changes.
- SQLite for local-only use until distributed needs are real.

## Doc 7: Interview Walkthrough

Practice answer:

"This is a Python CLI pipeline. Typer exposes commands, the pipeline module coordinates six stages, SQLite stores job progress, LLM modules score and tailor applications, and the apply module launches isolated Chrome workers controlled by Claude or Codex CLI agents. The design trade-off is local simplicity versus distributed scalability."

Follow-up trade-offs:

- SQLite is pragmatic for local automation.
- Agent abstraction makes backend switching easier.
- Browser automation is powerful but risky, so dry-run and allowlists matter.
- Tests cover core parsing and launcher state, but external integration paths still need careful fixtures.
