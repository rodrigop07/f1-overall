"""Counterfactual simulators: Equal-Machinery Season & Monte Carlo Seat-Swap."""

from __future__ import annotations

import sqlite3

import numpy as np

FIA_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def simulate_equal_machinery_season(
    conn: sqlite3.Connection,
    year: int,
    exclude_mechanical_dnfs: bool = True,
) -> dict:
    """Re-score every round of `year` assuming identical cars (based on isolated weekend_score)."""
    rows = conn.execute(
        """
        SELECT
            m.round_id, m.round_number, m.round_name, m.driver_id,
            d.reference, d.forename || ' ' || d.surname AS name,
            t.name AS team_name, t.primary_color AS team_color,
            m.finish_pos, m.points, m.status_category, m.weekend_score
        FROM race_driver_metrics m
        JOIN drivers d ON d.id = m.driver_id
        JOIN teams t ON t.id = m.team_id
        WHERE m.year = ? AND m.status_category != 'DNS_OTHER'
        ORDER BY m.round_number ASC, m.weekend_score DESC
        """,
        (year,),
    ).fetchall()

    if not rows:
        return {"year": year, "standings": [], "rounds_count": 0}

    by_round: dict[int, list[dict]] = {}
    drv_acc: dict[int, dict] = {}
    for r in rows:
        did = int(r["driver_id"])
        by_round.setdefault(int(r["round_id"]), []).append(dict(r))
        if did not in drv_acc:
            drv_acc[did] = {
                "driver_id": did,
                "reference": r["reference"],
                "name": r["name"],
                "team_name": r["team_name"],
                "team_color": r["team_color"],
                "actual_points": 0.0,
                "actual_wins": 0,
                "equal_points": 0,
                "equal_wins": 0,
                "equal_podiums": 0,
                "races": 0,
            }
        drv_acc[did]["actual_points"] += float(r["points"] or 0.0)
        if r["finish_pos"] == 1:
            drv_acc[did]["actual_wins"] += 1
        drv_acc[did]["races"] += 1

    # Also check official WDC final standings if available (includes sprint points & fastest lap points)
    wdc_rows = conn.execute(
        """
        SELECT driver_id, position, points, win_count
        FROM driver_championships
        WHERE year = ? AND season_id > 0
        """,
        (year,),
    ).fetchall()
    official_pos = {}
    for wr in wdc_rows:
        did = int(wr["driver_id"])
        if did in drv_acc:
            if wr["position"] is not None:
                official_pos[did] = int(wr["position"])
            if wr["points"] is not None:
                drv_acc[did]["actual_points"] = float(wr["points"])
            if wr["win_count"] is not None:
                drv_acc[did]["actual_wins"] = int(wr["win_count"])

    # Compute equal-machinery race outcomes round by round
    for rlist in by_round.values():
        def _sort_key(item: dict) -> tuple[int, float]:
            cat = item["status_category"]
            if cat == "CLEAN_FINISH":
                tier = 2
            elif cat == "MECHANICAL_DNF":
                tier = 2 if exclude_mechanical_dnfs else 1
            else:
                tier = 0  # DRIVER_ERROR always classifies behind clean drivers
            return (tier, float(item["weekend_score"] or 60.0))

        ordered = sorted(rlist, key=_sort_key, reverse=True)
        for pos_idx, item in enumerate(ordered):
            did = int(item["driver_id"])
            if pos_idx < len(FIA_POINTS) and (item["status_category"] == "CLEAN_FINISH" or exclude_mechanical_dnfs):
                drv_acc[did]["equal_points"] += FIA_POINTS[pos_idx]
            if pos_idx == 0:
                drv_acc[did]["equal_wins"] += 1
            if pos_idx < 3:
                drv_acc[did]["equal_podiums"] += 1

    all_list = list(drv_acc.values())
    actual_sorted = sorted(
        all_list,
        key=lambda x: (-(official_pos.get(x["driver_id"], 999)), x["actual_points"], x["actual_wins"]),
        reverse=True,
    )
    if official_pos:
        actual_sorted = sorted(
            all_list,
            key=lambda x: (official_pos.get(x["driver_id"], 999), -x["actual_points"]),
        )
    else:
        actual_sorted = sorted(all_list, key=lambda x: (x["actual_points"], x["actual_wins"]), reverse=True)

    actual_rank_map = {x["driver_id"]: idx for idx, x in enumerate(actual_sorted, start=1)}

    equal_sorted = sorted(
        all_list,
        key=lambda x: (x["equal_points"], x["equal_wins"], x["equal_podiums"]),
        reverse=True,
    )
    standings = []
    for eq_pos, item in enumerate(equal_sorted, start=1):
        act_pos = actual_rank_map[item["driver_id"]]
        standings.append(
            {
                **item,
                "actual_pos": act_pos,
                "equal_pos": eq_pos,
                "pos_delta": act_pos - eq_pos,
                "actual_points": round(item["actual_points"], 1),
            }
        )

    return {
        "year": year,
        "exclude_mechanical_dnfs": exclude_mechanical_dnfs,
        "rounds_count": len(by_round),
        "actual_champion": actual_sorted[0] if actual_sorted else None,
        "equal_champion": standings[0] if standings else None,
        "standings": standings,
    }


def simulate_seat_swap(
    conn: sqlite3.Connection,
    driver_ref: str,
    target_team_id: int,
    year: int,
    replace_driver_ref: str | None = None,
    n_sims: int = 500,
) -> dict:
    """Run vectorized Monte Carlo season placing `driver_ref` in `target_team_id` for `year`."""
    # Load target season drivers & cars
    grid_rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT sr.*, d.reference, d.forename || ' ' || d.surname AS name
            FROM driver_season_ratings sr
            JOIN drivers d ON d.id = sr.driver_id
            WHERE sr.year = ? AND sr.mode = 'season'
            ORDER BY sr.races_count DESC, sr.overall_raw DESC
            """,
            (year,),
        ).fetchall()
    ]
    if not grid_rows:
        raise ValueError(f"Season {year} not found")

    car_rows = {
        int(r["team_id"]): dict(r)
        for r in conn.execute("SELECT * FROM car_season_ratings WHERE year = ?", (year,)).fetchall()
    }
    if target_team_id not in car_rows:
        raise ValueError(f"Team {target_team_id} did not compete in {year}")
    target_car = car_rows[target_team_id]

    # Load candidate driver skill profile (prefer same-year skill if active in `year`, else All-Time)
    cand_drv = conn.execute(
        """
        SELECT d.id, d.reference, d.forename || ' ' || d.surname AS name,
               a.overall, a.overall_raw, a.z_pace, a.z_quali, a.z_consistency, a.z_racecraft
        FROM drivers d
        JOIN driver_alltime_ratings a ON a.driver_id = d.id
        WHERE d.reference = ?
        """,
        (driver_ref,),
    ).fetchone()
    if not cand_drv:
        raise ValueError(f"Driver '{driver_ref}' not found")
    cand_dict = dict(cand_drv)
    cand_in_year = next((g for g in grid_rows if g["reference"] == driver_ref), None)
    if cand_in_year:
        cand_z = {
            "z_pace": float(cand_in_year["z_pace"]),
            "z_quali": float(cand_in_year["z_quali"]),
            "z_consistency": float(cand_in_year["z_consistency"]),
            "z_racecraft": float(cand_in_year["z_racecraft"]),
            "overall": int(cand_in_year["overall"]),
        }
    else:
        cand_z = {
            "z_pace": float(cand_dict["z_pace"]),
            "z_quali": float(cand_dict["z_quali"]),
            "z_consistency": float(cand_dict["z_consistency"]),
            "z_racecraft": float(cand_dict["z_racecraft"]),
            "overall": int(cand_dict["overall"]),
        }

    # Build simulated 20-22 car grid: keep top ~22 drivers in `year` by races_count/overall
    # First pick up to 2 drivers per team to form realistic constructor grid
    by_team: dict[int, list[dict]] = {}
    for g in grid_rows:
        by_team.setdefault(int(g["team_id"]), []).append(g)

    active_grid: list[dict] = []
    for tid, tdrivers in by_team.items():
        tdrivers_sorted = sorted(tdrivers, key=lambda x: (x["races_count"], x["overall_raw"]), reverse=True)
        active_grid.extend(tdrivers_sorted[:2])

    # Identify driver to replace at target_team_id
    team_mates = [g for g in active_grid if int(g["team_id"]) == target_team_id]
    if not team_mates:
        raise ValueError(f"No active entries for team {target_team_id} in {year}")

    if replace_driver_ref:
        replaced = next((g for g in team_mates if g["reference"] == replace_driver_ref), None)
    else:
        # If candidate is already on target_team_id, keep him there; otherwise replace #2 driver (lower overall)
        replaced = next((g for g in team_mates if g["reference"] == driver_ref), None)
        if not replaced:
            replaced = sorted(team_mates, key=lambda x: (x["overall_raw"], x["races_count"]))[0]

    teammate = next((g for g in team_mates if g["driver_id"] != replaced["driver_id"]), None)

    # Remove candidate from old seat if candidate was already in `active_grid` at another team
    sim_entries: list[dict] = []
    for g in active_grid:
        if g["driver_id"] == replaced["driver_id"]:
            sim_entries.append(
                {
                    "driver_id": int(cand_dict["id"]),
                    "reference": cand_dict["reference"],
                    "name": cand_dict["name"],
                    "team_id": target_team_id,
                    "team_name": target_car["team_name"],
                    "team_color": target_car["team_color"],
                    "car_z": (float(target_car["car_rating"]) - 82.0) / 6.0,
                    "z_pace": cand_z["z_pace"],
                    "z_quali": cand_z["z_quali"],
                    "z_consistency": cand_z["z_consistency"],
                    "z_racecraft": cand_z["z_racecraft"],
                    "overall": cand_z["overall"],
                    "is_swapped_driver": True,
                    "is_teammate": False,
                }
            )
        elif g["reference"] == driver_ref:
            # Candidate vacated old seat -> backfill with replaced driver so grid size remains balanced
            old_car = car_rows.get(int(g["team_id"]), {"car_rating": 82.0, "team_name": g["team_name"], "team_color": g["team_color"]})
            sim_entries.append(
                {
                    "driver_id": int(replaced["driver_id"]),
                    "reference": replaced["reference"],
                    "name": replaced["name"],
                    "team_id": int(g["team_id"]),
                    "team_name": old_car["team_name"],
                    "team_color": old_car["team_color"],
                    "car_z": (float(old_car["car_rating"]) - 82.0) / 6.0,
                    "z_pace": float(replaced["z_pace"]),
                    "z_quali": float(replaced["z_quali"]),
                    "z_consistency": float(replaced["z_consistency"]),
                    "z_racecraft": float(replaced["z_racecraft"]),
                    "overall": int(replaced["overall"]),
                    "is_swapped_driver": False,
                    "is_teammate": False,
                }
            )
        else:
            c_info = car_rows.get(int(g["team_id"]), {"car_rating": 82.0})
            sim_entries.append(
                {
                    "driver_id": int(g["driver_id"]),
                    "reference": g["reference"],
                    "name": g["name"],
                    "team_id": int(g["team_id"]),
                    "team_name": g["team_name"],
                    "team_color": g["team_color"],
                    "car_z": (float(c_info["car_rating"]) - 82.0) / 6.0,
                    "z_pace": float(g["z_pace"]),
                    "z_quali": float(g["z_quali"]),
                    "z_consistency": float(g["z_consistency"]),
                    "z_racecraft": float(g["z_racecraft"]),
                    "overall": int(g["overall"]),
                    "is_swapped_driver": False,
                    "is_teammate": (teammate is not None and g["driver_id"] == teammate["driver_id"]),
                }
            )

    n_drivers = len(sim_entries)
    n_rounds = int(
        conn.execute("SELECT COUNT(DISTINCT round_id) FROM race_driver_metrics WHERE year = ?", (year,)).fetchone()[0]
    )
    n_rounds = max(12, min(n_rounds, 24))

    rng = np.random.default_rng(42)
    car_z = np.array([e["car_z"] for e in sim_entries], dtype=float)
    drv_skill_z = np.array(
        [0.55 * e["z_pace"] + 0.30 * e["z_quali"] + 0.15 * e["z_racecraft"] for e in sim_entries],
        dtype=float,
    )
    cons_z = np.array([e["z_consistency"] for e in sim_entries], dtype=float)
    dnf_prob = np.clip(0.055 - 0.02 * cons_z, 0.012, 0.15) + 0.05  # driver error + mechanical rate

    # Vectorized Monte Carlo: shape (n_sims, n_rounds, n_drivers)
    base_perf = 0.78 * car_z[None, None, :] + 0.28 * drv_skill_z[None, None, :]
    noise = rng.normal(0.0, 0.42, size=(n_sims, n_rounds, n_drivers))
    dnf_mask = rng.random(size=(n_sims, n_rounds, n_drivers)) < dnf_prob[None, None, :]
    race_perf = np.where(dnf_mask, -99.0 + noise, base_perf + noise)

    # Order descending along driver axis -> finishing positions (0 = P1)
    order = np.argsort(-race_perf, axis=2)
    ranks = np.empty_like(order)
    grid_s = np.arange(n_sims)[:, None, None]
    grid_r = np.arange(n_rounds)[None, :, None]
    ranks[grid_s, grid_r, order] = np.arange(n_drivers)[None, None, :]

    pts_lut = np.zeros(n_drivers, dtype=float)
    for pos_i, pval in enumerate(FIA_POINTS[:n_drivers]):
        pts_lut[pos_i] = pval

    pts_matrix = np.where(dnf_mask, 0.0, pts_lut[ranks])
    season_pts = pts_matrix.sum(axis=1)  # shape (n_sims, n_drivers)
    wins_matrix = ((ranks == 0) & (~dnf_mask)).sum(axis=1)
    podiums_matrix = ((ranks < 3) & (~dnf_mask)).sum(axis=1)

    # Championship rank per simulation (0 = WDC)
    champ_order = np.argsort(-season_pts, axis=1)
    champ_ranks = np.empty_like(champ_order)
    champ_ranks[np.arange(n_sims)[:, None], champ_order] = np.arange(n_drivers)[None, :]

    standings = []
    for idx, e in enumerate(sim_entries):
        standings.append(
            {
                "driver_id": e["driver_id"],
                "reference": e["reference"],
                "name": e["name"],
                "team_name": e["team_name"],
                "team_color": e["team_color"],
                "overall": e["overall"],
                "is_swapped_driver": e["is_swapped_driver"],
                "is_teammate": e["is_teammate"],
                "expected_points": round(float(np.mean(season_pts[:, idx])), 1),
                "expected_wins": round(float(np.mean(wins_matrix[:, idx])), 2),
                "expected_podiums": round(float(np.mean(podiums_matrix[:, idx])), 2),
                "expected_pos": round(float(np.mean(champ_ranks[:, idx]) + 1.0), 2),
                "title_prob_pct": round(float(100.0 * np.mean(champ_ranks[:, idx] == 0)), 1),
            }
        )

    standings.sort(key=lambda x: x["expected_points"], reverse=True)
    for pos, item in enumerate(standings, start=1):
        item["projected_rank"] = pos

    swapped_summary = next(x for x in standings if x["is_swapped_driver"])
    teammate_summary = next((x for x in standings if x["is_teammate"]), None)

    teammate_beat_pct = None
    if teammate_summary:
        sw_idx = next(i for i, e in enumerate(sim_entries) if e["is_swapped_driver"])
        tm_idx = next(i for i, e in enumerate(sim_entries) if e["is_teammate"])
        teammate_beat_pct = round(float(100.0 * np.mean(season_pts[:, sw_idx] > season_pts[:, tm_idx])), 1)

    return {
        "year": year,
        "rounds_simulated": n_rounds,
        "n_simulations": n_sims,
        "driver": swapped_summary,
        "target_team": {
            "team_id": target_team_id,
            "team_name": target_car["team_name"],
            "team_color": target_car["team_color"],
            "car_rating": float(target_car["car_rating"]),
        },
        "replaced_driver": replaced["name"],
        "teammate": teammate_summary,
        "teammate_beat_pct": teammate_beat_pct,
        "standings": standings,
    }
