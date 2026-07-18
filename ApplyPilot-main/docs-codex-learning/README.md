# Codex Learning Documentation

This folder is a permanent learning layer for this repository. It does not replace the existing README, architecture notes, or training docs. It gives you four different ways to study the same codebase so you can build stronger engineering judgment instead of only memorizing file names.

ApplyPilot is a Python CLI/package for an AI-assisted job application workflow. The main product path is:

`discover jobs -> enrich details -> score fit -> tailor resume -> generate cover letter -> convert PDFs -> auto-apply with browser agents`

The strongest teaching anchors are:

- `src/applypilot/cli.py:22-220`, where Typer commands become user-facing workflows.
- `src/applypilot/pipeline.py:35-165` and `src/applypilot/pipeline.py:222-480`, where pipeline stages are defined and orchestrated.
- `src/applypilot/database.py:20-219` and `src/applypilot/database.py:329-427`, where SQLite acts as the durable state machine.
- `src/applypilot/apply/launcher.py:174-330` and `src/applypilot/apply/launcher.py:416-731`, where Stage 6 claims jobs, launches Chrome, runs agents, and records outcomes.
- `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/apply/agents/parsing.py:13-87`, `src/applypilot/apply/agents/claude_runner.py:48-149`, and `src/applypilot/apply/agents/codex_runner.py:58-145`, where two CLI backends share one normalized contract.

## The Four Suites

| Suite | Use It When | What It Trains |
| --- | --- | --- |
| `architectural-cartographer/` | You want a top-down map of the system. | Codebase reading, architecture tracing, critique, debugging, ownership. |
| `mission-learning-path/` | You want active exercises. | Reading discipline, self-explanation, review instincts, debugging intuition. |
| `user-story-build-path/` | You want realistic feature tickets to implement later. | Planning, scoping, testing, safe changes, using Codex without outsourcing thought. |
| `technology-best-practices/` | You want to study the actual tools in this repo. | Python packaging, Typer, SQLite, Playwright, LLM clients, pytest, browser automation. |

## Recommended Reading Order

1. `architectural-cartographer/00-reading-map.md`
2. `architectural-cartographer/01-junior-engineer.md`
3. `mission-learning-path/01-tier-1-junior-missions.md`
4. `technology-best-practices/01-technology-map.md`
5. `user-story-build-path/01-stories.md`
6. `architectural-cartographer/02-mid-level-engineer.md`
7. `mission-learning-path/02-tier-2-mid-level-missions.md`
8. `technology-best-practices/02-real-code-patterns.md`
9. `architectural-cartographer/03-senior-engineer.md`
10. `mission-learning-path/03-tier-3-senior-missions.md`

## How To Use These Docs With Codex

Use Codex as a sparring partner, not a replacement brain. A strong learning loop looks like this:

1. Read the assigned code first.
2. Write your own explanation in 5-10 bullets.
3. Ask Codex to challenge your explanation.
4. Implement tiny practice changes only after you can predict which files will move.
5. Ask Codex for review after you make your own attempt.

Good prompt:

```text
I am studying src/applypilot/apply/launcher.py:174-271. Ask me questions that reveal whether I understand the job-claiming transaction. Do not explain it first. After I answer, grade my mental model and point me to the next file.
```

## How To Use The User Stories Without Letting AI Do All The Thinking

For each story:

- Write your own implementation plan before asking Codex anything.
- Name the expected files and the database columns involved.
- Ask for hints in stages.
- Let Codex review your diff, but make yourself explain every line it changes.
- Reject any AI-generated edit that touches files outside the story's likely scope without a clear reason.

## 30-Day Self-Study Rhythm

Days 1-5: orient to CLI, config, database, pipeline, and existing tests.

Days 6-10: trace discovery and enrichment into the `jobs` table.

Days 11-15: trace scoring, tailoring, validation, and PDF generation.

Days 16-20: trace auto-apply, Chrome workers, agent prompts, and result parsing.

Days 21-25: perform code review exercises and write missing tests in scratch branches.

Days 26-30: implement one user story from the build path, explain the architecture out loud, and ask Codex to review your trade-offs.

The point is not speed. The point is to build the engineer's habit of connecting behavior, code, data, tests, and risk.
