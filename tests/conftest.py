from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from knowledge_garden.config import Settings
from knowledge_garden.storage import Database, Repository


def _ensure_injection_pdf() -> Path:
    fixture = Path(__file__).parent / "fixtures" / "prompt_injection.pdf"
    if not fixture.exists():
        import runpy

        runpy.run_path(str(fixture.parent / "make_prompt_injection_pdf.py"), run_name="__main__")
    return fixture


def pytest_configure(config: pytest.Config) -> None:
    _ensure_injection_pdf()


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "knowledge.db",
        mcp_host="127.0.0.1",
        mcp_port=8765,
        embed_backend="fake",
        embedding_model="fake-v1",
        embedding_dim=32,
    )


@pytest.fixture()
def repository(settings: Settings) -> Repository:
    return Repository(Database(settings))


@pytest.fixture(autouse=True)
def _data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KG_EMBED_BACKEND", "fake")
    os.environ.pop("KG_AGENT_MODEL", None)


@pytest.fixture()
def sqlite_connection(settings: Settings) -> sqlite3.Connection:
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()
