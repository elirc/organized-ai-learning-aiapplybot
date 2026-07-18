# agents/base.py — The Backend Contract

**File:** `src/applypilot/apply/agents/base.py` (37 lines)
**Role:** Defines the shared data models and protocol that all agent backends must implement.

---

## What This File Does

This is the **smallest but most architecturally important** file in the agents package. It defines:

1. **`ParsedOutcome`** — what the agent decided (applied? failed? why?)
2. **`AgentRunResult`** — the full execution report (timing, logs, exit code)
3. **`AgentRunner`** — the interface contract that all backends implement

At 37 lines, this file is a masterclass in **interface-driven design**. It defines *what* backends must do without specifying *how*.

---

## ParsedOutcome — The Terminal Verdict

```python
@dataclass
class ParsedOutcome:
    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool
```

After an AI agent runs for 30-120 seconds filling out a job application, the entire result is distilled into these three fields:

### `status` — What Happened?

| Status | Meaning |
|--------|---------|
| `APPLIED` | Application was submitted successfully |
| `FAILED` | Something went wrong (reason explains what) |
| `CAPTCHA` | Blocked by an unsolvable CAPTCHA |
| `NEEDS_REVIEW` | Ambiguous — couldn't determine outcome |
| `DRY_RUN` | Would have submitted, but `--dry-run` was on |

### `reason` — Machine-Readable Why

Examples: `"submitted"`, `"expired"`, `"not_eligible_location"`, `"login_issue"`, `"captcha"`, `"timeout"`, `"no_result_marker"`.

The reason is designed to be **machine-readable** (no spaces, lowercase, underscored) so the launcher can match on it:
```python
if reason in PERMANENT_FAILURES:
    mark_as_permanent(...)
```

### `submitted` — Was the Button Clicked?

This boolean distinguishes "the form was submitted" from "the form was filled but not submitted." Important because:
- `status=APPLIED, submitted=True` → confident success
- `status=NEEDS_REVIEW, submitted=True` → something weird happened AFTER submitting
- `status=FAILED, submitted=False` → failed before reaching the submit button

### Why a Dataclass?

`@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__`. For a simple container of three fields, it's the perfect choice — less boilerplate than a regular class, more explicit than a dict.

**Why not a TypedDict?** Dataclasses have type checking at construction time (with `Literal`), and they're true objects with methods. TypedDicts are just dicts with type hints — they don't enforce anything at runtime.

---

## AgentRunResult — The Full Report

```python
@dataclass
class AgentRunResult:
    engine: str             # "claude" or "codex"
    exit_code: int          # 0 = clean exit, -1 = timeout, etc.
    final_text: str         # combined text output from the agent
    events_path: Path | None  # Codex JSONL events file (None for Claude)
    raw_log_path: Path      # full process stdout/stderr log
    duration_ms: int        # wall-clock time
    parsed: ParsedOutcome   # the distilled verdict
```

### Why This Exists

The launcher needs more than just "applied" or "failed." It needs:
- **Timing** (`duration_ms`) — for performance tracking and the dashboard
- **Logs** (`raw_log_path`) — for debugging failed applications
- **Exit code** — did the process crash (non-zero) or finish cleanly?
- **Engine** — which backend produced this result?

### `events_path` — Codex-Specific

Codex outputs a JSONL (JSON Lines) file with structured events (tool calls, agent messages, etc.). Claude streams JSON to stdout instead. So `events_path` is `None` for Claude and a real path for Codex.

**Why keep a Codex-specific field in a shared model?** Because the launcher might want to inspect events for debugging. Making it `Optional` keeps the model honest — Claude simply doesn't produce this artifact.

---

## AgentRunner — The Protocol

```python
class AgentRunner(Protocol):
    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ...
```

### What is a Protocol?

A Protocol (from `typing`) defines **structural typing** — also called "duck typing with type checker support." Any class with a `run(prompt, *, workdir, timeout_s) -> AgentRunResult` method satisfies this protocol, WITHOUT needing to explicitly inherit from it.

```python
class ClaudeRunner:  # Note: does NOT inherit from AgentRunner
    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ...  # This satisfies the protocol because the signature matches
```

### Why a Protocol Instead of an ABC?

With an Abstract Base Class (`abc.ABC`):
```python
class AgentRunner(ABC):
    @abstractmethod
    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult: ...

class ClaudeRunner(AgentRunner):  # MUST inherit
    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult: ...
```

With a Protocol:
```python
class AgentRunner(Protocol):
    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult: ...

class ClaudeRunner:  # No inheritance needed
    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult: ...
```

Protocols are **less coupled**. The runner classes don't need to import `AgentRunner` or know it exists. They just need to have the right method signature. This is the Pythonic way to define interfaces.

### The Method Signature

```python
def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
```

- **`prompt: str`** — the full instruction text to send to the AI agent
- **`*, workdir: Path`** — keyword-only; the directory to run the subprocess in
- **`timeout_s: int`** — keyword-only; max seconds before killing the process
- **Returns `AgentRunResult`** — the full execution report

**Why keyword-only args (`*`)?** Prevents confusion between `workdir` and `timeout_s` at the call site. You must write `runner.run(prompt, workdir=path, timeout_s=300)`, not `runner.run(prompt, path, 300)`.

---

## Why This File Matters

This 37-line file is the **architectural cornerstone** of the entire Stage 6 system. It enables:

1. **Backend swappability** — Claude and Codex are interchangeable
2. **Auto-fallback** — the launcher can try both without special-casing
3. **Future extensibility** — adding a Gemini agent means writing one class
4. **Testability** — you can create a `FakeRunner` for tests

```python
# Example: how easy it is to add a new backend
class GeminiRunner:
    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult:
        # Launch gemini CLI, parse output, return AgentRunResult
        ...
```

That's it. No base class to inherit, no registration, no factory. Just implement `run()` and pass the runner to the launcher.

---

## Design Patterns to Notice

### 1. Thin Interface, Rich Implementations
The protocol is minimal — one method. All complexity lives in the implementations (ClaudeRunner, CodexRunner). This follows the Interface Segregation Principle: clients depend on the smallest possible interface.

### 2. Value Objects
`ParsedOutcome` and `AgentRunResult` are immutable-ish value objects. They carry data, don't have behavior, and are created once and never modified. This makes reasoning about data flow straightforward.

### 3. Layered Abstraction
```
Agent subprocess output (messy text/JSON)
         ↓ parsing.py
    ParsedOutcome (clean)
         ↓ wrapped in
    AgentRunResult (with metadata)
         ↓ consumed by
    launcher.py (_map_outcome)
         ↓ stored in
    database (apply_status column)
```
Each layer adds structure and removes noise.
