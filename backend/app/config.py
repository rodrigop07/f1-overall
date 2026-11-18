"""Application configuration constants and paths."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = Path(os.environ.get("F1_DATA_DIR", BACKEND_DIR / "data"))
CACHE_DIR = DATA_DIR / "cache"
OPENF1_CACHE_DIR = CACHE_DIR / "openf1"
FASTF1_CACHE_DIR = CACHE_DIR / "fastf1"
DB_PATH = Path(os.environ.get("F1_DB_PATH", DATA_DIR / "f1_overall.sqlite"))
FRONTEND_DIST_DIR = Path(os.environ.get("F1_FRONTEND_DIST_DIR", REPO_ROOT / "frontend" / "dist"))

JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"
JOLPICA_DUMPS_URL = "https://api.jolpi.ca/data/dumps/download/"
OPENF1_BASE_URL = "https://api.openf1.org/v1"
USER_AGENT = "F1OverallEngine/1.0 (f1-overall research project)"

# Default methodology weights and hyperparameters
DEFAULT_WEIGHTS = {
    "pace": 0.35,
    "qualifying": 0.25,
    "consistency": 0.20,
    "racecraft": 0.15,
    "experience": 0.05,
}
DEFAULT_SHRINKAGE_M = 10.0
DEFAULT_BASELINE_Z = -0.30
DEFAULT_HALF_LIFE_SEASON = 14.0
DEFAULT_HALF_LIFE_CURRENT = 16.0
DEFAULT_BASE_OVR = 82.0
DEFAULT_SCALE_FACTOR = 6.0
MIN_OVR = 60.0
MAX_OVR = 99.0


def ensure_directories() -> None:
    """Create local data and cache directories if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OPENF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
