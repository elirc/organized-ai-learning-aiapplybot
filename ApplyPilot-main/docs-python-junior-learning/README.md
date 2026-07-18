# Python Junior Learning Guide For ApplyPilot

This folder is a tutorial for learning Python and learning this codebase at the same time.

It assumes you are not yet comfortable building complex software independently. That is fine. The goal is to train the exact muscles you need:

- read unfamiliar Python files without panic
- understand functions, dictionaries, classes, dataclasses, type hints, imports, and tests
- trace one feature through CLI input, business logic, SQLite state, files, subprocesses, and output
- learn what senior engineers look for when reviewing code
- practice with fake examples before touching real production code

ApplyPilot is a Python CLI automation app. It is not a React/Node/TypeScript app. Its main user interface is the `applypilot` command declared in `pyproject.toml:34-35` and implemented in `src/applypilot/cli.py:22-438`. Its durable state lives in a local SQLite database created in `src/applypilot/database.py:62-140`.

## How To Read This Tutorial

Read in this order:

1. `00-learning-map.md`
2. `01-python-basics-with-applypilot-examples.md`
3. `02-how-to-read-a-python-file.md`
4. `03-the-applypilot-system-map.md`
5. `04-data-state-and-sqlite.md`
6. `05-cli-pipeline-and-feature-flow.md`
7. `06-agents-browser-and-llm-boundaries.md`
8. `07-testing-debugging-and-review.md`
9. `08-practice-labs.md`

Each file mixes:

- real code references from this repo
- fake code examples to teach the idea gently
- "read this like an engineer" notes
- practice exercises
- self-grading rubrics

## What This Folder Is Not

This is not a replacement for the existing README or architecture docs. It is a hands-on learning curriculum. It intentionally repeats some core ideas in different ways because beginners need repetition with variation.

## The Core Mental Model

Think of ApplyPilot as a job application assembly line:

```text
discover jobs
  -> enrich job details
  -> score fit
  -> tailor resume
  -> generate cover letter
  -> create PDFs
  -> auto-apply with browser agents
```

The conveyor belt is the `jobs` table in SQLite. Each stage adds more fields to a job row. You can see that table design in `src/applypilot/database.py:90-133`.

