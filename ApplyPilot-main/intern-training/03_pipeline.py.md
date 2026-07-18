# pipeline.py — The Orchestrator

**File:** `src/applypilot/pipeline.py` (532 lines)
**Role:** Runs pipeline stages in sequence or concurrently. The "conductor" of Stages 1-5.

---

## What This File Does

This is the brain that decides **when** to run each stage and **how** to coordinate them. It supports two execution modes:

1. **Sequential** — Run stages one at a time: discover → enrich → score → tailor → cover → pdf
2. **Streaming** — Run all stages concurrently as threads, using the DB as a conveyor belt

---

## Stage Definitions

```python
STAGE_ORDER = ("discover", "enrich", "score", "tailor", "cover", "pdf")

STAGE_META: dict[str, dict] = {
    "discover": {"desc": "Job discovery (JobSpy + Workday + smart extract)"},
    "enrich":   {"desc": "Detail enrichment (full descriptions + apply URLs)"},
    ...
}

_UPSTREAM: dict[str, str | None] = {
    "discover": None,
    "enrich":   "discover",
    "score":    "enrich",
    "tailor":   "score",
    "cover":    "tailor",
    "pdf":      "cover",
}
```

### The Upstream Dependency Map

`_UPSTREAM` defines the directed acyclic graph (DAG) of stage dependencies:
```
discover → enrich → score → tailor → cover → pdf
```

Each stage depends on the one before it. In streaming mode, a stage won't finish until its upstream is done AND it has no remaining work.

**Why a dict instead of just using the order?** Because you can run a subset of stages. If you run `applypilot run score tailor`, the system needs to know that `score` depends on `enrich` (which was skipped) — so it marks `enrich` as "done" and lets `score` proceed.

---

## Stage Runners

Each stage has a thin wrapper function:

```python
def _run_discover(workers=1) -> dict:
    from applypilot.discovery.jobspy import run_discovery
    run_discovery()
    from applypilot.discovery.workday import run_workday_discovery
    run_workday_discovery(workers=workers)
    from applypilot.discovery.smartextract import run_smart_extract
    run_smart_extract(workers=workers)
    return stats
```

### Why Wrappers?

1. **Error isolation.** If JobSpy fails, Workday still runs. Each sub-scraper is wrapped in its own try/except.
2. **Uniform interface.** All runners return a dict with a `"status"` key. The orchestrator doesn't care about the internal details.
3. **Lazy imports.** The heavy libraries (pandas, playwright, jobspy) are only loaded when their stage actually runs.

```python
_STAGE_RUNNERS: dict[str, callable] = {
    "discover": _run_discover,
    "enrich":   _run_enrich,
    ...
}
```

This dict maps stage names to their runner functions, allowing the orchestrator to call any stage by name without a giant if/else chain.

---

## Sequential Mode

```python
def _run_sequential(ordered, min_score, workers=1) -> dict:
    for name in ordered:
        runner = _STAGE_RUNNERS[name]
        kwargs = {}
        if name in ("tailor", "cover"):
            kwargs["min_score"] = min_score
        if name in ("discover", "enrich"):
            kwargs["workers"] = workers
        result = runner(**kwargs)
```

Simple loop. For each stage:
1. Print a banner with the stage name and timestamp
2. Call the runner function with appropriate kwargs
3. Track timing and errors
4. Print results

**Note the keyword argument routing:**
```python
if name in ("tailor", "cover"):
    kwargs["min_score"] = min_score
```
Not all stages need all parameters. Discovery doesn't care about `min_score`. Scoring doesn't need `workers`. The pipeline handles this routing so individual stages don't need to accept and ignore irrelevant parameters.

---

## Streaming Mode (The Interesting Part)

Streaming mode runs all stages concurrently, using the database as a **conveyor belt**:

```
Thread 1 (discover): Scrapes jobs → writes to DB
Thread 2 (enrich):   Polls DB for unscraped jobs → enriches → writes back
Thread 3 (score):    Polls DB for unscored enriched jobs → scores → writes back
Thread 4 (tailor):   Polls DB for scored untailored jobs → tailors → writes back
```

As soon as Stage 1 writes a job, Stage 2 can pick it up — even while Stage 1 is still finding more jobs.

### The StageTracker

```python
class _StageTracker:
    def __init__(self):
        self._events = {stage: threading.Event() for stage in STAGE_ORDER}
        self._results = {}
        self._lock = threading.Lock()

    def mark_done(self, stage, result=None):
        with self._lock:
            self._results[stage] = result
        self._events[stage].set()

    def wait(self, stage, timeout=None):
        return self._events[stage].wait(timeout=timeout)
```

`threading.Event()` is a thread-safe signal. When Stage 1 (discover) finishes, it calls `tracker.mark_done("discover")`, which signals `_events["discover"]`. Any thread waiting on `tracker.wait("discover")` wakes up immediately.

**Why not just check the DB?** Performance. Polling the DB every second is wasteful. `Event.wait()` is a zero-CPU sleep until the signal fires.

### The Streaming Loop

```python
def _run_stage_streaming(stage, tracker, stop_event, min_score, workers):
    if stage == "discover":
        # Discover runs once
        result = runner(**kwargs)
        tracker.mark_done(stage, result)
        return

    # Downstream stages: poll for work
    while not stop_event.is_set():
        pending = _count_pending(stage, min_score)

        if pending > 0:
            runner(**kwargs)  # process available work
        else:
            upstream_done = tracker.is_done(upstream)
            if upstream_done:
                break  # no work + upstream done = this stage is done
            stop_event.wait(timeout=_STREAM_POLL_INTERVAL)  # wait and retry
```

**The key insight:** A downstream stage is "done" when two conditions are met:
1. Its upstream is finished (no more work will be produced)
2. It has no remaining pending items (all work is processed)

**Why does discover run once?** Unlike enrichment/scoring which process jobs one-by-one, discovery does a full crawl in one batch. Running it in a loop would just re-scrape the same jobs.

### Pending Work SQL

```python
_PENDING_SQL = {
    "enrich": "SELECT COUNT(*) FROM jobs WHERE detail_scraped_at IS NULL",
    "score":  "SELECT COUNT(*) FROM jobs WHERE full_description IS NOT NULL AND fit_score IS NULL",
    "tailor": "SELECT COUNT(*) FROM jobs WHERE fit_score >= ? AND tailored_resume_path IS NULL ...",
}
```

These SQL queries count how many jobs need processing at each stage. They're the "work queue" — the database IS the queue.

---

## Stage Resolution

```python
def _resolve_stages(stage_names):
    if "all" in stage_names:
        return list(STAGE_ORDER)

    resolved = []
    for name in stage_names:
        if name not in STAGE_META:
            raise SystemExit(1)
        if name not in resolved:
            resolved.append(name)

    # Maintain canonical order
    return [s for s in STAGE_ORDER if s in resolved]
```

If you type `applypilot run tailor score`, the stages are reordered to `score, tailor` (canonical order). This prevents accidentally running tailor before score.

**Why not just use the user's order?** Because the pipeline has dependencies. Running tailor before score would find zero eligible jobs and do nothing — confusing for the user.

---

## The Pipeline Entry Point

```python
def run_pipeline(stages=None, min_score=7, dry_run=False, stream=False, workers=1):
    load_env()
    ensure_dirs()
    init_db()

    ordered = _resolve_stages(stages or ["all"])

    if dry_run:
        # Just print what would happen
        for name in ordered:
            console.print(f"    {name}  {STAGE_META[name]['desc']}")
        return

    if stream:
        result = _run_streaming(ordered, min_score, workers)
    else:
        result = _run_sequential(ordered, min_score, workers)
```

### Dry Run Mode

When `--dry-run` is passed, the pipeline prints what it *would* do without actually doing it. This is a common CLI pattern — let users verify before committing.

### Summary Table

After execution, a Rich table shows timing and status for each stage:
```
┌──────────┬────────┬───────┐
│ Stage    │ Status │ Time  │
├──────────┼────────┼───────┤
│ discover │ ok     │ 45.2s │
│ enrich   │ ok     │ 23.1s │
│ score    │ ok     │ 12.3s │
│ Total    │        │ 80.6s │
└──────────┴────────┴───────┘
```

This provides immediate feedback on what happened and how long each stage took.

---

## Design Patterns to Notice

### 1. Database as Message Queue
Instead of RabbitMQ or Redis for inter-stage communication, the database serves as both the work queue and the result store. This is simpler for a small system but doesn't scale to high throughput.

### 2. Thread Coordination via Events
`threading.Event` provides efficient thread-safe signaling without polling. This is the standard Python pattern for "wait until something happens."

### 3. Graceful Shutdown
```python
except KeyboardInterrupt:
    stop_event.set()  # signal all threads to stop
    for t in threads.values():
        t.join(timeout=10)  # wait up to 10s for cleanup
```
On Ctrl+C, the stop event is set, all stage threads check it in their loops and exit gracefully.

### 4. Separation of Orchestration from Execution
`pipeline.py` doesn't know *how* to scrape jobs or score them. It only knows *when* to run each stage and *how* to coordinate them. The actual work is in the stage modules.
