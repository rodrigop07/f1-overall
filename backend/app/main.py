"""FastAPI application entrypoint with CORS, in-memory simulator preload, and optional SPA serving."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
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


def configure_spa_serving(target_app: FastAPI, dist_dir: Path) -> None:
    """Mount compiled frontend assets and serve SPA fallback safely."""
    index_file = dist_dir / "index.html"
    if not dist_dir.exists() or not index_file.exists():
        return

    resolved_root = dist_dir.resolve()
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        target_app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @target_app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (dist_dir / full_path).resolve()
            if candidate.is_relative_to(resolved_root) and candidate.exists() and candidate.is_file():
                return FileResponse(str(candidate))
        return FileResponse(str(index_file))


configure_spa_serving(app, FRONTEND_DIST_DIR)
