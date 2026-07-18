# llm.py — The Unified LLM Client

**File:** `src/applypilot/llm.py` (159 lines)
**Role:** Single integration point for all LLM API calls across stages 1-5 (scoring, tailoring, cover letters, smart extraction).

---

## What This File Does

Every time ApplyPilot needs to call an LLM — scoring a job, tailoring a resume, generating a cover letter — it goes through this module. It abstracts away the difference between three providers:

1. **Google Gemini** (default) — `GEMINI_API_KEY`
2. **OpenAI** — `OPENAI_API_KEY`
3. **Local LLM** (Ollama, llama.cpp) — `LLM_URL`

All three are accessed through the **OpenAI-compatible** chat completions API, which is the de facto standard for LLM APIs.

---

## Provider Detection

```python
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
_LOCAL_URL = os.environ.get("LLM_URL", "")

def _detect_provider():
    model_override = os.environ.get("LLM_MODEL", "")

    if _GEMINI_KEY and not _LOCAL_URL:
        return (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            model_override or "gemini-2.0-flash",
            _GEMINI_KEY,
        )

    if _OPENAI_KEY and not _LOCAL_URL:
        return (
            "https://api.openai.com/v1",
            model_override or "gpt-4o-mini",
            _OPENAI_KEY,
        )

    if _LOCAL_URL:
        return (_LOCAL_URL.rstrip("/"), model_override or "local-model", ...)
```

### Why Gemini First?

The detection priority is: Gemini → OpenAI → Local. Gemini is the default because:
- It has a generous free tier
- `gemini-2.0-flash` is fast and cheap
- Google's OpenAI-compatible endpoint makes integration trivial

### The `LLM_URL` Override

```python
if _LOCAL_URL:
    return (_LOCAL_URL.rstrip("/"), model_override or "local-model", ...)
```

`LLM_URL` overrides cloud providers. If set, it connects to whatever endpoint is at that URL (Ollama at `http://localhost:11434/v1`, vLLM, llama.cpp, etc.). This is for users who want to run everything locally.

### `LLM_MODEL` Override

```python
model_override = os.environ.get("LLM_MODEL", "")
```

If set, this overrides the default model for any provider. Useful for testing with different models without changing code:
```bash
LLM_MODEL=gemini-2.0-flash-lite applypilot run score
```

---

## The LLMClient Class

```python
class LLMClient:
    def __init__(self, base_url, model, api_key):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=_TIMEOUT)

    def chat(self, messages, temperature=0.0, max_tokens=4096) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload, headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```

### Why Raw httpx Instead of Official SDKs?

You might expect `from openai import OpenAI` or `import google.generativeai`. Instead, this uses raw `httpx.Client`. Why?

1. **Fewer dependencies.** One HTTP library instead of two SDKs.
2. **Uniform API.** All three providers support the OpenAI-compatible endpoint format (`/chat/completions`). So one HTTP call works for all three.
3. **Control.** We control retry logic, timeout handling, and header management directly.

### The Qwen3 Optimization

```python
if "qwen" in self.model.lower() and messages:
    first = messages[0]
    if first.get("role") == "user" and not first["content"].startswith("/no_think"):
        messages = [{"role": first["role"], "content": f"/no_think\n{first['content']}"}] + messages[1:]
```

Qwen3 models support a `/no_think` prefix that skips chain-of-thought reasoning. For structured extraction tasks (scoring, parsing), thinking tokens are wasted — we just want the answer.

This is a **model-specific optimization** that saves tokens and reduces latency. It's placed in the client so individual callers don't need to know about it.

---

## Retry Logic

```python
_MAX_RETRIES = 3

for attempt in range(_MAX_RETRIES):
    try:
        resp = self._client.post(...)

        if resp.status_code in (429, 503) and attempt < _MAX_RETRIES - 1:
            wait = 2 ** attempt  # 1s, 2s, 4s
            log.warning("LLM returned %s, retrying in %ds", resp.status_code, wait)
            time.sleep(wait)
            continue

        resp.raise_for_status()
        return data["choices"][0]["message"]["content"]

    except httpx.TimeoutException:
        if attempt < _MAX_RETRIES - 1:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        raise
```

### Exponential Backoff

When the API returns 429 (rate limited) or 503 (server overloaded), we wait and retry:
- Attempt 1: wait 1 second
- Attempt 2: wait 2 seconds
- Attempt 3: wait 4 seconds

This is **exponential backoff** (`2 ** attempt`) — the standard pattern for handling transient API failures. Each retry waits longer, giving the server time to recover.

### Why Only 429 and 503?

- **429** — Rate limited. The API is saying "slow down." Waiting helps.
- **503** — Server temporarily unavailable. Usually recovers quickly.
- **400, 401, 403, 404** — These are permanent errors (bad request, bad key, etc.). Retrying won't fix them, so we fail immediately.

### Timeout Handling

```python
except httpx.TimeoutException:
    if attempt < _MAX_RETRIES - 1:
        time.sleep(wait)
        continue
    raise
```

Network timeouts are transient by nature. The request might have succeeded on the server side — we just didn't hear back. Retrying is safe because LLM calls are idempotent (the same input always produces output, and we don't mind slightly different output on retry).

---

## Singleton Pattern

```python
_instance: LLMClient | None = None

def get_client() -> LLMClient:
    global _instance
    if _instance is None:
        base_url, model, api_key = _detect_provider()
        log.info("LLM provider: %s  model: %s", base_url, model)
        _instance = LLMClient(base_url, model, api_key)
    return _instance
```

### Why a Singleton?

1. **Connection reuse.** `httpx.Client` maintains a connection pool. Creating a new client for every request would waste TCP connections.
2. **One-time detection.** Provider detection only needs to happen once per process.
3. **Simple API.** Callers just call `get_client()` without worrying about initialization.

### Thread Safety?

The singleton isn't explicitly thread-safe (no lock around `_instance` creation). This is acceptable because:
- `_instance` is set once and never modified after
- If two threads race to create it, they'll create identical clients
- The "losing" client gets garbage collected
- In practice, `_bootstrap()` calls `get_client()` before any threads start

---

## The Convenience Method

```python
def ask(self, prompt, **kwargs) -> str:
    return self.chat([{"role": "user", "content": prompt}], **kwargs)
```

For simple single-turn queries (no system prompt, no conversation history), `ask()` saves boilerplate:

```python
# Without ask():
client.chat([{"role": "user", "content": "Score this job..."}])

# With ask():
client.ask("Score this job...")
```

---

## Design Patterns to Notice

### 1. Provider Abstraction
Three different LLM providers, one interface. Callers never import provider-specific code — they just call `get_client().chat()`.

### 2. Convention-Based Configuration
No config files for LLM selection. The provider is auto-detected from environment variables. Set `GEMINI_API_KEY` → you get Gemini. Simple.

### 3. Fail-Fast on Missing Config
```python
raise RuntimeError("No LLM provider configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or LLM_URL.")
```
If no provider is configured, the error message lists all three options. The user knows exactly what to do.

### 4. Thin Client
This class is intentionally thin — ~30 lines of actual logic. It doesn't add streaming, function calling, or conversation management. It's the **minimum viable LLM client** needed for this application's use cases.
