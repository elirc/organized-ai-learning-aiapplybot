# Product User Stories For ApplyPilot

This folder contains 25 implementation-ready user stories for ApplyPilot. They are written as if a product owner were assigning progressively harder work to a mid-level engineer, but each implementation plan is detailed enough for a junior developer to follow carefully.

No story in this folder has been implemented. These are plans only.

## How To Use These Stories

For each story:

1. Read the product goal.
2. Open every file listed under "Files You Will Likely Touch."
3. Write your own one-paragraph implementation plan before reading the provided plan.
4. Compare your plan to the provided plan.
5. Implement in a branch only when you are ready.
6. Run the listed tests or verification steps.
7. Ask for code review before merging.

## Difficulty Progression

- Stories 1-5: small CLI, text, parser, or validation improvements.
- Stories 6-10: reporting and read-only features that use existing data.
- Stories 11-17: medium features that add command options, helper functions, or artifact metadata.
- Stories 18-22: hard features involving new state, recovery behavior, privacy, or workflow checkpoints.
- Stories 23-25: expert-level product features with architectural implications.

## Important Product Rule

ApplyPilot automates job applications. That means safety, privacy, and user trust are product requirements, not optional engineering polish. Any feature that changes auto-apply behavior should be reviewed for:

- accidental submissions
- repeated submissions
- leaked personal data
- unsafe domains
- retry loops
- poor failure visibility

## Core Code Anchors

- CLI commands: `src/applypilot/cli.py`
- Pipeline stages: `src/applypilot/pipeline.py`
- SQLite state: `src/applypilot/database.py`
- Apply workflow: `src/applypilot/apply/launcher.py`
- Agent result parsing: `src/applypilot/apply/agents/parsing.py`
- Prompt construction: `src/applypilot/apply/prompt.py`
- Rich apply dashboard: `src/applypilot/apply/dashboard.py`
- HTML dashboard: `src/applypilot/view.py`
- Config normalization: `src/applypilot/config.py`
- Tests: `tests/`

## Files

- `01-stories-01-08.md`: early stories and first medium reporting features.
- `02-stories-09-17.md`: medium workflow and artifact stories.
- `03-stories-18-25.md`: hard and expert architecture stories.

