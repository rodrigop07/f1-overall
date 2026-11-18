"""Pillar 4 (15%): Combat / Racecraft (grid-adjusted Lap 1 gains + green-flag overtakes & defenses)."""

from __future__ import annotations

import numpy as np


def compute_raw_racecraft_events(
    race_entries: list[dict],
    laps_by_driver: dict[int, list[tuple[int, int | None, float | None]]],
    pit_in_laps_by_driver: dict[int, set[int]],
    neutralized_laps: set[int],
    gap_ahead_map: dict[tuple[int, int], float],
) -> dict[int, dict]:
    """Extract Lap 1 position changes, on-track green-flag overtakes, and defensive holds.

    Args:
        race_entries: list of race entry dicts with driver_id, grid, finish_pos, status_category.
        laps_by_driver: driver_id -> list of (lap_number, position, time_sec).
        pit_in_laps_by_driver: driver_id -> set of pit-in lap numbers.
        neutralized_laps: set of SC/VSC/red-flag lap numbers.
        gap_ahead_map: (driver_id, lap_number) -> gap in seconds to car ahead.
    """
    n_starters = sum(1 for e in race_entries if e["status_category"] != "DNS_OTHER")
    pos_matrix: dict[int, dict[int, int]] = {}
    max_lap_by_drv: dict[int, int] = {}

    for drv_id, llist in laps_by_driver.items():
        pmap: dict[int, int] = {}
        ml = 0
        for ln, pos, _ in llist:
            if ln > 0 and pos is not None and pos > 0:
                pmap[ln] = pos
                if ln > ml:
                    ml = ln
        if pmap:
            pos_matrix[drv_id] = pmap
            max_lap_by_drv[drv_id] = ml

    has_lap_positions = len(pos_matrix) >= 6
    out: dict[int, dict] = {}
    for e in race_entries:
        did = e["driver_id"]
        grid = e.get("grid")
        if grid is not None and grid == 0:
            grid = n_starters  # Pit-lane start mapped to back of grid
        lap1_pos = pos_matrix.get(did, {}).get(1)
        out[did] = {
            "effective_grid": grid,
            "lap1_pos": lap1_pos,
            "raw_lap1_gain": (
                float(grid - lap1_pos)
                if (grid and lap1_pos and e["status_category"] != "DNS_OTHER")
                else None
            ),
            "on_track_overtakes": 0,
            "on_track_overtaken": 0,
            "defense_laps": 0,
            "has_lap_positions": has_lap_positions,
            "surv_q": None,
            "surv_gain": None,
        }

    if not has_lap_positions:
        # Classic era (pre-1996): measure position gain strictly among non-mechanical clean finishers
        survivors = []
        for e in race_entries:
            fin = e.get("finish_pos") if e.get("finish_pos") is not None else e.get("position")
            eg = out[e["driver_id"]]["effective_grid"]
            if e["status_category"] == "CLEAN_FINISH" and eg is not None and eg >= 1 and fin is not None and fin >= 1:
                survivors.append((e["driver_id"], int(eg), int(fin)))

        m_surv = len(survivors)
        if m_surv >= 2:
            by_grid = sorted(survivors, key=lambda x: x[1])
            by_fin = sorted(survivors, key=lambda x: x[2])
            g_rank = {did: r for r, (did, _, _) in enumerate(by_grid, start=1)}
            f_rank = {did: r for r, (did, _, _) in enumerate(by_fin, start=1)}
            for did, _, _ in survivors:
                gr = g_rank[did]
                fr = f_rank[did]
                out[did]["surv_q"] = (gr - 1) / max(m_surv - 1, 1)
                out[did]["surv_gain"] = float(gr - fr)
        return out

    # Count green-flag on-track overtakes & defenses between consecutive laps
    all_laps = sorted({ln for pmap in pos_matrix.values() for ln in pmap})
    active_drivers = list(pos_matrix.keys())

    for ln in all_laps:
        if ln <= 1 or ln in neutralized_laps or (ln - 1) in neutralized_laps:
            continue

        # Drivers completing both ln-1 and ln without pitting on either lap
        clean_runners: list[int] = []
        for did in active_drivers:
            pmap = pos_matrix[did]
            pits = pit_in_laps_by_driver.get(did, set())
            if (ln - 1) in pmap and ln in pmap and (ln - 1) not in pits and ln not in pits:
                clean_runners.append(did)

        # Pairwise position swaps on track among cars that did not pit or DNF
        n_clean = len(clean_runners)
        for idx_a in range(n_clean):
            da = clean_runners[idx_a]
            pa_prev = pos_matrix[da][ln - 1]
            pa_curr = pos_matrix[da][ln]
            for idx_b in range(idx_a + 1, n_clean):
                db = clean_runners[idx_b]
                pb_prev = pos_matrix[db][ln - 1]
                pb_curr = pos_matrix[db][ln]
                if pa_prev > pb_prev and pa_curr < pb_curr:
                    out[da]["on_track_overtakes"] += 1
                    out[db]["on_track_overtaken"] += 1
                elif pb_prev > pa_prev and pb_curr < pa_curr:
                    out[db]["on_track_overtakes"] += 1
                    out[da]["on_track_overtaken"] += 1

        # Defensive holds: car directly behind (pos + 1) was within 1.2s at end of ln-1 and did not pass on ln
        pos_to_drv_prev = {pos_matrix[d][ln - 1]: d for d in clean_runners}
        for d_def in clean_runners:
            p_def = pos_matrix[d_def][ln - 1]
            d_att = pos_to_drv_prev.get(p_def + 1)
            if d_att is None:
                continue
            gap = gap_ahead_map.get((d_att, ln - 1))
            if gap is not None and gap <= 1.2:
                # Defended successfully if attacker is still behind at end of ln
                if pos_matrix[d_def][ln] < pos_matrix[d_att][ln]:
                    out[d_def]["defense_laps"] += 1

    return out


def finalize_racecraft_scores(
    race_metrics_rows: list[dict],
) -> tuple[dict[int, float], dict[int, float]]:
    """Apply empirical Lap 1 grid expectation and compute combined Racecraft score per row.

    Returns:
        lap1_grid_curve: grid_slot (1..24) -> expected raw Lap 1 position gain
        row_scores: index -> combined racecraft score
    """
    # Fit empirical E[ΔP_Lap1 | grid = g] across all valid starts
    by_grid: dict[int, list[float]] = {}
    for row in race_metrics_rows:
        g = row.get("effective_grid")
        gain = row.get("raw_lap1_gain")
        if g is not None and 1 <= g <= 26 and gain is not None:
            by_grid.setdefault(g, []).append(gain)

    lap1_curve: dict[int, float] = {}
    for g in range(1, 25):
        vals = by_grid.get(g, [])
        if len(vals) >= 15:
            lap1_curve[g] = float(np.mean(vals))
        else:
            # Smooth prior: P1 loses slightly on avg, back of grid gains ~0.4 positions
            lap1_curve[g] = float(np.clip(-0.35 + 0.04 * g, -0.4, 0.7))

    # Fit empirical expected survivor position gain per grid decile for classic pre-1996 races
    surv_bins: dict[int, list[float]] = {}
    for row in race_metrics_rows:
        if not row.get("has_lap_positions") and row.get("surv_q") is not None and row.get("surv_gain") is not None:
            b = min(9, max(0, int(row["surv_q"] * 10)))
            surv_bins.setdefault(b, []).append(float(row["surv_gain"]))
    surv_exp_by_bin = {
        b: float(np.mean(surv_bins[b])) if surv_bins.get(b) else 0.0
        for b in range(10)
    }

    row_scores: dict[int, float] = {}
    for idx, row in enumerate(race_metrics_rows):
        if row["status_category"] == "DNS_OTHER":
            continue

        g = row.get("effective_grid")
        raw_gain = row.get("raw_lap1_gain")
        if g is not None and raw_gain is not None:
            exp_gain = lap1_curve.get(min(max(g, 1), 24), 0.0)
            lap1_net = float(np.clip(raw_gain - exp_gain, -6.0, 6.0))
        else:
            lap1_net = None
        row["lap1_net_gain"] = lap1_net

        if row.get("has_lap_positions"):
            overtakes = row["on_track_overtakes"]
            overtaken = row["on_track_overtaken"]
            defenses = row["defense_laps"]
            # Efficiency balances net green-flag passes + successful close-range defenses
            pass_balance = (overtakes - 0.8 * overtaken) / max(1.0, np.sqrt(overtakes + overtaken + 2.0))
            def_bonus = 0.25 * np.log1p(defenses)
            track_combat = float(np.clip(pass_balance + def_bonus, -3.5, 4.5))

            if lap1_net is not None:
                # 50% grid-adjusted Lap 1 gain (scaled to similar variance) + 50% on-track duel efficiency
                combined = 0.50 * (lap1_net / 1.8) + 0.50 * track_combat
            else:
                combined = track_combat
            row_scores[idx] = float(np.clip(combined, -4.0, 4.5))
        else:
            # Classic era (pre-1996): grid-quantile-adjusted survivor gain (removes attrition & P1 truncation bias)
            if row.get("surv_q") is not None and row.get("surv_gain") is not None:
                b = min(9, max(0, int(row["surv_q"] * 10)))
                exp_s = surv_exp_by_bin.get(b, 0.0)
                row_scores[idx] = float(np.clip((float(row["surv_gain"]) - exp_s) / 1.6, -3.5, 4.0))
            elif row["status_category"] == "DRIVER_ERROR":
                row_scores[idx] = float(-0.8 * float(row.get("driver_fault_score") or 0.5))

    return lap1_curve, row_scores
