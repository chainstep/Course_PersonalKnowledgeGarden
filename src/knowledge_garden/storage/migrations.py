from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).parent / "sql" / "001_initial.sql"


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA.read_text())
