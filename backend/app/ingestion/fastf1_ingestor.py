"""FastF1 telemetry connector (2018-2026) with cache awareness and graceful auth handling."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import fastf1
import httpx
import pandas as pd

from app.config import FASTF1_CACHE_DIR, ensure_directories
from app.ingestion.openf1_ingestor import _normalize_compound

logger = logging.getLogger(__name__)


def probe_fastf1_live_access() -> bool:
    """Check once whether unauthenticated/authenticated F1 live-timing static archive is accessible."""
    headers = {"User-Agent": "BestHTTP"}
    token = os.environ.get("FASTF1_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = httpx.get(
            "https://livetiming.formula1.com/static/2024/2024-03-02_Bahrain_Grand_Prix/2024-03-02_Race/SessionInfo.jsonStream",
            headers=headers,
            timeout=6.0,
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def _has_cached_fastf1_files(cache_dir: Path) -> bool:
    if not cache_dir.exists():
        return False
    return any(cache_dir.rglob("*.ff1pkl"))


def enrich_from_fastf1(
    conn: sqlite3.Connection,
    years: tuple[int, ...] = tuple(range(2018, 2027)),
    force_live: bool = False,
) -> dict[str, int | str]:
    """Enrich 2018-2026 rounds from FastF1 cache or authenticated live archive."""
    ensure_directories()

    live_ok = force_live or probe_fastf1_live_access()
    has_cache = _has_cached_fastf1_files(FASTF1_CACHE_DIR)
    if not live_ok and not has_cache:
        msg = (
            "FastF1 live archive returned HTTP 401 (requires F1 TV auth) and local cache is empty; "
            "using Jolpica + OpenF1 layers seamlessly."
        )
        logger.info(msg)
        return {"sessions_enriched": 0, "stints_inserted": 0, "status": "skipped_no_auth"}

    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))
    if not live_ok and has_cache:
        fastf1.Cache.offline_mode(True)

    sessions_enriched = 0
    stints_inserted = 0

    for year in years:
        db_rounds = conn.execute(
            """
            SELECT r.id, r.number, r.name
            FROM rounds r
            JOIN seasons s ON s.id = r.season_id
            WHERE s.year = ? AND r.is_cancelled = 0
              AND EXISTS (
                  SELECT 1 FROM sessions ss
                  JOIN session_entries se ON se.session_id = ss.id
                  WHERE ss.round_id = r.id AND ss.type = 'R'
              )
            ORDER BY r.number
            """,
            (year,),
        ).fetchall()

        for rnd in db_rounds:
            round_id = int(rnd["id"])
            # Skip if already enriched by fastf1
            if conn.execute(
                "SELECT 1 FROM stint_enrichments WHERE round_id = ? AND source = 'fastf1' LIMIT 1",
                (round_id,),
            ).fetchone():
                continue

            try:
                sess = fastf1.get_session(year, int(rnd["number"]), "R")
                sess.load(laps=True, telemetry=False, weather=False, messages=False)
            except Exception as exc:
                logger.debug("FastF1 session %s R%s unavailable: %s", year, rnd["number"], exc)
                continue

            laps_df = getattr(sess, "laps", None)
            if laps_df is None or laps_df.empty:
                continue

            # Map DriverNumber -> driver_id
            car_rows = conn.execute(
                """
                SELECT re.car_number, td.driver_id
                FROM round_entries re
                JOIN team_drivers td ON td.id = re.team_driver_id
                WHERE re.round_id = ? AND re.car_number IS NOT NULL
                """,
                (round_id,),
            ).fetchall()
            car_to_driver = {int(r["car_number"]): int(r["driver_id"]) for r in car_rows}

            stint_rows = []
            for (drv_num, stint_num), grp in laps_df.groupby(["DriverNumber", "Stint"]):
                if pd.isna(drv_num) or pd.isna(stint_num):
                    continue
                driver_id = car_to_driver.get(int(drv_num))
                if not driver_id:
                    continue
                lap_nums = grp["LapNumber"].dropna().astype(int)
                if lap_nums.empty:
                    continue
                comp = _normalize_compound(str(grp["Compound"].dropna().iloc[0])) if not grp["Compound"].dropna().empty else "UNKNOWN"
                tyre_lives = grp["TyreLife"].dropna()
                age_start = max(0, int(tyre_lives.min()) - 1) if not tyre_lives.empty else 0
                stint_rows.append(
                    (
                        round_id,
                        driver_id,
                        int(stint_num),
                        int(lap_nums.min()),
                        int(lap_nums.max()),
                        comp,
                        age_start,
                        "fastf1",
                    )
                )

            if stint_rows:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO stint_enrichments (
                        round_id, driver_id, stint_number, lap_start, lap_end,
                        compound, tyre_age_at_start, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    stint_rows,
                )
                stints_inserted += len(stint_rows)

            # TrackStatus != '1' indicates Yellow/SC/VSC/Red
            if "TrackStatus" in laps_df.columns and "LapNumber" in laps_df.columns:
                non_green = laps_df[laps_df["TrackStatus"].astype(str).apply(lambda s: any(c in s for c in ("4", "5", "6", "7")))]
                bad_laps = sorted({int(x) for x in non_green["LapNumber"].dropna().astype(int)})
                if bad_laps:
                    conn.execute(
                        "DELETE FROM track_neutralizations WHERE round_id = ? AND source = 'fastf1'",
                        (round_id,),
                    )
                    # Compress contiguous laps into intervals
                    intervals = []
                    s_lap = prev = bad_laps[0]
                    for lnum in bad_laps[1:]:
                        if lnum == prev + 1:
                            prev = lnum
                        else:
                            intervals.append((round_id, s_lap, prev, "SC_OR_VSC", "fastf1"))
                            s_lap = prev = lnum
                    intervals.append((round_id, s_lap, prev, "SC_OR_VSC", "fastf1"))
                    conn.executemany(
                        "INSERT INTO track_neutralizations (round_id, lap_start, lap_end, status_type, source) VALUES (?, ?, ?, ?, ?)",
                        intervals,
                    )

            sessions_enriched += 1

    return {
        "sessions_enriched": sessions_enriched,
        "stints_inserted": stints_inserted,
        "status": "ok",
    }
