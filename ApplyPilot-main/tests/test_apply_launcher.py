from __future__ import annotations

from applypilot.apply import launcher
from applypilot import config as app_config
from applypilot import database


def _setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "applypilot.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(app_config, "DB_PATH", db_path)
    database.close_connection(db_path)
    database.init_db(db_path)
    return db_path, database.get_connection(db_path)


def _insert_apply_ready_job(conn, tmp_path, *, url="https://example.com/jobs/123", status=None, attempts=0):
    conn.execute(
        """
        INSERT INTO jobs (
            url, title, site, application_url, tailored_resume_path,
            fit_score, full_description, apply_status, apply_attempts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            url,
            "Platform Engineer",
            "Example Corp",
            url.replace("/jobs/", "/apply/"),
            str(tmp_path / "resume.txt"),
            9,
            "Role details",
            status,
            attempts,
        ),
    )
    conn.commit()


def test_acquire_job_target_url_selects_unattempted_job(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    conn.execute(
        """
        INSERT INTO jobs (
            url, title, site, application_url, tailored_resume_path, fit_score, full_description, apply_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "https://example.com/jobs/123",
            "Platform Engineer",
            "Example Corp",
            "https://example.com/apply/123",
            str(tmp_path / "resume.txt"),
            9,
            "Role details",
            None,
        ),
    )
    conn.commit()

    job = launcher.acquire_job(target_url="https://example.com/jobs/123", worker_id=4)

    assert job is not None
    assert job["url"] == "https://example.com/jobs/123"

    row = conn.execute(
        "SELECT apply_status, agent_id FROM jobs WHERE url = ?",
        ("https://example.com/jobs/123",),
    ).fetchone()
    assert row["apply_status"] == "in_progress"
    assert row["agent_id"] == "worker-4"

    database.close_connection(db_path)


def test_acquire_job_skips_manual_ats_and_claims_next_job(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr(launcher, "_load_blocked", lambda: (set(), []))
    monkeypatch.setattr(app_config, "is_manual_ats", lambda url: "manual-ats.example" in url)

    conn.executemany(
        """
        INSERT INTO jobs (
            url, title, site, application_url, tailored_resume_path, fit_score, full_description, apply_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "https://example.com/jobs/manual",
                "Manual ATS Job",
                "Example Corp",
                "https://manual-ats.example/apply/manual",
                str(tmp_path / "resume-manual.txt"),
                10,
                "Role details",
                None,
            ),
            (
                "https://example.com/jobs/valid",
                "Valid Job",
                "Example Corp",
                "https://example.com/apply/valid",
                str(tmp_path / "resume-valid.txt"),
                9,
                "Role details",
                None,
            ),
        ],
    )
    conn.commit()

    job = launcher.acquire_job(min_score=7, worker_id=2)

    assert job is not None
    assert job["url"] == "https://example.com/jobs/valid"

    manual_row = conn.execute(
        "SELECT apply_status, apply_error FROM jobs WHERE url = ?",
        ("https://example.com/jobs/manual",),
    ).fetchone()
    valid_row = conn.execute(
        "SELECT apply_status, agent_id FROM jobs WHERE url = ?",
        ("https://example.com/jobs/valid",),
    ).fetchone()

    assert manual_row["apply_status"] == "manual"
    assert manual_row["apply_error"] == "manual ATS"
    assert valid_row["apply_status"] == "in_progress"
    assert valid_row["agent_id"] == "worker-2"

    database.close_connection(db_path)


def test_worker_loop_with_zero_limit_exits_immediately(monkeypatch) -> None:
    def fail_acquire(*args, **kwargs):
        raise AssertionError("acquire_job should not run when no work is assigned")

    monkeypatch.setattr(launcher, "acquire_job", fail_acquire)

    applied, failed = launcher.worker_loop(limit=0, continuous=False)

    assert applied == 0
    assert failed == 0


def test_mark_result_retryable_failure_increments_attempts(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    _insert_apply_ready_job(conn, tmp_path, status="in_progress", attempts=1)

    launcher.mark_result(
        "https://example.com/jobs/123",
        "failed",
        "temporary_network_error",
        permanent=False,
        duration_ms=1234,
        task_id="task-retry",
    )

    row = conn.execute(
        """
        SELECT apply_status, apply_error, apply_attempts, agent_id,
               apply_duration_ms, apply_task_id
        FROM jobs WHERE url = ?
        """,
        ("https://example.com/jobs/123",),
    ).fetchone()
    assert row["apply_status"] == "failed"
    assert row["apply_error"] == "temporary_network_error"
    assert row["apply_attempts"] == 2
    assert row["agent_id"] is None
    assert row["apply_duration_ms"] == 1234
    assert row["apply_task_id"] == "task-retry"

    database.close_connection(db_path)


def test_mark_result_permanent_failure_blocks_normal_retry(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    _insert_apply_ready_job(conn, tmp_path, status="in_progress", attempts=1)

    launcher.mark_result(
        "https://example.com/jobs/123",
        "failed",
        "domain_not_allowed:blocked.example",
        permanent=True,
    )

    row = conn.execute(
        "SELECT apply_status, apply_error, apply_attempts, agent_id FROM jobs WHERE url = ?",
        ("https://example.com/jobs/123",),
    ).fetchone()
    assert row["apply_status"] == "failed"
    assert row["apply_error"] == "domain_not_allowed:blocked.example"
    assert row["apply_attempts"] == 99
    assert row["agent_id"] is None

    database.close_connection(db_path)


def test_release_lock_only_clears_in_progress_jobs(tmp_path, monkeypatch) -> None:
    db_path, conn = _setup_db(tmp_path, monkeypatch)
    _insert_apply_ready_job(conn, tmp_path, status="in_progress")
    _insert_apply_ready_job(conn, tmp_path, url="https://example.com/jobs/failed", status="failed")

    launcher.release_lock("https://example.com/jobs/123")
    launcher.release_lock("https://example.com/jobs/failed")

    unlocked = conn.execute(
        "SELECT apply_status, agent_id FROM jobs WHERE url = ?",
        ("https://example.com/jobs/123",),
    ).fetchone()
    failed = conn.execute(
        "SELECT apply_status FROM jobs WHERE url = ?",
        ("https://example.com/jobs/failed",),
    ).fetchone()
    assert unlocked["apply_status"] is None
    assert unlocked["agent_id"] is None
    assert failed["apply_status"] == "failed"

    database.close_connection(db_path)


def test_run_job_blocks_disallowed_domain_before_side_effects(monkeypatch) -> None:
    def fail_reset_worker_dir(*args, **kwargs):
        raise AssertionError("worker directory should not be reset for blocked domains")

    def fail_build_prompt(*args, **kwargs):
        raise AssertionError("prompt should not be built for blocked domains")

    monkeypatch.setattr(launcher, "reset_worker_dir", fail_reset_worker_dir)
    monkeypatch.setattr(launcher.prompt_mod, "build_prompt", fail_build_prompt)

    job = {
        "url": "https://safe.example/jobs/123",
        "title": "Platform Engineer",
        "site": "Example Corp",
        "application_url": "https://blocked.example/apply/123",
        "tailored_resume_path": None,
    }

    result, duration_ms = launcher.run_job(
        job,
        port=9222,
        domain_allowlist=["safe.example"],
    )

    assert result == "failed:domain_not_allowed:blocked.example"
    assert duration_ms == 0


def test_domain_allowlist_accepts_subdomains() -> None:
    assert launcher._is_domain_allowed("https://careers.example.com/apply", ["example.com"])
    assert launcher._is_domain_allowed("https://example.com/apply", ["example.com"])
    assert not launcher._is_domain_allowed("https://example.org/apply", ["example.com"])
