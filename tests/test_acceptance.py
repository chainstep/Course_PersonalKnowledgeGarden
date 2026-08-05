from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from knowledge_garden.digest import render_digest
from knowledge_garden.ingestion import IngestionService


def test_ingest_is_idempotent_on_same_hash(tmp_path: Path, settings, repository):
    sample = tmp_path / "note.md"
    sample.write_text("# Same\n\none")
    service = IngestionService(repository, settings)
    first = service.add(str(sample))
    second = service.add(str(sample))
    assert first.item.id == second.item.id
    assert second.created is False


def test_ingest_replaces_on_content_change(tmp_path: Path, settings, repository):
    sample = tmp_path / "note.md"
    sample.write_text("# Same\n\nfirst version")
    service = IngestionService(repository, settings)
    first = service.add(str(sample))
    sample.write_text("# Same\n\nupdated content with more details")
    second = service.add(str(sample))
    assert second.created is True
    assert second.item.id == first.item.id
    assert second.item.source_hash != first.item.source_hash


def test_search_uses_hybrid_ranking(tmp_path: Path, settings, repository):
    a = tmp_path / "a.md"
    a.write_text("# SQLite\n\nFTS5 keyword search and vector nearest neighbours.")
    b = tmp_path / "b.md"
    b.write_text("# Postgres\n\nAn advanced relational database system.")
    service = IngestionService(repository, settings)
    service.add(str(a))
    service.add(str(b))
    from knowledge_garden.search import SearchService

    hits = SearchService(repository, settings).search("sqlite", limit=5)
    assert hits
    assert any("sqlite" in hit.excerpt.lower() for hit in hits)


def test_digest_is_deterministic(tmp_path: Path, settings, repository):
    sample = tmp_path / "note.md"
    sample.write_text("# Tag\n\nsomething")
    IngestionService(repository, settings).add(str(sample), tags=["history"])
    generated = datetime.now(UTC)
    text_a = render_digest(repository.recent(24, 100), 24, generated_at=generated)
    text_b = render_digest(repository.recent(24, 100), 24, generated_at=generated)
    assert text_a == text_b
    assert "[no items added]" not in text_a
    assert "history: 1" in text_a


def test_reindex_rejects_model_mismatch(tmp_path: Path, settings, repository):
    """Hermetic mismatch test: two fake backends with different dims (no torch/model download).

    The guard compares stored (embedding_model, embedding_dim) against the active
    backend, so a dimension change on the fake backend exercises it fully.
    """
    from dataclasses import replace

    from knowledge_garden.models import EmbeddingModelMismatchError
    from knowledge_garden.reindex import reindex

    sample = tmp_path / "note.md"
    sample.write_text("# Hi\n\ntext")
    IngestionService(repository, settings).add(str(sample))
    mismatch = replace(settings, embedding_dim=64)
    with pytest.raises(EmbeddingModelMismatchError):
        reindex(mismatch)
    assert reindex(mismatch, force=True) == 1


@pytest.mark.skipif(
    os.environ.get("KG_REAL_EMBED_TEST") != "1",
    reason="real SentenceTransformer smoke test is opt-in (KG_REAL_EMBED_TEST=1); loads torch + model",
)
def test_real_sentence_transformer_backend_smoke(tmp_path: Path, settings, repository):
    from dataclasses import replace

    from knowledge_garden.reindex import reindex

    sample = tmp_path / "note.md"
    sample.write_text("# Hi\n\ntext")
    IngestionService(repository, settings).add(str(sample))
    st_settings = replace(
        settings, embed_backend="st", embedding_model="BAAI/bge-small-en-v1.5", embedding_dim=384
    )
    assert reindex(st_settings, force=True) == 1
