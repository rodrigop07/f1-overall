"""Ingestor for Jolpica-F1 official delayed CSV dumps (1950-2026)."""

from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import CACHE_DIR, JOLPICA_DUMPS_URL, USER_AGENT, ensure_directories
from app.db.schema import init_schema
from app.ingestion.parsers import (
    clean_str,
    parse_bool,
    parse_duration_seconds,
    parse_float,
    parse_int,
    resolve_team_color,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_jolpica_dump(force: bool = False) -> tuple[Path, dict]:
    """Download Jolpica delayed CSV dump if not already cached with matching SHA-256."""
    ensure_directories()
    zip_path = CACHE_DIR / "jolpica_delayed_csv.zip"
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        meta_resp = client.get(JOLPICA_DUMPS_URL)
        meta_resp.raise_for_status()
        meta = meta_resp.json()

    dump_info = meta["delayed_dumps"]["csv"]
    expected_hash = dump_info["file_hash"]

    if not force and zip_path.exists():
        if _sha256_file(zip_path) == expected_hash:
            return zip_path, dump_info

    with httpx.Client(headers=headers, timeout=180.0, follow_redirects=True) as client:
        with client.stream("GET", dump_info["download_url"]) as resp:
            resp.raise_for_status()
            tmp_path = zip_path.with_suffix(".tmp")
            with tmp_path.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
            tmp_path.replace(zip_path)

    actual_hash = _sha256_file(zip_path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"SHA-256 mismatch on Jolpica CSV dump: expected {expected_hash}, got {actual_hash}"
        )
    return zip_path, dump_info


def _iter_csv_rows(zf: zipfile.ZipFile, filename: str):
    with zf.open(filename) as raw_f:
        wrapper = io.TextIOWrapper(raw_f, encoding="utf-8")
        yield from csv.DictReader(wrapper)


def load_jolpica_dump_into_db(
    conn: sqlite3.Connection,
    zip_path: Path,
    dump_info: dict | None = None,
) -> dict[str, int]:
    """Bulk-load Jolpica CSV dump tables into SQLite inside an atomic transaction."""
    init_schema(conn)
    counts: dict[str, int] = {}

    raw_tables = [
        "laps",
        "pit_stops",
        "penalties",
        "session_entries",
        "sessions",
        "round_entries",
        "rounds",
        "team_drivers",
        "teams",
        "base_teams",
        "drivers",
        "circuits",
        "seasons",
        "driver_championships",
    ]
    for tbl in raw_tables:
        conn.execute(f"DELETE FROM {tbl}")

    with zipfile.ZipFile(zip_path) as zf:
        # 1. Seasons
        rows = [
            (parse_int(r["id"]), parse_int(r["year"]), clean_str(r.get("wikipedia")))
            for r in _iter_csv_rows(zf, "formula_one_season.csv")
        ]
        conn.executemany("INSERT INTO seasons (id, year, wikipedia) VALUES (?, ?, ?)", rows)
        counts["seasons"] = len(rows)

        # 2. Circuits
        rows = [
            (
                parse_int(r["id"]),
                clean_str(r.get("reference")),
                clean_str(r.get("name")) or "Unknown Circuit",
                clean_str(r.get("country")),
                clean_str(r.get("country_code")),
                clean_str(r.get("locality")),
            )
            for r in _iter_csv_rows(zf, "formula_one_circuit.csv")
        ]
        conn.executemany(
            "INSERT INTO circuits (id, reference, name, country, country_code, locality) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        counts["circuits"] = len(rows)

        # 3. Drivers (ensure unique non-null reference)
        seen_refs: set[str] = set()
        driver_rows = []
        for r in _iter_csv_rows(zf, "formula_one_driver.csv"):
            did = parse_int(r["id"])
            ref = clean_str(r.get("reference")) or clean_str(r.get("api_id")) or f"driver_{did}"
            if ref in seen_refs:
                ref = f"{ref}_{did}"
            seen_refs.add(ref)
            driver_rows.append(
                (
                    did,
                    ref,
                    clean_str(r.get("api_id")),
                    clean_str(r.get("abbreviation")),
                    clean_str(r.get("forename")) or "",
                    clean_str(r.get("surname")) or "",
                    clean_str(r.get("date_of_birth")),
                    clean_str(r.get("nationality")),
                    clean_str(r.get("country_code")),
                    parse_int(r.get("permanent_car_number")),
                    clean_str(r.get("wikipedia")),
                )
            )
        conn.executemany(
            """
            INSERT INTO drivers (
                id, reference, api_id, abbreviation, forename, surname,
                date_of_birth, nationality, country_code, permanent_car_number, wikipedia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            driver_rows,
        )
        counts["drivers"] = len(driver_rows)

        # 4. Base Teams
        rows = [
            (parse_int(r["id"]), clean_str(r.get("api_id")), clean_str(r.get("name")) or "Unknown")
            for r in _iter_csv_rows(zf, "formula_one_baseteam.csv")
        ]
        conn.executemany("INSERT INTO base_teams (id, api_id, name) VALUES (?, ?, ?)", rows)
        counts["base_teams"] = len(rows)

        # 5. Teams
        rows = [
            (
                parse_int(r["id"]),
                clean_str(r.get("reference")),
                clean_str(r.get("api_id")),
                parse_int(r.get("base_team_id")),
                clean_str(r.get("name")) or "Unknown",
                clean_str(r.get("nationality")),
                clean_str(r.get("country_code")),
                resolve_team_color(r.get("reference"), r.get("primary_color"), r.get("name")),
                clean_str(r.get("wikipedia")),
            )
            for r in _iter_csv_rows(zf, "formula_one_team.csv")
        ]
        conn.executemany(
            """
            INSERT INTO teams (
                id, reference, api_id, base_team_id, name,
                nationality, country_code, primary_color, wikipedia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        counts["teams"] = len(rows)

        # 6. TeamDrivers
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["season_id"]),
                parse_int(r["team_id"]),
                parse_int(r["driver_id"]),
                parse_int(r.get("role")),
            )
            for r in _iter_csv_rows(zf, "formula_one_teamdriver.csv")
        ]
        conn.executemany(
            "INSERT INTO team_drivers (id, season_id, team_id, driver_id, role) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        counts["team_drivers"] = len(rows)

        # 7. Rounds
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["season_id"]),
                parse_int(r.get("circuit_id")),
                parse_int(r.get("number")),
                parse_int(r.get("race_number")),
                clean_str(r.get("name")) or "Grand Prix",
                clean_str(r.get("date")),
                parse_bool(r.get("is_cancelled")),
            )
            for r in _iter_csv_rows(zf, "formula_one_round.csv")
        ]
        conn.executemany(
            """
            INSERT INTO rounds (
                id, season_id, circuit_id, number, race_number, name, date, is_cancelled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        counts["rounds"] = len(rows)

        # 8. RoundEntries
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["round_id"]),
                parse_int(r["team_driver_id"]),
                parse_int(r.get("car_number")),
            )
            for r in _iter_csv_rows(zf, "formula_one_roundentry.csv")
        ]
        conn.executemany(
            "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, ?, ?, ?)",
            rows,
        )
        counts["round_entries"] = len(rows)

        # 9. Sessions
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["round_id"]),
                clean_str(r.get("type")) or "R",
                parse_int(r.get("number")),
                parse_int(r.get("scheduled_laps")),
                parse_int(r.get("completed_laps")),
                clean_str(r.get("timestamp")),
                parse_bool(r.get("is_cancelled")),
            )
            for r in _iter_csv_rows(zf, "formula_one_session.csv")
        ]
        conn.executemany(
            """
            INSERT INTO sessions (
                id, round_id, type, number, scheduled_laps, completed_laps, timestamp, is_cancelled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        counts["sessions"] = len(rows)

        # 10. SessionEntries
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["session_id"]),
                parse_int(r["round_entry_id"]),
                parse_int(r.get("position")),
                parse_bool(r.get("is_classified")) if clean_str(r.get("is_classified")) is not None else None,
                parse_int(r.get("status")),
                clean_str(r.get("detail")),
                parse_float(r.get("points")),
                parse_int(r.get("grid")),
                parse_duration_seconds(r.get("time")),
                parse_int(r.get("laps_completed")),
                parse_int(r.get("fastest_lap_rank")),
            )
            for r in _iter_csv_rows(zf, "formula_one_sessionentry.csv")
        ]
        conn.executemany(
            """
            INSERT INTO session_entries (
                id, session_id, round_entry_id, position, is_classified, status,
                detail, points, grid, time_sec, laps_completed, fastest_lap_rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        counts["session_entries"] = len(rows)

        # 11. Laps (stream in batches of 50k to keep peak RAM low)
        lap_batch: list[tuple] = []
        lap_total = 0
        for r in _iter_csv_rows(zf, "formula_one_lap.csv"):
            lap_batch.append(
                (
                    parse_int(r["id"]),
                    parse_int(r["session_entry_id"]),
                    parse_int(r.get("number")),
                    parse_int(r.get("position")),
                    parse_duration_seconds(r.get("time")),
                    parse_bool(r.get("is_deleted")),
                    parse_bool(r.get("is_entry_fastest_lap")),
                )
            )
            if len(lap_batch) >= 50000:
                conn.executemany(
                    """
                    INSERT INTO laps (
                        id, session_entry_id, number, position, time_sec, is_deleted, is_entry_fastest_lap
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    lap_batch,
                )
                lap_total += len(lap_batch)
                lap_batch.clear()
        if lap_batch:
            conn.executemany(
                """
                INSERT INTO laps (
                    id, session_entry_id, number, position, time_sec, is_deleted, is_entry_fastest_lap
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                lap_batch,
            )
            lap_total += len(lap_batch)
        counts["laps"] = lap_total

        # 12. PitStops
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["session_entry_id"]),
                parse_int(r.get("number")),
                parse_int(r.get("lap_id")),
                parse_duration_seconds(r.get("duration")),
            )
            for r in _iter_csv_rows(zf, "formula_one_pitstop.csv")
        ]
        conn.executemany(
            "INSERT INTO pit_stops (id, session_entry_id, number, lap_id, duration_sec) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        counts["pit_stops"] = len(rows)

        # 13. Penalties
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r.get("earned_id")),
                parse_int(r.get("served_id")),
                parse_int(r.get("license_points")),
                parse_int(r.get("position")),
                parse_duration_seconds(r.get("time")),
                parse_bool(r.get("is_time_served_in_pit")),
            )
            for r in _iter_csv_rows(zf, "formula_one_penalty.csv")
        ]
        if rows:
            conn.executemany(
                """
                INSERT INTO penalties (
                    id, earned_id, served_id, license_points, position, time_sec, is_time_served_in_pit
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        counts["penalties"] = len(rows)

        # 14. Driver Championships
        rows = [
            (
                parse_int(r["id"]),
                parse_int(r["driver_id"]),
                parse_int(r.get("season_id")) or 0,
                parse_int(r.get("round_id")),
                parse_int(r.get("position")),
                parse_float(r.get("points")),
                parse_int(r.get("win_count")),
                parse_int(r.get("year")),
                parse_int(r.get("round_number")),
                parse_int(r.get("session_number")),
            )
            for r in _iter_csv_rows(zf, "formula_one_driverchampionship.csv")
        ]
        conn.executemany(
            """
            INSERT INTO driver_championships (
                id, driver_id, season_id, round_id, position, points, win_count, year, round_number, session_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        counts["driver_championships"] = len(rows)

    now_iso = datetime.now(timezone.utc).isoformat()
    if dump_info:
        conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_state (key, value, updated_at)
            VALUES ('jolpica_dump_uploaded_at', ?, ?)
            """,
            (str(dump_info.get("uploaded_at", "")), now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_state (key, value, updated_at)
            VALUES ('jolpica_dump_hash', ?, ?)
            """,
            (str(dump_info.get("file_hash", "")), now_iso),
        )

    return counts
