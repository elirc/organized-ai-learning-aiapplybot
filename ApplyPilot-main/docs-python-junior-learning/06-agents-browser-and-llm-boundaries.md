# 06 - Agents, Browser, And LLM Boundaries

This is the most advanced part of ApplyPilot. Read slowly.

## What Is A Boundary?

A boundary is where your code talks to something outside itself:

- the file system
- a database
- a website
- an LLM API
- a browser
- another command-line program

Boundaries are where bugs and surprises live.

## LLM Boundary

The LLM client is in `src/applypilot/llm.py`.

### Provider Detection

```python
# src/applypilot/llm.py:22-53
def _detect_provider() -> tuple[str, str, str]:
    model_override = os.environ.get("LLM_MODEL", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    local_url = os.environ.get("LLM_URL", "")

    if gemini_key and not local_url:
        return (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            model_override or "gemini-2.0-flash",
            gemini_key,
        )
```

Inline lesson:

- Read env vars.
- Prefer Gemini if `GEMINI_API_KEY` exists and no local URL is set.
- Return base URL, model, and API key.

Fake simplified version:

```python
def choose_provider(env):
    if env.get("GEMINI_API_KEY"):
        return "gemini"
    if env.get("OPENAI_API_KEY"):
        return "openai"
    return "none"
```

### Chat Request

```python
# src/applypilot/llm.py:92-126
for attempt in range(_MAX_RETRIES):
    try:
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        if response.status_code in (429, 503) and attempt < _MAX_RETRIES - 1:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        if attempt < _MAX_RETRIES - 1:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        raise
```

Inline lesson:

- Try several times.
- Retry rate limits and service unavailable responses.
- Retry timeouts.
- Return only the assistant text.

Senior note:

Retries are useful, but they can also multiply cost or delay. Any new LLM call should think about max tokens, timeout, and retry behavior.

## LLM Output Is Not Trusted

Example: score parsing.

```python
# src/applypilot/scoring/scorer.py:43-69
def _parse_score_response(response: str) -> dict:
    score = 0
    keywords = ""
    reasoning = response

    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score = int(re.search(r"\d+", line).group())
                score = max(1, min(10, score))
            except (AttributeError, ValueError):
                score = 0
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()

    return {"score": score, "keywords": keywords, "reasoning": reasoning}
```

Inline lesson:

- Parse expected text markers.
- Clamp score to 1-10.
- Fall back to score 0 if parsing fails.

Fake bad example:

```python
# Bad fake code: trusts the LLM completely.
score = int(llm_response)
```

Fake better example:

```python
try:
    score = int(llm_response)
except ValueError:
    score = 0

score = max(0, min(10, score))
```

## Browser Boundary

Auto-apply uses Chrome workers.

Evidence:

- Browser launch function: `src/applypilot/apply/chrome.py:189-255`
- Worker loop call: `src/applypilot/apply/launcher.py:671-721`

```python
# src/applypilot/apply/launcher.py:671-721
chrome_proc = None
try:
    add_event(f"[W{worker_id}] Launching Chrome...")
    chrome_proc = launch_chrome(worker_id, port=port, headless=headless)

    result, duration_ms = run_job(...)
finally:
    if chrome_proc:
        cleanup_worker(worker_id, chrome_proc)
```

Inline lesson:

- Start Chrome before running the agent.
- Always clean up Chrome in `finally`.
- `finally` runs even if an exception occurs.

Fake reinforcement:

```python
resource = open_resource()
try:
    use_resource(resource)
finally:
    close_resource(resource)
```

This pattern is everywhere in reliable software.

## Agent Runner Boundary

ApplyPilot can run Claude or Codex.

The shared contract:

```python
# src/applypilot/apply/agents/base.py:10-36
@dataclass
class ParsedOutcome:
    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool

@dataclass
class AgentRunResult:
    engine: str
    exit_code: int
    final_text: str
    events_path: Path | None
    raw_log_path: Path
    duration_ms: int
    parsed: ParsedOutcome

class AgentRunner(Protocol):
    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        """Run a backend CLI and return normalized output."""
```

Inline lesson:

- `ParsedOutcome` is the clean business result.
- `AgentRunResult` includes debugging details.
- `AgentRunner` says every runner must have a `run()` method.

Fake interface example:

```python
class PaymentProcessor(Protocol):
    def charge(self, amount: int) -> Receipt:
        ...

# Stripe and PayPal could both implement charge().
```

Same idea:

- Claude and Codex both implement `run()`.
- The launcher does not need to know every internal detail.

## Parsing Agent Output

```python
# src/applypilot/apply/agents/parsing.py:74-87
def parse_agent_result(text: str) -> ParsedOutcome:
    """Parse known RESULT conventions or fallback to NEEDS_REVIEW."""
    if not text.strip():
        return ParsedOutcome(status="NEEDS_REVIEW", reason="empty_output", submitted=False)

    parsed_json = _try_parse_json_lines(text)
    if parsed_json:
        return parsed_json

    parsed_result = _try_parse_result_lines(text)
    if parsed_result:
        return parsed_result

    return ParsedOutcome(status="NEEDS_REVIEW", reason="no_result_marker", submitted=False)
```

Inline lesson:

- Empty output is not trusted.
- JSON output is tried first.
- `RESULT:` output is tried second.
- Unknown output becomes `NEEDS_REVIEW`.

Why this matters:

When an agent is uncertain, the app should not pretend an application was submitted.

## Prompt Boundary

Prompts are code-adjacent. They encode business rules.

```python
# src/applypilot/apply/prompt.py:520-565
if dry_run:
    submit_instruction = (
        "IMPORTANT: Do NOT click the final Submit/Apply button. Review the form, verify all fields, "
        "then output RESULT:DRY_RUN - dry_run_no_submission."
    )
else:
    submit_instruction = (
        "BEFORE clicking Submit/Apply, take a snapshot and review EVERY field on the page. Verify all "
        "data matches the APPLICANT PROFILE and TAILORED RESUME -- name, email, phone, location, work "
        "auth, resume uploaded, cover letter if applicable. If anything is wrong or missing, fix it FIRST. "
        "Only click Submit after confirming everything is correct."
    )
```

Inline lesson:

- `dry_run` changes agent behavior.
- Real submissions require verification before clicking submit.
- Prompt text is a safety mechanism.

Senior note:

Prompts should be reviewed like code when they control user-impacting behavior.

## Domain Allowlist Safety

```python
# src/applypilot/apply/launcher.py:430-433
apply_url = job.get("application_url") or job["url"]
if not _is_domain_allowed(apply_url, domain_allowlist):
    host = _url_host(apply_url) or "unknown-domain"
    return f"failed:domain_not_allowed:{host}", 0
```

Inline lesson:

- Check safety before resetting worker dirs or building prompts.
- Return failure with 0 duration.
- Do not launch external automation for disallowed domains.

Real tests:

- `tests/test_apply_launcher.py:226-252` verifies blocked domains stop before side effects.
- `tests/test_apply_launcher.py:254-257` verifies subdomain allowlist behavior.

## Practice

Write fake pseudocode for a safe external boundary:

```python
def call_external_service(payload):
    validate_payload(payload)
    try:
        response = send_request(payload)
    except TimeoutError:
        return {"status": "needs_review", "reason": "timeout"}

    parsed = parse_response(response)
    if not parsed.is_safe:
        return {"status": "needs_review", "reason": "unsafe_response"}

    return {"status": "ok", "data": parsed.data}
```

Self-grade:

- Strong answer validates input, handles failure, parses output, and returns safe fallback.
- Weak answer only calls the external service.

