"""FastAPI endpoints for F1 Driver Overall rankings, profiles, head-to-head, network & sandbox."""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.schemas import SeatSwapRequest, SimulateRequest
from app.config import USER_AGENT
from app.db.connection import get_connection
from app.engine.counterfactual import (
    simulate_equal_machinery_season,
    simulate_seat_swap,
)
from app.engine.lineages import get_lineage_detail, list_lineages
from app.engine.pipeline import run_full_computation
from app.ingestion.jolpica_incremental import sync_missing_recent_rounds
from app.ingestion.openf1_ingestor import enrich_from_openf1

router = APIRouter(prefix="/api/v1")


def _parse_badges(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("badges_json")
    if isinstance(raw, str):
        try:
            item["badges"] = json.loads(raw)
        except json.JSONDecodeError:
            item["badges"] = []
    elif isinstance(item.get("badges"), list):
        pass
    else:
        item["badges"] = []
    return item


def _get_db() -> sqlite3.Connection:
    return get_connection()


def _bfs_teammate_path(
    conn: sqlite3.Connection,
    src_id: int,
    dst_id: int,
    min_shared_races: int = 5,
) -> list[dict]:
    """Find shortest teammate calibration path between two drivers via BFS."""
    if src_id == dst_id:
        return []

    edges = conn.execute("SELECT * FROM teammate_network_edges").fetchall()
    drivers = {
        int(r["id"]): {
            "driver_id": int(r["id"]),
            "reference": r["reference"],
            "name": f"{r['forename']} {r['surname']}".strip(),
            "abbreviation": r["abbreviation"],
        }
        for r in conn.execute("SELECT id, reference, forename, surname, abbreviation FROM drivers").fetchall()
    }

    for threshold in (min_shared_races, 1):
        adj: dict[int, list[tuple[int, dict]]] = {}
        for e in edges:
            sr = int(e["shared_races"])
            sq = int(e["shared_quali"])
            if max(sr, sq) < threshold:
                continue
            a = int(e["driver_a_id"])
            b = int(e["driver_b_id"])
            seasons = json.loads(e["seasons_json"])
            teams = json.loads(e["teams_json"])
            q_del = e["median_quali_delta_pct"]
            p_del = e["median_pace_delta_pct"]

            adj.setdefault(a, []).append(
                (
                    b,
                    {
                        "from": drivers[a],
                        "to": drivers[b],
                        "shared_races": sr,
                        "shared_quali": sq,
                        "seasons": seasons,
                        "teams": teams,
                        "quali_delta_pct": round(float(q_del), 3) if q_del is not None else None,
                        "pace_delta_pct": round(float(p_del), 3) if p_del is not None else None,
                        "quali_wins_from": int(e["quali_wins_a"]),
                        "quali_wins_to": int(e["quali_wins_b"]),
                        "race_wins_from": int(e["race_wins_a"]),
                        "race_wins_to": int(e["race_wins_b"]),
                    },
                )
            )
            adj.setdefault(b, []).append(
                (
                    a,
                    {
                        "from": drivers[b],
                        "to": drivers[a],
                        "shared_races": sr,
                        "shared_quali": sq,
                        "seasons": seasons,
                        "teams": teams,
                        "quali_delta_pct": round(float(-q_del), 3) if q_del is not None else None,
                        "pace_delta_pct": round(float(-p_del), 3) if p_del is not None else None,
                        "quali_wins_from": int(e["quali_wins_b"]),
                        "quali_wins_to": int(e["quali_wins_a"]),
                        "race_wins_from": int(e["race_wins_b"]),
                        "race_wins_to": int(e["race_wins_a"]),
                    },
                )
            )

        # Sort neighbors by shared_races descending so BFS picks most reliable teammate links
        for k in adj:
            adj[k].sort(key=lambda item: item[1]["shared_races"], reverse=True)

        visited = {src_id}
        parent: dict[int, tuple[int, dict]] = {}
        queue = deque([src_id])
        found = False
        while queue:
            cur = queue.popleft()
            if cur == dst_id:
                found = True
                break
            for nxt, hop in adj.get(cur, []):
                if nxt not in visited:
                    visited.add(nxt)
                    parent[nxt] = (cur, hop)
                    queue.append(nxt)

        if found:
            path: list[dict] = []
            cur = dst_id
            while cur != src_id:
                prev, hop = parent[cur]
                path.append(hop)
                cur = prev
            path.reverse()
            return path

    return []


@router.get("/health")
def health_check() -> dict[str, Any]:
    conn = _get_db()
    try:
        drv_cnt = int(conn.execute("SELECT COUNT(*) FROM driver_alltime_ratings").fetchone()[0])
        round_cnt = int(conn.execute("SELECT COUNT(DISTINCT round_id) FROM race_driver_metrics").fetchone()[0])
        lap_cnt = int(conn.execute("SELECT COUNT(*) FROM laps").fetchone()[0])
        diag_row = conn.execute("SELECT value_json FROM model_diagnostics WHERE key = 'last_updated'").fetchone()
        last_updated = json.loads(diag_row["value_json"]) if diag_row else None
        return {
            "status": "ok",
            "drivers_rated": drv_cnt,
            "rounds_analyzed": round_cnt,
            "raw_laps": lap_cnt,
            "last_updated": last_updated,
        }
    finally:
        conn.close()


@router.get("/drivers")
def list_all_drivers(q: str = Query("", max_length=80)) -> dict[str, Any]:
    conn = _get_db()
    try:
        sql = """
            SELECT
                d.id AS driver_id, d.reference, d.abbreviation,
                d.forename || ' ' || d.surname AS name,
                d.nationality, d.country_code,
                a.overall, a.overall_raw, a.career_starts, a.career_wins, a.championships,
                a.first_year, a.last_year, a.primary_team_name, a.primary_team_color
            FROM driver_alltime_ratings a
            JOIN drivers d ON d.id = a.driver_id
        """
        params: list[Any] = []
        if q.strip():
            like = f"%{q.strip()}%"
            sql += " WHERE (d.forename || ' ' || d.surname) LIKE ? OR d.reference LIKE ? OR COALESCE(d.abbreviation, '') LIKE ?"
            params.extend([like, like, like])
        sql += " ORDER BY a.overall_raw DESC, a.career_starts DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return {"drivers": rows, "total": len(rows)}
    finally:
        conn.close()


@router.get("/seasons")
def list_seasons() -> dict[str, Any]:
    conn = _get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                sr.year,
                COUNT(*) AS driver_count,
                MAX(sr.overall_raw) AS top_overall_raw
            FROM driver_season_ratings sr
            WHERE sr.mode = 'season'
            GROUP BY sr.year
            ORDER BY sr.year DESC
            """
        ).fetchall()

        top_drivers = {}
        for r in conn.execute(
            """
            SELECT sr.year, d.reference, d.forename || ' ' || d.surname AS name, sr.overall, sr.team_name, sr.team_color
            FROM driver_season_ratings sr
            JOIN drivers d ON d.id = sr.driver_id
            WHERE sr.mode = 'season'
            ORDER BY sr.year DESC, sr.overall_raw DESC
            """
        ).fetchall():
            yr = int(r["year"])
            if yr not in top_drivers:
                top_drivers[yr] = dict(r)

        out = []
        for r in rows:
            yr = int(r["year"])
            top = top_drivers.get(yr, {})
            out.append(
                {
                    "year": yr,
                    "driver_count": int(r["driver_count"]),
                    "top_driver_name": top.get("name"),
                    "top_driver_ref": top.get("reference"),
                    "top_driver_overall": top.get("overall"),
                    "top_team_name": top.get("team_name"),
                    "top_team_color": top.get("team_color"),
                }
            )
        return {"seasons": out}
    finally:
        conn.close()


@router.get("/rankings/current")
def get_current_rankings() -> dict[str, Any]:
    conn = _get_db()
    try:
        max_yr_row = conn.execute(
            "SELECT MAX(year) FROM driver_season_ratings WHERE mode = 'rolling_current'"
        ).fetchone()
        if not max_yr_row or not max_yr_row[0]:
            raise HTTPException(status_code=404, detail="No current grid ratings computed")
        year = int(max_yr_row[0])
        return _fetch_season_rankings(conn, year, mode="rolling_current")
    finally:
        conn.close()


@router.get("/rankings/season/{year}")
def get_season_rankings(year: int) -> dict[str, Any]:
    conn = _get_db()
    try:
        res = _fetch_season_rankings(conn, year, mode="season")
        if not res["drivers"]:
            raise HTTPException(status_code=404, detail=f"No data for season {year}")
        return res
    finally:
        conn.close()


def _fetch_season_rankings(conn: sqlite3.Connection, year: int, mode: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT
            sr.*,
            d.reference, d.abbreviation, d.forename, d.surname,
            d.forename || ' ' || d.surname AS name,
            d.nationality, d.country_code, d.permanent_car_number
        FROM driver_season_ratings sr
        JOIN drivers d ON d.id = sr.driver_id
        WHERE sr.year = ? AND sr.mode = ?
        ORDER BY sr.overall_raw DESC, sr.races_count DESC
        """,
        (year, mode),
    ).fetchall()

    drivers = []
    for idx, r in enumerate(rows, start=1):
        item = _parse_badges(dict(r))
        item["rank"] = idx
        item["car_delta"] = round(float(item["overall_raw"]) - float(item["car_rating"]), 2)
        drivers.append(item)

    cars = [
        dict(c)
        for c in conn.execute(
            """
            SELECT year, team_id, team_name, team_color, car_rating, pace_car_pct, quali_car_pct
            FROM car_season_ratings
            WHERE year = ?
            ORDER BY car_rating DESC
            """,
            (year,),
        ).fetchall()
    ]

    rounds_done = int(
        conn.execute(
            "SELECT COUNT(DISTINCT round_id) FROM race_driver_metrics WHERE year = ?",
            (year,),
        ).fetchone()[0]
    )

    return {
        "year": year,
        "mode": mode,
        "rounds_analyzed": rounds_done,
        "drivers": drivers,
        "cars": cars,
    }


@router.get("/rankings/alltime")
def get_alltime_rankings(
    decade: int | None = Query(None, ge=1950, le=2020),
    min_starts: int = Query(0, ge=0, le=400),
    nationality: str | None = Query(None),
    champions_only: bool = Query(False),
    search: str = Query("", max_length=80),
    sort_by: str = Query(
        "overall_raw",
        pattern="^(overall_raw|peak_overall|longevity_overall|pace_ovr|quali_ovr|consistency_ovr|racecraft_ovr|experience_ovr|career_starts|career_wins)$",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conn = _get_db()
    try:
        where = ["a.career_starts >= ?"]
        params: list[Any] = [min_starts]

        if decade is not None:
            where.append("a.first_year <= ? AND a.last_year >= ?")
            params.extend([decade + 9, decade])
        if nationality:
            where.append("d.nationality = ?")
            params.append(nationality)
        if champions_only:
            where.append("a.championships > 0")
        if search.strip():
            like = f"%{search.strip()}%"
            where.append(
                "((d.forename || ' ' || d.surname) LIKE ? OR d.reference LIKE ? OR a.primary_team_name LIKE ?)"
            )
            params.extend([like, like, like])

        where_sql = " AND ".join(where)
        total = int(
            conn.execute(
                f"SELECT COUNT(*) FROM driver_alltime_ratings a JOIN drivers d ON d.id = a.driver_id WHERE {where_sql}",
                params,
            ).fetchone()[0]
        )

        # Fetch ordered slice
        rows = conn.execute(
            f"""
            SELECT
                a.*,
                d.reference, d.abbreviation, d.forename, d.surname,
                d.forename || ' ' || d.surname AS name,
                d.nationality, d.country_code, d.permanent_car_number
            FROM driver_alltime_ratings a
            JOIN drivers d ON d.id = a.driver_id
            WHERE {where_sql}
            ORDER BY a.{sort_by} DESC, a.career_wins DESC, a.career_starts DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

        drivers = []
        for idx, r in enumerate(rows, start=offset + 1):
            item = _parse_badges(dict(r))
            item["rank"] = idx
            drivers.append(item)

        nationalities = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT nationality FROM drivers WHERE nationality IS NOT NULL ORDER BY nationality"
            ).fetchall()
        ]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "drivers": drivers,
            "nationalities": nationalities,
        }
    finally:
        conn.close()


@router.get("/drivers/{driver_ref}")
def get_driver_profile(driver_ref: str) -> dict[str, Any]:
    conn = _get_db()
    try:
        drv = conn.execute(
            """
            SELECT
                d.*, d.forename || ' ' || d.surname AS name,
                a.*
            FROM drivers d
            JOIN driver_alltime_ratings a ON a.driver_id = d.id
            WHERE d.reference = ?
            """,
            (driver_ref,),
        ).fetchone()
        if not drv:
            raise HTTPException(status_code=404, detail=f"Driver '{driver_ref}' not found")

        did = int(drv["driver_id"])
        # Global All-Time Rank
        alltime_rank = int(
            conn.execute(
                """
                SELECT COUNT(*) + 1
                FROM driver_alltime_ratings
                WHERE overall_raw > ? OR (overall_raw = ? AND career_wins > ?)
                """,
                (drv["overall_raw"], drv["overall_raw"], drv["career_wins"]),
            ).fetchone()[0]
        )

        current_rating = conn.execute(
            """
            SELECT * FROM driver_season_ratings
            WHERE driver_id = ? AND mode = 'rolling_current'
            ORDER BY year DESC LIMIT 1
            """,
            (did,),
        ).fetchone()

        seasons = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM driver_season_ratings
                WHERE driver_id = ? AND mode = 'season'
                ORDER BY year ASC
                """,
                (did,),
            ).fetchall()
        ]

        # Teammates from network edges
        edge_rows = conn.execute(
            """
            SELECT
                e.*,
                da.reference AS ref_a, da.forename || ' ' || da.surname AS name_a, oa.overall AS ovr_a, oa.primary_team_color AS color_a,
                db.reference AS ref_b, db.forename || ' ' || db.surname AS name_b, ob.overall AS ovr_b, ob.primary_team_color AS color_b
            FROM teammate_network_edges e
            JOIN drivers da ON da.id = e.driver_a_id
            JOIN drivers db ON db.id = e.driver_b_id
            JOIN driver_alltime_ratings oa ON oa.driver_id = e.driver_a_id
            JOIN driver_alltime_ratings ob ON ob.driver_id = e.driver_b_id
            WHERE e.driver_a_id = ? OR e.driver_b_id = ?
            ORDER BY e.shared_races DESC
            """,
            (did, did),
        ).fetchall()

        teammates = []
        for e in edge_rows:
            is_a = int(e["driver_a_id"]) == did
            q_del = e["median_quali_delta_pct"]
            p_del = e["median_pace_delta_pct"]
            teammates.append(
                {
                    "teammate_id": int(e["driver_b_id"] if is_a else e["driver_a_id"]),
                    "teammate_ref": e["ref_b"] if is_a else e["ref_a"],
                    "teammate_name": e["name_b"] if is_a else e["name_a"],
                    "teammate_overall": int(e["ovr_b"] if is_a else e["ovr_a"]),
                    "shared_races": int(e["shared_races"]),
                    "shared_quali": int(e["shared_quali"]),
                    "seasons": json.loads(e["seasons_json"]),
                    "teams": json.loads(e["teams_json"]),
                    "quali_delta_pct": round(float(q_del if is_a else -q_del), 3) if q_del is not None else None,
                    "pace_delta_pct": round(float(p_del if is_a else -p_del), 3) if p_del is not None else None,
                    "quali_wins": int(e["quali_wins_a"] if is_a else e["quali_wins_b"]),
                    "quali_losses": int(e["quali_wins_b"] if is_a else e["quali_wins_a"]),
                    "race_wins": int(e["race_wins_a"] if is_a else e["race_wins_b"]),
                    "race_losses": int(e["race_wins_b"] if is_a else e["race_wins_a"]),
                }
            )

        # Hygiene breakdown & recent races
        hygiene_counts = {
            r["status_category"]: int(r["cnt"])
            for r in conn.execute(
                """
                SELECT status_category, COUNT(*) AS cnt
                FROM race_driver_metrics
                WHERE driver_id = ?
                GROUP BY status_category
                """,
                (did,),
            ).fetchall()
        }

        recent_races = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                    m.round_id, m.year, m.round_number, m.round_name, m.round_date,
                    m.circuit_type, m.is_wet_race, m.weekend_score,
                    t.name AS team_name, t.primary_color AS team_color,
                    m.grid, m.finish_pos, m.status_category, m.fia_driving_penalties,
                    m.quali_session_used, m.quali_teammate_delta_pct,
                    m.clean_air_laps, m.clean_laps_total, m.pace_teammate_delta_pct,
                    m.lap1_net_gain, m.on_track_overtakes, m.on_track_overtaken,
                    m.data_tier
                FROM race_driver_metrics m
                JOIN teams t ON t.id = m.team_id
                WHERE m.driver_id = ?
                ORDER BY m.year DESC, m.round_number DESC
                LIMIT 25
                """,
                (did,),
            ).fetchall()
        ]

        return {
            "driver": _parse_badges({**dict(drv), "alltime_rank": alltime_rank}),
            "current_rating": _parse_badges(dict(current_rating)) if current_rating else None,
            "seasons": [_parse_badges(s) for s in seasons],
            "teammates": teammates,
            "hygiene_summary": {
                "clean_finishes": hygiene_counts.get("CLEAN_FINISH", 0),
                "mechanical_dnfs_excluded": hygiene_counts.get("MECHANICAL_DNF", 0),
                "driver_error_dnfs": hygiene_counts.get("DRIVER_ERROR", 0),
                "dns_excluded": hygiene_counts.get("DNS_OTHER", 0),
                "fia_penalties_count": int(drv["fia_penalties_count"]),
                "clean_air_laps_total": int(drv["clean_air_laps_total"]),
            },
            "recent_races": recent_races,
        }
    finally:
        conn.close()


@router.get("/compare")
def compare_drivers(
    driver_a: str = Query(...),
    driver_b: str = Query(...),
    mode: str = Query("alltime", pattern="^(alltime|current|season)$"),
    year: int | None = Query(None),
) -> dict[str, Any]:
    conn = _get_db()
    try:
        def _load_one(ref: str) -> dict[str, Any]:
            base = conn.execute(
                """
                SELECT d.*, d.forename || ' ' || d.surname AS name, a.*
                FROM drivers d
                JOIN driver_alltime_ratings a ON a.driver_id = d.id
                WHERE d.reference = ?
                """,
                (ref,),
            ).fetchone()
            if not base:
                raise HTTPException(status_code=404, detail=f"Driver '{ref}' not found")
            d_dict = dict(base)
            did = int(base["driver_id"])
            if mode in ("current", "season"):
                target_mode = "rolling_current" if mode == "current" else "season"
                sql = "SELECT * FROM driver_season_ratings WHERE driver_id = ? AND mode = ?"
                params: list[Any] = [did, target_mode]
                if year is not None:
                    sql += " AND year = ?"
                    params.append(year)
                else:
                    sql += " ORDER BY year DESC LIMIT 1"
                sr = conn.execute(sql, params).fetchone()
                if sr:
                    d_dict["active_rating"] = _parse_badges(dict(sr))
                else:
                    d_dict["active_rating"] = None
            else:
                d_dict["active_rating"] = {
                    "overall": d_dict["overall"],
                    "overall_raw": d_dict["overall_raw"],
                    "overall_ci": d_dict.get("overall_ci", 1.5),
                    "pace_ovr": d_dict["pace_ovr"],
                    "quali_ovr": d_dict["quali_ovr"],
                    "consistency_ovr": d_dict["consistency_ovr"],
                    "racecraft_ovr": d_dict["racecraft_ovr"],
                    "experience_ovr": d_dict["experience_ovr"],
                    "wet_ovr": d_dict.get("wet_ovr", 82.0),
                    "street_ovr": d_dict.get("street_ovr", 82.0),
                    "high_speed_ovr": d_dict.get("high_speed_ovr", 82.0),
                    "tyre_mgmt_ovr": d_dict.get("tyre_mgmt_ovr", 82.0),
                    "badges": _parse_badges(d_dict)["badges"],
                    "team_name": d_dict["primary_team_name"],
                    "team_color": d_dict["primary_team_color"],
                }
            return _parse_badges(d_dict)

        da = _load_one(driver_a)
        db = _load_one(driver_b)

        id_a = int(da["driver_id"])
        id_b = int(db["driver_id"])
        lo, hi = min(id_a, id_b), max(id_a, id_b)
        direct_edge = conn.execute(
            "SELECT * FROM teammate_network_edges WHERE driver_a_id = ? AND driver_b_id = ?",
            (lo, hi),
        ).fetchone()

        direct_summary = None
        if direct_edge:
            a_is_lo = id_a == lo
            q_del = direct_edge["median_quali_delta_pct"]
            p_del = direct_edge["median_pace_delta_pct"]
            direct_summary = {
                "shared_races": int(direct_edge["shared_races"]),
                "shared_quali": int(direct_edge["shared_quali"]),
                "seasons": json.loads(direct_edge["seasons_json"]),
                "teams": json.loads(direct_edge["teams_json"]),
                "quali_delta_a_vs_b_pct": round(float(q_del if a_is_lo else -q_del), 3) if q_del is not None else None,
                "pace_delta_a_vs_b_pct": round(float(p_del if a_is_lo else -p_del), 3) if p_del is not None else None,
                "quali_wins_a": int(direct_edge["quali_wins_a"] if a_is_lo else direct_edge["quali_wins_b"]),
                "quali_wins_b": int(direct_edge["quali_wins_b"] if a_is_lo else direct_edge["quali_wins_a"]),
                "race_wins_a": int(direct_edge["race_wins_a"] if a_is_lo else direct_edge["race_wins_b"]),
                "race_wins_b": int(direct_edge["race_wins_b"] if a_is_lo else direct_edge["race_wins_a"]),
            }

        path = _bfs_teammate_path(conn, id_a, id_b)
        return {
            "mode": mode,
            "driver_a": da,
            "driver_b": db,
            "direct_teammates": direct_summary,
            "calibration_path": path,
        }
    finally:
        conn.close()


@router.get("/network")
def get_teammate_network(
    center_driver: str | None = Query(None),
    decade: int | None = Query(None, ge=1950, le=2020),
    min_shared_races: int = Query(5, ge=1, le=100),
    path_from: str | None = Query(None),
    path_to: str | None = Query(None),
    max_nodes: int = Query(75, ge=10, le=200),
) -> dict[str, Any]:
    conn = _get_db()
    try:
        all_drivers = {
            int(r["driver_id"]): dict(r)
            for r in conn.execute(
                """
                SELECT
                    a.driver_id, d.reference, d.abbreviation,
                    d.forename || ' ' || d.surname AS name,
                    a.overall, a.overall_raw, a.career_starts, a.career_wins,
                    a.championships, a.first_year, a.last_year,
                    a.primary_team_name AS team_name, a.primary_team_color AS team_color
                FROM driver_alltime_ratings a
                JOIN drivers d ON d.id = a.driver_id
                """
            ).fetchall()
        }
        ref_to_id = {v["reference"]: k for k, v in all_drivers.items()}
        raw_edges = [dict(r) for r in conn.execute("SELECT * FROM teammate_network_edges").fetchall()]

        shortest_path: list[dict] = []
        path_node_ids: set[int] = set()
        if path_from and path_to and path_from in ref_to_id and path_to in ref_to_id:
            shortest_path = _bfs_teammate_path(conn, ref_to_id[path_from], ref_to_id[path_to], min_shared_races=1)
            for hop in shortest_path:
                path_node_ids.add(hop["from"]["driver_id"])
                path_node_ids.add(hop["to"]["driver_id"])

        selected_ids: set[int] = set(path_node_ids)

        if center_driver and center_driver in ref_to_id:
            cid = ref_to_id[center_driver]
            selected_ids.add(cid)
            hop1: set[int] = set()
            for e in raw_edges:
                if max(e["shared_races"], e["shared_quali"]) < min_shared_races:
                    continue
                a, b = int(e["driver_a_id"]), int(e["driver_b_id"])
                if a == cid:
                    hop1.add(b)
                elif b == cid:
                    hop1.add(a)
            selected_ids |= hop1
            # Add top 2-hop neighbors up to max_nodes
            hop2_candidates: list[tuple[int, int]] = []
            for e in raw_edges:
                if max(e["shared_races"], e["shared_quali"]) < min_shared_races:
                    continue
                a, b = int(e["driver_a_id"]), int(e["driver_b_id"])
                if a in hop1 and b not in selected_ids:
                    hop2_candidates.append((b, all_drivers[b]["overall"] + e["shared_races"]))
                elif b in hop1 and a not in selected_ids:
                    hop2_candidates.append((a, all_drivers[a]["overall"] + e["shared_races"]))
            hop2_candidates.sort(key=lambda x: x[1], reverse=True)
            for did, _ in hop2_candidates:
                if len(selected_ids) >= max_nodes:
                    break
                selected_ids.add(did)
        else:
            # Filter by decade (or top overall drivers across F1 history)
            candidates = []
            for did, info in all_drivers.items():
                if decade is not None:
                    if not (info["first_year"] <= decade + 9 and info["last_year"] >= decade):
                        continue
                if info["career_starts"] < 15 and did not in path_node_ids:
                    continue
                candidates.append((did, info["overall_raw"] + 0.03 * min(info["career_starts"], 200)))
            candidates.sort(key=lambda x: x[1], reverse=True)
            for did, _ in candidates[:max_nodes]:
                selected_ids.add(did)

        nodes = [all_drivers[did] for did in sorted(selected_ids) if did in all_drivers]
        edges_out = []
        for e in raw_edges:
            a, b = int(e["driver_a_id"]), int(e["driver_b_id"])
            if a not in selected_ids or b not in selected_ids:
                continue
            in_path = (a in path_node_ids and b in path_node_ids)
            if not in_path and max(e["shared_races"], e["shared_quali"]) < min_shared_races:
                continue
            edges_out.append(
                {
                    "source": a,
                    "target": b,
                    "shared_races": int(e["shared_races"]),
                    "shared_quali": int(e["shared_quali"]),
                    "seasons": json.loads(e["seasons_json"]),
                    "teams": json.loads(e["teams_json"]),
                    "median_quali_delta_pct": round(float(e["median_quali_delta_pct"]), 3)
                    if e["median_quali_delta_pct"] is not None
                    else None,
                    "median_pace_delta_pct": round(float(e["median_pace_delta_pct"]), 3)
                    if e["median_pace_delta_pct"] is not None
                    else None,
                    "in_shortest_path": in_path,
                }
            )

        return {
            "nodes": nodes,
            "edges": edges_out,
            "shortest_path": shortest_path,
        }
    finally:
        conn.close()


@router.post("/simulate")
def simulate_ratings(payload: SimulateRequest, request: Request) -> dict[str, Any]:
    sim = request.app.state.simulator
    if not sim.loaded:
        conn = _get_db()
        try:
            sim.reload_from_db(conn)
        finally:
            conn.close()

    return sim.simulate(
        scope=payload.scope,
        year=payload.year,
        weights=payload.weights.model_dump(),
        shrinkage_m=payload.shrinkage_m,
        half_life_races=payload.half_life_races,
        base_ovr=payload.base_ovr,
        scale_factor=payload.scale_factor,
        min_starts=payload.min_starts,
        limit=payload.limit,
    )


@router.get("/diagnostics")
def get_model_diagnostics() -> dict[str, Any]:
    conn = _get_db()
    try:
        rows = conn.execute("SELECT key, value_json FROM model_diagnostics").fetchall()
        return {r["key"]: json.loads(r["value_json"]) for r in rows}
    finally:
        conn.close()


@router.get("/races/{year}")
def get_season_races(year: int) -> dict[str, Any]:
    conn = _get_db()
    try:
        rounds = conn.execute(
            """
            SELECT r.id AS round_id, r.number AS round_number, r.name, r.date,
                   c.name AS circuit_name, c.country, c.locality
            FROM rounds r
            JOIN seasons s ON s.id = r.season_id
            LEFT JOIN circuits c ON c.id = r.circuit_id
            WHERE s.year = ? AND r.is_cancelled = 0
              AND EXISTS (SELECT 1 FROM race_driver_metrics m WHERE m.round_id = r.id)
            ORDER BY r.number ASC
            """,
            (year,),
        ).fetchall()
        if not rounds:
            raise HTTPException(status_code=404, detail=f"No races found for season {year}")

        metrics = conn.execute(
            """
            SELECT m.round_id, m.driver_id, m.finish_pos, m.weekend_score, m.circuit_type, m.is_wet_race,
                   d.reference, d.forename || ' ' || d.surname AS name,
                   t.name AS team_name, t.primary_color AS team_color
            FROM race_driver_metrics m
            JOIN drivers d ON d.id = m.driver_id
            JOIN teams t ON t.id = m.team_id
            WHERE m.year = ?
            """,
            (year,),
        ).fetchall()

        by_rnd: dict[int, list[dict]] = {}
        for m in metrics:
            by_rnd.setdefault(int(m["round_id"]), []).append(dict(m))

        out = []
        for rnd in rounds:
            rid = int(rnd["round_id"])
            rows = by_rnd.get(rid, [])
            winner = next((x for x in rows if x["finish_pos"] == 1), None)
            dotw = max(rows, key=lambda x: float(x["weekend_score"] or 0.0), default=None)
            sample = rows[0] if rows else {}
            out.append(
                {
                    "round_id": rid,
                    "round_number": int(rnd["round_number"]),
                    "name": rnd["name"],
                    "date": rnd["date"],
                    "circuit_name": rnd["circuit_name"],
                    "country": rnd["country"],
                    "locality": rnd["locality"],
                    "circuit_type": sample.get("circuit_type", "TECHNICAL"),
                    "is_wet_race": bool(sample.get("is_wet_race", 0)),
                    "winner_name": winner["name"] if winner else None,
                    "winner_ref": winner["reference"] if winner else None,
                    "winner_team_color": winner["team_color"] if winner else None,
                    "dotw_name": dotw["name"] if dotw else None,
                    "dotw_ref": dotw["reference"] if dotw else None,
                    "dotw_score": dotw["weekend_score"] if dotw else None,
                }
            )
        return {"year": year, "races": out}
    finally:
        conn.close()


@router.get("/races/{year}/{round_number}")
def get_race_xray(year: int, round_number: int) -> dict[str, Any]:
    conn = _get_db()
    try:
        rnd = conn.execute(
            """
            SELECT r.id AS round_id, r.number AS round_number, r.name, r.date,
                   c.name AS circuit_name, c.country, c.locality
            FROM rounds r
            JOIN seasons s ON s.id = r.season_id
            LEFT JOIN circuits c ON c.id = r.circuit_id
            WHERE s.year = ? AND r.number = ? AND r.is_cancelled = 0
            """,
            (year, round_number),
        ).fetchone()
        if not rnd:
            raise HTTPException(status_code=404, detail=f"Round {year} R{round_number} not found")
        rid = int(rnd["round_id"])

        drivers = [
            dict(r)
            for r in conn.execute(
                """
                SELECT m.*, d.reference, d.abbreviation, d.forename || ' ' || d.surname AS name,
                       d.country_code, d.nationality,
                       t.name AS team_name, t.primary_color AS team_color
                FROM race_driver_metrics m
                JOIN drivers d ON d.id = m.driver_id
                JOIN teams t ON t.id = m.team_id
                WHERE m.round_id = ?
                ORDER BY m.weekend_score DESC, COALESCE(m.finish_pos, 99) ASC
                """,
                (rid,),
            ).fetchall()
        ]
        if not drivers:
            raise HTTPException(status_code=404, detail=f"No computed race metrics for {year} R{round_number}")

        neutralizations = [
            dict(r)
            for r in conn.execute(
                "SELECT lap_start, lap_end, status_type, source FROM track_neutralizations WHERE round_id = ? ORDER BY lap_start",
                (rid,),
            ).fetchall()
        ]

        stints = [
            dict(r)
            for r in conn.execute(
                """
                SELECT s.driver_id, d.reference, d.abbreviation, d.forename || ' ' || d.surname AS name,
                       s.stint_number, s.lap_start, s.lap_end, s.compound, s.tyre_age_at_start, s.source
                FROM stint_enrichments s
                JOIN drivers d ON d.id = s.driver_id
                WHERE s.round_id = ?
                ORDER BY s.driver_id, s.stint_number
                """,
                (rid,),
            ).fetchall()
        ]

        # Lap-time distribution (clean green-flag laps per driver)
        lap_rows = conn.execute(
            """
            SELECT td.driver_id, l.time_sec
            FROM laps l
            JOIN session_entries se ON se.id = l.session_entry_id
            JOIN sessions ss ON ss.id = se.session_id
            JOIN round_entries re ON re.id = se.round_entry_id
            JOIN team_drivers td ON td.id = re.team_driver_id
            WHERE ss.round_id = ? AND ss.type = 'R' AND l.number >= 2 AND l.is_deleted = 0 AND l.time_sec BETWEEN 35 AND 400
            """,
            (rid,),
        ).fetchall()
        laps_by_d: dict[int, list[float]] = {}
        all_laps_flat: list[float] = []
        for lr in lap_rows:
            t = float(lr["time_sec"])
            laps_by_d.setdefault(int(lr["driver_id"]), []).append(t)
            all_laps_flat.append(t)

        lap_distributions = []
        if all_laps_flat:
            race_med = float(np.median(all_laps_flat))
            drv_lookup = {int(d["driver_id"]): d for d in drivers}
            for did, times in laps_by_d.items():
                clean_t = [t for t in times if 0.88 * race_med <= t <= 1.07 * race_med]
                if len(clean_t) < 3 or did not in drv_lookup:
                    continue
                arr = np.asarray(clean_t, dtype=float)
                dinfo = drv_lookup[did]
                lap_distributions.append(
                    {
                        "driver_id": did,
                        "reference": dinfo["reference"],
                        "abbreviation": dinfo["abbreviation"] or dinfo["name"].split()[-1][:3].upper(),
                        "name": dinfo["name"],
                        "team_color": dinfo["team_color"],
                        "laps_count": len(clean_t),
                        "min_sec": round(float(np.min(arr)), 3),
                        "q25_sec": round(float(np.percentile(arr, 25)), 3),
                        "median_sec": round(float(np.median(arr)), 3),
                        "q75_sec": round(float(np.percentile(arr, 75)), 3),
                        "max_sec": round(float(np.max(arr)), 3),
                    }
                )
            lap_distributions.sort(key=lambda x: x["median_sec"])

        sample = drivers[0]
        return {
            "round": {
                "round_id": rid,
                "year": year,
                "round_number": int(rnd["round_number"]),
                "name": rnd["name"],
                "date": rnd["date"],
                "circuit_name": rnd["circuit_name"],
                "country": rnd["country"],
                "locality": rnd["locality"],
                "circuit_type": sample.get("circuit_type", "TECHNICAL"),
                "is_wet_race": bool(sample.get("is_wet_race", 0)),
                "data_tier": sample.get("data_tier", "HISTORICAL_RESULT"),
            },
            "drivers": drivers,
            "neutralizations": neutralizations,
            "stints": stints,
            "lap_distributions": lap_distributions,
        }
    finally:
        conn.close()


@router.get("/teams")
def get_team_lineages() -> dict[str, Any]:
    conn = _get_db()
    try:
        return {"lineages": list_lineages(conn)}
    finally:
        conn.close()


@router.get("/teams/{slug}")
def get_team_lineage_detail(slug: str) -> dict[str, Any]:
    conn = _get_db()
    try:
        detail = get_lineage_detail(conn, slug)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Team lineage '{slug}' not found")
        return detail
    finally:
        conn.close()


@router.get("/counterfactual/season/{year}")
def get_equal_machinery_championship(
    year: int,
    exclude_mechanical_dnfs: bool = Query(True),
) -> dict[str, Any]:
    conn = _get_db()
    try:
        res = simulate_equal_machinery_season(conn, year, exclude_mechanical_dnfs=exclude_mechanical_dnfs)
        if not res["standings"]:
            raise HTTPException(status_code=404, detail=f"No race data for season {year}")
        return res
    finally:
        conn.close()


@router.post("/counterfactual/seat-swap")
def post_seat_swap(payload: SeatSwapRequest) -> dict[str, Any]:
    conn = _get_db()
    try:
        return simulate_seat_swap(
            conn,
            driver_ref=payload.driver_ref,
            target_team_id=payload.target_team_id,
            year=payload.year,
            replace_driver_ref=payload.replace_driver_ref,
            n_sims=payload.n_sims,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


def _resolve_portrait(conn: sqlite3.Connection, driver_id: int, wiki_url: str | None) -> str:
    cached = conn.execute(
        "SELECT thumbnail_url FROM driver_portraits WHERE driver_id = ?", (driver_id,)
    ).fetchone()
    if cached is not None:
        return str(cached["thumbnail_url"])

    thumb = ""
    if wiki_url and "/wiki/" in wiki_url:
        title = unquote(wiki_url.split("/wiki/")[-1].split("#")[0]).strip()
        if title:
            try:
                resp = httpx.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                    headers={"User-Agent": USER_AGENT},
                    timeout=3.5,
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    thumb = str((resp.json().get("thumbnail") or {}).get("source") or "")
            except httpx.HTTPError:
                thumb = ""

    conn.execute(
        "INSERT OR REPLACE INTO driver_portraits (driver_id, thumbnail_url, updated_at) VALUES (?, ?, ?)",
        (driver_id, thumb, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return thumb


@router.get("/portraits/{driver_ref}")
def get_driver_portrait(driver_ref: str) -> dict[str, Any]:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, wikipedia FROM drivers WHERE reference = ?", (driver_ref,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Driver '{driver_ref}' not found")
        thumb = _resolve_portrait(conn, int(row["id"]), row["wikipedia"])
        return {"reference": driver_ref, "thumbnail_url": thumb or None}
    finally:
        conn.close()


@router.get("/portraits")
def get_driver_portraits_batch(refs: str = Query(..., max_length=1500)) -> dict[str, Any]:
    ref_list = [r.strip() for r in refs.split(",") if r.strip()][:25]
    if not ref_list:
        return {"portraits": {}}
    conn = _get_db()
    try:
        placeholders = ",".join("?" for _ in ref_list)
        rows = conn.execute(
            f"SELECT id, reference, wikipedia FROM drivers WHERE reference IN ({placeholders})",
            ref_list,
        ).fetchall()
        portraits: dict[str, str | None] = {}
        for r in rows:
            thumb = _resolve_portrait(conn, int(r["id"]), r["wikipedia"])
            portraits[r["reference"]] = thumb or None
        return {"portraits": portraits}
    finally:
        conn.close()


@router.post("/admin/sync")
def trigger_incremental_sync(request: Request) -> dict[str, Any]:
    conn = _get_db()
    try:
        max_yr = int(conn.execute("SELECT COALESCE(MAX(year), 2026) FROM seasons").fetchone()[0])
        inc = sync_missing_recent_rounds(conn, year=max_yr)
        of1 = enrich_from_openf1(conn, years=(max_yr,))
        diag = run_full_computation(conn)
        conn.commit()
        request.app.state.simulator.reload_from_db(conn)
        return {
            "status": "ok",
            "year": max_yr,
            "incremental": inc,
            "openf1": of1,
            "coverage": diag["coverage_stats"],
        }
    finally:
        conn.close()
