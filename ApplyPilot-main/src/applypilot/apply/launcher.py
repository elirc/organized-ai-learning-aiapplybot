"""Apply orchestration: acquire jobs, run agent sessions, track results.

This is the main entry point for the apply pipeline. It pulls jobs from
the database, launches Chrome + agent CLI for each one, parses the
result, and updates the database. Supports parallel workers via --workers.
"""

import atexit
import json
import logging
import platform
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console
from rich.live import Live

from applypilot import config
from applypilot.database import get_connection
from applypilot.apply import prompt as prompt_mod
from applypilot.apply.agents import ClaudeRunner, CodexRunner
from applypilot.apply.chrome import (
    launch_chrome, cleanup_worker, kill_all_chrome,
    reset_worker_dir, cleanup_on_exit, _kill_process_tree,
    BASE_CDP_PORT,
)
from applypilot.apply.dashboard import (
    init_worker, update_state, add_event,
    render_full, get_totals,
)

logger = logging.getLogger(__name__)

# Blocked sites loaded from config/sites.yaml
def _load_blocked():
    from applypilot.config import load_blocked_sites
    return load_blocked_sites()

# How often to poll the DB when the queue is empty (seconds)
POLL_INTERVAL = config.DEFAULTS["poll_interval"]

# Thread-safe shutdown coordination
_stop_event = threading.Event()

# Track active agent processes for skip (Ctrl+C) handling
_agent_procs: dict[int, subprocess.Popen] = {}
_agent_lock = threading.Lock()

# Register cleanup on exit
atexit.register(cleanup_on_exit)
if platform.system() != "Windows":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


# ---------------------------------------------------------------------------
# MCP config
# ---------------------------------------------------------------------------

def _make_mcp_config(cdp_port: int, enable_gmail: bool = False) -> dict:
    """Build Claude MCP config dict for a specific CDP port."""
    servers: dict[str, dict] = {
        "playwright": {
            "command": "npx",
            "args": [
                "-y",
                "@playwright/mcp@latest",
                f"--cdp-endpoint=http://localhost:{cdp_port}",
                f"--viewport-size={config.DEFAULTS['viewport']}",
            ],
        }
    }
    if enable_gmail:
        servers["gmail"] = {
            "command": "npx",
            "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
        }
    return {"mcpServers": servers}


def _write_codex_mcp_config(workdir: Path, cdp_port: int, enable_gmail: bool = False) -> Path:
    """Write worker-local Codex MCP config TOML and return path."""
    codex_dir = workdir / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = codex_dir / "config.toml"

    lines = [
        "[mcp_servers.playwright]",
        'command = "npx"',
        (
            "args = ["
            f'"-y", "@playwright/mcp@latest", '
            f'"--cdp-endpoint=http://localhost:{cdp_port}", '
            f'"--viewport-size={config.DEFAULTS["viewport"]}"'
            "]"
        ),
        "",
    ]
    if enable_gmail:
        lines.extend(
            [
                "[mcp_servers.gmail]",
                'command = "npx"',
                'args = ["-y", "@gongrzhe/server-gmail-autoauth-mcp"]',
                "",
            ]
        )
    cfg_path.write_text("\n".join(lines), encoding="utf-8")
    return cfg_path


def _write_codex_output_schema(workdir: Path) -> Path:
    """Write strict final-output JSON schema for Codex."""
    schema_dir = workdir / ".codex"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = schema_dir / "apply-result-schema.json"
    schema = {
        "type": "object",
        "required": ["result", "reason", "submitted"],
        "properties": {
            "result": {
                "type": "string",
                "enum": ["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"],
            },
            "reason": {"type": "string"},
            "submitted": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return schema_path


def _register_agent_proc(worker_id: int, proc: subprocess.Popen[str]) -> None:
    with _agent_lock:
        _agent_procs[worker_id] = proc


def _unregister_agent_proc(worker_id: int) -> None:
    with _agent_lock:
        _agent_procs.pop(worker_id, None)


def _url_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip()
    return host


def _is_domain_allowed(url: str, allowlist: list[str] | None) -> bool:
    if not allowlist:
        return True
    host = _url_host(url)
    if not host:
        return False
    for allowed in allowlist:
        a = allowed.strip().lower()
        if not a:
            continue
        if host == a or host.endswith(f".{a}"):
            return True
    return False


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def acquire_job(target_url: str | None = None, min_score: int = 7,
                worker_id: int = 0) -> dict | None:
    """Atomically acquire the next job to apply to.

    Args:
        target_url: Apply to a specific URL instead of picking from queue.
        min_score: Minimum fit_score threshold.
        worker_id: Worker claiming this job (for tracking).

    Returns:
        Job dict or None if the queue is empty.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        from applypilot.config import is_manual_ats

        manual_rows_marked = False
        blocked_sites, blocked_patterns = _load_blocked() if not target_url else (set(), [])

        while True:
            if target_url:
                like = f"%{target_url.split('?')[0].rstrip('/')}%"
                row = conn.execute(
                    """
                    SELECT url, title, site, application_url, tailored_resume_path,
                           fit_score, location, full_description, cover_letter_path
                    FROM jobs
                    WHERE (url = ? OR application_url = ? OR application_url LIKE ? OR url LIKE ?)
                      AND tailored_resume_path IS NOT NULL
                      AND applied_at IS NULL
                      AND (apply_status IS NULL OR apply_status = 'failed')
                    LIMIT 1
                    """,
                    (target_url, target_url, like, like),
                ).fetchone()
            else:
                conditions = [
                    "tailored_resume_path IS NOT NULL",
                    "(apply_status IS NULL OR apply_status = 'failed')",
                    f"(apply_attempts IS NULL OR apply_attempts < {config.DEFAULTS['max_apply_attempts']})",
                    "fit_score >= ?",
                ]
                params: list[object] = [min_score]

                for site in sorted(blocked_sites):
                    conditions.append("site != ?")
                    params.append(site)
                for pattern in blocked_patterns:
                    conditions.append("url NOT LIKE ?")
                    params.append(pattern)

                where_clause = " AND ".join(conditions)
                row = conn.execute(
                    f"""
                    SELECT url, title, site, application_url, tailored_resume_path,
                           fit_score, location, full_description, cover_letter_path
                    FROM jobs
                    WHERE {where_clause}
                    ORDER BY fit_score DESC, url
                    LIMIT 1
                    """,
                    params,
                ).fetchone()

            if not row:
                if manual_rows_marked:
                    conn.commit()
                else:
                    conn.rollback()
                return None

            apply_url = row["application_url"] or row["url"]
            if is_manual_ats(apply_url):
                conn.execute(
                    "UPDATE jobs SET apply_status = 'manual', apply_error = 'manual ATS', agent_id = NULL WHERE url = ?",
                    (row["url"],),
                )
                manual_rows_marked = True
                logger.info("Skipping manual ATS: %s", row["url"][:80])
                if target_url:
                    conn.commit()
                    return None
                continue

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE jobs SET apply_status = 'in_progress',
                               agent_id = ?,
                               last_attempted_at = ?
                WHERE url = ?
                """,
                (f"worker-{worker_id}", now, row["url"]),
            )
            conn.commit()
            return dict(row)
    except Exception:
        conn.rollback()
        raise


def mark_result(url: str, status: str, error: str | None = None,
                permanent: bool = False, duration_ms: int | None = None,
                task_id: str | None = None) -> None:
    """Update a job's apply status in the database."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    if status == "applied":
        conn.execute("""
            UPDATE jobs SET apply_status = 'applied', applied_at = ?,
                           apply_error = NULL, agent_id = NULL,
                           apply_duration_ms = ?, apply_task_id = ?
            WHERE url = ?
        """, (now, duration_ms, task_id, url))
    else:
        attempts = 99 if permanent else "COALESCE(apply_attempts, 0) + 1"
        conn.execute(f"""
            UPDATE jobs SET apply_status = ?, apply_error = ?,
                           apply_attempts = {attempts}, agent_id = NULL,
                           apply_duration_ms = ?, apply_task_id = ?
            WHERE url = ?
        """, (status, error or "unknown", duration_ms, task_id, url))
    conn.commit()


def release_lock(url: str) -> None:
    """Release the in_progress lock without changing status."""
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET apply_status = NULL, agent_id = NULL WHERE url = ? AND apply_status = 'in_progress'",
        (url,),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Utility modes (--gen, --mark-applied, --mark-failed, --reset-failed)
# ---------------------------------------------------------------------------

def gen_prompt(
    target_url: str,
    min_score: int = 7,
    model: str = "haiku",
    worker_id: int = 0,
    dry_run: bool = False,
    domain_allowlist: list[str] | None = None,
    min_delay_seconds: int = 10,
    json_output: bool = False,
    enable_gmail: bool = False,
) -> Path | None:
    """Generate a prompt file and print the Claude CLI command for manual debugging.

    Returns:
        Path to the generated prompt file, or None if no job found.
    """
    job = acquire_job(target_url=target_url, min_score=min_score, worker_id=worker_id)
    if not job:
        return None

    # Read resume text
    resume_path = job.get("tailored_resume_path")
    txt_path = Path(resume_path).with_suffix(".txt") if resume_path else None
    resume_text = ""
    if txt_path and txt_path.exists():
        resume_text = txt_path.read_text(encoding="utf-8")

    prompt = prompt_mod.build_prompt(
        job=job,
        tailored_resume=resume_text,
        dry_run=dry_run,
        domain_allowlist=domain_allowlist or [],
        min_delay_seconds=min_delay_seconds,
        json_output=json_output,
        workspace_dir=config.APPLY_WORKER_DIR / f"prompt-preview-{worker_id}",
    )

    # Release the lock so the job stays available
    release_lock(job["url"])

    # Write prompt file
    config.ensure_dirs()
    site_slug = (job.get("site") or "unknown")[:20].replace(" ", "_")
    prompt_file = config.LOG_DIR / f"prompt_{site_slug}_{job['title'][:30].replace(' ', '_')}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    # Write MCP config for reference
    port = BASE_CDP_PORT + worker_id
    mcp_path = config.APP_DIR / f".mcp-apply-{worker_id}.json"
    mcp_path.write_text(json.dumps(_make_mcp_config(port, enable_gmail=enable_gmail)), encoding="utf-8")

    return prompt_file


def mark_job(url: str, status: str, reason: str | None = None) -> None:
    """Manually mark a job's apply status in the database.

    Args:
        url: Job URL to mark.
        status: Either 'applied' or 'failed'.
        reason: Failure reason (only for status='failed').
    """
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    if status == "applied":
        conn.execute("""
            UPDATE jobs SET apply_status = 'applied', applied_at = ?,
                           apply_error = NULL, agent_id = NULL
            WHERE url = ?
        """, (now, url))
    else:
        conn.execute("""
            UPDATE jobs SET apply_status = 'failed', apply_error = ?,
                           apply_attempts = 99, agent_id = NULL
            WHERE url = ?
        """, (reason or "manual", url))
    conn.commit()


def reset_failed() -> int:
    """Reset all failed jobs so they can be retried.

    Returns:
        Number of jobs reset.
    """
    conn = get_connection()
    cursor = conn.execute("""
        UPDATE jobs SET apply_status = NULL, apply_error = NULL,
                       apply_attempts = 0, agent_id = NULL
        WHERE apply_status = 'failed'
          OR (apply_status IS NOT NULL AND apply_status != 'applied'
              AND apply_status != 'in_progress')
    """)
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Per-job execution
# ---------------------------------------------------------------------------

def run_job(
    job: dict,
    port: int,
    worker_id: int = 0,
    agent: str = "claude",
    claude_model: str = "haiku",
    codex_model: str | None = None,
    dry_run: bool = False,
    enable_gmail: bool = False,
    domain_allowlist: list[str] | None = None,
    min_delay_seconds: int = 10,
    timeout_s: int = config.DEFAULTS["apply_timeout"],
) -> tuple[str, int]:
    """Run one job through the selected agent backend."""
    apply_url = job.get("application_url") or job["url"]
    if not _is_domain_allowed(apply_url, domain_allowlist):
        host = _url_host(apply_url) or "unknown-domain"
        return f"failed:domain_not_allowed:{host}", 0

    resume_path = job.get("tailored_resume_path")
    txt_path = Path(resume_path).with_suffix(".txt") if resume_path else None
    resume_text = ""
    if txt_path and txt_path.exists():
        resume_text = txt_path.read_text(encoding="utf-8")

    worker_dir = reset_worker_dir(worker_id)

    update_state(
        worker_id,
        status="applying",
        job_title=job["title"],
        company=job.get("site", ""),
        score=job.get("fit_score", 0),
        start_time=time.time(),
        actions=0,
        last_action=f"starting ({agent})",
    )
    add_event(f"[W{worker_id}] Starting ({agent}): {job['title'][:40]} @ {job.get('site', '')}")

    worker_log = config.LOG_DIR / f"worker-{worker_id}.log"
    ts_header = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with worker_log.open("a", encoding="utf-8") as lf:
        lf.write(
            f"\n{'=' * 60}\n"
            f"[{ts_header}] {job['title']} @ {job.get('site', '')}\n"
            f"URL: {apply_url}\n"
            f"Score: {job.get('fit_score', 'N/A')}/10\n"
            f"Agent: {agent}\n"
            f"{'=' * 60}\n"
        )

    def _map_outcome(run_result) -> tuple[str, int]:
        elapsed = int(run_result.duration_ms / 1000)
        parsed = run_result.parsed
        with worker_log.open("a", encoding="utf-8") as lf:
            lf.write(f"[{run_result.engine}] raw_log={run_result.raw_log_path}\n")
            if run_result.events_path:
                lf.write(f"[{run_result.engine}] events={run_result.events_path}\n")
            lf.write(f"[{run_result.engine}] parsed={parsed.status}:{parsed.reason}\n")

        if parsed.status == "APPLIED":
            add_event(f"[W{worker_id}] APPLIED ({elapsed}s): {job['title'][:30]}")
            update_state(worker_id, status="applied", last_action=f"APPLIED ({elapsed}s)")
            return "applied", run_result.duration_ms
        if parsed.status == "CAPTCHA":
            add_event(f"[W{worker_id}] CAPTCHA ({elapsed}s): {job['title'][:30]}")
            update_state(worker_id, status="captcha", last_action=f"CAPTCHA ({elapsed}s)")
            return "captcha", run_result.duration_ms
        if parsed.status == "DRY_RUN":
            add_event(f"[W{worker_id}] DRY_RUN ({elapsed}s): {parsed.reason[:40]}")
            update_state(worker_id, status="idle", last_action=f"DRY_RUN ({elapsed}s)")
            return "skipped", run_result.duration_ms
        if parsed.status == "FAILED":
            reason = parsed.reason or "unknown"
            if reason in {"captcha", "expired", "login_issue"}:
                update_state(worker_id, status=reason, last_action=f"{reason.upper()} ({elapsed}s)")
            else:
                update_state(worker_id, status="failed", last_action=f"FAILED: {reason[:25]}")
            add_event(f"[W{worker_id}] FAILED ({elapsed}s): {reason[:40]}")
            return f"failed:{reason}", run_result.duration_ms

        reason = parsed.reason or "needs_review"
        add_event(f"[W{worker_id}] NEEDS_REVIEW ({elapsed}s): {reason[:40]}")
        update_state(worker_id, status="failed", last_action=f"NEEDS_REVIEW: {reason[:18]}")
        return f"failed:needs_review:{reason}", run_result.duration_ms

    def _run_engine(engine: str):
        prompt = prompt_mod.build_prompt(
            job=job,
            tailored_resume=resume_text,
            dry_run=dry_run,
            domain_allowlist=domain_allowlist or [],
            min_delay_seconds=min_delay_seconds,
            json_output=(engine == "codex"),
            workspace_dir=worker_dir,
        )
        if engine == "claude":
            mcp_config_path = config.APP_DIR / f".mcp-apply-{worker_id}.json"
            mcp_config_path.write_text(json.dumps(_make_mcp_config(port, enable_gmail=enable_gmail)), encoding="utf-8")
            runner = ClaudeRunner(
                mcp_config_path=mcp_config_path,
                model=claude_model,
                worker_id=worker_id,
                log_dir=config.LOG_DIR,
                on_process_start=_register_agent_proc,
                on_process_exit=_unregister_agent_proc,
            )
            return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)

        _write_codex_mcp_config(worker_dir, port, enable_gmail=enable_gmail)
        schema_path = _write_codex_output_schema(worker_dir)
        runner = CodexRunner(
            model=codex_model,
            worker_id=worker_id,
            log_dir=config.LOG_DIR,
            output_schema_path=schema_path,
            on_process_start=_register_agent_proc,
            on_process_exit=_unregister_agent_proc,
        )
        return runner.run(prompt, workdir=worker_dir, timeout_s=timeout_s)

    if agent in {"claude", "codex"}:
        try:
            result = _run_engine(agent)
        except FileNotFoundError as e:
            return f"failed:needs_review:{agent}_not_installed:{e}", 0
        except Exception as e:
            return f"failed:{agent}_error:{str(e)[:80]}", 0
        if result.exit_code != 0:
            return f"failed:{agent}_exit_{result.exit_code}", result.duration_ms
        return _map_outcome(result)

    # auto mode: try Claude first, then Codex on hard failure / parse failure
    errors: list[str] = []
    for engine in ("claude", "codex"):
        try:
            result = _run_engine(engine)
        except FileNotFoundError:
            errors.append(f"{engine}_not_installed")
            continue
        except Exception as e:
            errors.append(f"{engine}_error:{str(e)[:50]}")
            continue

        if result.exit_code != 0:
            errors.append(f"{engine}_exit_{result.exit_code}")
            continue
        if result.parsed.status == "NEEDS_REVIEW":
            errors.append(f"{engine}_needs_review:{result.parsed.reason}")
            continue
        return _map_outcome(result)

    return f"failed:needs_review:auto_fallback_exhausted:{'|'.join(errors) or 'no_runner'}", 0


# ---------------------------------------------------------------------------
# Permanent failure classification
# ---------------------------------------------------------------------------

PERMANENT_FAILURES: set[str] = {
    "expired", "captcha", "login_issue",
    "not_eligible_location", "not_eligible_salary",
    "already_applied", "account_required",
    "not_a_job_application", "unsafe_permissions",
    "unsafe_verification", "sso_required",
    "domain_not_allowed",
    "site_blocked", "cloudflare_blocked", "blocked_by_cloudflare",
}

PERMANENT_PREFIXES: tuple[str, ...] = ("site_blocked", "cloudflare", "blocked_by", "domain_not_allowed")


def _is_permanent_failure(result: str) -> bool:
    """Determine if a failure should never be retried."""
    reason = result.split(":", 1)[-1] if ":" in result else result
    return (
        result in PERMANENT_FAILURES
        or reason in PERMANENT_FAILURES
        or any(reason.startswith(p) for p in PERMANENT_PREFIXES)
    )


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

def worker_loop(worker_id: int = 0, limit: int = 1,
                target_url: str | None = None,
                min_score: int = 7, headless: bool = False,
                agent: str = "claude",
                claude_model: str = "haiku",
                codex_model: str | None = None,
                dry_run: bool = False,
                continuous: bool = False,
                enable_gmail: bool = False,
                domain_allowlist: list[str] | None = None,
                min_delay_seconds: int = 10,
                timeout_s: int = config.DEFAULTS["apply_timeout"]) -> tuple[int, int]:
    """Run jobs sequentially until limit is reached or queue is empty.

    Args:
        worker_id: Numeric worker identifier.
        limit: Max jobs to process for non-continuous runs.
        target_url: Apply to a specific URL.
        min_score: Minimum fit_score threshold.
        headless: Run Chrome headless.
        agent: Backend selection (claude, codex, auto).
        claude_model: Claude model name.
        codex_model: Codex model name.
        dry_run: Don't click Submit.
        continuous: Keep polling for new jobs.
        enable_gmail: Enable Gmail MCP server.
        domain_allowlist: Restrict applications by host.
        min_delay_seconds: Delay between attempts.
        timeout_s: CLI timeout.

    Returns:
        Tuple of (applied_count, failed_count).
    """
    applied = 0
    failed = 0
    jobs_done = 0
    empty_polls = 0
    port = BASE_CDP_PORT + worker_id

    if not continuous and limit <= 0:
        update_state(worker_id, status="done", last_action="no work assigned")
        return applied, failed

    while not _stop_event.is_set():
        if not continuous and jobs_done >= limit:
            break

        update_state(worker_id, status="idle", job_title="", company="",
                     last_action="waiting for job", actions=0)

        job = acquire_job(target_url=target_url, min_score=min_score,
                          worker_id=worker_id)
        if not job:
            if not continuous:
                add_event(f"[W{worker_id}] Queue empty")
                update_state(worker_id, status="done", last_action="queue empty")
                break
            empty_polls += 1
            update_state(worker_id, status="idle",
                         last_action=f"polling ({empty_polls})")
            if empty_polls == 1:
                add_event(f"[W{worker_id}] Queue empty, polling every {POLL_INTERVAL}s...")
            # Use Event.wait for interruptible sleep
            if _stop_event.wait(timeout=POLL_INTERVAL):
                break  # Stop was requested during wait
            continue

        empty_polls = 0

        chrome_proc = None
        try:
            add_event(f"[W{worker_id}] Launching Chrome...")
            chrome_proc = launch_chrome(worker_id, port=port, headless=headless)

            result, duration_ms = run_job(
                job,
                port=port,
                worker_id=worker_id,
                agent=agent,
                claude_model=claude_model,
                codex_model=codex_model,
                dry_run=dry_run,
                enable_gmail=enable_gmail,
                domain_allowlist=domain_allowlist,
                min_delay_seconds=min_delay_seconds,
                timeout_s=timeout_s,
            )

            if result == "skipped":
                release_lock(job["url"])
                add_event(f"[W{worker_id}] Skipped: {job['title'][:30]}")
            elif result == "applied":
                mark_result(job["url"], "applied", duration_ms=duration_ms)
                applied += 1
                update_state(worker_id, jobs_applied=applied,
                             jobs_done=applied + failed)
            else:
                reason = result.split(":", 1)[-1] if ":" in result else result
                mark_result(job["url"], "failed", reason,
                            permanent=_is_permanent_failure(result),
                            duration_ms=duration_ms)
                failed += 1
                update_state(worker_id, jobs_failed=failed,
                             jobs_done=applied + failed)

        except KeyboardInterrupt:
            release_lock(job["url"])
            if _stop_event.is_set():
                break
            add_event(f"[W{worker_id}] Job skipped (Ctrl+C)")
            continue
        except Exception as e:
            logger.exception("Worker %d launcher error", worker_id)
            add_event(f"[W{worker_id}] Launcher error: {str(e)[:40]}")
            release_lock(job["url"])
            failed += 1
            update_state(worker_id, jobs_failed=failed)
        finally:
            if chrome_proc:
                cleanup_worker(worker_id, chrome_proc)

        jobs_done += 1
        if target_url:
            break
        if min_delay_seconds > 0 and not _stop_event.is_set():
            if _stop_event.wait(timeout=min_delay_seconds):
                break

    update_state(worker_id, status="done", last_action="finished")
    return applied, failed


# ---------------------------------------------------------------------------
# Main entry point (called from cli.py)
# ---------------------------------------------------------------------------

def main(
    limit: int = 1,
    target_url: str | None = None,
    min_score: int = 7,
    headless: bool = False,
    agent: str = "claude",
    claude_model: str = "haiku",
    codex_model: str | None = None,
    dry_run: bool = False,
    continuous: bool = False,
    poll_interval: int = 60,
    workers: int = 1,
    enable_gmail: bool = False,
    domain_allowlist: list[str] | None = None,
    max_applies: int = 25,
    min_delay_seconds: int = 10,
    timeout_s: int = config.DEFAULTS["apply_timeout"],
) -> None:
    """Launch the apply pipeline.

    Args:
        limit: Max jobs to apply to (0 or with continuous=True means run forever).
        target_url: Apply to a specific URL.
        min_score: Minimum fit_score threshold.
        headless: Run Chrome in headless mode.
        agent: Backend selection (claude, codex, auto).
        claude_model: Claude model name.
        codex_model: Codex model name.
        dry_run: Don't click Submit.
        continuous: Run forever, polling for new jobs.
        poll_interval: Seconds between DB polls when queue is empty.
        workers: Number of parallel workers (default 1).
        enable_gmail: Enable Gmail MCP.
        domain_allowlist: Restrict job domains.
        max_applies: Hard stop count across the run.
        min_delay_seconds: Delay between attempts.
        timeout_s: Per-runner timeout in seconds.
    """
    global POLL_INTERVAL
    POLL_INTERVAL = poll_interval
    _stop_event.clear()

    config.ensure_dirs()
    console = Console()

    if target_url and workers > 1:
        console.print("[yellow]Targeted apply runs use one worker to avoid duplicate claims.[/yellow]")
        workers = 1

    requested_limit = 0 if continuous else limit
    if max_applies > 0:
        effective_limit = max_applies if requested_limit == 0 else min(requested_limit, max_applies)
    else:
        effective_limit = requested_limit
    mode_label = "continuous" if effective_limit == 0 else f"{effective_limit} jobs"

    # Initialize dashboard for all workers
    for i in range(workers):
        init_worker(i)

    worker_label = f"{workers} worker{'s' if workers > 1 else ''}"
    console.print(f"Launching apply pipeline ({mode_label}, {worker_label}, poll every {POLL_INTERVAL}s)...")
    console.print(
        f"Agent={agent} | Claude={claude_model} | Codex={codex_model or '(default)'} | "
        f"Gmail MCP={'on' if enable_gmail else 'off'}"
    )
    if domain_allowlist:
        console.print(f"Domain allowlist: {', '.join(domain_allowlist)}")
    console.print(f"Min delay: {min_delay_seconds}s | Dry run: {dry_run}")
    console.print("[dim]Ctrl+C = skip current job(s) | Ctrl+C x2 = stop[/dim]")

    # Double Ctrl+C handler
    _ctrl_c_count = 0

    def _sigint_handler(sig, frame):
        nonlocal _ctrl_c_count
        _ctrl_c_count += 1
        if _ctrl_c_count == 1:
            console.print("\n[yellow]Skipping current job(s)... (Ctrl+C again to STOP)[/yellow]")
            # Kill all active agent processes to skip current jobs
            with _agent_lock:
                for wid, cproc in list(_agent_procs.items()):
                    if cproc.poll() is None:
                        _kill_process_tree(cproc.pid)
        else:
            console.print("\n[red bold]STOPPING[/red bold]")
            _stop_event.set()
            with _agent_lock:
                for wid, cproc in list(_agent_procs.items()):
                    if cproc.poll() is None:
                        _kill_process_tree(cproc.pid)
            kill_all_chrome()
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        with Live(render_full(), console=console, refresh_per_second=2) as live:
            # Daemon thread for display refresh only (no business logic)
            _dashboard_running = True

            def _refresh():
                while _dashboard_running:
                    live.update(render_full())
                    time.sleep(0.5)

            refresh_thread = threading.Thread(target=_refresh, daemon=True)
            refresh_thread.start()

            if workers == 1:
                # Single worker — run directly in main thread
                total_applied, total_failed = worker_loop(
                    worker_id=0,
                    limit=effective_limit,
                    target_url=target_url,
                    min_score=min_score,
                    headless=headless,
                    agent=agent,
                    claude_model=claude_model,
                    codex_model=codex_model,
                    dry_run=dry_run,
                    continuous=continuous,
                    enable_gmail=enable_gmail,
                    domain_allowlist=domain_allowlist,
                    min_delay_seconds=min_delay_seconds,
                    timeout_s=timeout_s,
                )
            else:
                # Multi-worker — distribute limit across workers
                if effective_limit:
                    base = effective_limit // workers
                    extra = effective_limit % workers
                    limits = [base + (1 if i < extra else 0)
                              for i in range(workers)]
                else:
                    limits = [0] * workers  # continuous mode

                with ThreadPoolExecutor(max_workers=workers,
                                        thread_name_prefix="apply-worker") as executor:
                    futures = {
                        executor.submit(
                            worker_loop,
                            worker_id=i,
                            limit=limits[i],
                            target_url=target_url,
                            min_score=min_score,
                            headless=headless,
                            agent=agent,
                            claude_model=claude_model,
                            codex_model=codex_model,
                            dry_run=dry_run,
                            continuous=continuous,
                            enable_gmail=enable_gmail,
                            domain_allowlist=domain_allowlist,
                            min_delay_seconds=min_delay_seconds,
                            timeout_s=timeout_s,
                        ): i
                        for i in range(workers)
                    }

                    results: list[tuple[int, int]] = []
                    for future in as_completed(futures):
                        wid = futures[future]
                        try:
                            results.append(future.result())
                        except Exception:
                            logger.exception("Worker %d crashed", wid)
                            results.append((0, 0))

                total_applied = sum(r[0] for r in results)
                total_failed = sum(r[1] for r in results)

            _dashboard_running = False
            refresh_thread.join(timeout=2)
            live.update(render_full())

        totals = get_totals()
        console.print(
            f"\n[bold]Done: {total_applied} applied, {total_failed} failed "
            f"(${totals['cost']:.3f})[/bold]"
        )
        console.print(f"Logs: {config.LOG_DIR}")

    except KeyboardInterrupt:
        pass
    finally:
        _stop_event.set()
        kill_all_chrome()
