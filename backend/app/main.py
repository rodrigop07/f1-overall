"""FastAPI application entrypoint with CORS, in-memory simulator preload, and optional SPA serving."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import FRONTEND_DIST_DIR
from app.db.connection import get_connection
from app.db.schema import init_schema
from app.engine.simulator import OverallSimulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    sim = OverallSimulator()
    conn = get_connection()
    try:
        init_schema(conn)
        cnt = int(conn.execute("SELECT COUNT(*) FROM driver_alltime_ratings").fetchone()[0])
        if cnt > 0:
            sim.reload_from_db(conn)
    finally:
        conn.close()
    app.state.simulator = sim
    yield


app = FastAPI(
    title="F1 Driver Overall Engine API",
    version="1.0.0",
    description="Mathematical driver skill isolation (0-99) for Formula 1 (1950-2026)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# Optional production static serving when frontend/dist is built
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        candidate = FRONTEND_DIST_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST_DIR / "index.html"))
