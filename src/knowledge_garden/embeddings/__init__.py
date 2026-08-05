from ..config import Settings
from .base import EmbeddingBackend, FakeEmbeddingBackend
from .sentence_transformer import SentenceTransformerBackend


def get_backend(settings: Settings) -> EmbeddingBackend:
    if settings.embed_backend == "fake":
        return FakeEmbeddingBackend(settings.embedding_dim, "fake-v1")
    return SentenceTransformerBackend(settings.embedding_model)
