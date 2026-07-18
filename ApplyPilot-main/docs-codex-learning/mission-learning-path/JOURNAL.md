# Mission Design Journal

## Design Rationale

The missions follow the system the way an engineer should learn it: entry point, folders, contracts, UI surfaces, core functions, data flow, routing/execution, state, abstractions, side effects, boundaries, feature trace, diff review, composition, type discipline, architecture critique, bugs, performance, security, tests, and git history.

Because this repo is Python rather than React/TypeScript/Node, missions were adapted around Python equivalents:

- Typer CLI instead of frontend routes.
- SQLite rows instead of React Query cache or ORM entities.
- Rich/HTML dashboards instead of React components.
- Function/module contracts instead of REST controllers.
- Agent runner Protocols instead of TypeScript interfaces.

## Why Missions Are Ordered This Way

Junior missions teach navigation and simple contracts. Mid-level missions teach ownership boundaries and data movement. Senior missions teach skepticism: performance, security, missing tests, and architecture decisions.

## Chosen Code Paths

- CLI: `src/applypilot/cli.py:22-220`.
- Pipeline: `src/applypilot/pipeline.py:35-165`, `src/applypilot/pipeline.py:222-480`.
- Database: `src/applypilot/database.py:20-219`, `src/applypilot/database.py:329-427`.
- Config: `src/applypilot/config.py:11-33`, `src/applypilot/config.py:129-238`, `src/applypilot/config.py:300-440`.
- Apply launcher: `src/applypilot/apply/launcher.py:174-731`.
- Agent runners: `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/apply/agents/parsing.py:13-87`.
- Tests: `tests/test_apply_launcher.py:17-122`, `tests/test_agent_parsing.py:4-24`.

## What A Senior Would Do Differently

A senior does not only ask "where is the code?" They ask:

- What invariant is this file protecting?
- What is trusted and untrusted input?
- What happens on retry, timeout, partial failure, or interruption?
- Which tests prove the behavior?
- Which part would become painful if the product grew?

## Gaps That Changed Mission Design

No React, Next.js, Express, NestJS, GraphQL, Prisma, TypeORM, Redux, Zustand, React Query, or REST controllers were found. The missions explain those absences and train equivalent full-stack judgment through CLI, SQLite, browser automation, LLM boundaries, and pytest.
