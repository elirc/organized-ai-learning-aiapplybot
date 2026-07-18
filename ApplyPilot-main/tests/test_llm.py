from __future__ import annotations

from applypilot import llm


def test_detect_provider_uses_current_environment(monkeypatch) -> None:
    llm.reset_client()
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    base_url, model, api_key = llm._detect_provider()
    assert base_url == "https://api.openai.com/v1"
    assert model == "gpt-test"
    assert api_key == "openai-key"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_URL", "http://localhost:8080/v1/")
    monkeypatch.setenv("LLM_API_KEY", "local-key")
    base_url, model, api_key = llm._detect_provider()
    assert base_url == "http://localhost:8080/v1"
    assert model == "gpt-test"
    assert api_key == "local-key"
