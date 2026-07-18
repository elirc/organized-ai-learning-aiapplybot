from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

import pytest

from applypilot import config
from applypilot.apply.agents import ClaudeRunner, CodexRunner


pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_cdp(port: int, timeout_s: int = 20) -> None:
    deadline = time.time() + timeout_s
    last_err: str | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
                return
        except Exception as e:  # pragma: no cover - environment dependent
            last_err = str(e)
            time.sleep(0.5)
    raise RuntimeError(f"Chrome CDP did not start on port {port}: {last_err}")


@pytest.fixture()
def local_form_server() -> str:
    fixtures_dir = Path(__file__).parent / "fixtures"
    port = _free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=str(fixtures_dir))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/fake_job_form.html"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


@pytest.fixture()
def chrome_cdp(tmp_path: Path) -> int:
    try:
        chrome_path = config.get_chrome_path()
    except FileNotFoundError as e:
        pytest.skip(str(e))
    port = _free_port()
    user_data = tmp_path / "chrome-profile"
    user_data.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--headless=new",
        "about:blank",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for_cdp(port)
        yield port
    finally:
        if proc.poll() is None:
            proc.kill()


def _write_claude_mcp_config(path: Path, cdp_port: int) -> None:
    data = {
        "mcpServers": {
            "playwright": {
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest", f"--cdp-endpoint=http://localhost:{cdp_port}"],
            }
        }
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_codex_project_config(workdir: Path, cdp_port: int) -> Path:
    codex_dir = workdir / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    cfg = codex_dir / "config.toml"
    cfg.write_text(
        "\n".join(
            [
                "[mcp_servers.playwright]",
                'command = "npx"',
                f'args = ["-y", "@playwright/mcp@latest", "--cdp-endpoint=http://localhost:{cdp_port}"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _write_output_schema(workdir: Path) -> Path:
    schema = {
        "type": "object",
        "required": ["result", "reason", "submitted"],
        "properties": {
            "result": {"type": "string", "enum": ["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]},
            "reason": {"type": "string"},
            "submitted": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
    schema_path = workdir / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return schema_path


def test_claude_runner_dry_run_integration(tmp_path: Path, local_form_server: str, chrome_cdp: int) -> None:
    if not shutil.which("claude"):
        pytest.skip("Claude CLI not installed")
    if not shutil.which("npx"):
        pytest.skip("npx not installed")

    mcp_path = tmp_path / "mcp.json"
    _write_claude_mcp_config(mcp_path, chrome_cdp)
    prompt = (
        f"Use browser tools to navigate to {local_form_server}, take a snapshot, and do not submit anything.\n"
        "Final line exactly: RESULT: DRY_RUN - integration_test"
    )
    runner = ClaudeRunner(mcp_config_path=mcp_path, model="haiku", worker_id=0, log_dir=tmp_path)
    result = runner.run(prompt, workdir=tmp_path, timeout_s=180)

    if result.parsed.status == "NEEDS_REVIEW":
        assert result.exit_code != 0
    else:
        assert result.parsed.status == "DRY_RUN"


def test_codex_runner_dry_run_integration(tmp_path: Path, local_form_server: str, chrome_cdp: int) -> None:
    if not shutil.which("codex"):
        pytest.skip("Codex CLI not installed")
    if not shutil.which("npx"):
        pytest.skip("npx not installed")

    _write_codex_project_config(tmp_path, chrome_cdp)
    schema_path = _write_output_schema(tmp_path)
    prompt = (
        f"Use browser tools to navigate to {local_form_server}, take a snapshot, and do not submit anything.\n"
        'Return JSON: {"result":"DRY_RUN","reason":"integration_test","submitted":false}'
    )
    runner = CodexRunner(model=None, worker_id=0, log_dir=tmp_path, output_schema_path=schema_path)
    result = runner.run(prompt, workdir=tmp_path, timeout_s=180)

    if result.parsed.status == "NEEDS_REVIEW":
        assert result.exit_code != 0
    else:
        assert result.parsed.status == "DRY_RUN"
