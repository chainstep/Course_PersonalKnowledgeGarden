from __future__ import annotations

from collections import defaultdict

from ..embeddings import get_backend
from ..models import SearchHit
from ..security.sanitizer import envelope, sanitize
from ..storage.repository import Repository


def rrf(rank: int, constant: int = 60) -> float:
    return 1.0 / (constant + rank)


class SearchService:
    def __init__(self, repository: Repository, settings) -> None:
        self.repository = repository
        self.backend = get_backend(settings)

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        keyword = self.repository.keyword_search(query, max(limit * 3, 20))
        vector = self.repository.vector_search(self.backend.embed([query])[0], max(limit * 3, 20))
        grouped: dict[str, dict] = defaultdict(
            lambda: {"keyword": None, "vector": None, "chunk": None, "source": None}
        )
        for rank, (chunk, item, score) in enumerate(keyword, 1):
            key = item["item_uuid"]
            grouped[key].update(keyword=rrf(rank), keyword_score=score, chunk=chunk, source=item)
        for rank, (chunk, item, score) in enumerate(vector, 1):
            key = item["item_uuid"]
            value = grouped[key]
            value.update(vector=rrf(rank), vector_score=score)
            if value["chunk"] is None:
                value.update(chunk=chunk, source=item)
        hits = []
        for value in grouped.values():
            chunk, item = value["chunk"], value["source"]
            if not chunk or not item:
                continue
            safe = sanitize(chunk["safe_text"]).text
            fetched = self.repository.fetch(item["item_uuid"])
            if fetched is None:
                continue
            hits.append(
                SearchHit(
                    item=fetched[0],
                    excerpt=envelope(safe, item["source_path"]),
                    page=chunk["page"],
                    heading=chunk["heading"],
                    keyword_score=value.get("keyword_score"),
                    vector_score=value.get("vector_score"),
                    fused_score=(value.get("keyword") or 0) + (value.get("vector") or 0),
                )
            )
        hits.sort(key=lambda hit: hit.fused_score, reverse=True)
        return hits[:limit]
