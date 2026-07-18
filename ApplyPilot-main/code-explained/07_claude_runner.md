# agents/claude_runner.py — The Claude Backend

**File:** `src/applypilot/apply/agents/claude_runner.py` (150 lines)
**Role:** Runs the Claude Code CLI as a subprocess, streams its JSON output, and returns a normalized result.

---

## What This File Does

This file wraps the `claude` command-line tool. It:
1. Builds the CLI command with all necessary flags
2. Launches it as a subprocess
3. Feeds the prompt via stdin
4. Streams stdout, parsing each line as JSON
5. Extracts text from `assistant` and `result` messages
6. Parses the final output into a `ParsedOutcome`

---

## The Gmail Tool Blocklist

```python
CLAUDE_DISALLOWED_GMAIL_TOOLS = (
    "mcp__gmail__draft_email,mcp__gmail__modify_email,"
    "mcp__gmail__delete_email,mcp__gmail__download_attachment,"
    ...
)
```

### Why Block These?

The Gmail MCP server gives Claude access to email (for reading verification codes). But we DON'T want Claude to:
- Draft emails on behalf of the user
- Delete emails
- Modify existing emails
- Download attachments from unknown senders

Only read-only operations (`search_emails`, `read_email`) are allowed. The `--disallowedTools` flag tells Claude Code "you can see these tools exist, but you CANNOT call them."

**This is a security boundary.** Even though Claude is instructed not to misuse email, explicit tool blocking is a defense-in-depth measure.

---

## The CLI Command

```python
def run(self, prompt, *, workdir, timeout_s):
    cmd = ["claude"]
    if self.model:
        cmd.extend(["--model", self.model])
    cmd.extend([
        "-p",                              # print mode (non-interactive)
        "--mcp-config", str(self.mcp_config_path),  # MCP servers
        "--permission-mode", "bypassPermissions",    # no permission prompts
        "--no-session-persistence",         # don't save conversation
        "--disallowedTools", CLAUDE_DISALLOWED_GMAIL_TOOLS,
        "--output-format", "stream-json",   # structured JSON output
        "--verbose",                        # extra logging
        "-",                               # read prompt from stdin
    ])
```

### Key Flags Explained

**`-p` (print mode):** Run non-interactively. Claude reads the prompt, executes, and exits. No conversation loop.

**`--permission-mode bypassPermissions`:** In normal use, Claude Code asks for permission before taking actions (file writes, tool calls). For auto-apply, we trust it to act autonomously — the prompt contains all the guardrails.

**`--no-session-persistence`:** Don't save the conversation to disk. Each application is a fresh session. This prevents session data from bleeding between jobs.

**`--output-format stream-json`:** Instead of plain text, Claude outputs JSON objects — one per line. This lets us parse structured events (tool calls, messages, results) programmatically.

**`"-"` (stdin):** Read the prompt from stdin instead of a command-line argument. The prompt can be 10K+ characters, which would overflow most shells' argument limits.

---

## Environment Sanitization

```python
env = os.environ.copy()
env.pop("CLAUDECODE", None)
env.pop("CLAUDE_CODE_ENTRYPOINT", None)
```

### Why Remove These?

If ApplyPilot itself is running inside Claude Code (e.g., during development), these environment variables would make the *child* Claude process think it's nested inside another Claude session. Removing them ensures the child process starts clean.

This is a subtle but important detail — without it, nested Claude sessions can behave unpredictably.

---

## Subprocess Management

```python
proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,  # merge stderr into stdout
    text=True,                 # text mode (not bytes)
    encoding="utf-8",
    errors="replace",          # replace invalid chars instead of crashing
    cwd=str(workdir),
    env=env,
)
```

### Key Decisions

**`stderr=subprocess.STDOUT`:** Merge error output into the main output stream. This simplifies parsing — we only need to read one stream. Any error messages from Claude appear inline with the rest of the output.

**`errors="replace"`:** If Claude outputs invalid UTF-8 (rare, but possible with binary data or encoding issues), replace the bad bytes with `?` instead of raising `UnicodeDecodeError`. Robustness over correctness for edge cases.

**`cwd=str(workdir)`:** Each worker has an isolated directory. Claude's file operations (if any) are sandboxed to this directory.

---

## Streaming JSON Processing

```python
# Write prompt to stdin
proc.stdin.write(prompt)
proc.stdin.close()

# Stream stdout line by line
for line in proc.stdout:
    lf.write(line)  # log everything
    stripped = line.strip()
    if not stripped:
        continue

    try:
        msg = json.loads(stripped)
    except json.JSONDecodeError:
        text_parts.append(stripped)  # non-JSON lines are kept as text
        continue

    msg_type = msg.get("type")
    if msg_type == "assistant":
        for block in msg.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text"):
                text_parts.append(str(block["text"]))
    elif msg_type == "result":
        result_text = msg.get("result")
        if isinstance(result_text, str) and result_text.strip():
            text_parts.append(result_text)
```

### What Claude Streams

Claude Code with `--output-format stream-json` outputs JSON objects, one per line:

```json
{"type": "assistant", "message": {"content": [{"type": "text", "text": "Navigating to the job page..."}]}}
{"type": "tool_use", "tool": "mcp__playwright__browser_navigate", ...}
{"type": "tool_result", ...}
{"type": "assistant", "message": {"content": [{"type": "text", "text": "RESULT: APPLIED - submitted"}]}}
{"type": "result", "result": "RESULT: APPLIED - submitted"}
```

### What We Extract

We only care about **text content**:
1. From `assistant` messages → the agent's reasoning and final RESULT line
2. From `result` messages → the final result summary

Everything else (tool calls, tool results) is logged but not extracted. The RESULT line in the text is what gets parsed into a `ParsedOutcome`.

### Why Log Everything?

```python
with raw_log_path.open("w", encoding="utf-8") as lf:
    lf.write(f"$ {' '.join(cmd)}\n")  # log the command
    for line in proc.stdout:
        lf.write(line)  # log every line
```

Full logs are essential for debugging. If an application fails, the developer can read the log file to see:
- What page the agent saw
- What actions it took
- Where it got stuck
- What error occurred

---

## Timeout Handling

```python
proc.wait(timeout=timeout_s)
exit_code = int(proc.returncode or 0)
```

```python
except subprocess.TimeoutExpired:
    if proc is not None:
        proc.kill()
    text_parts.append("RESULT:FAILED:timeout")
    exit_code = -1
```

If the agent exceeds the timeout (default 300 seconds), we kill it and inject a synthetic RESULT line. The parser then picks this up as `FAILED` with reason `timeout`.

**Why inject "RESULT:FAILED:timeout"?** Instead of special-casing timeout in the launcher, we normalize it into the same output format the parser already handles. This keeps the launcher's parsing logic simple.

---

## Process Lifecycle Callbacks

```python
if self.on_process_start:
    self.on_process_start(self.worker_id, proc)
...
finally:
    if self.on_process_exit:
        self.on_process_exit(self.worker_id)
```

The launcher uses these callbacks to register/unregister active processes for Ctrl+C handling:

```python
runner = ClaudeRunner(
    on_process_start=_register_agent_proc,   # tracks the process
    on_process_exit=_unregister_agent_proc,   # removes tracking
)
```

When the user presses Ctrl+C, the launcher iterates over registered processes and kills them. Without these callbacks, orphan Claude processes would keep running.

---

## Final Text Assembly

```python
duration_ms = int((time.time() - start) * 1000)
final_text = "\n".join(text_parts).strip()
if not final_text and raw_log_path.exists():
    final_text = raw_log_path.read_text(encoding="utf-8", errors="replace")
parsed = parse_agent_result(final_text)
```

### The Fallback

If `text_parts` is empty (no JSON was parseable), we fall back to the raw log file. This handles cases where Claude outputs in an unexpected format — at least the parser can try to find a RESULT line in the raw output.

---

## Design Patterns to Notice

### 1. Process-as-a-Service
The Claude CLI is treated as a black-box service: prompt in → result out. All complexity of the Claude API, MCP protocol, and browser automation is hidden behind the CLI.

### 2. Defensive I/O
Every file operation and process interaction has error handling. The `errors="replace"` encoding, the timeout handling, and the raw log fallback all ensure the runner never crashes — it always returns an `AgentRunResult`, even on failure.

### 3. Callback Injection
Instead of hardcoding process tracking, callbacks are injected via constructor. This makes the runner testable (pass in no-op callbacks) and decoupled from the launcher's tracking mechanism.
