#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${MPLCONFIGDIR:-/tmp/matplotlib}"

if [ "${1:-}" = "uvicorn" ] && [ "${AUTO_BOOTSTRAP:-true}" = "true" ]; then
  if python - <<'PY'
import os
import sqlite3
import sys
from pathlib import Path
from app.config import DB_PATH

db_path = Path(os.environ.get("F1_DB_PATH", str(DB_PATH)))
if not db_path.exists() or db_path.stat().st_size == 0:
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
try:
    has_tbl = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='driver_alltime_ratings'"
    ).fetchone()[0]
    if not has_tbl:
        sys.exit(1)
    cnt = conn.execute("SELECT COUNT(*) FROM driver_alltime_ratings").fetchone()[0]
    sys.exit(0 if int(cnt) > 0 else 1)
except sqlite3.Error:
    sys.exit(1)
finally:
    conn.close()
PY
  then
    echo "[entrypoint] Banco SQLite existente detectado. Iniciando API..."
  else
    echo "[entrypoint] Banco vazio detectado — executando bootstrap inicial (1950-2026)..."
    python -m app.cli bootstrap --skip-fastf1
  fi
fi

exec "$@"
