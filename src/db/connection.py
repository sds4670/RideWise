"""Read-only SQLite connection.

The database is opened with mode=ro via a file: URI, so the process physically
cannot write to or modify data/ridewise.db. Rows come back as sqlite3.Row so
callers can use column names.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import DB_PATH


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a read-only connection to the RideWise database.

    Raises FileNotFoundError with a clear message if the DB has not been copied
    into data/ yet (see README).
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Copy the provided ridewise.db into "
            f"the data/ folder (see README)."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
