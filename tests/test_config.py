from __future__ import annotations

from knowledge_garden.config import Settings


def test_settings_default_paths():
    settings = Settings.from_env()
    assert settings.data_dir.exists() or settings.data_dir.expanduser()


def test_settings_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("KG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KG_MCP_PORT", "9090")
    settings = Settings.from_env()
    assert settings.data_dir == tmp_path
    assert settings.mcp_port == 9090
