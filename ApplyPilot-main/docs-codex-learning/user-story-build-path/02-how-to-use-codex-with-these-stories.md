# How To Use Codex With These Stories

## Start With Story 1

Read the story twice. Before opening Codex, write:

- the user-facing behavior
- the likely file
- the smallest possible change
- how you will verify it

Then open the cited file and find the exact line range. Only after that should you ask Codex for a hint.

## Ask For Hints Instead Of Full Solutions

Good prompt:

```text
I am working on Story 1. I found status() in src/applypilot/cli.py. I think the display table is built around lines 373-390. Ask me what stat key I should reuse before showing code.
```

Bad prompt:

```text
Implement Story 1.
```

## Ask Codex To Explain Existing Patterns Before Code

```text
Explain how tests in tests/test_apply_launcher.py isolate the database. Do not write new tests yet. After explaining, ask me how I would adapt the pattern for my story.
```

## Ask Codex To Review Your Attempt

```text
Review my diff for Story 6. Prioritize behavior regressions, missing tests, database state mistakes, and unrelated changes. Do not rewrite the solution unless there is a bug.
```

## Ask Codex To Create Tests After You Implement

```text
I implemented the behavior for Story 8. Before writing tests, ask me which invariant needs protection. Then suggest the smallest pytest that proves preview is read-only.
```

## Ask Codex To Explain A Diff

```text
Explain this diff like a code reviewer. For each changed file, tell me the contract it affects, the risk, and the test that should cover it.
```

## Prevent Codex From Making Unrelated Changes

Use explicit scope:

```text
Only inspect and modify src/applypilot/cli.py and tests needed for Story 1. Do not refactor unrelated code. Do not change existing docs.
```

## Checklist Before Accepting AI-Generated Code

- Does the change touch only expected files?
- Does it preserve existing public command behavior?
- Does it update SQLite state intentionally?
- Does it avoid real user data in tests?
- Does it add tests for risky behavior?
- Can you explain every changed line?

## Checklist Before Opening A PR

- Run targeted tests.
- Run `git diff --stat`.
- Read the full diff.
- Confirm no generated runtime files are included.
- Explain the user story and acceptance criteria in the PR.
- Mention any manual verification.

## Example Prompts

Understanding a file:

```text
Walk me through src/applypilot/apply/launcher.py:174-271. Pause after each block and ask me what invariant it protects.
```

Tracing a bug:

```text
Dry runs appear to disappear from the apply queue. Help me trace likely state transitions. Ask for evidence before proposing fixes.
```

Planning a change:

```text
I want to add an apply preview command. Help me identify the minimal files and tests. Do not write implementation code yet.
```

Reviewing a diff:

```text
Review this diff for hidden behavior changes. Focus on SQLite state, retry behavior, personal-data risk, and test gaps.
```

Writing tests:

```text
Help me write a pytest for this behavior using the existing tmp_path and monkeypatch patterns. Explain why each assertion matters.
```

Hints only:

```text
Give me one hint at a time. After each hint, wait for my attempt before giving the next.
```
