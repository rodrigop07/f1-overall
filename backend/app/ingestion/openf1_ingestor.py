"""OpenF1 API enricher (2023-2026): tyre compounds, stint ages, SC/VSC neutralizations, and FIA penalties."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import httpx

from app.config import OPENF1_BASE_URL, OPENF1_CACHE_DIR, USER_AGENT, ensure_directories

_CAR_NUM_RE = re.compile(r"\bCAR\s+(\d+)\b", re.IGNORECASE)


def _normalize_compound(comp: str | None) -> str:
    c = (comp or "").strip().upper()
    if c in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"):
        return c
    if "INTER" in c:
        return "INTERMEDIATE"
    if "WET" in c:
        return "WET"
    return "UNKNOWN"


def _fetch_cached_json(
    client: httpx.Client,
    cache_file: Path,
    endpoint: str,
    params: dict,
    refresh: bool = False,
) -> list[dict]:
    if not refresh and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    url = f"{OPENF1_BASE_URL}/{endpoint}"
    for attempt in range(5):
        time.sleep(0.6 + attempt * 1.0)
        resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data
            return []
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(3.5 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
    return []


def _parse_neutralization_laps(rc_messages: list[dict]) -> list[tuple[int, int, str]]:
    """Extract (lap_start, lap_end, status_type) intervals from OpenF1 race_control."""
    intervals: list[tuple[int, int, str]] = []
    active_sc_start: int | None = None
    active_vsc_start: int | None = None
    active_red_start: int | None = None
    max_lap = 1

    sorted_msgs = sorted(rc_messages, key=lambda m: (m.get("date") or "", int(m.get("lap_number") or 0)))
    for m in sorted_msgs:
        lap = int(m.get("lap_number") or 0)
        if lap > max_lap:
            max_lap = lap
        cat = (m.get("category") or "").strip()
        flag = (m.get("flag") or "").strip().upper()
        msg = (m.get("message") or "").strip().upper()

        if cat == "SafetyCar":
            if "VIRTUAL" in msg or "VSC" in msg:
                if "DEPLOYED" in msg and active_vsc_start is None:
                    active_vsc_start = max(1, lap)
                elif ("ENDING" in msg or "ENDED" in msg) and active_vsc_start is not None:
                    intervals.append((active_vsc_start, max(active_vsc_start, lap), "VSC"))
                    active_vsc_start = None
            else:
                if "DEPLOYED" in msg and active_sc_start is None:
                    active_sc_start = max(1, lap)
                elif ("IN THIS LAP" in msg or "ENDING" in msg or "ENDED" in msg) and active_sc_start is not None:
                    intervals.append((active_sc_start, max(active_sc_start, lap), "SC"))
                    active_sc_start = None
        elif flag == "RED" and active_red_start is None:
            active_red_start = max(1, lap)
        elif active_red_start is not None and (flag in ("GREEN", "CLEAR") or "RACE RESUME" in msg or "TRACK CLEAR" in msg):
            intervals.append((active_red_start, max(active_red_start, lap), "RED"))
            active_red_start = None

    if active_sc_start is not None:
        intervals.append((active_sc_start, max(active_sc_start, max_lap), "SC"))
    if active_vsc_start is not None:
        intervals.append((active_vsc_start, max(active_vsc_start, max_lap), "VSC"))
    if active_red_start is not None:
        intervals.append((active_red_start, max(active_red_start, max_lap), "RED"))

    return intervals


def _parse_fia_driving_penalties(rc_messages: list[dict]) -> dict[int, list[str]]:
    """Extract driver_number -> list of distinct FIA penalty messages (excluding SERVED notifications)."""
    out: dict[int, list[str]] = {}
    for m in rc_messages:
        msg = (m.get("message") or "").strip()
        upper = msg.upper()
        if "PENALTY" not in upper:
            continue
        if "PENALTY SERVED" in upper or "NO FURTHER" in upper or "NOTED" in upper:
            continue
        if not any(k in upper for k in ("TIME PENALTY", "DRIVE THROUGH", "STOP-AND-GO", "STOP AND GO", "DISQUALIFIED")):
            continue
        # Extract car number
        dnum = m.get("driver_number")
        if dnum is None:
            match = _CAR_NUM_RE.search(upper)
            if match:
                dnum = int(match.group(1))
        if dnum is None:
            continue
        out.setdefault(int(dnum), []).append(msg)
    return out


def enrich_from_openf1(
    conn: sqlite3.Connection,
    years: tuple[int, ...] = (2023, 2024, 2025, 2026),
) -> dict[str, int]:
    """Ingest OpenF1 stint compounds, SC/VSC neutralizations, and FIA penalties for 2023-2026."""
    ensure_directories()
    headers = {"User-Agent": USER_AGENT}
    sessions_matched = 0
    stints_inserted = 0
    neutralizations_inserted = 0
    penalties_inserted = 0

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for year in years:
            db_rounds = conn.execute(
                """
                SELECT r.id, r.name, r.date
                FROM rounds r
                JOIN seasons s ON s.id = r.season_id
                WHERE s.year = ? AND r.is_cancelled = 0 AND r.date IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM sessions ss
                      JOIN session_entries se ON se.session_id = ss.id
                      WHERE ss.round_id = r.id AND ss.type = 'R'
                  )
                ORDER BY r.number
                """,
                (year,),
            ).fetchall()
            if not db_rounds:
                continue

            sessions_cache = OPENF1_CACHE_DIR / f"sessions_{year}.json"
            # Refresh current year's session list if new rounds exist without local match
            of1_sessions = _fetch_cached_json(
                client,
                sessions_cache,
                "sessions",
                {"year": year, "session_name": "Race"},
                refresh=(year >= 2026),
            )
            if not of1_sessions:
                continue

            parsed_of1: list[tuple[datetime, dict]] = []
            for s in of1_sessions:
                ds = s.get("date_start")
                if not ds:
                    continue
                try:
                    dt = datetime.fromisoformat(ds.replace("Z", "+00:00")).replace(tzinfo=None)
                    parsed_of1.append((dt, s))
                except ValueError:
                    continue

            for rnd in db_rounds:
                round_id = int(rnd["id"])
                try:
                    rnd_dt = datetime.strptime(rnd["date"], "%Y-%m-%d")
                except ValueError:
                    continue

                best_session = None
                best_diff = 999.0
                for dt, s_obj in parsed_of1:
                    diff_days = abs((dt.date() - rnd_dt.date()).days)
                    if diff_days <= 3 and diff_days < best_diff:
                        best_diff = diff_days
                        best_session = s_obj

                if not best_session:
                    continue

                skey = int(best_session["session_key"])
                sessions_matched += 1

                # Map car_number -> driver_id for this round
                car_rows = conn.execute(
                    """
                    SELECT re.car_number, td.driver_id
                    FROM round_entries re
                    JOIN team_drivers td ON td.id = re.team_driver_id
                    WHERE re.round_id = ? AND re.car_number IS NOT NULL
                    """,
                    (round_id,),
                ).fetchall()
                car_to_driver = {int(cr["car_number"]): int(cr["driver_id"]) for cr in car_rows}

                # Fallback via permanent_car_number if car_number missing
                if not car_to_driver:
                    perm_rows = conn.execute(
                        """
                        SELECT d.permanent_car_number, td.driver_id
                        FROM round_entries re
                        JOIN team_drivers td ON td.id = re.team_driver_id
                        JOIN drivers d ON d.id = td.driver_id
                        WHERE re.round_id = ? AND d.permanent_car_number IS NOT NULL
                        """,
                        (round_id,),
                    ).fetchall()
                    car_to_driver = {int(pr["permanent_car_number"]): int(pr["driver_id"]) for pr in perm_rows}

                # Stints
                stints = _fetch_cached_json(
                    client,
                    OPENF1_CACHE_DIR / f"stints_{skey}.json",
                    "stints",
                    {"session_key": skey},
                )
                if stints:
                    stint_rows = []
                    for st in stints:
                        dnum = st.get("driver_number")
                        st_num = st.get("stint_number")
                        if dnum is None or st_num is None:
                            continue
                        driver_id = car_to_driver.get(int(dnum))
                        if not driver_id:
                            continue
                        stint_rows.append(
                            (
                                round_id,
                                driver_id,
                                int(st_num),
                                st.get("lap_start"),
                                st.get("lap_end"),
                                _normalize_compound(st.get("compound")),
                                int(st.get("tyre_age_at_start") or 0),
                                "openf1",
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

                # Race Control (SC/VSC + FIA Penalties)
                rc = _fetch_cached_json(
                    client,
                    OPENF1_CACHE_DIR / f"race_control_{skey}.json",
                    "race_control",
                    {"session_key": skey},
                )
                if rc:
                    intervals = _parse_neutralization_laps(rc)
                    conn.execute(
                        "DELETE FROM track_neutralizations WHERE round_id = ? AND source = 'openf1'",
                        (round_id,),
                    )
                    if intervals:
                        conn.executemany(
                            """
                            INSERT INTO track_neutralizations (round_id, lap_start, lap_end, status_type, source)
                            VALUES (?, ?, ?, ?, 'openf1')
                            """,
                            [(round_id, ls, le, stype) for ls, le, stype in intervals],
                        )
                        neutralizations_inserted += len(intervals)

                    pen_map = _parse_fia_driving_penalties(rc)
                    if pen_map:
                        pen_rows = []
                        for dnum, msgs in pen_map.items():
                            driver_id = car_to_driver.get(dnum)
                            if driver_id:
                                pen_rows.append((round_id, driver_id, len(msgs), json.dumps(msgs)))
                        if pen_rows:
                            conn.executemany(
                                """
                                INSERT OR REPLACE INTO openf1_penalties (
                                    round_id, driver_id, penalty_count, messages_json
                                ) VALUES (?, ?, ?, ?)
                                """,
                                pen_rows,
                            )
                            penalties_inserted += len(pen_rows)

    return {
        "sessions_matched": sessions_matched,
        "stints_inserted": stints_inserted,
        "neutralizations_inserted": neutralizations_inserted,
        "penalties_inserted": penalties_inserted,
    }
