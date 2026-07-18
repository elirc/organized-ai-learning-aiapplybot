"""Shared result models and runner protocol for auto-apply agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass
class ParsedOutcome:
    """Parsed terminal outcome emitted by the agent."""

    status: Literal["APPLIED", "FAILED", "CAPTCHA", "NEEDS_REVIEW", "DRY_RUN"]
    reason: str
    submitted: bool


@dataclass
class AgentRunResult:
    """Normalized execution result for one backend invocation."""

    engine: str
    exit_code: int
    final_text: str
    events_path: Path | None
    raw_log_path: Path
    duration_ms: int
    parsed: ParsedOutcome


class AgentRunner(Protocol):
    """Backend runner interface used by apply launcher."""

    def run(self, prompt: str, *, workdir: Path, timeout_s: int) -> AgentRunResult:
        """Run a backend CLI and return normalized output."""
