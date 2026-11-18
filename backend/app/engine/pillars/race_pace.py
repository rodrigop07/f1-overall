"""Pillar 1 (35%): Clean-Air Race Pace with tyre compound/age, fuel burn & stint degradation adjustments."""

from __future__ import annotations

import numpy as np

from app.engine.hygiene import robust_median


def compute_cumulative_clocks_and_clean_air(
    raw_laps_by_driver: dict[int, list[tuple[int, float]]],
    clean_air_gap_sec: float = 1.8,
) -> tuple[dict[tuple[int, int], bool], dict[tuple[int, int], float]]:
    """Reconstruct cumulative race clocks T_i(L) and identify clean-air laps + gap to car ahead.

    Args:
        raw_laps_by_driver: driver_id -> sorted list of (lap_number, time_sec).
        clean_air_gap_sec: minimum time gap (seconds) to any car ahead on track.

    Returns:
        clean_air_map: (driver_id, lap_number) -> True if clean air at both lap start & finish.
        gap_ahead_map: (driver_id, lap_number) -> gap in seconds to nearest car ahead at lap end.
    """
    all_crossings: list[float] = []
    crossing_driver: list[int] = []
    driver_clocks: dict[tuple[int, int], float] = {}

    for drv_id, laps in raw_laps_by_driver.items():
        cum_t = 0.0
        expected_lap = 1
        for lnum, tsec in sorted(laps, key=lambda x: x[0]):
            if lnum != expected_lap or tsec is None or tsec <= 0:
                break  # Must be contiguous from lap 1 to reconstruct exact track clock
            cum_t += tsec
            driver_clocks[(drv_id, lnum)] = cum_t
            all_crossings.append(cum_t)
            crossing_driver.append(drv_id)
            expected_lap += 1

    if not all_crossings:
        return {}, {}

    order = np.argsort(all_crossings)
    sorted_t = np.asarray(all_crossings, dtype=float)[order]
    sorted_drv = np.asarray(crossing_driver, dtype=np.int64)[order]

    clean_air_map: dict[tuple[int, int], bool] = {}
    gap_ahead_map: dict[tuple[int, int], float] = {}

    for (drv_id, lnum), t_end in driver_clocks.items():
        # Gap at lap end: look strictly before t_end for any other car crossing
        idx = int(np.searchsorted(sorted_t, t_end, side="left")) - 1
        gap_end = 999.0
        while idx >= 0:
            if sorted_drv[idx] != drv_id:
                gap_end = float(t_end - sorted_t[idx])
                break
            idx -= 1

        gap_ahead_map[(drv_id, lnum)] = gap_end

        if lnum == 1:
            clean_air_map[(drv_id, lnum)] = False
            continue

        t_start = driver_clocks.get((drv_id, lnum - 1))
        if t_start is None:
            clean_air_map[(drv_id, lnum)] = gap_end >= clean_air_gap_sec
            continue

        idx_s = int(np.searchsorted(sorted_t, t_start, side="left")) - 1
        gap_start = 999.0
        while idx_s >= 0:
            if sorted_drv[idx_s] != drv_id:
                gap_start = float(t_start - sorted_t[idx_s])
                break
            idx_s -= 1

        clean_air_map[(drv_id, lnum)] = (gap_start >= clean_air_gap_sec) and (gap_end >= clean_air_gap_sec)

    return clean_air_map, gap_ahead_map


def _estimate_race_pace_adjustments(
    lap_records: list[dict],
    max_laps: int,
) -> tuple[float, dict[str, float], dict[str, float], float]:
    """Estimate fuel burn slope, per-compound fixed offset, and per-compound degradation slope.

    Returns:
        fuel_slope_pct_per_lap: positive %/lap fuel burn benefit (0..0.09)
        compound_offsets: compound -> % delta relative to race baseline compound
        compound_deg_slopes: compound -> positive %/lap tyre degradation
        default_deg_slope: fallback %/lap tyre degradation when compound unknown
    """
    if len(lap_records) < 20:
        return 0.03, {}, {}, 0.02

    # Estimate global fuel burn via linear regression of normalized % lap delta on (max_laps - lap)
    # within stints so compound swaps don't confound fuel burn
    fuel_diffs: list[float] = []
    deg_obs_by_comp: dict[str, list[float]] = {}

    by_drv_stint: dict[tuple[int, int], list[dict]] = {}
    for rec in lap_records:
        by_drv_stint.setdefault((rec["driver_id"], rec["stint"]), []).append(rec)

    # First estimate within-stint combined slope (tyre_deg - fuel_burn)
    for recs in by_drv_stint.values():
        if len(recs) < 6:
            continue
        ages = np.array([r["tyre_age"] for r in recs], dtype=float)
        deltas = np.array([r["raw_delta_pct"] for r in recs], dtype=float)
        if np.std(ages) < 1.0:
            continue
        slope = float(np.polyfit(ages, deltas, 1)[0])
        comp = recs[0]["compound"]
        deg_obs_by_comp.setdefault(comp, []).append(slope)

    # Estimate fuel effect from drivers' median pace across early vs late stints on similar tyre age
    by_drv: dict[int, list[dict]] = {}
    for rec in lap_records:
        by_drv.setdefault(rec["driver_id"], []).append(rec)
    for recs in by_drv.values():
        if len(recs) < 12:
            continue
        early = [r["raw_delta_pct"] for r in recs if r["lap_num"] <= max_laps * 0.35 and r["tyre_age"] <= 12]
        late = [r["raw_delta_pct"] for r in recs if r["lap_num"] >= max_laps * 0.65 and r["tyre_age"] <= 12]
        if len(early) >= 3 and len(late) >= 3:
            span = max(10.0, max_laps * 0.50)
            fuel_diffs.append(float((np.median(early) - np.median(late)) / span))

    fuel_slope = float(np.clip(np.median(fuel_diffs), 0.0, 0.085)) if fuel_diffs else 0.035

    compound_deg: dict[str, float] = {}
    all_deg_slopes: list[float] = []
    for comp, slopes in deg_obs_by_comp.items():
        # Net degradation = observed within-stint slope + fuel burn correction
        net_slopes = [float(np.clip(s + fuel_slope, 0.0, 0.14)) for s in slopes]
        if net_slopes:
            med_s = float(np.median(net_slopes))
            compound_deg[comp] = med_s
            all_deg_slopes.extend(net_slopes)

    default_deg = float(np.median(all_deg_slopes)) if all_deg_slopes else 0.025

    # Estimate compound fixed pace offsets using drivers who used >= 2 compounds
    comp_diffs: dict[str, list[float]] = {}
    for recs in by_drv.values():
        comps_used = {r["compound"] for r in recs if r["compound"] != "UNKNOWN"}
        if len(comps_used) < 2:
            continue
        fuel_tyre_adj_by_comp: dict[str, list[float]] = {}
        for r in recs:
            c = r["compound"]
            if c == "UNKNOWN":
                continue
            deg_c = compound_deg.get(c, default_deg)
            # Remove fuel remaining & tyre degradation to isolate pure compound speed
            adj = r["raw_delta_pct"] - fuel_slope * (max_laps - r["lap_num"]) - deg_c * r["tyre_age"]
            fuel_tyre_adj_by_comp.setdefault(c, []).append(adj)
        if "MEDIUM" in fuel_tyre_adj_by_comp:
            base_c = "MEDIUM"
        elif "HARD" in fuel_tyre_adj_by_comp:
            base_c = "HARD"
        else:
            base_c = sorted(fuel_tyre_adj_by_comp.keys())[0]
        base_val = float(np.median(fuel_tyre_adj_by_comp[base_c]))
        for c, vals in fuel_tyre_adj_by_comp.items():
            if len(vals) >= 3:
                comp_diffs.setdefault(c, []).append(float(np.median(vals)) - base_val)

    compound_offsets: dict[str, float] = {}
    for c, diffs in comp_diffs.items():
        compound_offsets[c] = float(np.clip(np.median(diffs), -1.8, 1.8))

    # Re-center compound offsets around median compound
    if compound_offsets:
        center = float(np.median(list(compound_offsets.values())))
        compound_offsets = {c: v - center for c, v in compound_offsets.items()}

    return fuel_slope, compound_offsets, compound_deg, default_deg


def compute_race_pace_metrics(
    race_entries: list[dict],
    clean_laps_by_driver: dict[int, list[tuple[int, float, int, int]]],
    clean_air_map: dict[tuple[int, int], bool],
    stint_enrichments_by_driver: dict[int, list[dict]],
    max_laps: int,
) -> dict[int, dict]:
    """Compute Race Pace residuals, clean-air counts, degradation conservation bonus, and teammate deltas.

    Higher `pace_residual_pct` means FASTER pace (e.g., +0.50 = 0.50% faster than race median).
    """
    # Collect all clean green-flag laps across field to define race median m_r
    all_clean_times: list[float] = []
    for claps in clean_laps_by_driver.values():
        for _, tsec, _, _ in claps:
            all_clean_times.append(tsec)

    results: dict[int, dict] = {}
    has_lap_data = len(all_clean_times) >= 30 and len(clean_laps_by_driver) >= 6

    if has_lap_data:
        race_med = float(np.median(all_clean_times))
        lap_records: list[dict] = []

        for drv_id, claps in clean_laps_by_driver.items():
            enrichments = stint_enrichments_by_driver.get(drv_id, [])
            for ln, tsec, inferred_stint, inferred_age in claps:
                comp = "UNKNOWN"
                tyre_age = inferred_age
                stint_id = inferred_stint
                for st in enrichments:
                    ls = st.get("lap_start")
                    le = st.get("lap_end")
                    if ls is not None and le is not None and ls <= ln <= le:
                        comp = st.get("compound", "UNKNOWN")
                        stint_id = int(st.get("stint_number", inferred_stint))
                        tyre_age = int(st.get("tyre_age_at_start") or 0) + (ln - ls)
                        break

                raw_delta_pct = 100.0 * (tsec - race_med) / race_med
                lap_records.append(
                    {
                        "driver_id": drv_id,
                        "lap_num": ln,
                        "time_sec": tsec,
                        "stint": stint_id,
                        "tyre_age": tyre_age,
                        "compound": comp,
                        "raw_delta_pct": raw_delta_pct,
                        "is_clean_air": clean_air_map.get((drv_id, ln), False),
                    }
                )

        fuel_slope, comp_offsets, comp_deg, default_deg = _estimate_race_pace_adjustments(
            lap_records, max(1, max_laps)
        )

        # Score each lap & aggregate per driver
        by_drv_records: dict[int, list[dict]] = {}
        for rec in lap_records:
            c = rec["compound"]
            c_off = comp_offsets.get(c, 0.0)
            c_deg = comp_deg.get(c, default_deg)
            expected_delta = fuel_slope * (max_laps - rec["lap_num"]) + c_off + c_deg * rec["tyre_age"]
            # Positive advantage = faster than expected
            rec["pace_adv_pct"] = float(-(rec["raw_delta_pct"] - expected_delta))
            rec["detrended_delta"] = float(rec["raw_delta_pct"] - expected_delta)
            by_drv_records.setdefault(rec["driver_id"], []).append(rec)

        for entry in race_entries:
            drv_id = entry["driver_id"]
            recs = by_drv_records.get(drv_id, [])
            clean_air_advs = [r["pace_adv_pct"] for r in recs if r["is_clean_air"]]
            dirty_air_advs = [r["pace_adv_pct"] + 0.25 for r in recs if not r["is_clean_air"]]

            if len(clean_air_advs) >= 5:
                pace_score = float(np.median(clean_air_advs))
            elif len(clean_air_advs) >= 3 and len(recs) >= 6:
                ca_med = float(np.median(clean_air_advs))
                all_med = float(np.median(clean_air_advs + dirty_air_advs))
                pace_score = 0.65 * ca_med + 0.35 * all_med
            elif len(recs) >= 5:
                pace_score = float(np.median(clean_air_advs + dirty_air_advs))
            else:
                pace_score = None

            # Stint degradation conservation bonus (stints >= 8 laps)
            deg_bonuses: list[float] = []
            by_stint: dict[int, list[dict]] = {}
            for r in recs:
                by_stint.setdefault(r["stint"], []).append(r)
            for s_recs in by_stint.values():
                if len(s_recs) >= 8:
                    ages = np.array([x["tyre_age"] for x in s_recs], dtype=float)
                    if np.std(ages) >= 1.5:
                        # Residual degradation beyond expected compound slope
                        resids = np.array(
                            [x["raw_delta_pct"] - fuel_slope * (max_laps - x["lap_num"]) for x in s_recs],
                            dtype=float,
                        )
                        actual_slope = float(np.polyfit(ages, resids, 1)[0])
                        c_deg = comp_deg.get(s_recs[0]["compound"], default_deg)
                        # Positive bonus if driver degraded LESS than expected
                        deg_diff = float(np.clip((c_deg - actual_slope) * 5.0, -0.15, 0.15))
                        deg_bonuses.append(deg_diff)

            deg_bonus = float(np.median(deg_bonuses)) if deg_bonuses else 0.0
            final_pace = (pace_score + 0.5 * deg_bonus) if pace_score is not None else None
            if final_pace is not None:
                final_pace = float(np.clip(final_pace, -6.0, 6.0))

            results[drv_id] = {
                "clean_air_laps": len(clean_air_advs),
                "clean_laps_total": len(recs),
                "pace_residual_pct": final_pace,
                "stint_deg_bonus_pct": deg_bonus,
                "pace_sample_weight": 1.0 if len(clean_air_advs) >= 5 else (0.75 if len(recs) >= 5 else 0.0),
                "pace_teammate_delta_pct": None,
                "detrended_by_stint": {
                    s_id: [x["detrended_delta"] for x in s_recs]
                    for s_id, s_recs in by_stint.items()
                },
            }

        # Compute direct same-team pace delta using clean-air/adjusted race pace
        by_team: dict[int, list[dict]] = {}
        for entry in race_entries:
            if entry["status_category"] in ("CLEAN_FINISH", "DRIVER_ERROR"):
                by_team.setdefault(entry["team_id"], []).append(entry)

        for team_entries in by_team.values():
            valid = [
                e for e in team_entries
                if results.get(e["driver_id"], {}).get("pace_residual_pct") is not None
            ]
            if len(valid) >= 2:
                for e in valid:
                    others = [
                        results[o["driver_id"]]["pace_residual_pct"]
                        for o in valid
                        if o["driver_id"] != e["driver_id"]
                    ]
                    if others:
                        own = results[e["driver_id"]]["pace_residual_pct"]
                        results[e["driver_id"]]["pace_teammate_delta_pct"] = float(
                            np.clip(own - float(np.mean(others)), -4.5, 4.5)
                        )
        return results

    # Historical fallback (1950-1995): compare teammates cleanly finishing on same/adjacent laps
    for entry in race_entries:
        results[entry["driver_id"]] = {
            "clean_air_laps": 0,
            "clean_laps_total": 0,
            "pace_residual_pct": None,
            "stint_deg_bonus_pct": 0.0,
            "pace_sample_weight": 0.0,
            "pace_teammate_delta_pct": None,
            "detrended_by_stint": {},
        }

    # Estimate field pace baseline per driver from avg lap time (total_time / laps_completed)
    avg_lap_times: dict[int, float] = {}
    for e in race_entries:
        if (
            e["status_category"] == "CLEAN_FINISH"
            and e.get("time_sec")
            and e.get("laps_completed")
            and e["laps_completed"] >= 5
            and e["time_sec"] > 60.0
        ):
            avg_lap_times[e["driver_id"]] = float(e["time_sec"]) / float(e["laps_completed"])

    med_avg_lap = robust_median(list(avg_lap_times.values()))
    if med_avg_lap and med_avg_lap > 0:
        for drv_id, avg_t in avg_lap_times.items():
            # Positive = faster than field median
            pct = float(np.clip(-100.0 * (avg_t - med_avg_lap) / med_avg_lap, -6.0, 6.0))
            results[drv_id]["pace_residual_pct"] = pct
            results[drv_id]["pace_sample_weight"] = 0.55

    by_team: dict[int, list[dict]] = {}
    for e in race_entries:
        if e["status_category"] == "CLEAN_FINISH" and e.get("laps_completed"):
            by_team.setdefault(e["team_id"], []).append(e)

    for team_entries in by_team.values():
        if len(team_entries) < 2:
            continue
        for e in team_entries:
            d_i = e["driver_id"]
            deltas: list[float] = []
            for o in team_entries:
                d_j = o["driver_id"]
                if d_j == d_i:
                    continue
                t_i = avg_lap_times.get(d_i)
                t_j = avg_lap_times.get(d_j)
                if t_i is not None and t_j is not None and e["laps_completed"] == o["laps_completed"]:
                    d_pct = -100.0 * (t_i - t_j) / (0.5 * (t_i + t_j))
                    deltas.append(float(np.clip(d_pct, -4.0, 4.0)))
                elif e["laps_completed"] and o["laps_completed"] and e["laps_completed"] != o["laps_completed"]:
                    max_l = max(e["laps_completed"], o["laps_completed"])
                    if max_l >= 10:
                        lap_diff_pct = 100.0 * (e["laps_completed"] - o["laps_completed"]) / max_l
                        deltas.append(float(np.clip(lap_diff_pct, -3.0, 3.0)))
            if deltas:
                results[d_i]["pace_teammate_delta_pct"] = float(np.median(deltas))
                if results[d_i]["pace_sample_weight"] == 0.0:
                    results[d_i]["pace_sample_weight"] = 0.45

    return results
