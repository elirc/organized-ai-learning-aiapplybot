# launcher.py — The Auto-Apply Brain

**File:** `src/applypilot/apply/launcher.py` (886 lines)
**Role:** Orchestrates the entire auto-apply workflow: acquire jobs, launch browsers, run AI agents, track results.

---

## What This File Does

This is the **most complex file** in the codebase. It coordinates:
1. Pulling jobs from the database (with atomic locking)
2. Launching Chrome instances per worker
3. Building MCP (Model Context Protocol) configs for AI agents
4. Running AI agents (Claude or Codex) via subprocess
5. Parsing the results and updating the database
6. Managing worker pools and graceful shutdown

Think of it as an **assembly line supervisor** — it doesn't fill out forms itself, but it manages the workers who do.

---

## MCP Configuration

### What is MCP?

MCP (Model Context Protocol) is the standard for connecting AI agents to external tools. In our case, the AI agent (Claude/Codex) needs to control a browser. We give it a **Playwright MCP server** that translates agent commands into browser actions.

```python
def _make_mcp_config(cdp_port, enable_gmail=False) -> dict:
    servers = {
        "playwright": {
            "command": "npx",
            "args": [
                "-y", "@playwright/mcp@latest",
                f"--cdp-endpoint=http://localhost:{cdp_port}",
                f"--viewport-size={config.DEFAULTS['viewport']}",
            ],
        }
    }
    return {"mcpServers": servers}
```

### How It Works

1. We launch Chrome with remote debugging on a specific port (e.g., 9222)
2. We create an MCP config that tells the Playwright MCP server to connect to Chrome on that port
3. We pass this config to the AI agent CLI (`claude --mcp-config ...`)
4. Now the AI agent can call tools like `browser_navigate`, `browser_click`, `browser_fill_form`

### Why Per-Worker MCP Configs?

```python
mcp_config_path = config.APP_DIR / f".mcp-apply-{worker_id}.json"
```

Each worker has its own Chrome instance on a different port (9222, 9223, 9224...). Each needs its own MCP config pointing to its own port. If workers shared a config, they'd all try to control the same browser.

### Codex MCP Config (TOML)

Codex uses TOML format instead of JSON:
```python
def _write_codex_mcp_config(workdir, cdp_port, enable_gmail=False):
    lines = [
        "[mcp_servers.playwright]",
        'command = "npx"',
        f'"args = ["-y", "@playwright/mcp@latest", "--cdp-endpoint=http://localhost:{cdp_port}"]',
    ]
```

**Why different formats?** Claude Code reads JSON MCP configs. Codex reads TOML project configs. We write whichever format the selected backend expects.

---

## Atomic Job Acquisition

```python
def acquire_job(target_url=None, min_score=7, worker_id=0):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT ... FROM jobs
            WHERE tailored_resume_path IS NOT NULL
              AND (apply_status IS NULL OR apply_status = 'failed')
              AND (apply_attempts IS NULL OR apply_attempts < 3)
              AND fit_score >= ?
            ORDER BY fit_score DESC, url
            LIMIT 1
        """, (min_score,)).fetchone()

        if not row:
            conn.rollback()
            return None

        conn.execute("""
            UPDATE jobs SET apply_status = 'in_progress',
                           agent_id = ?,
                           last_attempted_at = ?
            WHERE url = ?
        """, (f"worker-{worker_id}", now, row["url"]))
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
```

### Why `BEGIN IMMEDIATE`?

This is the **critical concurrency control** mechanism. Here's the problem:

```
Worker 1: SELECT next job → gets Job A
Worker 2: SELECT next job → ALSO gets Job A  ← BAD!
Worker 1: UPDATE Job A to 'in_progress'
Worker 2: UPDATE Job A to 'in_progress'      ← Double application!
```

`BEGIN IMMEDIATE` takes a **write lock** at the START of the transaction, before the SELECT. This means:

```
Worker 1: BEGIN IMMEDIATE → lock acquired → SELECT → UPDATE → COMMIT → lock released
Worker 2: BEGIN IMMEDIATE → WAITS (lock held) → lock acquired → SELECT → gets Job B instead
```

The SELECT + UPDATE happen atomically — no other thread can see or modify the data in between.

### Job Selection Query

```sql
WHERE tailored_resume_path IS NOT NULL    -- resume is ready
  AND (apply_status IS NULL OR apply_status = 'failed')  -- not applied or failed
  AND (apply_attempts IS NULL OR apply_attempts < 3)       -- hasn't failed too many times
  AND fit_score >= ?                                       -- minimum score threshold
ORDER BY fit_score DESC, url              -- highest scores first
LIMIT 1
```

Jobs are ordered by `fit_score DESC` so the best-matching jobs get applied to first. The `url` secondary sort ensures deterministic ordering when scores are tied.

### Blocked Sites Filter

```python
blocked_sites, blocked_patterns = _load_blocked()
site_filter = " AND ".join(f"site != '{s}'" for s in blocked_sites)
url_filter = " AND ".join(f"url NOT LIKE '{p}'" for p in blocked_patterns)
```

Sites that are known to be unsolvable (CAPTCHAs, manual-only ATS) are filtered out at query time, saving the cost of launching Chrome only to fail.

---

## Running a Job

```python
def run_job(job, port, worker_id, agent, claude_model, ...):
    # 1. Domain allowlist check
    if not _is_domain_allowed(apply_url, domain_allowlist):
        return f"failed:domain_not_allowed:{host}", 0

    # 2. Read resume text
    resume_text = txt_path.read_text(encoding="utf-8")

    # 3. Reset worker directory
    worker_dir = reset_worker_dir(worker_id)

    # 4. Build prompt and run agent
    def _run_engine(engine):
        prompt = prompt_mod.build_prompt(job=job, tailored_resume=resume_text, ...)

        if engine == "claude":
            runner = ClaudeRunner(mcp_config_path=..., model=..., ...)
            return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)
        else:
            runner = CodexRunner(model=..., ...)
            return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)

    # 5. Map outcome to DB status
    result = _run_engine(agent)
    return _map_outcome(result)
```

### The Outcome Mapper

```python
def _map_outcome(run_result):
    parsed = run_result.parsed  # ParsedOutcome from the parser

    if parsed.status == "APPLIED":
        return "applied", run_result.duration_ms
    if parsed.status == "CAPTCHA":
        return "captcha", run_result.duration_ms
    if parsed.status == "DRY_RUN":
        return "skipped", run_result.duration_ms
    if parsed.status == "FAILED":
        return f"failed:{parsed.reason}", run_result.duration_ms
    return f"failed:needs_review:{parsed.reason}", run_result.duration_ms
```

This converts the agent's output (which can be messy) into a clean database status. The agent might say "RESULT: FAILED - job_expired_no_longer_accepting", and this gets normalized to `failed:expired`.

### Auto Mode (Fallback Chain)

```python
if agent in {"claude", "codex"}:
    result = _run_engine(agent)
    return _map_outcome(result)

# auto mode: try Claude first, then Codex
for engine in ("claude", "codex"):
    result = _run_engine(engine)
    if result.parsed.status != "NEEDS_REVIEW":
        return _map_outcome(result)  # success or clear failure

return "failed:auto_fallback_exhausted", 0
```

In `--agent auto` mode:
1. Try Claude first
2. If Claude fails with NEEDS_REVIEW (ambiguous result), try Codex
3. If both fail, mark as `auto_fallback_exhausted`

**Why NEEDS_REVIEW triggers fallback?** APPLIED, FAILED, CAPTCHA, and DRY_RUN are all definitive outcomes. NEEDS_REVIEW means "I couldn't figure out what happened" — maybe the other agent will do better.

---

## Permanent Failure Classification

```python
PERMANENT_FAILURES = {
    "expired", "captcha", "login_issue",
    "not_eligible_location", "already_applied",
    "account_required", "sso_required",
    "domain_not_allowed", ...
}

def _is_permanent_failure(result):
    reason = result.split(":", 1)[-1]
    return reason in PERMANENT_FAILURES
```

Some failures should **never be retried**:
- **expired** — the job listing is gone
- **not_eligible_location** — you're in the wrong city
- **already_applied** — you already applied
- **captcha** — the site has unsolvable CAPTCHAs

For these, `apply_attempts` is set to 99 (effectively infinite), preventing future retry.

Transient failures (timeout, page_error, stuck) get retried up to 3 times.

---

## The Worker Loop

```python
def worker_loop(worker_id, limit, ...):
    while not _stop_event.is_set():
        if not continuous and jobs_done >= limit:
            break

        job = acquire_job(...)
        if not job:
            if not continuous:
                break  # queue empty, we're done
            _stop_event.wait(timeout=POLL_INTERVAL)  # wait and retry
            continue

        chrome_proc = launch_chrome(worker_id, port=port, headless=headless)
        try:
            result, duration_ms = run_job(job, port=port, ...)

            if result == "applied":
                mark_result(job["url"], "applied", duration_ms=duration_ms)
                applied += 1
            elif result == "skipped":
                release_lock(job["url"])
            else:
                mark_result(job["url"], "failed", reason, ...)
                failed += 1
        finally:
            cleanup_worker(worker_id, chrome_proc)  # always kill Chrome
```

### The Loop Structure

1. **Check stop conditions** — limit reached? shutdown requested?
2. **Acquire a job** — atomic grab from the DB
3. **Launch Chrome** — fresh instance on this worker's port
4. **Run the job** — prompt → agent → parse → result
5. **Update DB** — applied/failed/skipped
6. **Clean up** — kill Chrome (ALWAYS, via `finally:`)
7. **Delay** — wait `min_delay_seconds` between jobs

### Why `finally: cleanup_worker()`?

If the agent crashes, or the user presses Ctrl+C, or an exception occurs — Chrome MUST be killed. Orphaned Chrome processes eat RAM and block ports. The `finally` block guarantees cleanup regardless of how the try block exits.

---

## The Main Entry Point

```python
def main(limit, target_url, min_score, headless, agent, ...):
    # Double Ctrl+C handler
    def _sigint_handler(sig, frame):
        nonlocal _ctrl_c_count
        _ctrl_c_count += 1
        if _ctrl_c_count == 1:
            # Kill active agent processes (skip current jobs)
            with _agent_lock:
                for wid, cproc in list(_agent_procs.items()):
                    _kill_process_tree(cproc.pid)
        else:
            # Full stop
            _stop_event.set()
            kill_all_chrome()
            raise KeyboardInterrupt

    # Single worker: run directly in main thread
    if workers == 1:
        worker_loop(worker_id=0, ...)
    else:
        # Multi-worker: ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(worker_loop, worker_id=i, ...): i for i in range(workers)}
```

### Why Main Thread for Single Worker?

Threading adds overhead (thread creation, context switching). For the common case (1 worker), running directly in the main thread is simpler and slightly faster. Threading is only used when `--workers > 1`.

### Work Distribution

```python
if effective_limit:
    base = effective_limit // workers
    extra = effective_limit % workers
    limits = [base + (1 if i < extra else 0) for i in range(workers)]
```

If `limit=7` and `workers=3`: Worker 0 gets 3 jobs, Worker 1 gets 2, Worker 2 gets 2. The remainder is distributed to the first workers.

---

## Agent Process Tracking

```python
_agent_procs: dict[int, subprocess.Popen] = {}
_agent_lock = threading.Lock()

def _register_agent_proc(worker_id, proc):
    with _agent_lock:
        _agent_procs[worker_id] = proc

def _unregister_agent_proc(worker_id):
    with _agent_lock:
        _agent_procs.pop(worker_id, None)
```

Active agent processes are tracked so they can be killed on Ctrl+C. The lock prevents race conditions when multiple workers register/unregister simultaneously.

---

## Design Patterns to Notice

### 1. Command Pattern
`run_job()` takes all parameters it needs and returns a result. It doesn't access global state (except the database). This makes it testable and composable.

### 2. Strategy Pattern
The `agent` parameter selects which backend to use. The `_run_engine()` closure encapsulates backend-specific setup (MCP config format, runner class) behind a common interface.

### 3. Actor Model (Lightweight)
Each worker loop is essentially an actor: it has its own state (worker_id, port, counts), processes messages (jobs from the DB), and communicates results back to the DB.

### 4. Result Types as Strings
Results like `"failed:domain_not_allowed:example.com"` use colon-separated strings instead of structured objects. This is a pragmatic choice — the result goes straight into a TEXT column in SQLite, and parsing is trivial with `.split(":")`.
