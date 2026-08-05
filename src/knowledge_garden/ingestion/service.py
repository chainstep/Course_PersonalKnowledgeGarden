from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..embeddings import get_backend
from ..models import IngestResult
from ..security.sanitizer import sanitize
from ..security.trust import normalize_tags, safe_filename
from ..storage.repository import Repository
from .chunker import chunk_parts
from .extractors import detect_type, extract_text


@dataclass(frozen=True)
class PreparedChunk:
    safe_text: str
    raw_text: str
    page: int | None
    heading: str | None
    neutralized_spans: int


class IngestionService:
    def __init__(self, repository: Repository, settings) -> None:
        self.repository = repository
        self.settings = settings
        self.backend = get_backend(settings)

    def add(
        self, path: str, tags: list[str] | None = None, forced_type: str | None = None
    ) -> IngestResult:
        source = Path(path).expanduser().resolve()
        data = source.read_bytes()
        kind = forced_type or detect_type(source, data)
        parts = chunk_parts(extract_text(source, data, kind))
        prepared = []
        for part in parts:
            safe = sanitize(part.text)
            prepared.append(
                PreparedChunk(safe.text, part.text, part.page, part.heading, safe.neutralized_spans)
            )
        vectors = self.backend.embed([item.safe_text for item in prepared])
        return self.repository.upsert_item(
            safe_filename(str(source)),
            hashlib.sha256(data).hexdigest(),
            kind,
            normalize_tags(tags or []),
            prepared,
            vectors,
            self.backend.model_name,
            self.backend.dimension,
        )
