# agents/codex_runner.py — The Codex Backend

**File:** `src/applypilot/apply/agents/codex_runner.py` (146 lines)
**Role:** Runs the OpenAI Codex CLI as a subprocess, parses JSONL events, and returns a normalized result.

---

## What This File Does

This is the **mirror image** of `claude_runner.py`, adapted for OpenAI's Codex CLI. The key differences:

| Aspect | Claude | Codex |
|--------|--------|-------|
| CLI | `claude -p --output-format stream-json` | `codex exec --json` |
| Output format | JSON objects (type: assistant/result) | JSONL events (item.completed, turn.completed) |
| MCP config | JSON file passed via `--mcp-config` | TOML file in project `.codex/config.toml` |
| Permissions | `--permission-mode bypassPermissions` | `--dangerously-bypass-approvals-and-sandbox` |
| Output schema | N/A | Optional `--output-schema` for structured JSON |

---

## Event Text Extraction

```python
def _extract_text_from_event(event: dict) -> str | None:
    event_type = str(event.get("type", ""))

    if event_type == "item.completed":
        item = event.get("item", {})
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                return text
            if item.get("type") == "agent_message":
                msg = item.get("message")
                if isinstance(msg, str):
                    return msg

    if event_type == "turn.completed":
        summary = event.get("summary")
        if isinstance(summary, str):
            return summary

    text = event.get("text")
    if isinstance(text, str):
        return text

    return None
```

### Codex Event Format

Codex outputs JSONL (one JSON object per line). Events look like:

```json
{"type": "item.completed", "item": {"type": "agent_message", "text": "Navigating to the job page..."}}
{"type": "item.completed", "item": {"type": "tool_call", "tool": "mcp_playwright_browser_navigate", ...}}
{"type": "turn.completed", "summary": "Applied to the position successfully."}
```

### Why Multiple Extraction Paths?

The Codex event format evolved over versions. The text might be in:
- `event.item.text` (most common)
- `event.item.message` (for agent_message items)
- `event.summary` (for turn completion)
- `event.text` (fallback)

By trying all paths, the parser works across Codex versions.

### Why Return `None`?

Not all events contain text. Tool calls, system messages, and status updates don't have user-visible text. Returning `None` tells the caller "nothing useful here" — the caller filters these out:

```python
text = _extract_text_from_event(event)
if text:
    text_parts.append(text)
```

---

## The CLI Command

```python
cmd = [
    "codex",
    "exec",
    "--json",                          # output JSONL events
    "--skip-git-repo-check",           # don't require a git repo
    "--dangerously-bypass-approvals-and-sandbox",  # full autonomy
]
if self.model:
    cmd.extend(["--model", self.model])
if self.output_schema_path:
    cmd.extend(["--output-schema", str(self.output_schema_path)])
cmd.append("-")  # read prompt from stdin
```

### Key Differences from Claude

**`codex exec`:** Codex has an `exec` subcommand for non-interactive execution, equivalent to Claude's `-p` flag.

**`--skip-git-repo-check`:** Codex normally requires being run inside a git repository. Worker directories aren't git repos, so we skip this check.

**`--dangerously-bypass-approvals-and-sandbox`:** Like Claude's `bypassPermissions`, this gives the agent full autonomy. The name is more explicit about the security implications.

**`--output-schema`:** Codex supports a JSON Schema for structured final output. We use this to enforce the result format:
```json
{
    "type": "object",
    "required": ["result", "reason", "submitted"],
    "properties": {
        "result": {"type": "string", "enum": ["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]},
        "reason": {"type": "string"},
        "submitted": {"type": "boolean"}
    }
}
```

This is a Codex-specific feature that improves parsing reliability — the agent is constrained to output valid JSON matching this schema.

---

## Dual File Logging

```python
with raw_log_path.open("w") as raw_fh, events_path.open("w") as jsonl_fh:
    raw_fh.write(f"$ {' '.join(cmd)}\n")

    for line in proc.stdout:
        raw_fh.write(line)       # everything goes to raw log
        stripped = line.strip()
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue             # non-JSON lines: warnings, errors
        jsonl_fh.write(stripped + "\n")  # valid events go to JSONL file
```

### Why Two Log Files?

- **`raw_log_path`** — every byte of output, including non-JSON warnings and errors. For debugging when things go very wrong.
- **`events_path`** — only valid JSONL events, clean and parseable. For structured analysis of what the agent did.

Claude doesn't produce a separate events file (it logs everything inline), so `events_path` is a Codex-specific artifact stored in `AgentRunResult.events_path`.

---

## Structural Comparison with ClaudeRunner

The two runners are intentionally parallel in structure:

```python
# Both runners follow this exact pattern:
class XxxRunner:
    def __init__(self, *, model, worker_id, log_dir, ...):
        # store config

    def run(self, prompt, *, workdir, timeout_s) -> AgentRunResult:
        # 1. Build command
        # 2. Open log files
        # 3. Launch subprocess
        # 4. Write prompt to stdin, close stdin
        # 5. Stream stdout, parse each line
        # 6. Wait for process exit
        # 7. Handle timeout
        # 8. Assemble final text
        # 9. Parse with parse_agent_result()
        # 10. Return AgentRunResult
```

The difference is in step 5 — Claude parses `{"type": "assistant"}` messages, Codex parses `{"type": "item.completed"}` events. Everything else is structurally identical.

**Why not share code via a base class?** The differences are small but numerous (command flags, event format, extra log file, output schema). A shared base class would need so many hooks and overrides that it would be harder to understand than two parallel implementations.

This is a deliberate choice: **duplication is cheaper than the wrong abstraction.** The two runners are simple, self-contained, and easy to modify independently.

---

## Design Patterns to Notice

### 1. Structural Parallelism
Both runners follow the same structure, making it easy to compare and understand. When you've read one, you understand both.

### 2. Schema-Enforced Output
The output schema feature is unique to Codex. By constraining the agent's final output to a JSON schema, we get more reliable parsing. This is a good example of using the backend's unique capabilities when available.

### 3. Forward Compatibility
The `_extract_text_from_event` function tries multiple paths, handling both current and potential future event formats. This makes the parser resilient to Codex version updates.
