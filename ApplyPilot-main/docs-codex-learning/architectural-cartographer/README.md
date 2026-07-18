# Architectural Cartographer

This suite is the top-down architecture guide. It teaches you how ApplyPilot is organized, how work moves through the system, and how a stronger engineer reads the repo without getting lost.

Use it when you want to answer:

- What kind of system is this?
- Where does execution start?
- What owns durable state?
- Which files are coordination layers and which files do domain work?
- Where would bugs, security risks, and scaling limits appear first?

## Who This Is For

This is for a developer moving from "I can read functions" toward "I can reason about a system." The codebase is a good training ground because it includes CLI routing, pipeline orchestration, SQLite persistence, browser automation, LLM integration, config normalization, and tests.

## Reading Order

1. `JOURNAL.md` for the inspection story.
2. `00-reading-map.md` for the shortest path through the repo.
3. `01-junior-engineer.md` for setup, folders, entry points, and code anatomy.
4. `02-mid-level-engineer.md` for feature tracing and architecture relationships.
5. `03-senior-engineer.md` for critique, risk, performance, security, and ownership.
6. `04-reference-suite.md` for reusable onboarding, review, debugging, and interview guides.

## How To Work Through Checkpoints

Answer each checkpoint in your own words before reading the self-grade. A strong answer should cite at least one file and explain not only "what happens" but "why this design protects or risks the system."

## How This Differs From The Other Suites

The mission suite is active training. The user-story suite is implementation planning. The technology suite studies individual tools. This suite is the map of the whole terrain.
