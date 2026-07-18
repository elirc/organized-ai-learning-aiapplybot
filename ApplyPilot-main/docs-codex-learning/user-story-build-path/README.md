# User Story Build Path

This suite gives you ten realistic features to build later. They are not implemented here. Each story is grounded in ApplyPilot's actual domain: job discovery, scoring, tailoring, generated artifacts, auto-apply safety, dashboard visibility, and local configuration.

## Difficulty Progression

- Stories 1-3: small UI/config/validation changes touching 1-2 files.
- Stories 4-5: medium UI or reporting features touching 3-4 files.
- Stories 6-7: new behavior requiring state, validation, or integration points.
- Stories 8-9: full pipeline changes touching DB, CLI, and domain modules.
- Story 10: architectural feature with safety/observability implications.

## How To Know A Story Is Done

A story is done when:

- acceptance criteria are independently verifiable
- the touched files match the intended scope
- tests or manual checks prove the behavior
- `git diff` has no unrelated changes
- you can explain the state transition out loud

## How To Use Codex Without Blind Pasting

Use this model prompt:

```text
I'm working on Story X. I'm stuck on Y. Here is what I've tried: Z. Do not give me the solution immediately. Ask me questions that help me reason through the problem. Point me to the relevant files and patterns. Give hints in stages.
```

Before accepting AI-generated code:

- Ask which invariant the code protects.
- Ask why each file was touched.
- Compare the diff to existing patterns.
- Run targeted tests.
- Reject broad refactors that are not required by the story.
