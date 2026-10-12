"""Settings shared by the API and the MCP server.

Claude Desktop launches the MCP server from an unpredictable working directory,
so the database path is always resolved to an absolute path.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("STORE_DB_PATH", PROJECT_ROOT / "data" / "store.db")).resolve()
DATABASE_URL = f"sqlite:///{DB_PATH}"

LOW_STOCK_THRESHOLD = int(os.getenv("STORE_LOW_STOCK_THRESHOLD", "5"))
