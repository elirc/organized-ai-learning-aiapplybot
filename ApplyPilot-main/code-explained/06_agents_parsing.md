# agents/parsing.py — The Rosetta Stone

**File:** `src/applypilot/apply/agents/parsing.py` (88 lines)
**Role:** Parses messy agent output into clean, normalized `ParsedOutcome` objects.

---

## What This File Does

AI agents (Claude, Codex) produce text output that includes their reasoning, tool calls, and eventually a result line. This file extracts the **terminal outcome** from that text, regardless of format.

It handles two output conventions:
1. **JSON objects** — `{"result":"APPLIED","reason":"submitted","submitted":true}`
2. **RESULT lines** — `RESULT: FAILED - job_expired`

If neither format is found, it returns `NEEDS_REVIEW` with reason `"no_result_marker"`.

---

## Status Normalization

```python
def _normalize_status(raw, reason):
    token = (raw or "").strip().upper()
    reason = (reason or "").strip() or "unspecified"

    if token == "APPLIED":
        return "APPLIED", reason if reason != "unspecified" else "submitted", True
    if token == "DRY_RUN":
        return "DRY_RUN", reason, False
    if token == "CAPTCHA":
        return "CAPTCHA", reason, False
    if token == "FAILED":
        return "FAILED", reason, False
    if token in {"EXPIRED", "LOGIN_ISSUE"}:
        mapped = token.lower()
        return "FAILED", mapped, False
    if token == "NEEDS_REVIEW":
        return "NEEDS_REVIEW", reason, False
    return "NEEDS_REVIEW", f"unrecognized_result:{token or 'missing'}", False
```

### Why Normalize?

The AI agent might output any of these:
- `APPLIED` / `applied` / `Applied`
- `EXPIRED` (which should be mapped to `FAILED` with reason `expired`)
- `LOGIN_ISSUE` (also maps to `FAILED`)
- Something unexpected like `SUCCESS` or `DONE`

The normalizer collapses all of these into exactly five statuses: `APPLIED`, `FAILED`, `CAPTCHA`, `NEEDS_REVIEW`, `DRY_RUN`.

### The `submitted` Boolean

Notice:
- `APPLIED` → `submitted=True` (the form was definitely submitted)
- Everything else → `submitted=False`

This is a safety signal. If `submitted=True`, the job DEFINITELY got the application. If `submitted=False`, we know the form wasn't submitted and can safely retry.

### `EXPIRED` and `LOGIN_ISSUE` Mapping

```python
if token in {"EXPIRED", "LOGIN_ISSUE"}:
    mapped = token.lower()
    return "FAILED", mapped, False
```

The prompt tells the agent to output `RESULT: FAILED - expired`, but some agents write `RESULT: EXPIRED` directly. Instead of failing to parse, we normalize it: `EXPIRED` → `FAILED` with reason `expired`.

**Why not just tell the agent to always use FAILED?** Because AI agents are probabilistic. Despite clear instructions, they sometimes deviate. Good parsing code anticipates this.

---

## JSON Line Parser

```python
def _try_parse_json_lines(text):
    for line in reversed(text.splitlines()):
        line = line.strip().strip("`")
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw_status = payload.get("result") or payload.get("status")
        if not raw_status:
            continue
        ...
        return ParsedOutcome(status=status, reason=parsed_reason, submitted=default_submitted)
    return None
```

### Why Scan in Reverse?

```python
for line in reversed(text.splitlines()):
```

The agent produces many lines of output: reasoning, tool calls, intermediate thoughts. The **final** result is at the end. By scanning from the bottom up, we find the terminal outcome first, skipping all the noise.

### Why `strip("`")`?

```python
line = line.strip().strip("`")
```

AI agents sometimes wrap JSON in markdown code fences:
````
```json
{"result": "APPLIED", "reason": "submitted", "submitted": true}
```
````

The backtick stripping handles this gracefully without requiring a full markdown parser.

### Flexible Key Names

```python
raw_status = payload.get("result") or payload.get("status")
```

The JSON might use `"result"` (Codex convention) or `"status"` (alternative). Accepting both makes the parser resilient to variations.

### Explicit `submitted` Override

```python
if isinstance(submitted, bool):
    default_submitted = submitted
```

If the JSON explicitly says `"submitted": true`, that overrides the default. But if it's omitted, `_normalize_status` provides a sensible default based on the status.

---

## RESULT Line Parser

```python
_RESULT_RE = re.compile(
    r"RESULT\s*:\s*([A-Z_]+)(?::([A-Za-z0-9_\-./]+))?(?:\s*-\s*(.*))?$",
    re.IGNORECASE
)

def _try_parse_result_lines(text):
    last_match = None
    for line in text.splitlines():
        m = _RESULT_RE.search(line.strip())
        if m:
            last_match = m
    ...
```

### The Regex Explained

```
RESULT\s*:\s*     →  "RESULT:" with optional whitespace
([A-Z_]+)         →  Status token: APPLIED, FAILED, etc. (capture group 1)
(?::([A-Za-z0-9_\-./]+))?  →  Optional :suffix like :expired (capture group 2)
(?:\s*-\s*(.*))?  →  Optional " - reason text" (capture group 3)
```

This matches all of these formats:
```
RESULT: APPLIED - submitted successfully
RESULT:APPLIED:submitted
RESULT: FAILED - not_eligible_location
RESULT:FAILED:expired
RESULT: DRY_RUN - dry_run_no_submission
```

### Why Keep the Last Match?

```python
for line in text.splitlines():
    m = _RESULT_RE.search(line.strip())
    if m:
        last_match = m  # keep updating
```

If the agent prints multiple RESULT lines (e.g., thought about one, then changed its mind), we want the **last** one — that's the final answer.

### Suffix vs. Dash Reason

```python
suffix = (last_match.group(2) or "").strip()    # "RESULT:FAILED:expired"
dash_reason = (last_match.group(3) or "").strip()  # "RESULT: FAILED - expired"
reason = dash_reason or suffix or None
```

The agent might use either format. Dash-separated is preferred (more human-readable), suffix is accepted as fallback.

---

## The Main Entry Point

```python
def parse_agent_result(text: str) -> ParsedOutcome:
    if not text.strip():
        return ParsedOutcome(status="NEEDS_REVIEW", reason="empty_output", submitted=False)

    # Try JSON first (more structured, preferred)
    parsed_json = _try_parse_json_lines(text)
    if parsed_json:
        return parsed_json

    # Try RESULT lines (text format)
    parsed_result = _try_parse_result_lines(text)
    if parsed_result:
        return parsed_result

    # Neither format found
    return ParsedOutcome(status="NEEDS_REVIEW", reason="no_result_marker", submitted=False)
```

### The Fallback Chain

1. **Empty output?** → `NEEDS_REVIEW` (agent crashed or produced nothing)
2. **JSON format?** → Parse it (Codex uses this, Claude sometimes does too)
3. **RESULT line?** → Parse it (Claude's default format)
4. **Nothing found?** → `NEEDS_REVIEW` with `no_result_marker`

**Why JSON first?** JSON is more structured and unambiguous. A RESULT line could be embedded in a sentence ("I will now output my RESULT: ..."), but a valid JSON object on its own line is harder to confuse.

---

## Why This File is Critical

Without this parser, the launcher would need to write separate parsing logic for Claude and Codex. By having a **unified parser**, the launcher is backend-agnostic:

```python
# In launcher.py:
result = runner.run(prompt, ...)  # could be Claude or Codex
outcome = result.parsed  # already parsed by the runner using parse_agent_result()
```

Both `ClaudeRunner` and `CodexRunner` call `parse_agent_result()` on their final text, producing the same `ParsedOutcome` type. The launcher doesn't care which backend produced it.

---

## Design Patterns to Notice

### 1. Robustness Over Strictness
This parser is intentionally lenient. It handles extra whitespace, markdown fences, multiple formats, and unknown status tokens. In production, AI output is messy — a brittle parser would fail constantly.

### 2. Graceful Degradation
If parsing fails, the result is `NEEDS_REVIEW` — not a crash. The launcher can handle `NEEDS_REVIEW` (try the other backend, or mark for human review). This is fail-safe design.

### 3. Single Responsibility
This file does ONE thing: parse agent text into a ParsedOutcome. It doesn't make decisions about retries, DB updates, or backend selection. Those responsibilities belong to the launcher.

### 4. No Side Effects
Every function in this file is a pure function: input → output, no state mutation, no I/O. This makes it trivially testable:
```python
def test_applied():
    result = parse_agent_result('RESULT: APPLIED - submitted')
    assert result.status == "APPLIED"
    assert result.submitted == True
```
