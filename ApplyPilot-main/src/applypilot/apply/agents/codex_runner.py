"""Codex CLI backend runner for apply automation."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .base import AgentRunResult
from .parsing import parse_agent_result


def _extract_text_from_event(event: dict) -> str | None:
    event_type = str(event.get("type", ""))
    if event_type == "item.completed":
        item = event.get("item", {})
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                return text
            if item.get("type") == "agent_message":
                msg = item.get("message")
                if isinstance(msg, str):
                    return msg
    if event_type == "turn.completed":
        summary = event.get("summary")
        if isinstance(summary, str):
            return summary
    text = event.get("text")
    if isinstance(text, str):
        return text
    return None


class CodexRunner:
    """Run `codex exec` non-interactively and parse JSONL events."""

    def __init__(
        self,
        *,
        model: str | None,
        worker_id: int,
        log_dir: Path,
        output_schema_path: Path | None = None,
        on_process_start: Callable[[int, subprocess.Popen[str]], None] | None = None,
        on_process_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.model = model
        self.worker_id = worker_id
        self.log_dir = log_dir
        self.output_schema_path = output_schema_path
        self.on_process_start = on_process_start
        self.on_process_exit = on_process_exit

    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_log_path = self.log_dir / f"agent_codex_{ts}_w{self.worker_id}.log"
        events_path = self.log_dir / f"agent_codex_{ts}_w{self.worker_id}.jsonl"

        cmd = [
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.output_schema_path:
            cmd.extend(["--output-schema", str(self.output_schema_path)])
        cmd.append("-")

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
            )
            if self.on_process_start:
                self.on_process_start(self.worker_id, proc)

            with raw_log_path.open("w", encoding="utf-8") as raw_fh, events_path.open("w", encoding="utf-8") as jsonl_fh:
                raw_fh.write(f"$ {' '.join(cmd)}\n")

                assert proc.stdin is not None
                proc.stdin.write(prompt)
                proc.stdin.close()

                assert proc.stdout is not None
                for line in proc.stdout:
                    raw_fh.write(line)
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        event = json.loads(stripped)
                    except json.JSONDecodeError:
                        # codex may emit warnings on non-json lines; keep them in raw log.
                        continue
                    jsonl_fh.write(stripped + "\n")
                    text = _extract_text_from_event(event)
                    if text:
                        text_parts.append(text)

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
            engine="codex",
            exit_code=exit_code,
            final_text=final_text,
            events_path=events_path,
            raw_log_path=raw_log_path,
            duration_ms=duration_ms,
            parsed=parsed,
        )
