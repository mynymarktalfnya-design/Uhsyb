from pathlib import Path
import sys
import os

from fastapi import Request
from fastapi.responses import FileResponse

BACKEND_DIR = Path(__file__).resolve().parent / "market-backend"
WEB_ROOT = Path(__file__).resolve().parent / "web"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("JWT_SECRET_KEY", os.environ.get("JWT_SECRET", ""))

from server import app  # noqa: E402


@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str, request: Request):
    requested = (WEB_ROOT / path).resolve()
    if requested.is_file() and WEB_ROOT in requested.parents:
        return FileResponse(requested)
    return FileResponse(WEB_ROOT / "index.html")
