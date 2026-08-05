from __future__ import annotations

import math
import sqlite3
import struct
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from ..models import Chunk, IngestResult, Item
from ..security.sanitizer import VERSION, sanitize
from .database import Database


def now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right)) / (
        (math.sqrt(sum(a * a for a in left)) or 1) * (math.sqrt(sum(b * b for b in right)) or 1)
    )


class Repository:
    def __init__(self, database: Database, sanitizer_version: str = VERSION) -> None:
        self.database = database
        self.sanitizer_version = sanitizer_version

    def _tags(self, connection: sqlite3.Connection, item_id: str) -> list[str]:
        return [
            row[0]
            for row in connection.execute(
                "SELECT tag FROM item_tags WHERE item_id=? ORDER BY tag", (item_id,)
            )
        ]

    def _item(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Item:
        count = connection.execute(
            "SELECT count(*) FROM chunks WHERE item_id=?", (row["id"],)
        ).fetchone()[0]
        spans = connection.execute(
            "SELECT count(*) FROM chunks WHERE item_id=? AND safe_text LIKE '%NEUTRALIZED%'",
            (row["id"],),
        ).fetchone()[0]
        return Item(
            id=row["id"],
            source_path=row["source_path"],
            source_hash=row["source_hash"],
            type=row["type"],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            tags=self._tags(connection, row["id"]),
            chunk_count=count,
            neutralized_spans=spans,
        )

    def upsert_item(
        self,
        source_path: str,
        source_hash: str,
        kind: str,
        tags: list[str],
        chunks: Iterable,
        vectors: list[list[float]],
        model: str,
        dimension: int,
    ) -> IngestResult:
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM items WHERE source_path=?", (source_path,)
            ).fetchone()
            if existing and existing["source_hash"] == source_hash:
                item = self._item(connection, existing)
                connection.commit()
                return IngestResult(
                    item=item,
                    created=False,
                    chunk_count=item.chunk_count,
                    neutralized_spans=item.neutralized_spans,
                )
            item_id = existing["id"] if existing else str(uuid.uuid4())
            timestamp = now_utc()
            if existing:
                connection.execute(
                    "INSERT INTO chunks_fts(chunks_fts, rowid, safe_text) SELECT 'delete', id, safe_text FROM chunks WHERE item_id=?",
                    (item_id,),
                )
                connection.execute("DELETE FROM chunks WHERE item_id=?", (item_id,))
                connection.execute("DELETE FROM item_tags WHERE item_id=?", (item_id,))
                connection.execute(
                    "UPDATE items SET source_hash=?, type=?, updated_at=?, sanitizer_version=? WHERE id=?",
                    (source_hash, kind, timestamp, self.sanitizer_version, item_id),
                )
            else:
                connection.execute(
                    "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item_id,
                        source_path,
                        source_hash,
                        kind,
                        timestamp,
                        timestamp,
                        self.sanitizer_version,
                    ),
                )
            for tag in tags:
                connection.execute("INSERT INTO item_tags VALUES (?, ?)", (item_id, tag))
            total_spans = 0
            for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors)):
                total_spans += chunk.neutralized_spans
                cursor = connection.execute(
                    "INSERT INTO chunks(item_id, ordinal, safe_text, raw_text, page, heading, embedding_dim, embedding_model, embedding_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item_id,
                        ordinal,
                        chunk.safe_text,
                        chunk.raw_text,
                        chunk.page,
                        chunk.heading,
                        dimension,
                        model,
                        "v1",
                    ),
                )
                chunk_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO chunks_fts(rowid, safe_text) VALUES (?, ?)",
                    (chunk_id, chunk.safe_text),
                )
                connection.execute("INSERT INTO vec_chunks VALUES (?, ?)", (chunk_id, pack(vector)))
            row = connection.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            item = self._item(connection, row)
            connection.commit()
            return IngestResult(
                item=item, created=True, chunk_count=item.chunk_count, neutralized_spans=total_spans
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recent(self, hours: int = 24, limit: int = 20) -> list[Item]:
        connection = self.database.connect()
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
        rows = connection.execute(
            "SELECT * FROM items WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        result = [self._item(connection, row) for row in rows]
        connection.close()
        return result

    def fetch(self, item_id: str) -> tuple[Item, list[Chunk]] | None:
        connection = self.database.connect()
        row = connection.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            connection.close()
            return None
        chunks = [
            Chunk(
                id=r["id"],
                item_id=r["item_id"],
                ordinal=r["ordinal"],
                safe_text=__import__(
                    "knowledge_garden.security.sanitizer", fromlist=["envelope"]
                ).envelope(r["safe_text"], row["source_path"]),
                page=r["page"],
                heading=r["heading"],
            )
            for r in connection.execute(
                "SELECT * FROM chunks WHERE item_id=? ORDER BY ordinal", (item_id,)
            )
        ]
        item = self._item(connection, row)
        connection.close()
        return item, chunks

    def keyword_search(
        self, query: str, limit: int
    ) -> list[tuple[sqlite3.Row, sqlite3.Row, float]]:
        connection = self.database.connect()
        rows = connection.execute(
            "SELECT c.id AS chunk_id, c.item_id, c.ordinal, c.safe_text, c.raw_text, c.page, c.heading, c.embedding_dim, c.embedding_model, c.embedding_version, i.id AS item_uuid, i.source_path, i.source_hash, i.type, i.created_at, i.updated_at, i.sanitizer_version, bm25(chunks_fts) AS score FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid JOIN items i ON i.id=c.item_id WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
            (query, limit),
        ).fetchall()
        result = [(row, row, float(row["score"])) for row in rows]
        connection.close()
        return result

    def vector_search(
        self, vector: list[float], limit: int
    ) -> list[tuple[sqlite3.Row, sqlite3.Row, float]]:
        connection = self.database.connect()
        rows = connection.execute(
            "SELECT c.id AS chunk_id, c.item_id, c.ordinal, c.safe_text, c.raw_text, c.page, c.heading, c.embedding_dim, c.embedding_model, c.embedding_version, i.id AS item_uuid, i.source_path, i.source_hash, i.type, i.created_at, i.updated_at, i.sanitizer_version, v.embedding FROM vec_chunks v JOIN chunks c ON c.id=v.chunk_id JOIN items i ON i.id=c.item_id"
        ).fetchall()
        scored = [(row, row, cosine(vector, unpack(row["embedding"]))) for row in rows]
        scored.sort(key=lambda value: value[2], reverse=True)
        connection.close()
        return scored[:limit]

    def resanitize(self) -> int:
        connection = self.database.connect()
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("SELECT id, raw_text FROM chunks").fetchall()
        count = 0
        for row in rows:
            safe = sanitize(row["raw_text"]).text
            connection.execute(
                "UPDATE chunks SET safe_text=?, embedding_version=? WHERE id=?",
                (safe, VERSION, row["id"]),
            )
            connection.execute(
                "INSERT INTO chunks_fts(chunks_fts, rowid, safe_text) VALUES ('delete', ?, ?)",
                (row["id"], safe),
            )
            connection.execute(
                "INSERT INTO chunks_fts(rowid, safe_text) VALUES (?, ?)", (row["id"], safe)
            )
            count += 1
        connection.execute("UPDATE items SET sanitizer_version=?", (VERSION,))
        connection.commit()
        connection.close()
        return count

    def all_chunks(self) -> list[tuple[sqlite3.Row, sqlite3.Row]]:
        connection = self.database.connect()
        rows = connection.execute(
            "SELECT c.id AS chunk_id, c.item_id, c.ordinal, c.safe_text, c.raw_text, c.page, c.heading, c.embedding_dim, c.embedding_model, c.embedding_version, i.id AS item_uuid, i.source_path, i.source_hash, i.type, i.created_at, i.updated_at, i.sanitizer_version FROM chunks c JOIN items i ON i.id=c.item_id ORDER BY c.item_id, c.ordinal"
        ).fetchall()
        result = [(row, row) for row in rows]
        connection.close()
        return result

    def replace_vectors(self, vectors: list[tuple[int, list[float]]]) -> None:
        connection = self.database.connect()
        try:
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute("DELETE FROM vec_chunks")
            connection.executemany(
                "INSERT INTO vec_chunks VALUES (?, ?)",
                [(chunk_id, pack(vector)) for chunk_id, vector in vectors],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
