from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | None = None
    item_id: str
    ordinal: int
    safe_text: str
    page: int | None = None
    heading: str | None = None


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_path: str
    source_hash: str
    type: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    chunk_count: int = 0
    neutralized_spans: int = 0


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: Item
    excerpt: str
    page: int | None = None
    heading: str | None = None
    keyword_score: float | None = None
    vector_score: float | None = None
    fused_score: float = 0.0


class IngestResult(BaseModel):
    item: Item
    created: bool
    chunk_count: int
    neutralized_spans: int


class DomainError(Exception):
    exit_code = 3


class UnsupportedTypeError(DomainError):
    pass


class DecodeError(DomainError):
    pass


class EncryptedPDFError(DomainError):
    pass


class OCRNotSupportedError(DomainError):
    pass


class EmbeddingModelMismatchError(DomainError):
    pass


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)
