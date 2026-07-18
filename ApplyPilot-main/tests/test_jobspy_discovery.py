from __future__ import annotations

import builtins

import pytest

from applypilot.discovery import jobspy


def test_get_scrape_jobs_reports_missing_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "jobspy":
            raise ModuleNotFoundError("jobspy")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="python-jobspy is not installed"):
        jobspy._get_scrape_jobs()
