# Cross-Cutting Engineering Lessons

## Separation Of Concerns

Concept: Put command parsing, config, persistence, orchestration, and domain work in different places.

Where it appears: `src/applypilot/cli.py`, `src/applypilot/config.py`, `src/applypilot/database.py`, `src/applypilot/pipeline.py`.

Junior miss: they may jump straight into the largest module.

Senior notice: `run_job()` in `src/applypilot/apply/launcher.py:416-568` is a natural future split point because it prepares files, builds prompts, selects backends, maps outcomes, and logs.

Practice: Draw the owner for each side effect in Stage 6.

## Type Safety

Concept: Make contracts visible.

Where it appears: `src/applypilot/apply/agents/base.py:10-36` uses dataclasses, Literal, and Protocol.

Junior miss: they may think Python type hints are only editor hints.

Senior notice: typed agent results are strong, but `job: dict` in `src/applypilot/apply/launcher.py:416-428` is a weak contract.

Practice: Draft a `TypedDict` for an apply-ready job row.

## Validation Boundaries

Concept: Treat user input, external sites, and LLM output as untrusted.

Where it appears:

- Config normalization: `src/applypilot/config.py:129-238`.
- LLM JSON validation: `src/applypilot/scoring/validator.py:93-165`.
- Agent output parsing: `src/applypilot/apply/agents/parsing.py:74-87`.

Junior miss: they may trust a successful LLM response.

Senior notice: validation is layered: prompts constrain, parsers normalize, validators reject, DB status records outcomes.

Practice: Add a test for one invalid LLM resume field.

## API Design

Concept: APIs are boundaries, not necessarily HTTP.

Where it appears: `AgentRunner.run()` in `src/applypilot/apply/agents/base.py:32-36`.

Junior miss: they may say "there is no API" because there are no routes.

Senior notice: module APIs matter as much as web APIs in a local CLI.

Practice: Describe the runner API in five sentences.

## State Management

Concept: Durable state, transient state, and artifacts need different homes.

Where it appears:

- Durable DB: `src/applypilot/database.py:90-133`.
- Runtime paths: `src/applypilot/config.py:11-29`.
- Dashboard memory state: `src/applypilot/apply/dashboard.py:41-88`.

Junior miss: they may not see SQLite as state management.

Senior notice: SQLite is also acting as a queue and audit surface.

Practice: For each job column, name which stage writes it.

## Data Fetching

Concept: External data fetching needs retries, filtering, and partial failure handling.

Where it appears:

- JobSpy lazy import and retry: `src/applypilot/discovery/jobspy.py:21-85`.
- Enrichment extraction cascade: `src/applypilot/enrichment/detail.py:529-604`.

Junior miss: they may expect one happy-path scraper.

Senior notice: the cascade reduces LLM dependency by trying JSON-LD and deterministic extraction first.

Practice: Trace what happens when enrichment finds an apply URL but no description.

## Database Access

Concept: Keep schema and migrations centralized.

Where it appears: `src/applypilot/database.py:62-219`.

Junior miss: they may add columns only to an `INSERT`.

Senior notice: `_ALL_COLUMNS` is a custom migration registry; changing schema means changing both creation and migration behavior.

Practice: Plan a new audit table without writing code.

## Error Handling

Concept: Failures should become useful status, not mystery crashes.

Where it appears:

- Stage runner exceptions become status dicts in `src/applypilot/pipeline.py:62-154`.
- Agent timeout becomes `RESULT:FAILED:timeout` in `src/applypilot/apply/agents/codex_runner.py:120-124`.
- Parser fallback becomes `NEEDS_REVIEW` in `src/applypilot/apply/agents/parsing.py:74-87`.

Junior miss: they may only read success paths.

Senior notice: the best failures are durable and actionable.

Practice: Pick one exception path and write the expected user-visible symptom.

## Testing Strategy

Concept: Test the boundary where behavior matters.

Where it appears:

- Parser behavior: `tests/test_agent_parsing.py:4-24`.
- Job claiming: `tests/test_apply_launcher.py:17-108`.
- Config normalization: `tests/test_config_normalization.py:8-109`.

Junior miss: they may mock too much or test implementation details.

Senior notice: path monkeypatching prevents tests from touching real user data.

Practice: Write a test plan for `domain_allowlist`.

## Production Readiness

Concept: Local automation can be production-oriented even without a server.

Where it appears:

- `doctor`: `src/applypilot/cli.py:295-359`.
- Runtime logs: `src/applypilot/apply/launcher.py:455-475`.
- Safety flags: `src/applypilot/cli.py:137-146`.

Junior miss: production-readiness is not only Kubernetes or cloud.

Senior notice: safety and observability matter more than deployment complexity here.

Practice: List three checks `doctor` should add.

## Security Posture

Concept: Automating applications requires privacy and submission safety.

Where it appears:

- Profile fields: `src/applypilot/config.py:36-80`.
- Prompt hard rules: `src/applypilot/apply/prompt.py:188-213`.
- Dry-run and final output controls: `src/applypilot/apply/prompt.py:520-565`.
- Codex sandbox bypass: `src/applypilot/apply/agents/codex_runner.py:63-74`.

Junior miss: they may focus on code correctness and miss user harm.

Senior notice: the application submission moment is a security boundary.

Practice: Review one log file path and decide what must not be written there.

## Performance

Concept: Optimize only after identifying the bottleneck and safety trade-off.

Where it appears:

- Streaming threads: `src/applypilot/pipeline.py:376-436`.
- Sequential scoring: `src/applypilot/scoring/scorer.py:139-161`.
- Per-job Chrome lifecycle: `src/applypilot/apply/launcher.py:671-721`.

Junior miss: they may parallelize without rate limits.

Senior notice: slow but safe may be correct for submissions.

Practice: Design metrics for apply throughput.

## Developer Experience

Concept: Good local tooling reduces support burden.

Where it appears:

- README setup: `README.md:83-139`.
- `doctor`: `src/applypilot/cli.py:295-359`.
- pytest examples: `tests/`.

Junior miss: DX is part of engineering quality.

Senior notice: `doctor` should grow as external dependencies grow.

Practice: Add a checklist for diagnosing missing Playwright.

## Configuration Management

Concept: Config should be normalized once and consumed consistently.

Where it appears: `src/applypilot/config.py:129-238`, `src/applypilot/config.py:319-394`.

Junior miss: they may parse YAML directly in feature code.

Senior notice: normalization protects older user files.

Practice: Add a test for one legacy profile field.

## Dependency Management

Concept: Optional dependencies should fail gracefully.

Where it appears: JobSpy lazy import in `src/applypilot/discovery/jobspy.py:21-30` and `doctor` optional checks in `src/applypilot/cli.py:306-330`.

Junior miss: they may import optional packages at module import time.

Senior notice: graceful missing-dependency errors improve CLI reliability.

Practice: Write a missing-dependency test like `tests/test_jobspy_discovery.py`.
