"""Entry point for Claude Desktop.

Claude Desktop runs `python /abs/path/server.py` from an arbitrary working directory,
so the project root is put on sys.path before importing the package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
