"""Incremental REST sync from Jolpica-F1 for rounds completed after the delayed CSV dump."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

import httpx

from app.config import JOLPICA_BASE_URL, USER_AGENT
from app.ingestion.parsers import parse_duration_seconds, parse_float, parse_int, resolve_team_color

_DRIVER_ERROR_DETAILS = {"Accident", "Collision", "Spun off"}
_DNS_DETAILS = {"Withdrawn", "Did not start", "Did not qualify", "Did not prequalify", "Injury", "Illness"}


def _map_status_text(status_text: str) -> tuple[int, int]:
    """Map Ergast/Jolpica status string to (SessionStatus int, is_classified 0/1)."""
    s = (status_text or "").strip()
    sl = s.lower()
    if s == "Finished":
        return 0, 1
    if sl.startswith("+") or "lap" in sl:
        return 1, 1
    if s in _DRIVER_ERROR_DETAILS or any(k in sl for k in ("accident", "collision", "spun")):
        return 10, 0
    if s == "Disqualified":
        return 20, 0
    if s in _DNS_DETAILS or "did not" in sl or "withdrawn" in sl:
        return 30, 0
    return 11, 0


def _paginated_get(client: httpx.Client, path: str, max_pages: int = 30) -> list[dict]:
    """Fetch paginated MRData.RaceTable.Races list safely under Jolpica rate limits."""
    offset = 0
    limit = 100
    all_races: list[dict] = []
    for _ in range(max_pages):
        time.sleep(0.35)
        url = f"{JOLPICA_BASE_URL}/{path}"
        resp = client.get(url, params={"limit": limit, "offset": offset})
        if resp.status_code == 429:
            time.sleep(2.5)
            resp = client.get(url, params={"limit": limit, "offset": offset})
        resp.raise_for_status()
        mr = resp.json().get("MRData", {})
        races = mr.get("RaceTable", {}).get("Races", [])
        if not races:
            break
        all_races.extend(races)
        total = int(mr.get("total") or 0)
        offset += limit
        if offset >= total:
            break
    return all_races


def _ensure_driver(conn: sqlite3.Connection, d_obj: dict) -> int:
    ref = d_obj["driverId"]
    row = conn.execute("SELECT id FROM drivers WHERE reference = ?", (ref,)).fetchone()
    if row:
        return int(row["id"])
    next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM drivers").fetchone()[0])
    conn.execute(
        """
        INSERT INTO drivers (
            id, reference, api_id, abbreviation, forename, surname,
            date_of_birth, nationality, country_code, permanent_car_number, wikipedia
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            next_id,
            ref,
            f"rest_{ref}",
            d_obj.get("code"),
            d_obj.get("givenName", ""),
            d_obj.get("familyName", ""),
            d_obj.get("dateOfBirth"),
            d_obj.get("nationality"),
            parse_int(d_obj.get("permanentNumber")),
            d_obj.get("url"),
        ),
    )
    return next_id


def _ensure_team(conn: sqlite3.Connection, c_obj: dict) -> int:
    ref = c_obj["constructorId"]
    row = conn.execute("SELECT id FROM teams WHERE reference = ?", (ref,)).fetchone()
    if row:
        return int(row["id"])
    next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM teams").fetchone()[0])
    conn.execute(
        """
        INSERT INTO teams (
            id, reference, api_id, base_team_id, name, nationality, country_code, primary_color, wikipedia
        ) VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, ?)
        """,
        (
            next_id,
            ref,
            f"rest_{ref}",
            c_obj.get("name", ref),
            c_obj.get("nationality"),
            resolve_team_color(ref, None, c_obj.get("name")),
            c_obj.get("url"),
        ),
    )
    return next_id


def _ensure_team_driver(conn: sqlite3.Connection, season_id: int, team_id: int, driver_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM team_drivers WHERE season_id = ? AND team_id = ? AND driver_id = ?",
        (season_id, team_id, driver_id),
    ).fetchone()
    if row:
        return int(row["id"])
    next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM team_drivers").fetchone()[0])
    conn.execute(
        "INSERT INTO team_drivers (id, season_id, team_id, driver_id, role) VALUES (?, ?, ?, ?, NULL)",
        (next_id, season_id, team_id, driver_id),
    )
    return next_id


def _ensure_round_entry(conn: sqlite3.Connection, round_id: int, team_driver_id: int, car_number: int | None) -> int:
    row = conn.execute(
        "SELECT id FROM round_entries WHERE round_id = ? AND team_driver_id = ?",
        (round_id, team_driver_id),
    ).fetchone()
    if row:
        return int(row["id"])
    next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM round_entries").fetchone()[0])
    conn.execute(
        "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, ?, ?, ?)",
        (next_id, round_id, team_driver_id, car_number),
    )
    return next_id


def _ensure_session(conn: sqlite3.Connection, round_id: int, sess_type: str, scheduled_laps: int | None = None) -> int:
    row = conn.execute(
        "SELECT id FROM sessions WHERE round_id = ? AND type = ?",
        (round_id, sess_type),
    ).fetchone()
    if row:
        return int(row["id"])
    next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM sessions").fetchone()[0])
    conn.execute(
        "INSERT INTO sessions (id, round_id, type, number, scheduled_laps, completed_laps, is_cancelled) VALUES (?, ?, ?, NULL, ?, NULL, 0)",
        (next_id, round_id, sess_type, scheduled_laps),
    )
    return next_id


def sync_missing_recent_rounds(conn: sqlite3.Connection, year: int = 2026) -> dict[str, int]:
    """Fetch any completed rounds in `year` missing Race session entries in SQLite."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    season_row = conn.execute("SELECT id FROM seasons WHERE year = ?", (year,)).fetchone()
    if not season_row:
        return {"synced_rounds": 0}
    season_id = int(season_row["id"])

    missing_rounds = conn.execute(
        """
        SELECT r.id, r.number, r.name, r.date
        FROM rounds r
        WHERE r.season_id = ?
          AND r.is_cancelled = 0
          AND r.date IS NOT NULL
          AND r.date <= ?
          AND NOT EXISTS (
              SELECT 1 FROM sessions s
              JOIN session_entries se ON se.session_id = s.id
              WHERE s.round_id = r.id AND s.type = 'R'
          )
        ORDER BY r.number
        """,
        (season_id, today_str),
    ).fetchall()

    if not missing_rounds:
        return {"synced_rounds": 0}

    synced = 0
    laps_inserted = 0
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for rnd in missing_rounds:
            round_id = int(rnd["id"])
            rnum = int(rnd["number"])
            results_pages = _paginated_get(client, f"{year}/{rnum}/results.json", max_pages=3)
            if not results_pages or not results_pages[0].get("Results"):
                continue  # Race hasn't been published yet

            results = []
            for p in results_pages:
                results.extend(p.get("Results", []))

            race_session_id = _ensure_session(conn, round_id, "R")
            driver_to_se: dict[str, int] = {}

            next_se_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM session_entries").fetchone()[0])
            for res in results:
                d_id = _ensure_driver(conn, res["Driver"])
                t_id = _ensure_team(conn, res["Constructor"])
                td_id = _ensure_team_driver(conn, season_id, t_id, d_id)
                car_num = parse_int(res.get("number"))
                re_id = _ensure_round_entry(conn, round_id, td_id, car_num)

                status_int, is_class = _map_status_text(res.get("status", ""))
                time_obj = res.get("Time") or {}
                time_sec = None
                if time_obj.get("millis"):
                    time_sec = float(time_obj["millis"]) / 1000.0
                elif time_obj.get("time"):
                    time_sec = parse_duration_seconds(time_obj["time"])
                fl_rank = parse_int((res.get("FastestLap") or {}).get("rank"))

                existing_se = conn.execute(
                    "SELECT id FROM session_entries WHERE session_id = ? AND round_entry_id = ?",
                    (race_session_id, re_id),
                ).fetchone()
                if existing_se:
                    se_id = int(existing_se["id"])
                else:
                    se_id = next_se_id
                    next_se_id += 1
                    conn.execute(
                        """
                        INSERT INTO session_entries (
                            id, session_id, round_entry_id, position, is_classified, status,
                            detail, points, grid, time_sec, laps_completed, fastest_lap_rank
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            se_id,
                            race_session_id,
                            re_id,
                            parse_int(res.get("position")),
                            is_class,
                            status_int,
                            res.get("status"),
                            parse_float(res.get("points")),
                            parse_int(res.get("grid")),
                            time_sec,
                            parse_int(res.get("laps")),
                            fl_rank,
                        ),
                    )
                driver_to_se[res["Driver"]["driverId"]] = se_id

            # Qualifying (Q1, Q2, Q3)
            quali_pages = _paginated_get(client, f"{year}/{rnum}/qualifying.json", max_pages=3)
            if quali_pages:
                q_results = []
                for p in quali_pages:
                    q_results.extend(p.get("QualifyingResults", []))
                q_sessions = {q: _ensure_session(conn, round_id, q) for q in ("Q1", "Q2", "Q3")}
                for qr in q_results:
                    d_id = _ensure_driver(conn, qr["Driver"])
                    t_id = _ensure_team(conn, qr["Constructor"])
                    td_id = _ensure_team_driver(conn, season_id, t_id, d_id)
                    re_id = _ensure_round_entry(conn, round_id, td_id, parse_int(qr.get("number")))
                    for q_phase in ("Q1", "Q2", "Q3"):
                        q_time = parse_duration_seconds(qr.get(q_phase))
                        if q_time is None:
                            continue
                        q_sid = q_sessions[q_phase]
                        if not conn.execute(
                            "SELECT 1 FROM session_entries WHERE session_id = ? AND round_entry_id = ?",
                            (q_sid, re_id),
                        ).fetchone():
                            conn.execute(
                                """
                                INSERT INTO session_entries (
                                    id, session_id, round_entry_id, position, is_classified, status,
                                    detail, points, grid, time_sec, laps_completed, fastest_lap_rank
                                ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, NULL)
                                """,
                                (next_se_id, q_sid, re_id, parse_int(qr.get("position")), q_time),
                            )
                            next_se_id += 1

            # Laps
            lap_pages = _paginated_get(client, f"{year}/{rnum}/laps.json", max_pages=25)
            next_lap_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM laps").fetchone()[0])
            lap_num_to_id: dict[tuple[int, int], int] = {}
            lap_rows: list[tuple] = []
            for p in lap_pages:
                for lap_obj in p.get("Laps", []):
                    lnum = parse_int(lap_obj.get("number"))
                    if lnum is None:
                        continue
                    for timing in lap_obj.get("Timings", []):
                        se_id = driver_to_se.get(timing["driverId"])
                        if not se_id:
                            continue
                        tsec = parse_duration_seconds(timing.get("time"))
                        if (se_id, lnum) in lap_num_to_id:
                            continue
                        lid = next_lap_id
                        next_lap_id += 1
                        lap_num_to_id[(se_id, lnum)] = lid
                        lap_rows.append((lid, se_id, lnum, parse_int(timing.get("position")), tsec, 0, 0))
            if lap_rows:
                conn.executemany(
                    """
                    INSERT INTO laps (
                        id, session_entry_id, number, position, time_sec, is_deleted, is_entry_fastest_lap
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    lap_rows,
                )
                laps_inserted += len(lap_rows)

            # Pit stops
            pit_pages = _paginated_get(client, f"{year}/{rnum}/pitstops.json", max_pages=5)
            next_pit_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM pit_stops").fetchone()[0])
            pit_rows: list[tuple] = []
            seen_pits: set[tuple[int, int]] = set()
            for p in pit_pages:
                for ps in p.get("PitStops", []):
                    se_id = driver_to_se.get(ps["driverId"])
                    stop_num = parse_int(ps.get("stop"))
                    lnum = parse_int(ps.get("lap"))
                    if not se_id or stop_num is None or (se_id, stop_num) in seen_pits:
                        continue
                    seen_pits.add((se_id, stop_num))
                    lap_id = lap_num_to_id.get((se_id, lnum)) if lnum is not None else None
                    pit_rows.append(
                        (next_pit_id, se_id, stop_num, lap_id, parse_duration_seconds(ps.get("duration")))
                    )
                    next_pit_id += 1
            if pit_rows:
                conn.executemany(
                    "INSERT INTO pit_stops (id, session_entry_id, number, lap_id, duration_sec) VALUES (?, ?, ?, ?, ?)",
                    pit_rows,
                )

            synced += 1

    return {"synced_rounds": synced, "laps_inserted": laps_inserted}
