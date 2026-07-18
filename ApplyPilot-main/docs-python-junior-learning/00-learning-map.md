# 00 - Learning Map

## What Kind Of Project Is This?

ApplyPilot is a Python package and command-line application. Evidence:

- `pyproject.toml:1-18` declares project metadata.
- `pyproject.toml:20-29` lists runtime dependencies like `typer`, `rich`, `httpx`, `playwright`, `python-dotenv`, `pyyaml`, and `pandas`.
- `pyproject.toml:34-35` declares the command-line entry point: `applypilot = "applypilot.cli:app"`.
- `src/applypilot/cli.py:22-31` creates the Typer CLI app and lists valid pipeline stages.

There is no React frontend, no Node.js backend, no TypeScript source, no REST controller, no GraphQL resolver, and no ORM like Prisma or TypeORM. The closest equivalents are:

| Web App Concept | ApplyPilot Equivalent | Evidence |
| --- | --- | --- |
| Frontend route | Typer command | `src/applypilot/cli.py:70-153` |
| Backend route/controller | Python function called by CLI | `src/applypilot/apply/launcher.py:174-271` |
| Database model | SQLite `jobs` table | `src/applypilot/database.py:90-133` |
| API client | `LLMClient` using `httpx` | `src/applypilot/llm.py:60-126` |
| UI component | Rich dashboard or generated HTML | `src/applypilot/apply/dashboard.py:22-190`, `src/applypilot/view.py:25-407` |
| State management | SQLite plus local files | `src/applypilot/config.py:11-29`, `src/applypilot/database.py:90-133` |

## Top 12 Files For A Junior Developer

1. `pyproject.toml:20-35`
   - Learn package dependencies and how the `applypilot` command starts.

2. `src/applypilot/__main__.py:1-5`
   - Learn how `python -m applypilot` delegates to the CLI.

3. `src/applypilot/cli.py:22-45`
   - Learn app setup and shared bootstrap.

4. `src/applypilot/cli.py:78-124`
   - Learn how `applypilot run` starts the pipeline.

5. `src/applypilot/config.py:11-29`
   - Learn where user data, logs, resumes, and DB files live.

6. `src/applypilot/config.py:129-238`
   - Learn how user profile and search config are normalized.

7. `src/applypilot/database.py:20-49`
   - Learn SQLite connections and thread-local storage.

8. `src/applypilot/database.py:90-133`
   - Learn the `jobs` table as the app's state machine.

9. `src/applypilot/pipeline.py:35-165`
   - Learn the six pipeline stages and how each stage is called.

10. `src/applypilot/scoring/scorer.py:72-100`
    - Learn a simple LLM-powered business function.

11. `src/applypilot/apply/agents/base.py:10-36`
    - Learn dataclasses and Protocols as contracts.

12. `tests/test_apply_launcher.py:8-122`
    - Learn how tests isolate a database and prove behavior.

## The Learning Route

### Phase 1: Learn Python Shapes

Focus on:

- variables
- functions
- dictionaries
- lists
- imports
- exceptions
- classes
- dataclasses
- type hints

You will practice these in `01-python-basics-with-applypilot-examples.md`.

### Phase 2: Learn The Codebase Skeleton

Focus on:

- entry points
- folders
- stage order
- SQLite schema
- config paths

You will practice this in `03-the-applypilot-system-map.md`.

### Phase 3: Learn Feature Tracing

Focus on:

- CLI input
- function call chain
- database read/write
- external side effect
- user-visible output

You will practice this in `05-cli-pipeline-and-feature-flow.md`.

### Phase 4: Learn Engineering Judgment

Focus on:

- what can fail
- how to test
- how to review
- how to debug
- how to change code safely

You will practice this in `07-testing-debugging-and-review.md` and `08-practice-labs.md`.

## A Simple Rule For Reading Any File

Before reading line by line, answer:

1. What does this file own?
2. Who calls it?
3. What does it read?
4. What does it write?
5. What can go wrong?
6. What tests protect it?

Example:

`src/applypilot/database.py` owns SQLite state. It is called by CLI bootstrap, pipeline stages, dashboard, tests, and apply launcher. It reads/writes `~/.applypilot/applypilot.db`. It can fail if schema changes are unsafe or tests touch real user state. It is partially protected by tests like `tests/test_apply_launcher.py:8-122`.

