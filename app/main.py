from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import APP_NAME, CURRENT_PHASE, SERVICE_NAME, __version__
from app.diagnostics import get_diagnostics
from app.gpu_collector import get_gpu_snapshot

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title=APP_NAME,
    description="Local NVIDIA GPU monitoring dashboard.",
    version=__version__,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": CURRENT_PHASE,
    }


@app.get("/api/snapshot")
def api_snapshot() -> Dict[str, object]:
    return get_gpu_snapshot()


@app.get("/api/diagnostics")
def api_diagnostics() -> Dict[str, object]:
    return get_diagnostics()
