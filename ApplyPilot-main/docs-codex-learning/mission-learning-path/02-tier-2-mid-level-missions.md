# Tier 2 Mid-Level Missions

### Mission 9: State Has a Home and a Reason

**Tier:** Mid-Level

**Time Estimate:** 50 minutes

**Goal:** Identify where each kind of state belongs.

**The Concept:** State is like a job application's file folder. Some notes are permanent, some are temporary desk notes, and some are generated attachments.

**Design Intent Before You Read the Code:** Durable workflow state belongs in SQLite. Personal config and artifacts belong in `~/.applypilot`. Transient UI state belongs in memory.

**Find It In The Code:** Open `src/applypilot/config.py:11-29`, `src/applypilot/database.py:90-133`, and `src/applypilot/apply/dashboard.py:41-88`.

```python
# src/applypilot/config.py:11-29
APP_DIR = Path(os.environ.get("APPLYPILOT_DIR", Path.home() / ".applypilot"))
DB_PATH = APP_DIR / "applypilot.db"
TAILORED_DIR = APP_DIR / "tailored_resumes"
LOG_DIR = APP_DIR / "logs"
```

**The Aha Moment:** Good state design lets you recover after a crash.

**Socratic Checkpoint:** What state survives process exit? What state is safe to lose? Which state contains personal data? Which columns show progress? Which tests avoid touching real user state?

**How to Self-Grade:** Strong answers cite config paths, DB schema, and `tests/test_apply_launcher.py:8-14`.

**Connects To:** Mission 14.

### Mission 10: The Custom Hook or Reusable Abstraction Ecosystem

**Tier:** Mid-Level

**Time Estimate:** 45 minutes

**Goal:** Recognize reusable abstractions without React hooks.

**The Concept:** A custom hook packages repeatable behavior for components. Here, reusable helpers package repeatable behavior for pipeline and agent code.

**Design Intent Before You Read the Code:** Shared abstractions should reduce repeated process parsing, config normalization, and DB connection logic.

**Find It In The Code:** Open `src/applypilot/database.py:20-49`, `src/applypilot/config.py:129-238`, and `src/applypilot/apply/agents/parsing.py:74-87`.

```python
# src/applypilot/database.py:20-49
def get_connection(...):
    # One cached SQLite connection per thread.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
```

**The Aha Moment:** Reusable abstractions are valuable when they protect an invariant.

**Socratic Checkpoint:** What invariant does `get_connection()` protect? What invariant does `_normalize_profile()` protect? What invariant does `parse_agent_result()` protect? Which helper feels too broad? Which helper would you add?

**How to Self-Grade:** Strong answers explain thread safety, compatibility, and normalized status vocabulary.

**Connects To:** Mission 17.

### Mission 11: Side Effects Are Promises To The System

**Tier:** Mid-Level

**Time Estimate:** 60 minutes

**Goal:** Trace side effects and their failure modes.

**The Concept:** Every side effect is a promise: a file exists, a DB row changed, a browser launched, or an external API answered.

**Design Intent Before You Read the Code:** Side effects should be explicit, logged, and recoverable.

**Find It In The Code:** Open `src/applypilot/scoring/tailor.py:430-548`, `src/applypilot/apply/agents/codex_runner.py:58-145`, and `src/applypilot/apply/launcher.py:671-721`.

```python
# src/applypilot/scoring/tailor.py:467-485
txt_path.write_text(tailored, encoding="utf-8")       # Artifact side effect.
report_path.write_text(json.dumps(report, indent=2))  # Audit side effect.

# src/applypilot/scoring/tailor.py:526-540
conn.execute("UPDATE jobs SET tailored_resume_path=? ...")
```

**The Aha Moment:** The artifact and the database must agree.

**Socratic Checkpoint:** Which side effects can fail? What happens if PDF generation fails? Where are raw agent logs written? Where is Chrome cleaned up? Which side effect should be tested next?

**How to Self-Grade:** Strong answers mention filesystem, SQLite, subprocess, browser lifecycle, and cleanup.

**Connects To:** Mission 19.

### Mission 12: The Full API or Module Contract

**Tier:** Mid-Level

**Time Estimate:** 50 minutes

**Goal:** Map module contracts in a repo without internal HTTP APIs.

**The Concept:** A module contract is an API even if it is not HTTP. Callers still depend on names, parameters, return shapes, and failure behavior.

**Design Intent Before You Read the Code:** Agent runners must hide Claude/Codex differences.

**Find It In The Code:** Open `src/applypilot/apply/agents/base.py:10-36`, `src/applypilot/apply/agents/claude_runner.py:48-149`, and `src/applypilot/apply/agents/codex_runner.py:58-145`.

```python
# Both runners return AgentRunResult with parsed outcome.
return AgentRunResult(
    engine="codex",
    exit_code=exit_code,
    final_text=final_text,
    parsed=parsed,
)
```

**The Aha Moment:** Different backends can be operationally different and architecturally equivalent.

**Socratic Checkpoint:** Which fields does every runner return? Which runner writes JSONL events? Where do timeouts become failed results? Why does launcher not parse JSONL itself? What would a third runner need to implement?

**How to Self-Grade:** Strong answers explain the Protocol and normalized result model.

**Connects To:** Mission 16.

### Mission 13: The Middleware, Pipeline, Or Boundary Chain

**Tier:** Mid-Level

**Time Estimate:** 60 minutes

**Goal:** Understand pipeline dependencies and streaming behavior.

**The Concept:** The pipeline is a set of stations on a conveyor belt. Streaming mode lets downstream stations start once enough packages appear, while still waiting for upstream completion.

**Design Intent Before You Read the Code:** Downstream stages should not finish until upstream is done and no pending work remains.

**Find It In The Code:** Open `src/applypilot/pipeline.py:46-55`, `src/applypilot/pipeline.py:196-317`, and `src/applypilot/pipeline.py:376-436`.

```python
# src/applypilot/pipeline.py:222-241
_PENDING_SQL = {
    "enrich": "SELECT COUNT(*) FROM jobs WHERE detail_scraped_at IS NULL",
    "score": "SELECT COUNT(*) FROM jobs WHERE full_description IS NOT NULL AND fit_score IS NULL",
}
```

**The Aha Moment:** Streaming mode is powered by database state, not in-memory queues.

**Socratic Checkpoint:** What marks a stage done? What makes a downstream stage wait? What SQL defines pending work? What can go wrong if a stage crashes? Why is this simpler than Celery?

**How to Self-Grade:** Strong answers mention `_StageTracker`, `_UPSTREAM`, `_PENDING_SQL`, and polling trade-offs.

**Connects To:** Mission 14.

### Mission 14: End-to-End Feature Trace

**Tier:** Mid-Level

**Time Estimate:** 90 minutes

**Goal:** Trace one job from ready-to-apply to final status.

**The Concept:** A feature trace is a boarding pass scan: every station should stamp the same traveler, not create a new mystery person.

**Design Intent Before You Read the Code:** The apply flow must preserve job identity, artifact paths, browser isolation, agent output, and DB status.

**Find It In The Code:** Read in order: `src/applypilot/cli.py:127-220`, `src/applypilot/apply/launcher.py:174-271`, `src/applypilot/apply/launcher.py:416-568`, `src/applypilot/apply/launcher.py:602-731`, `src/applypilot/apply/agents/parsing.py:74-87`.

```python
# Chronology:
# 1. CLI validates dependencies.
# 2. acquire_job() marks row in_progress.
# 3. worker_loop() launches Chrome.
# 4. run_job() builds prompt and invokes backend.
# 5. parser normalizes result.
# 6. mark_result() persists final status.
```

**The Aha Moment:** End-to-end understanding means following identity and state, not just calls.

**Socratic Checkpoint:** Where is the job selected? Where is the browser port chosen? Where is the prompt built? Where is fallback implemented? Where is final DB state written?

**How to Self-Grade:** Strong answers can draw the flow without opening files and can cite at least five line ranges.

**Connects To:** Mission 15 and Mission 19.

### Mission 15: Read The Diff Like An Engineer

**Tier:** Mid-Level

**Time Estimate:** 45 minutes

**Goal:** Practice reviewing a hypothetical change.

**The Concept:** Reading a diff is not reading top-to-bottom. It is checking contracts, side effects, and tests.

**Design Intent Before You Read the Code:** A diff that changes apply behavior must protect safety, retries, and durable state.

**Find It In The Code:** Use `src/applypilot/apply/launcher.py:174-271`, `src/applypilot/apply/launcher.py:575-585`, and `tests/test_apply_launcher.py:17-122`.

```text
Hypothetical diff:
"Treat account_required as retryable instead of permanent."

Review:
1. Check PERMANENT_FAILURES.
2. Check mark_result attempt behavior.
3. Add a test proving retry count changes.
4. Confirm dashboard status still makes sense.
```

**The Aha Moment:** The interesting part of a diff is often the invariant it silently changes.

**Socratic Checkpoint:** Which file owns permanent failure classification? What DB column changes on retry? What test proves the new behavior? What user-visible symptom could regress? What log would you inspect?

**How to Self-Grade:** Strong answers tie a one-line constant change to user retry behavior.

**Connects To:** Mission 19.

### Mission 16: Composition Over Inheritance

**Tier:** Mid-Level

**Time Estimate:** 45 minutes

**Goal:** See how the repo composes behavior.

**The Concept:** Composition means building workflows by connecting small parts. The apply launcher composes prompt builder, runner, parser, dashboard, Chrome, and DB updates.

**Design Intent Before You Read the Code:** Claude and Codex do not inherit from a base class. They satisfy the same shape.

**Find It In The Code:** Open `src/applypilot/apply/agents/base.py:32-36`, `src/applypilot/apply/launcher.py:502-535`, and runner return blocks in `claude_runner.py:141-149` and `codex_runner.py:137-145`.

```python
# src/applypilot/apply/launcher.py:512-535
if engine == "claude":
    runner = ClaudeRunner(...)
else:
    runner = CodexRunner(...)
return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)
```

**The Aha Moment:** The launcher needs behavior, not ancestry.

**Socratic Checkpoint:** What behavior must both runners provide? Why is Protocol enough? What code is shared outside runners? What code is backend-specific? How would inheritance make this worse?

**How to Self-Grade:** Strong answers mention substitutability and normalized return shapes.

**Connects To:** Mission 18.

### Mission 17: TypeScript's Hidden Work

**Tier:** Mid-Level

**Time Estimate:** 55 minutes

**Goal:** Identify what static typing would protect if this were TypeScript.

**The Concept:** TypeScript catches broken contracts before runtime. In Python, tests and careful structures have to do more of that work.

**Design Intent Before You Read the Code:** Critical dictionaries should have documented shapes.

**Find It In The Code:** Open `src/applypilot/apply/launcher.py:416-428`, `src/applypilot/scoring/scorer.py:72-100`, and `src/applypilot/scoring/tailor.py:336-360`.

```python
# job is a dict, but actually needs a schema:
# url, title, site, application_url, tailored_resume_path,
# fit_score, full_description, cover_letter_path.
def run_job(job: dict, port: int, ...):
```

**The Aha Moment:** Untyped dicts are invisible contracts; strong engineers make them visible.

**Socratic Checkpoint:** Which job keys are required? Which are optional? Which missing key would crash? Where do tests create fake jobs? What TypedDict would you design?

**How to Self-Grade:** Strong answers name required keys and propose a realistic `JobRow` contract.

**Connects To:** Mission 23.
