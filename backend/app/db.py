"""
DuckDB connection management and parameterized database access for Abhedya-Chakra.
"""

import os
from typing import Optional
import duckdb

_DB_CONNECTION: Optional[duckdb.DuckDBPyConnection] = None
DEFAULT_DB_PATH = "data/db/abhedya.duckdb"


def get_db_path() -> str:
    """Return database path from environment or default."""
    return os.getenv("ABHEDYA_DB_PATH", DEFAULT_DB_PATH)


def init_db(db_path: Optional[str] = None) -> duckdb.DuckDBPyConnection:
    """Initialize read-only DuckDB connection."""
    global _DB_CONNECTION
    target_path = db_path or get_db_path()
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Database file not found at: {target_path}. Please run ingestion first.")
    
    _DB_CONNECTION = duckdb.connect(database=target_path, read_only=True)
    return _DB_CONNECTION


def get_db() -> duckdb.DuckDBPyConnection:
    """Get active DuckDB connection."""
    global _DB_CONNECTION
    if _DB_CONNECTION is None:
        init_db()
    return _DB_CONNECTION


def close_db():
    """Close DuckDB connection cleanly."""
    global _DB_CONNECTION
    if _DB_CONNECTION is not None:
        try:
            _DB_CONNECTION.close()
        except Exception:
            pass
        _DB_CONNECTION = None
