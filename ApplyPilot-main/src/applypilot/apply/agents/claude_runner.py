"""Claude CLI backend runner for apply automation."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .base import AgentRunResult
from .parsing import parse_agent_result

CLAUDE_DISALLOWED_GMAIL_TOOLS = (
    "mcp__gmail__draft_email,mcp__gmail__modify_email,"
    "mcp__gmail__delete_email,mcp__gmail__download_attachment,"
    "mcp__gmail__batch_modify_emails,mcp__gmail__batch_delete_emails,"
    "mcp__gmail__create_label,mcp__gmail__update_label,"
    "mcp__gmail__delete_label,mcp__gmail__get_or_create_label,"
    "mcp__gmail__list_email_labels,mcp__gmail__create_filter,"
    "mcp__gmail__list_filters,mcp__gmail__get_filter,"
    "mcp__gmail__delete_filter"
)


class ClaudeRunner:
    """Run `claude` non-interactively with shared MCP config."""

    def __init__(
        self,
        *,
        mcp_config_path: Path,
        model: str | None,
        worker_id: int,
        log_dir: Path,
        on_process_start: Callable[[int, subprocess.Popen[str]], None] | None = None,
        on_process_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.mcp_config_path = mcp_config_path
        self.model = model
        self.worker_id = worker_id
        self.log_dir = log_dir
        self.on_process_start = on_process_start
        self.on_process_exit = on_process_exit

    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_log_path = self.log_dir / f"agent_claude_{ts}_w{self.worker_id}.log"
        cmd = ["claude"]
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.extend(
            [
                "-p",
                "--mcp-config",
                str(self.mcp_config_path),
                "--permission-mode",
                "bypassPermissions",
                "--no-session-persistence",
                "--disallowedTools",
                CLAUDE_DISALLOWED_GMAIL_TOOLS,
                "--output-format",
                "stream-json",
                "--verbose",
                "-",
            ]
        )

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE_ENTRYPOINT", None)

        start = time.time()
        text_parts: list[str] = []
        proc: subprocess.Popen[str] | None = None
        exit_code = -1

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(workdir),
                env=env,
            )
            if self.on_process_start:
                self.on_process_start(self.worker_id, proc)
            with raw_log_path.open("w", encoding="utf-8") as lf:
                lf.write(f"$ {' '.join(cmd)}\n")
                assert proc.stdin is not None
                proc.stdin.write(prompt)
                proc.stdin.close()

                assert proc.stdout is not None
                for line in proc.stdout:
                    lf.write(line)
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        msg = json.loads(stripped)
                    except json.JSONDecodeError:
                        text_parts.append(stripped)
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

            proc.wait(timeout=timeout_s)
            exit_code = int(proc.returncode or 0)
        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.kill()
            text_parts.append("RESULT:FAILED:timeout")
            exit_code = -1
        finally:
            if self.on_process_exit:
                self.on_process_exit(self.worker_id)
            if proc is not None and proc.poll() is None:
                proc.kill()

        duration_ms = int((time.time() - start) * 1000)
        final_text = "\n".join(text_parts).strip()
        if not final_text and raw_log_path.exists():
            final_text = raw_log_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_agent_result(final_text)

        return AgentRunResult(
            engine="claude",
            exit_code=exit_code,
            final_text=final_text,
            events_path=None,
            raw_log_path=raw_log_path,
            duration_ms=duration_ms,
            parsed=parsed,
        )
