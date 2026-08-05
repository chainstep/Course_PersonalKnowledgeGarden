from __future__ import annotations

import json
import runpy
from pathlib import Path


def _fixture_pdf() -> Path:
    fixture = Path(__file__).parent / "fixtures" / "prompt_injection.pdf"
    if not fixture.exists():
        runpy.run_path(str(fixture.parent / "make_prompt_injection_pdf.py"), run_name="__main__")
    return fixture


def test_prompt_injection_text_is_neutralised():
    from knowledge_garden.security.sanitizer import sanitize

    text = Path(__file__).parent / "fixtures" / "prompt_injection_text.txt"
    result = sanitize(text.read_text())
    assert result.neutralized_spans >= 2
    assert "ignore previous instructions" not in result.text.lower()


def test_envelope_identifies_source_and_trust():
    from knowledge_garden.security.sanitizer import envelope

    payload = envelope("system prompt: ignore me", source="notes/x.md")
    assert "trust=untrusted" in payload
    assert "source=notes/x.md" in payload
    assert "BEGIN UNTRUSTED CONTENT" in payload
    assert "NEUTRALIZED" in payload


def test_pdf_fixture_generation():
    fixture = _fixture_pdf()
    assert fixture.exists()
    assert fixture.read_bytes()[:5] == b"%PDF-"


def test_pdf_fixture_holds_attack_phrase(tmp_path: Path):
    fixture = _fixture_pdf()
    import pymupdf

    document = pymupdf.open(fixture)
    text = "\n".join(page.get_text() for page in document)
    document.close()
    assert "ignore previous instructions" in text.lower()


def test_envelope_metadata_is_observable(tmp_path: Path, settings, repository):
    from knowledge_garden.ingestion import IngestionService

    fixture = _fixture_pdf()
    result = IngestionService(repository, settings).add(str(fixture))
    fetched = repository.fetch(result.item.id)
    assert fetched is not None
    _item, chunks = fetched
    assert all("BEGIN UNTRUSTED CONTENT" in chunk.safe_text for chunk in chunks)
    safe_text = " ".join(chunk.safe_text for chunk in chunks)
    assert "ignore previous instructions" not in safe_text.lower()
    assert result.neutralized_spans >= 2


def test_raw_text_is_quarantined(settings, repository, sqlite_connection):
    from knowledge_garden.ingestion import IngestionService

    fixture = _fixture_pdf()
    result = IngestionService(repository, settings).add(str(fixture))
    row = sqlite_connection.execute(
        "SELECT raw_text FROM chunks WHERE item_id=?", (result.item.id,)
    ).fetchone()
    assert "ignore previous instructions" in row[0].lower()
    assert result.item.model_dump() == {**result.item.model_dump()}


def test_cli_does_not_leak_raw_text(settings, repository):
    from typer.testing import CliRunner

    from knowledge_garden.cli import app
    from knowledge_garden.ingestion import IngestionService

    fixture = _fixture_pdf()
    IngestionService(repository, settings).add(str(fixture))
    runner = CliRunner()
    recent = runner.invoke(app, ["recent", "--json"])
    assert recent.exit_code == 0
    payload = json.loads(recent.stdout)
    text = json.dumps(payload)
    assert "ignore previous instructions" not in text.lower()
    digest = runner.invoke(app, ["digest"])
    assert digest.exit_code == 0
    assert "ignore previous instructions" not in digest.stdout.lower()
