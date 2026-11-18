"""Full statistical pipeline: feature extraction, network calibration, Z-scoring, Bayesian shrinkage & 0-99 mapping."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np

from app.config import (
    DEFAULT_BASE_OVR,
    DEFAULT_BASELINE_Z,
    DEFAULT_HALF_LIFE_CURRENT,
    DEFAULT_HALF_LIFE_SEASON,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_SHRINKAGE_M,
    DEFAULT_WEIGHTS,
    MAX_OVR,
    MIN_OVR,
)
from app.db.schema import reset_computed_tables
from app.engine.hygiene import (
    classify_entry_status,
    filter_driver_clean_laps,
    identify_neutralized_laps,
)
from app.engine.network_lmm import age_effect, solve_network_lmm
from app.engine.pillars.consistency import compute_race_consistency_metrics
from app.engine.pillars.experience import compute_experience_score
from app.engine.pillars.qualifying import compute_qualifying_metrics
from app.engine.pillars.race_pace import (
    compute_cumulative_clocks_and_clean_air,
    compute_race_pace_metrics,
)
from app.engine.pillars.racecraft import (
    compute_raw_racecraft_events,
    finalize_racecraft_scores,
)


def _compute_age_years(dob: str | None, race_date: str | None, fallback_year: int) -> float | None:
    if not dob:
        return None
    try:
        dob_dt = datetime.strptime(dob[:10], "%Y-%m-%d")
        if race_date:
            ref_dt = datetime.strptime(race_date[:10], "%Y-%m-%d")
        else:
            ref_dt = datetime(fallback_year, 7, 1)
        return round((ref_dt - dob_dt).days / 365.25, 2)
    except ValueError:
        return None


def _winsorized_mean_std(values: np.ndarray, z_limit: float | None = 3.5) -> tuple[float, float]:
    """Compute robust population mean and std after optional winsorization."""
    arr = values[np.isfinite(values)]
    if arr.size == 0:
        return 0.0, 1.0
    if arr.size == 1:
        return float(arr[0]), 1.0
    if z_limit is None:
        sd = float(np.std(arr))
        return float(np.mean(arr)), (sd if sd > 1e-6 else 1.0)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med))) * 1.4826
    scale = mad if mad > 1e-6 else float(np.std(arr))
    if scale <= 1e-6:
        return float(np.mean(arr)), 1.0
    lo = med - z_limit * scale
    hi = med + z_limit * scale
    clipped = np.clip(arr, lo, hi)
    std = float(np.std(clipped))
    return float(np.mean(clipped)), (std if std > 1e-6 else 1.0)


def _shrink_and_standardize_pillar(
    obs_values: np.ndarray,
    eff_n: np.ndarray,
    ref_mask: np.ndarray,
    shrinkage_m: float,
    baseline_z: float,
    winsorize_z: float | None = 3.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply Bayesian shrinkage toward entry baseline and return (Z_scores, shrunk_values).

    Note: Missing observations (`isnan` or `eff_n == 0`) shrink 100% to `baseline_z`.
    """
    valid_ref = ref_mask & np.isfinite(obs_values) & (eff_n > 0)
    if np.sum(valid_ref) < 2:
        valid_ref = np.isfinite(obs_values) & (eff_n > 0)

    mu_ref, sd_ref = _winsorized_mean_std(obs_values[valid_ref], z_limit=winsorize_z)
    base_val = mu_ref + baseline_z * sd_ref

    safe_obs = np.where(np.isfinite(obs_values) & (eff_n > 0), obs_values, base_val)
    safe_n = np.where(np.isfinite(obs_values) & (eff_n > 0), np.maximum(eff_n, 0.0), 0.0)

    if shrinkage_m > 0:
        shrunk = (safe_n * safe_obs + shrinkage_m * base_val) / (safe_n + shrinkage_m)
    else:
        shrunk = safe_obs

    # Standardize across the active reference grid
    grid_vals = shrunk[ref_mask] if np.sum(ref_mask) >= 2 else shrunk
    mu_g, sd_g = _winsorized_mean_std(grid_vals, z_limit=winsorize_z)
    clip_lim = 4.0 if winsorize_z is not None else 6.0
    z_scores = np.clip((shrunk - mu_g) / sd_g, -clip_lim, clip_lim)
    return z_scores, shrunk


def _map_z_to_ovr(z: np.ndarray, base_ovr: float, scale_factor: float) -> np.ndarray:
    return np.clip(base_ovr + scale_factor * z, MIN_OVR, MAX_OVR)


def run_full_computation(conn: sqlite3.Connection) -> dict:
    """Extract all race metrics (1950-2026), calibrate LMM network, and persist ratings."""
    reset_computed_tables(conn)

    # 1. Load metadata lookup maps
    drivers_meta = {
        int(r["id"]): dict(r)
        for r in conn.execute("SELECT id, reference, forename, surname, date_of_birth FROM drivers").fetchall()
    }
    teams_meta = {
        int(r["id"]): dict(r)
        for r in conn.execute("SELECT id, name, primary_color FROM teams").fetchall()
    }

    # Count completed seasons so in-progress seasons don't award premature WDC titles
    max_season_year = int(conn.execute("SELECT COALESCE(MAX(year), 2026) FROM seasons").fetchone()[0])
    incomplete_years: set[int] = set()
    for srow in conn.execute(
        """
        SELECT s.year,
               COUNT(*) AS total_rnds,
               SUM(CASE WHEN EXISTS (
                   SELECT 1 FROM sessions ss JOIN session_entries se ON se.session_id = ss.id
                   WHERE ss.round_id = r.id AND ss.type = 'R'
               ) THEN 1 ELSE 0 END) AS raced_rnds
        FROM rounds r
        JOIN seasons s ON s.id = r.season_id
        WHERE r.is_cancelled = 0
        GROUP BY s.year
        """
    ).fetchall():
        if int(srow["year"]) >= max_season_year and int(srow["raced_rnds"]) < int(srow["total_rnds"]):
            incomplete_years.add(int(srow["year"]))

    # Championship count per driver
    champ_counts: dict[int, int] = {}
    for crow in conn.execute(
        """
        SELECT driver_id, year
        FROM driver_championships
        WHERE season_id > 0 AND position = 1
        """
    ).fetchall():
        yr = int(crow["year"])
        if yr not in incomplete_years:
            did = int(crow["driver_id"])
            champ_counts[did] = champ_counts.get(did, 0) + 1

    # Load OpenF1 penalties, stint enrichments, and neutralizations
    openf1_pen_map: dict[tuple[int, int], int] = {}
    for row in conn.execute("SELECT round_id, driver_id, penalty_count FROM openf1_penalties").fetchall():
        openf1_pen_map[(int(row["round_id"]), int(row["driver_id"]))] = int(row["penalty_count"])

    stint_enrich_map: dict[tuple[int, int], list[dict]] = {}
    for row in conn.execute(
        """
        SELECT round_id, driver_id, stint_number, lap_start, lap_end, compound, tyre_age_at_start, source
        FROM stint_enrichments
        ORDER BY CASE WHEN source = 'fastf1' THEN 0 ELSE 1 END, stint_number
        """
    ).fetchall():
        key = (int(row["round_id"]), int(row["driver_id"]))
        stint_enrich_map.setdefault(key, []).append(dict(row))

    neutralizations_map: dict[int, list[tuple[int, int]]] = {}
    for row in conn.execute("SELECT round_id, lap_start, lap_end FROM track_neutralizations").fetchall():
        neutralizations_map.setdefault(int(row["round_id"]), []).append(
            (int(row["lap_start"]), int(row["lap_end"]))
        )

    # Load Jolpica penalties map (earned_id -> count of driving penalties)
    jolpica_pen_map: dict[int, int] = {}
    for row in conn.execute(
        """
        SELECT earned_id, COUNT(*) AS cnt
        FROM penalties
        WHERE earned_id IS NOT NULL
          AND (COALESCE(license_points, 0) > 0 OR time_sec IS NOT NULL OR is_time_served_in_pit = 1)
        GROUP BY earned_id
        """
    ).fetchall():
        jolpica_pen_map[int(row["earned_id"])] = int(row["cnt"])

    # Load all non-cancelled rounds ordered chronologically
    rounds = conn.execute(
        """
        SELECT r.id, r.number, r.race_number, r.name, r.date, s.year
        FROM rounds r
        JOIN seasons s ON s.id = r.season_id
        WHERE r.is_cancelled = 0
        ORDER BY s.year ASC, r.number ASC
        """
    ).fetchall()

    # Load all session entries joined with driver & team
    raw_entries = conn.execute(
        """
        SELECT
            se.id AS se_id,
            se.session_id,
            ss.round_id,
            ss.type AS session_type,
            re.id AS round_entry_id,
            td.driver_id,
            td.team_id,
            se.position,
            se.is_classified,
            se.status,
            se.detail,
            se.points,
            se.grid,
            se.time_sec,
            se.laps_completed
        FROM session_entries se
        JOIN sessions ss ON ss.id = se.session_id
        JOIN round_entries re ON re.id = se.round_entry_id
        JOIN team_drivers td ON td.id = re.team_driver_id
        WHERE ss.is_cancelled = 0
        """
    ).fetchall()

    race_entries_by_round: dict[int, list[dict]] = {}
    quali_entries_by_round: dict[int, dict[str, dict[int, list[dict]]]] = {}
    se_to_round_driver: dict[int, tuple[int, int, str]] = {}

    for row in raw_entries:
        rid = int(row["round_id"])
        stype = row["session_type"]
        did = int(row["driver_id"])
        se_id = int(row["se_id"])
        se_to_round_driver[se_id] = (rid, did, stype)

        if stype == "R":
            race_entries_by_round.setdefault(rid, []).append(dict(row))
        elif stype in ("Q1", "Q2", "Q3", "QB", "QA", "QO"):
            quali_entries_by_round.setdefault(rid, {}).setdefault(stype, {}).setdefault(did, []).append(dict(row))

    # Load all laps efficiently (include historical qualifying laps where number IS NULL)
    laps_by_race_se: dict[int, list[tuple[int, int | None, float | None, int]]] = {}
    quali_min_lap_by_se: dict[int, float] = {}
    lap_id_to_se_num: dict[int, tuple[int, int]] = {}

    for lrow in conn.execute(
        "SELECT id, session_entry_id, number, position, time_sec, is_deleted FROM laps WHERE time_sec IS NOT NULL OR position IS NOT NULL"
    ).fetchall():
        se_id = int(lrow["session_entry_id"])
        meta = se_to_round_driver.get(se_id)
        if not meta:
            continue
        rid, did, stype = meta
        lnum = int(lrow["number"]) if lrow["number"] is not None else None
        tsec = float(lrow["time_sec"]) if lrow["time_sec"] is not None else None
        is_del = int(lrow["is_deleted"] or 0)
        if lnum is not None:
            lap_id_to_se_num[int(lrow["id"])] = (se_id, lnum)

        if stype == "R" and lnum is not None and lnum >= 1:
            laps_by_race_se.setdefault(se_id, []).append(
                (lnum, lrow["position"], tsec, is_del)
            )
        elif stype in ("Q1", "Q2", "Q3", "QB", "QA", "QO") and not is_del and tsec and tsec > 25.0:
            prev = quali_min_lap_by_se.get(se_id)
            if prev is None or tsec < prev:
                quali_min_lap_by_se[se_id] = tsec

    # Load pit_stops mapped to (session_entry_id -> set of pit_in_lap_numbers)
    pit_in_laps_by_se: dict[int, set[int]] = {}
    for prow in conn.execute("SELECT session_entry_id, lap_id FROM pit_stops WHERE lap_id IS NOT NULL").fetchall():
        se_id = int(prow["session_entry_id"])
        lap_info = lap_id_to_se_num.get(int(prow["lap_id"]))
        if lap_info:
            pit_in_laps_by_se.setdefault(se_id, set()).add(lap_info[1])

    # 2. Process every Round chronologically
    cumulative_starts: dict[int, int] = {}
    career_wins: dict[int, int] = {}
    career_podiums: dict[int, int] = {}
    all_race_metrics: list[dict] = []

    for rnd in rounds:
        rid = int(rnd["id"])
        year = int(rnd["year"])
        rname = rnd["name"]
        rdate = rnd["date"]
        rnum = int(rnd["number"] or 0)

        entries = race_entries_by_round.get(rid, [])
        if not entries:
            continue

        # Deduplicate rare double-entry shared drives (1950s) per driver per round (keep best classification/laps)
        by_drv_dedup: dict[int, dict] = {}
        for e in entries:
            did = int(e["driver_id"])
            existing = by_drv_dedup.get(did)
            if existing is None or (e.get("laps_completed") or 0) > (existing.get("laps_completed") or 0):
                by_drv_dedup[did] = e
        entries = list(by_drv_dedup.values())

        # Classify DNF statuses & FIA driving penalties
        driver_teams: dict[int, int] = {}
        for e in entries:
            did = int(e["driver_id"])
            driver_teams[did] = int(e["team_id"])
            se_id = int(e["se_id"])
            pen_cnt = jolpica_pen_map.get(se_id, 0) + openf1_pen_map.get((rid, did), 0)
            cat, fault = classify_entry_status(
                e["status"], e["detail"], e["is_classified"], has_driving_penalty=(pen_cnt > 0)
            )
            e["status_category"] = cat
            e["driver_fault_score"] = fault
            e["fia_driving_penalties"] = pen_cnt

            if cat != "DNS_OTHER":
                cumulative_starts[did] = cumulative_starts.get(did, 0) + 1
                if e.get("position") == 1:
                    career_wins[did] = career_wins.get(did, 0) + 1
                if e.get("position") in (1, 2, 3):
                    career_podiums[did] = career_podiums.get(did, 0) + 1

        # Gather race laps per driver
        laps_by_driver_full: dict[int, list[tuple[int, int | None, float | None]]] = {}
        raw_times_for_clock: dict[int, list[tuple[int, float]]] = {}
        laps_by_number_field: dict[int, list[float]] = {}
        explicit_pits_by_driver: dict[int, set[int]] = {}
        max_laps = 1

        for e in entries:
            did = int(e["driver_id"])
            se_id = int(e["se_id"])
            explicit_pits_by_driver[did] = pit_in_laps_by_se.get(se_id, set())
            raw_l = laps_by_race_se.get(se_id, [])
            if raw_l:
                clean_tups = []
                clock_tups = []
                for ln, pos, tsec, is_del in sorted(raw_l, key=lambda x: x[0]):
                    if ln > max_laps:
                        max_laps = ln
                    clean_tups.append((ln, pos, tsec))
                    if tsec is not None and tsec > 0:
                        clock_tups.append((ln, tsec))
                        if not is_del:
                            laps_by_number_field.setdefault(ln, []).append(tsec)
                laps_by_driver_full[did] = clean_tups
                raw_times_for_clock[did] = clock_tups

            if e.get("laps_completed") and e["laps_completed"] > max_laps:
                max_laps = int(e["laps_completed"])

        # Data hygiene: SC/VSC/rain neutralizations & pit laps
        neutralized_laps, field_medians, race_baseline = identify_neutralized_laps(
            laps_by_number_field, neutralizations_map.get(rid, [])
        )
        clean_laps_by_driver: dict[int, list[tuple[int, float, int, int]]] = {}
        all_pit_in_by_driver: dict[int, set[int]] = {}
        for e in entries:
            did = int(e["driver_id"])
            se_id = int(e["se_id"])
            dlaps = [
                (ln, tsec)
                for ln, _, tsec, is_del in sorted(laps_by_race_se.get(se_id, []), key=lambda x: x[0])
                if not is_del and tsec is not None
            ]
            claps, pit_ins = filter_driver_clean_laps(
                dlaps,
                explicit_pits_by_driver.get(did, set()),
                neutralized_laps,
                field_medians,
                race_baseline,
            )
            if claps:
                clean_laps_by_driver[did] = claps
            all_pit_in_by_driver[did] = pit_ins

        # Pillar 1: Clean-Air Race Pace
        clean_air_map, gap_ahead_map = compute_cumulative_clocks_and_clean_air(raw_times_for_clock)
        stint_enrich_round = {
            int(e["driver_id"]): stint_enrich_map.get((rid, int(e["driver_id"])), [])
            for e in entries
        }
        pace_metrics = compute_race_pace_metrics(
            entries, clean_laps_by_driver, clean_air_map, stint_enrich_round, max_laps
        )

        # Pillar 2: Qualifying (last equal valid session; support multiple QB sessions per round)
        quali_phases_raw = quali_entries_by_round.get(rid, {})
        quali_times_by_phase: dict[str, dict[int, float]] = {}
        for phase, qmap in quali_phases_raw.items():
            phase_times: dict[int, float] = {}
            for did, qentries in qmap.items():
                best_t: float | None = None
                for qentry in qentries:
                    tsec = qentry.get("time_sec") or quali_min_lap_by_se.get(int(qentry["se_id"]))
                    if tsec and tsec > 25.0 and (best_t is None or float(tsec) < best_t):
                        best_t = float(tsec)
                if best_t is not None:
                    phase_times[did] = best_t
            if phase_times:
                quali_times_by_phase[phase] = phase_times
        quali_metrics = compute_qualifying_metrics(
            quali_times_by_phase,
            driver_teams,
            driver_grids={int(e["driver_id"]): e.get("grid") for e in entries},
        )

        # Pillar 3: Consistency
        cons_metrics = compute_race_consistency_metrics(entries, pace_metrics)

        # Pillar 4: Raw Racecraft events
        rc_events = compute_raw_racecraft_events(
            entries, laps_by_driver_full, all_pit_in_by_driver, neutralized_laps, gap_ahead_map
        )

        has_openf1_or_ff1 = any(bool(v) for v in stint_enrich_round.values())
        has_lap_data = any(pm["clean_laps_total"] > 0 for pm in pace_metrics.values())
        tier = (
            "TELEMETRY_COMPOUND"
            if has_openf1_or_ff1
            else ("LAP_BY_LAP" if has_lap_data else "HISTORICAL_RESULT")
        )

        is_indy_500 = (rname == "Indianapolis 500" and 1950 <= year <= 1960)

        for e in entries:
            did = int(e["driver_id"])
            tid = int(e["team_id"])
            pm = pace_metrics[did]
            qm = quali_metrics[did]
            cm = cons_metrics[did]
            rm = rc_events[did]
            dmeta = drivers_meta[did]

            all_race_metrics.append(
                {
                    "round_id": rid,
                    "driver_id": did,
                    "team_id": tid,
                    "year": year,
                    "round_number": rnum,
                    "round_name": rname,
                    "round_date": rdate,
                    "is_indy_500": is_indy_500,
                    "grid": e.get("grid"),
                    "effective_grid": rm["effective_grid"],
                    "finish_pos": e.get("position"),
                    "points": e.get("points") or 0.0,
                    "status_category": e["status_category"],
                    "driver_fault_score": e["driver_fault_score"],
                    "fia_driving_penalties": e["fia_driving_penalties"],
                    "quali_session_used": qm["quali_session_used"],
                    "quali_teammate_delta_pct": qm["quali_teammate_delta_pct"],
                    "quali_perf_pct": qm["quali_perf_pct"],
                    "clean_air_laps": pm["clean_air_laps"],
                    "clean_laps_total": pm["clean_laps_total"],
                    "pace_residual_pct": pm["pace_residual_pct"],
                    "stint_deg_bonus_pct": pm["stint_deg_bonus_pct"],
                    "pace_teammate_delta_pct": pm["pace_teammate_delta_pct"],
                    "pace_sample_weight": pm["pace_sample_weight"],
                    "stint_mad_pct": cm["stint_mad_pct"],
                    "incident_cost": cm["incident_cost"],
                    "consistency_variance_score": cm["consistency_variance_score"],
                    "lap1_pos": rm["lap1_pos"],
                    "raw_lap1_gain": rm["raw_lap1_gain"],
                    "lap1_net_gain": None,
                    "on_track_overtakes": rm["on_track_overtakes"],
                    "on_track_overtaken": rm["on_track_overtaken"],
                    "defense_laps": rm["defense_laps"],
                    "has_lap_positions": rm["has_lap_positions"],
                    "surv_q": rm.get("surv_q"),
                    "surv_gain": rm.get("surv_gain"),
                    "racecraft_score": None,
                    "cumulative_starts": cumulative_starts.get(did, 1),
                    "age_years": _compute_age_years(dmeta.get("date_of_birth"), rdate, year),
                    "data_tier": tier,
                }
            )

    # 3. Season-relative error baseline for Consistency & Grid-adjusted Racecraft
    by_year_costs: dict[int, list[float]] = {}
    for row in all_race_metrics:
        if row["status_category"] in ("CLEAN_FINISH", "DRIVER_ERROR"):
            by_year_costs.setdefault(row["year"], []).append(row["incident_cost"])

    year_mean_cost = {y: float(np.mean(vals)) for y, vals in by_year_costs.items()}
    for row in all_race_metrics:
        if row["status_category"] in ("CLEAN_FINISH", "DRIVER_ERROR"):
            base_c = year_mean_cost.get(row["year"], 0.15)
            # Positive = cleaner/fewer errors & FIA penalties than that season's grid average
            row["consistency_error_score"] = float(-(row["incident_cost"] - base_c))
        else:
            row["consistency_error_score"] = None

    lap1_curve, rc_scores = finalize_racecraft_scores(all_race_metrics)
    for idx, sc in rc_scores.items():
        all_race_metrics[idx]["racecraft_score"] = sc

    # 4. Build LMM inputs & Teammate Network Edges (excluding isolated 1950-60 Indy 500)
    pace_sess_obs: list[dict] = []
    pace_pair_obs: list[dict] = []
    quali_sess_obs: list[dict] = []
    quali_pair_obs: list[dict] = []

    by_round_team: dict[tuple[int, int], list[dict]] = {}
    for row in all_race_metrics:
        if row["is_indy_500"]:
            continue
        by_round_team.setdefault((row["round_id"], row["team_id"]), []).append(row)

        if row["pace_residual_pct"] is not None and row["pace_sample_weight"] > 0:
            pace_sess_obs.append(
                {
                    "driver_id": row["driver_id"],
                    "car_key": (row["team_id"], row["year"]),
                    "age": row["age_years"],
                    "y": row["pace_residual_pct"],
                    "weight": row["pace_sample_weight"],
                }
            )
        if row["quali_perf_pct"] is not None:
            w_q_sess = 0.65 if row["quali_session_used"] == "GRID" else (1.0 if row["year"] >= 1980 else 0.75)
            quali_sess_obs.append(
                {
                    "driver_id": row["driver_id"],
                    "car_key": (row["team_id"], row["year"]),
                    "age": row["age_years"],
                    "y": row["quali_perf_pct"],
                    "weight": w_q_sess,
                }
            )

    # Pairwise teammate duels for LMM & persistent teammate_network_edges
    edge_accum: dict[tuple[int, int], dict] = {}
    # Store round-level teammate pairing info for car-isolated observations
    round_teammates_pace: dict[tuple[int, int], list[tuple[int, float, float | None]]] = {}
    round_teammates_quali: dict[tuple[int, int], list[tuple[int, float, float | None]]] = {}

    for (rid, tid), trows in by_round_team.items():
        if len(trows) < 2:
            continue
        for idx_a in range(len(trows)):
            ra = trows[idx_a]
            da = ra["driver_id"]
            for idx_b in range(idx_a + 1, len(trows)):
                rb = trows[idx_b]
                db = rb["driver_id"]
                if da == db:
                    continue

                # Canonical undirected key a < b
                if da < db:
                    a_row, b_row = ra, rb
                else:
                    a_row, b_row = rb, ra
                key = (a_row["driver_id"], b_row["driver_id"])
                ed = edge_accum.setdefault(
                    key,
                    {
                        "shared_races": 0,
                        "shared_quali": 0,
                        "seasons": set(),
                        "teams": set(),
                        "quali_deltas": [],
                        "pace_deltas": [],
                        "quali_wins_a": 0,
                        "quali_wins_b": 0,
                        "race_wins_a": 0,
                        "race_wins_b": 0,
                    },
                )
                ed["seasons"].add(a_row["year"])
                tname = teams_meta.get(tid, {}).get("name", "Unknown")
                ed["teams"].add(tname)

                # Shared race finish comparison (exclude if either had DNS_OTHER)
                if a_row["status_category"] != "DNS_OTHER" and b_row["status_category"] != "DNS_OTHER":
                    ed["shared_races"] += 1
                    pa, pb = a_row["finish_pos"], b_row["finish_pos"]
                    if pa is not None and pb is not None:
                        if pa < pb:
                            ed["race_wins_a"] += 1
                        elif pb < pa:
                            ed["race_wins_b"] += 1
                    elif pa is not None and pb is None and a_row["status_category"] == "CLEAN_FINISH":
                        ed["race_wins_a"] += 1
                    elif pb is not None and pa is None and b_row["status_category"] == "CLEAN_FINISH":
                        ed["race_wins_b"] += 1

                # Direct pace pair comparison
                pa_res = a_row["pace_residual_pct"]
                pb_res = b_row["pace_residual_pct"]
                if (
                    pa_res is not None
                    and pb_res is not None
                    and a_row["status_category"] != "DNS_OTHER"
                    and b_row["status_category"] != "DNS_OTHER"
                ):
                    delta_ab = float(np.clip(pa_res - pb_res, -4.5, 4.5))
                    w_pair = min(a_row["pace_sample_weight"], b_row["pace_sample_weight"])
                    if w_pair > 0:
                        pace_pair_obs.append(
                            {
                                "driver_i": a_row["driver_id"],
                                "driver_j": b_row["driver_id"],
                                "age_i": a_row["age_years"],
                                "age_j": b_row["age_years"],
                                "delta_y": delta_ab,
                                "weight": w_pair,
                            }
                        )
                        ed["pace_deltas"].append(delta_ab)
                        round_teammates_pace.setdefault((rid, a_row["driver_id"]), []).append(
                            (b_row["driver_id"], delta_ab, b_row["age_years"])
                        )
                        round_teammates_pace.setdefault((rid, b_row["driver_id"]), []).append(
                            (a_row["driver_id"], -delta_ab, a_row["age_years"])
                        )

                # Direct quali pair comparison
                qa_perf = a_row["quali_perf_pct"]
                qb_perf = b_row["quali_perf_pct"]
                if qa_perf is not None and qb_perf is not None:
                    # Prefer exact same-phase teammate delta when available
                    if a_row["quali_teammate_delta_pct"] is not None and len(trows) == 2:
                        q_delta_ab = a_row["quali_teammate_delta_pct"]
                    else:
                        q_delta_ab = float(np.clip(qa_perf - qb_perf, -4.0, 4.0))
                    ed["shared_quali"] += 1
                    ed["quali_deltas"].append(q_delta_ab)
                    if q_delta_ab > 0:
                        ed["quali_wins_a"] += 1
                    elif q_delta_ab < 0:
                        ed["quali_wins_b"] += 1

                    w_q = 0.65 if a_row["quali_session_used"] == "GRID" else (1.0 if a_row["year"] >= 1980 else 0.75)
                    quali_pair_obs.append(
                        {
                            "driver_i": a_row["driver_id"],
                            "driver_j": b_row["driver_id"],
                            "age_i": a_row["age_years"],
                            "age_j": b_row["age_years"],
                            "delta_y": q_delta_ab,
                            "weight": w_q,
                        }
                    )
                    round_teammates_quali.setdefault((rid, a_row["driver_id"]), []).append(
                        (b_row["driver_id"], q_delta_ab, b_row["age_years"])
                    )
                    round_teammates_quali.setdefault((rid, b_row["driver_id"]), []).append(
                        (a_row["driver_id"], -q_delta_ab, a_row["age_years"])
                    )

    # Solve LMM / Ridge IRLS for Race Pace and Qualifying
    pace_lmm = solve_network_lmm(pace_sess_obs, pace_pair_obs)
    quali_lmm = solve_network_lmm(quali_sess_obs, quali_pair_obs)

    # Compute car-isolated race observations for Pace & Qualifying
    for row in all_race_metrics:
        rid = row["round_id"]
        did = row["driver_id"]
        car_key = (row["team_id"], row["year"])

        # Pace isolated
        tm_pace = round_teammates_pace.get((rid, did))
        if tm_pace:
            ests = []
            for j_id, delta_ij, age_j in tm_pace:
                tm_level = pace_lmm["driver_alpha"].get(j_id, 0.0) + age_effect(age_j, pace_lmm["age_beta"])
                ests.append(delta_ij + tm_level)
            row["pace_isolated"] = float(np.mean(ests))
            row["pace_eff_w"] = max(0.45, row["pace_sample_weight"])
        elif row["pace_residual_pct"] is not None:
            car_p = pace_lmm["car_gamma"].get(car_key, 0.0)
            row["pace_isolated"] = float(row["pace_residual_pct"] - car_p)
            row["pace_eff_w"] = 0.5 * row["pace_sample_weight"]
        else:
            row["pace_isolated"] = np.nan
            row["pace_eff_w"] = 0.0

        # Qualifying isolated
        tm_quali = round_teammates_quali.get((rid, did))
        if tm_quali:
            ests = []
            for j_id, delta_ij, age_j in tm_quali:
                tm_level = quali_lmm["driver_alpha"].get(j_id, 0.0) + age_effect(age_j, quali_lmm["age_beta"])
                ests.append(delta_ij + tm_level)
            row["quali_isolated"] = float(np.mean(ests))
            row["quali_eff_w"] = 1.0
        elif row["quali_perf_pct"] is not None:
            car_q = quali_lmm["car_gamma"].get(car_key, 0.0)
            row["quali_isolated"] = float(row["quali_perf_pct"] - car_q)
            row["quali_eff_w"] = 0.35 if row["quali_session_used"] == "GRID" else 0.5
        else:
            row["quali_isolated"] = np.nan
            row["quali_eff_w"] = 0.0

        if row["quali_isolated"] is not None and not np.isnan(row["quali_isolated"]) and tm_quali:
            row["quali_eff_w"] = 0.65 if row["quali_session_used"] == "GRID" else 1.0

        # Consistency combined per race (60% error-free + 40% variance MAD when available)
        err_s = row["consistency_error_score"]
        var_s = row["consistency_variance_score"]
        if err_s is not None and var_s is not None:
            # Normalize scales (~0.35 std on error_s, ~0.25 std on var_s)
            row["consistency_combined"] = 0.60 * (err_s / 0.35) + 0.40 * (var_s / 0.22)
            row["cons_eff_w"] = 1.0
        elif err_s is not None:
            row["consistency_combined"] = err_s / 0.35
            row["cons_eff_w"] = 0.7
        else:
            row["consistency_combined"] = np.nan
            row["cons_eff_w"] = 0.0

        if row["racecraft_score"] is not None:
            row["rc_eff_w"] = 1.0 if row["has_lap_positions"] else 0.5
        else:
            row["rc_eff_w"] = 0.0

    # Persist race_driver_metrics
    rdm_tuples = [
        (
            r["round_id"],
            r["driver_id"],
            r["team_id"],
            r["year"],
            r["round_number"],
            r["round_name"],
            r["round_date"],
            r["grid"],
            r["finish_pos"],
            r["points"],
            r["status_category"],
            r["driver_fault_score"],
            r["fia_driving_penalties"],
            r["quali_session_used"],
            r["quali_teammate_delta_pct"],
            r["quali_perf_pct"],
            r["clean_air_laps"],
            r["clean_laps_total"],
            r["pace_residual_pct"],
            r["stint_deg_bonus_pct"],
            r["pace_teammate_delta_pct"],
            None if np.isnan(r["pace_isolated"]) else float(r["pace_isolated"]),
            None if np.isnan(r["quali_isolated"]) else float(r["quali_isolated"]),
            r["pace_sample_weight"],
            r["stint_mad_pct"],
            r["consistency_error_score"],
            r["consistency_variance_score"],
            r["lap1_pos"],
            r["lap1_net_gain"],
            r["on_track_overtakes"],
            r["on_track_overtaken"],
            r["defense_laps"],
            r["racecraft_score"],
            r["cumulative_starts"],
            r["age_years"],
            r["data_tier"],
        )
        for r in all_race_metrics
    ]
    conn.executemany(
        """
        INSERT INTO race_driver_metrics (
            round_id, driver_id, team_id, year, round_number, round_name, round_date,
            grid, finish_pos, points, status_category, driver_fault_score, fia_driving_penalties,
            quali_session_used, quali_teammate_delta_pct, quali_perf_pct,
            clean_air_laps, clean_laps_total, pace_residual_pct, stint_deg_bonus_pct,
            pace_teammate_delta_pct, pace_isolated, quali_isolated, pace_sample_weight, stint_mad_pct,
            consistency_error_score, consistency_variance_score,
            lap1_pos, lap1_net_gain, on_track_overtakes, on_track_overtaken,
            defense_laps, racecraft_score, cumulative_starts, age_years, data_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rdm_tuples,
    )

    # Persist teammate_network_edges
    edge_rows = [
        (
            a_id,
            b_id,
            ed["shared_races"],
            ed["shared_quali"],
            json.dumps(sorted(ed["seasons"])),
            json.dumps(sorted(ed["teams"])),
            float(np.median(ed["quali_deltas"])) if ed["quali_deltas"] else None,
            float(np.median(ed["pace_deltas"])) if ed["pace_deltas"] else None,
            ed["quali_wins_a"],
            ed["quali_wins_b"],
            ed["race_wins_a"],
            ed["race_wins_b"],
        )
        for (a_id, b_id), ed in edge_accum.items()
        if ed["shared_races"] > 0 or ed["shared_quali"] > 0
    ]
    conn.executemany(
        """
        INSERT INTO teammate_network_edges (
            driver_a_id, driver_b_id, shared_races, shared_quali,
            seasons_json, teams_json, median_quali_delta_pct, median_pace_delta_pct,
            quali_wins_a, quali_wins_b, race_wins_a, race_wins_b
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        edge_rows,
    )

    # 5. Compute Car Season Ratings on 0-99 Scale (within each season)
    car_by_year: dict[int, list[tuple[int, float, float]]] = {}
    all_car_keys = set(pace_lmm["car_gamma"].keys()) | set(quali_lmm["car_gamma"].keys())
    for tid, yr in all_car_keys:
        cp = pace_lmm["car_gamma"].get((tid, yr), 0.0)
        cq = quali_lmm["car_gamma"].get((tid, yr), 0.0)
        car_by_year.setdefault(yr, []).append((tid, cp, cq))

    car_rating_lookup: dict[tuple[int, int], float] = {}
    car_rows_db: list[tuple] = []
    for yr, items in car_by_year.items():
        if not items:
            continue
        p_arr = np.array([x[1] for x in items], dtype=float)
        q_arr = np.array([x[2] for x in items], dtype=float)
        mu_p, sd_p = _winsorized_mean_std(p_arr)
        mu_q, sd_q = _winsorized_mean_std(q_arr)
        comb = 0.55 * ((p_arr - mu_p) / sd_p) + 0.45 * ((q_arr - mu_q) / sd_q)
        mu_c, sd_c = _winsorized_mean_std(comb)
        z_car = (comb - mu_c) / sd_c
        ovr_car = np.clip(DEFAULT_BASE_OVR + DEFAULT_SCALE_FACTOR * z_car, MIN_OVR, MAX_OVR)
        for idx, (tid, cp, cq) in enumerate(items):
            tm = teams_meta.get(tid, {})
            cr = round(float(ovr_car[idx]), 1)
            car_rating_lookup[(yr, tid)] = cr
            car_rows_db.append(
                (yr, tid, tm.get("name", "Unknown"), tm.get("primary_color", "#94A3B8"), cr, round(cp, 4), round(cq, 4))
            )
    conn.executemany(
        """
        INSERT INTO car_season_ratings (
            year, team_id, team_name, team_color, car_rating, pace_car_pct, quali_car_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        car_rows_db,
    )

    # 6. Compute Season & Current Rolling Ratings + All-Time Ratings
    all_years = sorted({r["year"] for r in all_race_metrics})
    rounds_per_year: dict[int, int] = {}
    for yr in all_years:
        rounds_per_year[yr] = len({r["round_id"] for r in all_race_metrics if r["year"] == yr and not r["is_indy_500"]})

    # Group race rows by driver for fast slicing
    by_driver: dict[int, list[dict]] = {}
    for idx, r in enumerate(all_race_metrics):
        r["_chron_idx"] = idx
        by_driver.setdefault(r["driver_id"], []).append(r)

    season_ratings_db: list[tuple] = []
    # Keep track of season-level network-calibrated scores per driver for All-Time Peak+Longevity
    driver_season_raw_pillars: dict[int, list[dict]] = {}
    prev_season_overall: dict[int, float] = {}

    def _aggregate_window(
        rows_slice: list[dict],
        half_life_races: float,
        max_chron_idx: int,
        weights: dict[str, float] = DEFAULT_WEIGHTS,
        shrinkage_m: float = DEFAULT_SHRINKAGE_M,
        baseline_z: float = DEFAULT_BASELINE_Z,
        base_ovr: float = DEFAULT_BASE_OVR,
        scale_factor: float = DEFAULT_SCALE_FACTOR,
        active_driver_ids: set[int] | None = None,
    ) -> list[dict]:
        by_d: dict[int, list[dict]] = {}
        for r in rows_slice:
            by_d.setdefault(r["driver_id"], []).append(r)

        if active_driver_ids is not None:
            cand_ids = sorted(active_driver_ids & set(by_d.keys()))
        else:
            cand_ids = sorted(by_d.keys())

        if not cand_ids:
            return []

        n_drv = len(cand_ids)
        pace_obs = np.full(n_drv, np.nan)
        pace_n = np.zeros(n_drv)
        quali_obs = np.full(n_drv, np.nan)
        quali_n = np.zeros(n_drv)
        cons_obs = np.full(n_drv, np.nan)
        cons_n = np.zeros(n_drv)
        rc_obs = np.full(n_drv, np.nan)
        rc_n = np.zeros(n_drv)
        exp_obs = np.zeros(n_drv)
        exp_n = np.zeros(n_drv)

        meta_list: list[dict] = []

        # Map race chron order among active races for exponential decay
        distinct_rounds = sorted({r["round_id"] for r in rows_slice})
        round_seq = {rid: i for i, rid in enumerate(distinct_rounds)}
        max_seq = max(round_seq.values()) if round_seq else 0

        for i, did in enumerate(cand_ids):
            drows = by_d[did]
            # Use races from the target year (if active_driver_ids provided) to identify primary team
            # Weighted means with exponential decay w = 2^(-delta_r / H)
            w_decay = np.array(
                [2.0 ** (-(max_seq - round_seq[r["round_id"]]) / max(half_life_races, 1.0)) for r in drows],
                dtype=float,
            )

            def _wavg(val_key: str, w_key: str) -> tuple[float, float]:
                vals = np.array([r[val_key] for r in drows], dtype=float)
                ws = np.array([r[w_key] for r in drows], dtype=float) * w_decay
                ok = np.isfinite(vals) & (ws > 0)
                if not np.any(ok):
                    return np.nan, 0.0
                return float(np.sum(vals[ok] * ws[ok]) / np.sum(ws[ok])), float(np.sum(ws[ok]))

            pace_obs[i], pace_n[i] = _wavg("pace_isolated", "pace_eff_w")
            quali_obs[i], quali_n[i] = _wavg("quali_isolated", "quali_eff_w")
            cons_obs[i], cons_n[i] = _wavg("consistency_combined", "cons_eff_w")
            rc_obs[i], rc_n[i] = _wavg("racecraft_score", "rc_eff_w")

            max_starts = max(r["cumulative_starts"] for r in drows)
            exp_obs[i] = compute_experience_score(max_starts)
            exp_n[i] = 100.0  # Experience is deterministic, no shrinkage needed

            latest = drows[-1]
            # Primary team in target season
            target_rows = [r for r in drows if r["year"] == latest["year"]] or drows
            team_counts: dict[int, int] = {}
            for tr in target_rows:
                team_counts[tr["team_id"]] = team_counts.get(tr["team_id"], 0) + 1
            prim_tid = max(team_counts.items(), key=lambda kv: kv[1])[0]
            starts_in_win = sum(1 for r in target_rows if r["status_category"] != "DNS_OTHER")
            clean_cnt = sum(1 for r in target_rows if r["status_category"] == "CLEAN_FINISH")
            tiers = {r["data_tier"] for r in target_rows}
            tier_label = (
                "TELEMETRY_COMPOUND"
                if "TELEMETRY_COMPOUND" in tiers
                else ("LAP_BY_LAP" if "LAP_BY_LAP" in tiers else "HISTORICAL_RESULT")
            )

            meta_list.append(
                {
                    "driver_id": did,
                    "team_id": prim_tid,
                    "races_count": starts_in_win,
                    "clean_races_count": clean_cnt,
                    "car_rating": car_rating_lookup.get((latest["year"], prim_tid), 82.0),
                    "data_tier": tier_label,
                    "pace_raw": pace_obs[i],
                    "quali_raw": quali_obs[i],
                    "cons_raw": cons_obs[i],
                    "rc_raw": rc_obs[i],
                    "eff_n_avg": float(np.mean([pace_n[i], quali_n[i], cons_n[i]])),
                }
            )

        # Reference mask: drivers with >= 3 races in window if at least 10 exist
        ref_mask = np.array([m["races_count"] >= 3 for m in meta_list], dtype=bool)
        if np.sum(ref_mask) < min(10, n_drv):
            ref_mask = np.ones(n_drv, dtype=bool)

        z_p, _ = _shrink_and_standardize_pillar(pace_obs, pace_n, ref_mask, shrinkage_m, baseline_z)
        z_q, _ = _shrink_and_standardize_pillar(quali_obs, quali_n, ref_mask, shrinkage_m, baseline_z)
        z_c, _ = _shrink_and_standardize_pillar(cons_obs, cons_n, ref_mask, shrinkage_m, baseline_z)
        z_r, _ = _shrink_and_standardize_pillar(rc_obs, rc_n, ref_mask, shrinkage_m, baseline_z)
        # Experience standardized directly without shrinkage toward negative prior
        z_e, _ = _shrink_and_standardize_pillar(exp_obs, exp_n, ref_mask, 0.0, 0.0)

        z_raw = (
            weights["pace"] * z_p
            + weights["qualifying"] * z_q
            + weights["consistency"] * z_c
            + weights["racecraft"] * z_r
            + weights["experience"] * z_e
        )
        grid_raw = z_raw[ref_mask] if np.sum(ref_mask) >= 2 else z_raw
        mu_raw, sd_raw = _winsorized_mean_std(grid_raw)
        z_final = np.clip((z_raw - mu_raw) / sd_raw, -3.8, 3.8)
        ovr_raw = _map_z_to_ovr(z_final, base_ovr, scale_factor)

        out_rows = []
        for i, m in enumerate(meta_list):
            tm = teams_meta.get(m["team_id"], {})
            shrink_w = float(m["eff_n_avg"] / (m["eff_n_avg"] + shrinkage_m)) if (m["eff_n_avg"] + shrinkage_m) > 0 else 0.0
            out_rows.append(
                {
                    "driver_id": m["driver_id"],
                    "team_id": m["team_id"],
                    "team_name": tm.get("name", "Unknown"),
                    "team_color": tm.get("primary_color", "#94A3B8"),
                    "races_count": m["races_count"],
                    "clean_races_count": m["clean_races_count"],
                    "overall": int(round(float(ovr_raw[i]))),
                    "overall_raw": round(float(ovr_raw[i]), 2),
                    "z_final": round(float(z_final[i]), 4),
                    "pace_ovr": round(float(_map_z_to_ovr(z_p[i], base_ovr, scale_factor)), 1),
                    "quali_ovr": round(float(_map_z_to_ovr(z_q[i], base_ovr, scale_factor)), 1),
                    "consistency_ovr": round(float(_map_z_to_ovr(z_c[i], base_ovr, scale_factor)), 1),
                    "racecraft_ovr": round(float(_map_z_to_ovr(z_r[i], base_ovr, scale_factor)), 1),
                    "experience_ovr": round(float(_map_z_to_ovr(z_e[i], base_ovr, scale_factor)), 1),
                    "z_pace": round(float(z_p[i]), 4),
                    "z_quali": round(float(z_q[i]), 4),
                    "z_consistency": round(float(z_c[i]), 4),
                    "z_racecraft": round(float(z_r[i]), 4),
                    "z_experience": round(float(z_e[i]), 4),
                    "car_rating": m["car_rating"],
                    "shrinkage_weight": round(shrink_w, 3),
                    "data_tier": m["data_tier"],
                    "pace_raw": m["pace_raw"],
                    "quali_raw": m["quali_raw"],
                    "cons_raw": m["cons_raw"],
                    "rc_raw": m["rc_raw"],
                }
            )
        return out_rows

    # Compute each historical season [year-1, year] for drivers active in `year`
    for yr in all_years:
        win_rows = [r for r in all_race_metrics if (yr - 1) <= r["year"] <= yr and not r["is_indy_500"]]
        active_yr = {r["driver_id"] for r in all_race_metrics if r["year"] == yr and not r["is_indy_500"]}
        # If Indy-only season edge case, keep them
        if not active_yr:
            win_rows = [r for r in all_race_metrics if r["year"] == yr]
            active_yr = {r["driver_id"] for r in win_rows}

        res_list = _aggregate_window(
            win_rows,
            half_life_races=DEFAULT_HALF_LIFE_SEASON,
            max_chron_idx=len(all_race_metrics),
            active_driver_ids=active_yr,
        )
        for item in res_list:
            did = item["driver_id"]
            prev = prev_season_overall.get(did)
            delta = round(item["overall_raw"] - prev, 2) if prev is not None else None
            prev_season_overall[did] = item["overall_raw"]

            season_ratings_db.append(
                (
                    yr,
                    did,
                    "season",
                    item["team_id"],
                    item["team_name"],
                    item["team_color"],
                    item["races_count"],
                    item["clean_races_count"],
                    item["overall"],
                    item["overall_raw"],
                    item["z_final"],
                    item["pace_ovr"],
                    item["quali_ovr"],
                    item["consistency_ovr"],
                    item["racecraft_ovr"],
                    item["experience_ovr"],
                    item["z_pace"],
                    item["z_quali"],
                    item["z_consistency"],
                    item["z_racecraft"],
                    item["z_experience"],
                    item["car_rating"],
                    item["shrinkage_weight"],
                    delta,
                    item["data_tier"],
                )
            )

        # Also record strict single-season standardized pillar Z-scores for All-Time Peak+Longevity
        strict_yr_rows = [r for r in all_race_metrics if r["year"] == yr and not r["is_indy_500"]]
        if strict_yr_rows:
            strict_res = _aggregate_window(
                strict_yr_rows,
                half_life_races=999.0,  # equal weighting within a single championship season
                max_chron_idx=len(all_race_metrics),
                shrinkage_m=4.0,
                active_driver_ids=active_yr,
            )
            n_rnds = max(6, rounds_per_year.get(yr, 12))
            for item in strict_res:
                frac = min(1.0, item["races_count"] / max(4.0, 0.70 * n_rnds))
                driver_season_raw_pillars.setdefault(item["driver_id"], []).append(
                    {
                        "year": yr,
                        "races": item["races_count"],
                        "season_frac": frac,
                        "pace": item["z_pace"],
                        "quali": item["z_quali"],
                        "cons": item["z_consistency"],
                        "rc": item["z_racecraft"],
                        "overall_raw": item["overall_raw"],
                    }
                )

    # Current Active Grid (rolling_current across [max_season_year - 2, max_season_year])
    current_active = {r["driver_id"] for r in all_race_metrics if r["year"] == max_season_year and not r["is_indy_500"]}
    current_win = [
        r for r in all_race_metrics if (max_season_year - 2) <= r["year"] <= max_season_year and not r["is_indy_500"]
    ]
    prev_yr_map = {
        row[1]: row[9] for row in season_ratings_db if row[0] == (max_season_year - 1) and row[2] == "season"
    }
    curr_res = _aggregate_window(
        current_win,
        half_life_races=DEFAULT_HALF_LIFE_CURRENT,
        max_chron_idx=len(all_race_metrics),
        active_driver_ids=current_active,
    )
    for item in curr_res:
        did = item["driver_id"]
        prev = prev_yr_map.get(did)
        delta = round(item["overall_raw"] - prev, 2) if prev is not None else None
        season_ratings_db.append(
            (
                max_season_year,
                did,
                "rolling_current",
                item["team_id"],
                item["team_name"],
                item["team_color"],
                item["races_count"],
                item["clean_races_count"],
                item["overall"],
                item["overall_raw"],
                item["z_final"],
                item["pace_ovr"],
                item["quali_ovr"],
                item["consistency_ovr"],
                item["racecraft_ovr"],
                item["experience_ovr"],
                item["z_pace"],
                item["z_quali"],
                item["z_consistency"],
                item["z_racecraft"],
                item["z_experience"],
                item["car_rating"],
                item["shrinkage_weight"],
                delta,
                item["data_tier"],
            )
        )

    conn.executemany(
        """
        INSERT INTO driver_season_ratings (
            year, driver_id, mode, team_id, team_name, team_color,
            races_count, clean_races_count, overall, overall_raw, z_final,
            pace_ovr, quali_ovr, consistency_ovr, racecraft_ovr, experience_ovr,
            z_pace, z_quali, z_consistency, z_racecraft, z_experience,
            car_rating, shrinkage_weight, delta_vs_prev, data_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        season_ratings_db,
    )

    # 7. All-Time Historical Rating (Peak Window 75% + Career Longevity 25%) for ALL ~860+ drivers
    all_driver_ids = sorted(by_driver.keys())
    n_all = len(all_driver_ids)
    at_pace = np.full(n_all, np.nan)
    at_pace_n = np.zeros(n_all)
    at_quali = np.full(n_all, np.nan)
    at_quali_n = np.zeros(n_all)
    at_cons = np.full(n_all, np.nan)
    at_cons_n = np.zeros(n_all)
    at_rc = np.full(n_all, np.nan)
    at_rc_n = np.zeros(n_all)
    at_exp = np.zeros(n_all)
    at_exp_n = np.full(n_all, 100.0)

    peak_pace = np.full(n_all, np.nan)
    peak_quali = np.full(n_all, np.nan)
    peak_cons = np.full(n_all, np.nan)
    peak_rc = np.full(n_all, np.nan)

    long_pace = np.full(n_all, np.nan)
    long_quali = np.full(n_all, np.nan)
    long_cons = np.full(n_all, np.nan)
    long_rc = np.full(n_all, np.nan)

    at_meta: list[dict] = []

    def _weighted_nanmean(vals: list[float], weights: list[float]) -> float:
        va = np.asarray(vals, dtype=float)
        wa = np.asarray(weights, dtype=float)
        ok = np.isfinite(va) & (wa > 0)
        if not np.any(ok):
            return float("nan")
        return float(np.sum(va[ok] * wa[ok]) / np.sum(wa[ok]))

    for i, did in enumerate(all_driver_ids):
        drows = by_driver[did]
        starts = sum(1 for r in drows if r["status_category"] != "DNS_OTHER")
        eff_starts = max(starts, len(drows))
        first_yr = min(r["year"] for r in drows)
        last_yr = max(r["year"] for r in drows)
        mech_dnfs = sum(1 for r in drows if r["status_category"] == "MECHANICAL_DNF")
        err_dnfs = sum(1 for r in drows if r["status_category"] == "DRIVER_ERROR")
        fia_pens = sum(int(r["fia_driving_penalties"] or 0) for r in drows)
        ca_laps = sum(int(r["clean_air_laps"] or 0) for r in drows)

        # Primary team = team with most starts
        tcounts: dict[int, int] = {}
        for r in drows:
            tcounts[r["team_id"]] = tcounts.get(r["team_id"], 0) + 1
        prim_tid = max(tcounts.items(), key=lambda kv: kv[1])[0]
        tm = teams_meta.get(prim_tid, {})

        tiers = {r["data_tier"] for r in drows}
        tier_label = (
            "TELEMETRY_COMPOUND"
            if "TELEMETRY_COMPOUND" in tiers
            else ("LAP_BY_LAP" if "LAP_BY_LAP" in tiers else "HISTORICAL_RESULT")
        )

        # Season-level Peak (best 3-season contiguous window) & Longevity (top 10 seasons decayed)
        s_list = sorted(driver_season_raw_pillars.get(did, []), key=lambda x: x["year"])
        peak_years_str = str(first_yr) if first_yr == last_yr else f"{first_yr}-{last_yr}"
        target_longevity_denom = sum(0.88 ** k for k in range(8))  # ~5.3316

        def _padded_zmean(vals: list[float], weights: list[float], target_w: float) -> float:
            va = np.asarray(vals, dtype=float)
            wa = np.asarray(weights, dtype=float)
            ok = np.isfinite(va) & (wa > 0)
            if not np.any(ok):
                return 0.0
            w_sum = float(np.sum(wa[ok]))
            pad = max(0.0, target_w - w_sum)
            return float(np.sum(va[ok] * wa[ok]) / (w_sum + pad))

        if s_list:
            # Find best 3-season contiguous window padded up to min 2.2 seasons
            best_score = -1e9
            best_slice = s_list[:1]
            for s_idx in range(len(s_list)):
                cand = s_list[s_idx : s_idx + 3]
                tot_frac = sum(c["season_frac"] for c in cand)
                if tot_frac <= 0:
                    continue
                adj_sc = sum((c["overall_raw"] - DEFAULT_BASE_OVR) * c["season_frac"] for c in cand) / max(tot_frac, 2.2)
                if adj_sc > best_score:
                    best_score = adj_sc
                    best_slice = cand

            if len(best_slice) == 1:
                peak_years_str = str(best_slice[0]["year"])
            else:
                peak_years_str = f"{best_slice[0]['year']}-{best_slice[-1]['year']}"

            pk_w = [c["season_frac"] for c in best_slice]
            peak_pace[i] = _padded_zmean([c["pace"] for c in best_slice], pk_w, 2.2)
            peak_quali[i] = _padded_zmean([c["quali"] for c in best_slice], pk_w, 2.2)
            peak_cons[i] = _padded_zmean([c["cons"] for c in best_slice], pk_w, 2.2)
            peak_rc[i] = _padded_zmean([c["rc"] for c in best_slice], pk_w, 2.2)

            # Longevity: top 10 seasons sorted by overall_raw with 0.88^rank decay & 8-season denominator
            top_s = sorted(s_list, key=lambda c: c["overall_raw"], reverse=True)[:10]
            lg_w = [c["season_frac"] * (0.88 ** rank) for rank, c in enumerate(top_s)]
            long_pace[i] = _padded_zmean([c["pace"] for c in top_s], lg_w, target_longevity_denom)
            long_quali[i] = _padded_zmean([c["quali"] for c in top_s], lg_w, target_longevity_denom)
            long_cons[i] = _padded_zmean([c["cons"] for c in top_s], lg_w, target_longevity_denom)
            long_rc[i] = _padded_zmean([c["rc"] for c in top_s], lg_w, target_longevity_denom)

            at_pace[i] = 0.75 * peak_pace[i] + 0.25 * long_pace[i]
            at_quali[i] = 0.75 * peak_quali[i] + 0.25 * long_quali[i]
            at_cons[i] = 0.75 * peak_cons[i] + 0.25 * long_cons[i]
            at_rc[i] = 0.75 * peak_rc[i] + 0.25 * long_rc[i]
        else:
            # Indy-500-only historical drivers without F1 road rounds
            at_pace[i] = np.nan
            at_quali[i] = np.nan
            at_cons[i] = np.nan
            at_rc[i] = np.nan
            peak_pace[i], peak_quali[i], peak_cons[i], peak_rc[i] = np.nan, np.nan, np.nan, np.nan
            long_pace[i], long_quali[i], long_cons[i], long_rc[i] = np.nan, np.nan, np.nan, np.nan

        eq_starts = sum(
            20.0 / max(6, rounds_per_year.get(r["year"], 16))
            for r in drows
            if r["status_category"] != "DNS_OTHER"
        )
        if not s_list:
            eq_starts = 0.0
        at_pace_n[i] = eq_starts
        at_quali_n[i] = eq_starts
        at_cons_n[i] = eq_starts
        at_rc_n[i] = eq_starts
        at_exp[i] = compute_experience_score(int(round(eq_starts)))

        at_meta.append(
            {
                "driver_id": did,
                "career_starts": eff_starts,
                "eq_starts": eq_starts,
                "career_wins": career_wins.get(did, 0),
                "career_podiums": career_podiums.get(did, 0),
                "championships": champ_counts.get(did, 0),
                "first_year": first_yr,
                "last_year": last_yr,
                "peak_years": peak_years_str,
                "primary_team_name": tm.get("name", "Unknown"),
                "primary_team_color": tm.get("primary_color", "#94A3B8"),
                "mechanical_dnfs_excluded": mech_dnfs,
                "driver_error_dnfs": err_dnfs,
                "fia_penalties_count": fia_pens,
                "clean_air_laps_total": ca_laps,
                "data_tier": tier_label,
            }
        )

    # Reference population for historical standardization: drivers with >= 12 calendar-normalized starts
    at_ref = np.array([m["eq_starts"] >= 12.0 for m in at_meta], dtype=bool)
    if np.sum(at_ref) < 20:
        at_ref = np.ones(n_all, dtype=bool)

    alltime_m = DEFAULT_SHRINKAGE_M
    zp_at, _ = _shrink_and_standardize_pillar(at_pace, at_pace_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zq_at, _ = _shrink_and_standardize_pillar(at_quali, at_quali_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zc_at, _ = _shrink_and_standardize_pillar(at_cons, at_cons_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zr_at, _ = _shrink_and_standardize_pillar(at_rc, at_rc_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    ze_at, _ = _shrink_and_standardize_pillar(at_exp, at_exp_n, at_ref, 0.0, 0.0, winsorize_z=None)

    zraw_at = (
        DEFAULT_WEIGHTS["pace"] * zp_at
        + DEFAULT_WEIGHTS["qualifying"] * zq_at
        + DEFAULT_WEIGHTS["consistency"] * zc_at
        + DEFAULT_WEIGHTS["racecraft"] * zr_at
        + DEFAULT_WEIGHTS["experience"] * ze_at
    )
    mu_at, sd_at = _winsorized_mean_std(zraw_at[at_ref], z_limit=None)
    zfin_at = np.clip((zraw_at - mu_at) / sd_at, -3.8, 3.8)
    ovr_at = _map_z_to_ovr(zfin_at, DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)

    # Also compute pure Peak Overall & Longevity Overall for display
    zp_pk, _ = _shrink_and_standardize_pillar(peak_pace, at_pace_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zq_pk, _ = _shrink_and_standardize_pillar(peak_quali, at_quali_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zc_pk, _ = _shrink_and_standardize_pillar(peak_cons, at_cons_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zr_pk, _ = _shrink_and_standardize_pillar(peak_rc, at_rc_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zraw_pk = (
        DEFAULT_WEIGHTS["pace"] * zp_pk
        + DEFAULT_WEIGHTS["qualifying"] * zq_pk
        + DEFAULT_WEIGHTS["consistency"] * zc_pk
        + DEFAULT_WEIGHTS["racecraft"] * zr_pk
        + DEFAULT_WEIGHTS["experience"] * ze_at
    )
    mu_pk, sd_pk = _winsorized_mean_std(zraw_pk[at_ref], z_limit=None)
    ovr_pk = _map_z_to_ovr(np.clip((zraw_pk - mu_pk) / sd_pk, -3.8, 3.8), DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)

    zp_lg, _ = _shrink_and_standardize_pillar(long_pace, at_pace_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zq_lg, _ = _shrink_and_standardize_pillar(long_quali, at_quali_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zc_lg, _ = _shrink_and_standardize_pillar(long_cons, at_cons_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zr_lg, _ = _shrink_and_standardize_pillar(long_rc, at_rc_n, at_ref, alltime_m, DEFAULT_BASELINE_Z, winsorize_z=None)
    zraw_lg = (
        DEFAULT_WEIGHTS["pace"] * zp_lg
        + DEFAULT_WEIGHTS["qualifying"] * zq_lg
        + DEFAULT_WEIGHTS["consistency"] * zc_lg
        + DEFAULT_WEIGHTS["racecraft"] * zr_lg
        + DEFAULT_WEIGHTS["experience"] * ze_at
    )
    mu_lg, sd_lg = _winsorized_mean_std(zraw_lg[at_ref], z_limit=None)
    ovr_lg = _map_z_to_ovr(np.clip((zraw_lg - mu_lg) / sd_lg, -3.8, 3.8), DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)

    alltime_tuples = [
        (
            m["driver_id"],
            m["career_starts"],
            m["career_wins"],
            m["career_podiums"],
            m["championships"],
            m["first_year"],
            m["last_year"],
            m["peak_years"],
            m["primary_team_name"],
            m["primary_team_color"],
            int(round(float(ovr_at[i]))),
            round(float(ovr_at[i]), 2),
            round(float(ovr_pk[i]), 2),
            round(float(ovr_lg[i]), 2),
            round(float(_map_z_to_ovr(zp_at[i], DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)), 1),
            round(float(_map_z_to_ovr(zq_at[i], DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)), 1),
            round(float(_map_z_to_ovr(zc_at[i], DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)), 1),
            round(float(_map_z_to_ovr(zr_at[i], DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)), 1),
            round(float(_map_z_to_ovr(ze_at[i], DEFAULT_BASE_OVR, DEFAULT_SCALE_FACTOR)), 1),
            round(float(zp_at[i]), 4),
            round(float(zq_at[i]), 4),
            round(float(zc_at[i]), 4),
            round(float(zr_at[i]), 4),
            round(float(ze_at[i]), 4),
            m["mechanical_dnfs_excluded"],
            m["driver_error_dnfs"],
            m["fia_penalties_count"],
            m["clean_air_laps_total"],
            m["data_tier"],
        )
        for i, m in enumerate(at_meta)
    ]
    conn.executemany(
        """
        INSERT INTO driver_alltime_ratings (
            driver_id, career_starts, career_wins, career_podiums, championships,
            first_year, last_year, peak_years, primary_team_name, primary_team_color,
            overall, overall_raw, peak_overall, longevity_overall,
            pace_ovr, quali_ovr, consistency_ovr, racecraft_ovr, experience_ovr,
            z_pace, z_quali, z_consistency, z_racecraft, z_experience,
            mechanical_dnfs_excluded, driver_error_dnfs, fia_penalties_count,
            clean_air_laps_total, data_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        alltime_tuples,
    )

    # 8. Save Model Diagnostics
    age_curve_points = [
        {
            "age": age,
            "pace_delta_pct": round(age_effect(float(age), pace_lmm["age_beta"]), 4),
            "quali_delta_pct": round(age_effect(float(age), quali_lmm["age_beta"]), 4),
        }
        for age in range(18, 46)
    ]
    lap1_curve_points = [
        {"grid": g, "expected_gain": round(float(val), 3)}
        for g, val in sorted(lap1_curve.items())
    ]

    tier_by_decade: dict[str, dict[str, int]] = {}
    for r in all_race_metrics:
        dec = f"{(r['year'] // 10) * 10}s"
        dmap = tier_by_decade.setdefault(dec, {"TELEMETRY_COMPOUND": 0, "LAP_BY_LAP": 0, "HISTORICAL_RESULT": 0})
        dmap[r["data_tier"]] = dmap.get(r["data_tier"], 0) + 1

    diagnostics = {
        "variance_decomposition": {
            "race_pace": pace_lmm["variance_decomposition"],
            "qualifying": quali_lmm["variance_decomposition"],
        },
        "age_curve": age_curve_points,
        "lap1_grid_curve": lap1_curve_points,
        "coverage_stats": {
            "total_drivers_rated": len(alltime_tuples),
            "total_seasons": len(all_years),
            "total_rounds_analyzed": len({r["round_id"] for r in all_race_metrics}),
            "total_race_entries": len(all_race_metrics),
            "total_clean_air_laps": sum(r["clean_air_laps"] for r in all_race_metrics),
            "total_mechanical_dnfs_excluded": sum(1 for r in all_race_metrics if r["status_category"] == "MECHANICAL_DNF"),
            "total_driver_errors_penalized": sum(1 for r in all_race_metrics if r["status_category"] == "DRIVER_ERROR"),
            "total_network_edges": len(edge_rows),
            "latest_season": max_season_year,
            "by_decade": [{"decade": k, **v} for k, v in sorted(tier_by_decade.items())],
        },
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    for k, v in diagnostics.items():
        conn.execute(
            "INSERT OR REPLACE INTO model_diagnostics (key, value_json) VALUES (?, ?)",
            (k, json.dumps(v)),
        )

    return diagnostics
