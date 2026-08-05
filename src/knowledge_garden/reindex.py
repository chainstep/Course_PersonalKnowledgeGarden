from __future__ import annotations

from .config import Settings
from .embeddings import get_backend
from .models import EmbeddingModelMismatchError
from .storage.database import Database
from .storage.repository import Repository


def reindex(settings: Settings, force: bool = False) -> int:
    repository = Repository(Database(settings))
    backend = get_backend(settings)
    rows = repository.all_chunks()
    if rows and not force:
        models = {(row["embedding_model"], row["embedding_dim"]) for row, _ in rows}
        if models != {(backend.model_name, backend.dimension)}:
            raise EmbeddingModelMismatchError(
                "embedding model mismatch; run kg reindex --force after changing models"
            )
    vectors = [(row["chunk_id"], backend.embed([row["safe_text"]])[0]) for row, _ in rows]
    repository.replace_vectors(vectors)
    repository.resanitize()
    return len(vectors)
