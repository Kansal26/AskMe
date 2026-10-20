"""DuckDB connection factory with security hardening."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from src.common.config import settings


def get_duckdb_connection(
    db_path: Path | str | None = None,
    read_only: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Creates a secure DuckDB connection.

    Security configuration when read_only=True:
    - enable_external_access=False: prevents reading or writing arbitrary filesystem files
    - lock_configuration=True: locks the configuration so it cannot be altered at runtime
    - read_only=True: prevents any data mutations or table modifications
    """
    path = Path(db_path or settings.duckdb_path)

    if read_only:
        if not path.exists():
            raise FileNotFoundError(
                f"DuckDB database file not found at '{path}'. "
                f"Please run the database loader before querying in read-only mode."
            )
        config: dict[str, Any] = {
            "enable_external_access": False,
            "lock_configuration": True,
        }
        return duckdb.connect(database=str(path), read_only=True, config=config)

    # Write mode (used solely by loader.py to build the database)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(database=str(path), read_only=False)
