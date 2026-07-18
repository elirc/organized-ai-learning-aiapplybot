# User Story Journal

## Why These Stories Were Chosen

The stories follow real ApplyPilot product value: making job status clearer, improving safety around auto-apply, surfacing better diagnostics, and extending the pipeline without rewriting it.

They are ordered so a junior can start with display/validation work before touching database schema, concurrency, browser agents, or LLM boundaries.

## Domain Mapping

- Job seekers need confidence about what the tool will apply to.
- High-fit jobs should be easy to inspect.
- Failed applications need understandable reasons.
- Auto-apply should be cautious, observable, and retryable.
- Generated resumes and cover letters need traceability.

## Safest Stories First

Stories 1-3 are safest because they mainly touch display text, dashboard filtering, or config validation. They do not require new database columns or external browser/LLM calls.

## Deeper Architecture Stories

Stories 8-10 require understanding `database.py`, `pipeline.py`, `apply/launcher.py`, and tests. A senior would watch for migration compatibility, personal-data leakage, retry semantics, and unintended real submissions.

## Repeated Files And Patterns

- `src/applypilot/cli.py` for user-facing command options.
- `src/applypilot/database.py` for durable state.
- `src/applypilot/pipeline.py` for stage orchestration.
- `src/applypilot/apply/launcher.py` for apply behavior.
- `src/applypilot/apply/agents/parsing.py` for result normalization.
- `tests/test_apply_launcher.py` and `tests/test_agent_parsing.py` for focused tests.

## What A Senior Would Watch For

- Does this feature alter retry behavior?
- Does it expose sensitive profile data?
- Does it make external automation more aggressive?
- Does it preserve existing local databases?
- Does it add a test at the right boundary?
