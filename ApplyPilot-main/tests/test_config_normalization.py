from __future__ import annotations

import json

from applypilot import config


def test_load_profile_normalizes_legacy_wizard_schema(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(config, "PROFILE_PATH", profile_path)

    profile_path.write_text(
        json.dumps(
            {
                "personal": {
                    "full_name": "Ada Lovelace",
                    "email": "ada@example.com",
                },
                "work_authorization": {
                    "legally_authorized": True,
                    "needs_sponsorship": False,
                },
                "experience": {
                    "current_title": "Backend Engineer",
                },
                "eeo_voluntary": {
                    "ethnicity": "Decline to self-identify",
                },
            }
        ),
        encoding="utf-8",
    )

    profile = config.load_profile()

    assert profile["personal"]["preferred_name"] == "Ada"
    assert profile["work_authorization"]["legally_authorized_to_work"] == "Yes"
    assert profile["work_authorization"]["require_sponsorship"] == "No"
    assert profile["experience"]["current_job_title"] == "Backend Engineer"
    assert profile["experience"]["target_role"] == "Backend Engineer"
    assert profile["eeo_voluntary"]["race_ethnicity"] == "Decline to self-identify"


def test_load_search_config_normalizes_aliases(tmp_path, monkeypatch) -> None:
    search_path = tmp_path / "searches.yaml"
    monkeypatch.setattr(config, "SEARCH_CONFIG_PATH", search_path)

    search_path.write_text(
        "\n".join(
            [
                "boards:",
                "  - indeed",
                "  - linkedin",
                'country: "USA"',
                "queries:",
                '  - query: "software engineer"',
                "    tier: 1",
                "locations:",
                '  - location: "San Francisco, CA"',
                "    remote: false",
                "location:",
                "  accept_patterns:",
                '    - "San Francisco"',
                "  reject_patterns:",
                '    - "London"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    search_config = config.load_search_config()

    assert search_config["sites"] == ["indeed", "linkedin"]
    assert search_config["defaults"]["country_indeed"] == "usa"
    assert search_config["location_accept"] == ["San Francisco"]
    assert search_config["location_reject_non_remote"] == ["London"]


def test_load_search_config_derives_accept_patterns_from_locations(tmp_path, monkeypatch) -> None:
    search_path = tmp_path / "searches.yaml"
    monkeypatch.setattr(config, "SEARCH_CONFIG_PATH", search_path)

    search_path.write_text(
        "\n".join(
            [
                "queries: []",
                "locations:",
                '  - location: "New York, NY"',
                "    remote: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    search_config = config.load_search_config()

    assert "New York, NY" in search_config["location_accept"]
    assert "New York" in search_config["location_accept"]


def test_get_tier_accepts_codex_as_stage_six_agent(monkeypatch) -> None:
    monkeypatch.setattr(config, "load_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "get_chrome_path", lambda: "chrome")
    monkeypatch.setattr(config.shutil, "which", lambda name: "codex" if name == "codex" else None)

    assert config.get_tier() == 3
