from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import Settings
from .migrations import migrate


class Database:
    def __init__(self, settings: Settings) -> None:
        settings.ensure_dirs()
        self.path = Path(settings.db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        migrate(connection)
        connection.commit()
        return connection
