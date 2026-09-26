import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

DIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "vite-frontend", "dist")
)

router = APIRouter()


@router.get("/")
def serve_root():
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


@router.get("/{full_path:path}")
def serve_spa(full_path: str):
    return FileResponse(os.path.join(DIST_DIR, "index.html"))