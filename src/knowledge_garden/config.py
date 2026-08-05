from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    mcp_host: str
    mcp_port: int
    embed_backend: str
    embedding_model: str
    embedding_dim: int
    sanitizer_version: str = "v1"

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(
            os.environ.get("KG_DATA_DIR", "~/.local/share/knowledge-garden")
        ).expanduser()
        backend = os.environ.get("KG_EMBED_BACKEND", "st")
        model = os.environ.get("KG_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        dim = int(os.environ.get("KG_EMBED_DIM", "384" if backend == "st" else "32"))
        return cls(
            data_dir,
            data_dir / "knowledge.db",
            "127.0.0.1",
            int(os.environ.get("KG_MCP_PORT", "8765")),
            backend,
            model,
            dim,
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
