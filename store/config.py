"""Settings shared by the API and the MCP server.

Claude Desktop launches the MCP server from an unpredictable working directory,
and `uvx` installs the package into a throwaway cache, so the database path is
always resolved to an absolute location the user owns.

Resolution order:
1. STORE_DB_PATH, if set.
2. <project>/data/store.db, if it already exists (keeps data from source checkouts).
3. ~/.ai-store/store.db (default for installed copies).
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DB_PATH = PROJECT_ROOT / "data" / "store.db"
DEFAULT_DB_PATH = Path.home() / ".ai-store" / "store.db"


def resolve_db_path(env: dict[str, str] | os._Environ[str] = os.environ) -> Path:
    if override := env.get("STORE_DB_PATH"):
        return Path(override).expanduser().resolve()
    if LEGACY_DB_PATH.exists():
        return LEGACY_DB_PATH.resolve()
    return DEFAULT_DB_PATH.resolve()


DB_PATH = resolve_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH}"

LOW_STOCK_THRESHOLD = int(os.getenv("STORE_LOW_STOCK_THRESHOLD", "5"))
