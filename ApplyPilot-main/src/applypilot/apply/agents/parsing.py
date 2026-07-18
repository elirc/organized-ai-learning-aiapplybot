"""Parse agent output into a normalized apply outcome."""

from __future__ import annotations

import json
import re

from .base import ParsedOutcome

_RESULT_RE = re.compile(r"RESULT\s*:\s*([A-Z_]+)(?::([A-Za-z0-9_\-./]+))?(?:\s*-\s*(.*))?$", re.IGNORECASE)


def _normalize_status(raw: str | None, reason: str | None) -> tuple[str, str, bool]:
    token = (raw or "").strip().upper()
    reason = (reason or "").strip() or "unspecified"

    if token == "APPLIED":
        return "APPLIED", reason if reason != "unspecified" else "submitted", True
    if token == "DRY_RUN":
        return "DRY_RUN", reason if reason != "unspecified" else "dry_run", False
    if token == "CAPTCHA":
        return "CAPTCHA", reason if reason != "unspecified" else "captcha", False
    if token == "FAILED":
        return "FAILED", reason, False
    if token in {"EXPIRED", "LOGIN_ISSUE"}:
        mapped = token.lower()
        if reason != "unspecified":
            mapped = f"{mapped}:{reason}"
        return "FAILED", mapped, False
    if token == "NEEDS_REVIEW":
        return "NEEDS_REVIEW", reason, False
    return "NEEDS_REVIEW", f"unrecognized_result:{token or 'missing'}", False


def _try_parse_json_lines(text: str) -> ParsedOutcome | None:
    for line in reversed(text.splitlines()):
        line = line.strip().strip("`")
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        raw_status = payload.get("result") or payload.get("status")
        if not raw_status:
            continue
        reason = payload.get("reason")
        submitted = payload.get("submitted")
        status, parsed_reason, default_submitted = _normalize_status(str(raw_status), str(reason) if reason is not None else None)
        if isinstance(submitted, bool):
            default_submitted = submitted
        return ParsedOutcome(status=status, reason=parsed_reason, submitted=default_submitted)
    return None


def _try_parse_result_lines(text: str) -> ParsedOutcome | None:
    last_match: re.Match[str] | None = None
    for line in text.splitlines():
        m = _RESULT_RE.search(line.strip())
        if m:
            last_match = m
    if not last_match:
        return None
    status = last_match.group(1) or ""
    suffix = (last_match.group(2) or "").strip()
    dash_reason = (last_match.group(3) or "").strip()
    reason = dash_reason or suffix or None
    parsed_status, parsed_reason, submitted = _normalize_status(status, reason)
    return ParsedOutcome(status=parsed_status, reason=parsed_reason, submitted=submitted)


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
