# 30-Day Technology Practice Plan

## Day 1

Focus area: package entry.

Files to read: `pyproject.toml:1-54`, `src/applypilot/__main__.py:1-5`.

Concept to understand: console scripts.

Small exercise: explain how `applypilot` starts.

Self-check question: Which file maps command name to Python object?

Optional Codex prompt for hints only: "Quiz me on how pyproject console scripts work in this repo."

## Day 2

Focus area: CLI bootstrap.

Files to read: `src/applypilot/cli.py:22-45`.

Concept to understand: shared startup invariants.

Small exercise: list what `_bootstrap()` prepares.

Self-check question: Why is DB init safe to run repeatedly?

Optional Codex prompt for hints only: "Ask me what each bootstrap call protects."

## Day 3

Focus area: stage commands.

Files to read: `src/applypilot/cli.py:78-124`.

Concept to understand: command validation.

Small exercise: trace invalid stage handling.

Self-check question: Where are LLM stages gated?

Optional Codex prompt for hints only: "Do not explain; ask me to locate stage validation."

## Day 4

Focus area: config paths.

Files to read: `src/applypilot/config.py:11-33`, `src/applypilot/config.py:300-394`.

Concept to understand: local runtime directories.

Small exercise: map each path to a user artifact.

Self-check question: How do tests avoid real `APP_DIR`?

Optional Codex prompt for hints only: "Help me make a path map from config.py."

## Day 5

Focus area: profile normalization.

Files to read: `src/applypilot/config.py:129-178`, `tests/test_config_normalization.py:8-42`.

Concept to understand: backward compatibility.

Small exercise: add a hypothetical legacy field mapping on paper.

Self-check question: Why not make every caller handle old shapes?

Optional Codex prompt for hints only: "Ask me why normalization belongs at load time."

## Day 6

Focus area: search config.

Files to read: `src/applypilot/config.py:181-238`, `tests/test_config_normalization.py:44-100`.

Concept to understand: config aliases.

Small exercise: explain `boards -> sites`.

Self-check question: What happens if location_accept is missing?

Optional Codex prompt for hints only: "Quiz me on search config normalization."

## Day 7

Focus area: SQLite schema.

Files to read: `src/applypilot/database.py:62-140`.

Concept to understand: schema as workflow map.

Small exercise: group columns by stage.

Self-check question: Which columns make a job apply-ready?

Optional Codex prompt for hints only: "Ask me to identify stage columns."

## Day 8

Focus area: DB connections.

Files to read: `src/applypilot/database.py:20-49`.

Concept to understand: thread-local SQLite.

Small exercise: explain WAL and busy timeout at a high level.

Self-check question: Why not share one connection across all threads?

Optional Codex prompt for hints only: "Give me one question at a time about SQLite connection safety."

## Day 9

Focus area: DB query helpers.

Files to read: `src/applypilot/database.py:365-427`.

Concept to understand: stage-based row selection.

Small exercise: write the pending-tailor condition in English.

Self-check question: Why does `min_score` matter only for some stages?

Optional Codex prompt for hints only: "Challenge my explanation of get_jobs_by_stage."

## Day 10

Focus area: pipeline registry.

Files to read: `src/applypilot/pipeline.py:35-165`.

Concept to understand: stage runner map.

Small exercise: draw stage order.

Self-check question: What does `_run_discover()` catch separately?

Optional Codex prompt for hints only: "Ask me to trace one stage runner."

## Day 11

Focus area: streaming pipeline.

Files to read: `src/applypilot/pipeline.py:196-317`.

Concept to understand: polling and upstream completion.

Small exercise: explain when `score` stops.

Self-check question: What SQL defines pending work?

Optional Codex prompt for hints only: "Ask me how streaming mode knows a stage is done."

## Day 12

Focus area: JobSpy discovery.

Files to read: `src/applypilot/discovery/jobspy.py:21-115`, `src/applypilot/discovery/jobspy.py:131-192`.

Concept to understand: optional dependency and deduplication.

Small exercise: explain duplicate handling.

Self-check question: Why lazy import JobSpy?

Optional Codex prompt for hints only: "Quiz me on missing optional dependency behavior."

## Day 13

Focus area: enrichment.

Files to read: `src/applypilot/enrichment/detail.py:529-675`.

Concept to understand: extraction cascade.

Small exercise: list tier 1, 2, and 3 extraction.

Self-check question: Why try deterministic extraction before LLM?

Optional Codex prompt for hints only: "Ask me to trace scrape_detail_page."

## Day 14

Focus area: LLM client.

Files to read: `src/applypilot/llm.py:22-126`.

Concept to understand: provider detection and retry.

Small exercise: explain provider priority.

Self-check question: Which env var overrides model?

Optional Codex prompt for hints only: "Quiz me on LLM provider detection."

## Day 15

Focus area: scoring.

Files to read: `src/applypilot/scoring/scorer.py:43-175`.

Concept to understand: text protocol parsing.

Small exercise: design a malformed response test.

Self-check question: What does score 0 mean?

Optional Codex prompt for hints only: "Ask me what can go wrong in score parsing."

## Day 16

Focus area: tailoring.

Files to read: `src/applypilot/scoring/tailor.py:167-245`, `src/applypilot/scoring/tailor.py:430-548`.

Concept to understand: structured LLM output and artifacts.

Small exercise: map text/report/PDF files.

Self-check question: Which DB update only happens on approved output?

Optional Codex prompt for hints only: "Challenge my explanation of tailoring side effects."

## Day 17

Focus area: validation.

Files to read: `src/applypilot/scoring/validator.py:82-180`, `src/applypilot/scoring/validator.py:279-315`.

Concept to understand: LLM output guardrails.

Small exercise: list three invalid outputs.

Self-check question: Why auto-fix smart quotes but reject banned words?

Optional Codex prompt for hints only: "Ask me to classify validation failures."

## Day 18

Focus area: dashboard UI.

Files to read: `src/applypilot/apply/dashboard.py:22-190`.

Concept to understand: terminal UI state.

Small exercise: explain thread-safe state updates.

Self-check question: Why is `_lock` needed?

Optional Codex prompt for hints only: "Quiz me on Rich dashboard state."

## Day 19

Focus area: HTML dashboard.

Files to read: `src/applypilot/view.py:25-115`, `src/applypilot/view.py:360-407`.

Concept to understand: generated static UI.

Small exercise: trace one SQL field into a job card.

Self-check question: What is risky about string-built HTML?

Optional Codex prompt for hints only: "Ask me how dashboard filtering works."

## Day 20

Focus area: prompt builder.

Files to read: `src/applypilot/apply/prompt.py:188-235`, `src/applypilot/apply/prompt.py:419-565`.

Concept to understand: prompts as safety logic.

Small exercise: identify all safety sections.

Self-check question: What changes when `dry_run` is true?

Optional Codex prompt for hints only: "Quiz me on apply prompt safety."

## Day 21

Focus area: agent contracts.

Files to read: `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/apply/agents/parsing.py:13-87`.

Concept to understand: normalized external output.

Small exercise: list all legal final statuses.

Self-check question: Why is `NEEDS_REVIEW` safer than raising for unknown output?

Optional Codex prompt for hints only: "Ask me to explain ParsedOutcome."

## Day 22

Focus area: Codex runner.

Files to read: `src/applypilot/apply/agents/codex_runner.py:58-145`.

Concept to understand: subprocess JSONL boundary.

Small exercise: explain raw log versus event log.

Self-check question: What happens on timeout?

Optional Codex prompt for hints only: "Challenge my understanding of CodexRunner."

## Day 23

Focus area: Claude runner.

Files to read: `src/applypilot/apply/agents/claude_runner.py:48-149`.

Concept to understand: shared runner shape, different process protocol.

Small exercise: compare Claude and Codex runners.

Self-check question: Which fields are identical in their return values?

Optional Codex prompt for hints only: "Ask me to identify backend-specific code."

## Day 24

Focus area: job claiming.

Files to read: `src/applypilot/apply/launcher.py:174-271`.

Concept to understand: SQLite queue claim.

Small exercise: explain why `BEGIN IMMEDIATE` appears before SELECT.

Self-check question: What prevents a manual ATS row from blocking the queue?

Optional Codex prompt for hints only: "Quiz me on acquire_job invariants."

## Day 25

Focus area: run one job.

Files to read: `src/applypilot/apply/launcher.py:416-568`.

Concept to understand: backend selection and outcome mapping.

Small exercise: draw the auto fallback path.

Self-check question: When does fallback skip to Codex?

Optional Codex prompt for hints only: "Ask me to trace run_job without code first."

## Day 26

Focus area: worker loop.

Files to read: `src/applypilot/apply/launcher.py:602-731`.

Concept to understand: process lifecycle and retry status.

Small exercise: list every exit path.

Self-check question: Where is Chrome cleaned up?

Optional Codex prompt for hints only: "Challenge me on cleanup and retry behavior."

## Day 27

Focus area: parser tests.

Files to read: `tests/test_agent_parsing.py:4-24`.

Concept to understand: behavior tests.

Small exercise: write one more test case on paper.

Self-check question: Why not test the regex directly?

Optional Codex prompt for hints only: "Ask me to design a parser edge-case test."

## Day 28

Focus area: launcher tests.

Files to read: `tests/test_apply_launcher.py:8-122`.

Concept to understand: isolated DB tests.

Small exercise: explain each monkeypatch.

Self-check question: What behavior is protected by the manual ATS test?

Optional Codex prompt for hints only: "Quiz me on test isolation."

## Day 29

Focus area: review a hypothetical diff.

Files to read: `src/applypilot/apply/launcher.py:575-585`, `src/applypilot/apply/launcher.py:690-702`.

Concept to understand: failure classification.

Small exercise: review changing `captcha` from permanent to retryable.

Self-check question: What user harm could each choice cause?

Optional Codex prompt for hints only: "Act as a reviewer and ask me questions about this hypothetical diff."

## Day 30

Focus area: interview explanation.

Files to read: `README.md:1-37`, `src/applypilot/pipeline.py:35-44`, `src/applypilot/apply/agents/base.py:10-36`.

Concept to understand: concise architecture communication.

Small exercise: give a two-minute system walkthrough.

Self-check question: Can you explain one trade-off honestly?

Optional Codex prompt for hints only: "Interview me on this codebase. Ask follow-up questions after each answer."
