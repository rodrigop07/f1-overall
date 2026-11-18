"""Pillar 2 (25%): Qualifying Pace using last equal valid session between teammates."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

_PHASE_PRIORITY = ("Q3", "Q2", "Q1", "QB", "QA", "QO")


def compute_qualifying_metrics(
    quali_times_by_phase: dict[str, dict[int, float]],
    driver_teams: dict[int, int],
    driver_grids: dict[int, int | None] | None = None,
) -> dict[int, dict]:
    """Compute qualifying teammate deltas (last equal valid phase) & normalized session pace.
    Falls back to grid-quantile normal score in pre-1994 seasons lacking qualifying lap times.
    """
    # Filter outlier times (> 1.07 * phase median) per phase
    clean_phases: dict[str, dict[int, float]] = {}
    phase_medians: dict[str, float] = {}

    for phase, dmap in quali_times_by_phase.items():
        vals = [t for t in dmap.values() if t is not None and 30.0 <= t <= 300.0]
        if len(vals) < 3:
            continue
        med = float(np.median(vals))
        filtered = {
            did: t for did, t in dmap.items()
            if t is not None and 0.85 * med <= t <= 1.07 * med
        }
        if filtered:
            clean_phases[phase] = filtered
            phase_medians[phase] = float(np.median(list(filtered.values())))

    # Estimate track evolution shift between Q1->Q2 and Q2->Q3 from advancing drivers
    # so drivers who drop out in Q1/Q2 are comparable on the same scale as Q3 drivers
    phase_shift: dict[str, float] = {"Q1": 0.0, "QB": 0.0, "QA": 0.0, "QO": 0.0}
    if "Q1" in clean_phases and "Q2" in clean_phases:
        common_12 = [
            100.0 * (clean_phases["Q2"][d] - clean_phases["Q1"][d]) / clean_phases["Q1"][d]
            for d in clean_phases["Q2"]
            if d in clean_phases["Q1"]
        ]
        phase_shift["Q2"] = float(np.clip(np.median(common_12), -2.0, 2.0)) if common_12 else 0.0
    if "Q2" in clean_phases and "Q3" in clean_phases:
        common_23 = [
            100.0 * (clean_phases["Q3"][d] - clean_phases["Q2"][d]) / clean_phases["Q2"][d]
            for d in clean_phases["Q3"]
            if d in clean_phases["Q2"]
        ]
        phase_shift["Q3"] = phase_shift.get("Q2", 0.0) + (
            float(np.clip(np.median(common_23), -2.0, 2.0)) if common_23 else 0.0
        )

    base_ref_phase = "Q1" if "Q1" in phase_medians else (
        next((p for p in ("QB", "QA", "QO", "Q2", "Q3") if p in phase_medians), None)
    )
    base_ref_med = phase_medians.get(base_ref_phase) if base_ref_phase else None

    results: dict[int, dict] = {
        did: {
            "quali_session_used": None,
            "quali_teammate_delta_pct": None,
            "quali_perf_pct": None,
        }
        for did in driver_teams
    }

    # Driver's highest valid session performance vs grid baseline
    if base_ref_med and base_ref_med > 0:
        for did in driver_teams:
            for phase in _PHASE_PRIORITY:
                if phase in clean_phases and did in clean_phases[phase]:
                    t_d = clean_phases[phase][did]
                    # Remove estimated track evolution relative to Q1 baseline
                    adj_t = t_d / (1.0 + phase_shift.get(phase, 0.0) / 100.0)
                    perf_pct = float(np.clip(-100.0 * (adj_t - base_ref_med) / base_ref_med, -6.0, 6.0))
                    results[did]["quali_perf_pct"] = perf_pct
                    results[did]["quali_session_used"] = phase
                    break

    # Group teammates and compare in LAST EQUAL VALID SESSION
    by_team: dict[int, list[int]] = {}
    for did, tid in driver_teams.items():
        by_team.setdefault(tid, []).append(did)

    for team_drivers in by_team.values():
        if len(team_drivers) < 2:
            continue
        for d_i in team_drivers:
            pair_deltas: list[float] = []
            used_phases: list[str] = []
            for d_j in team_drivers:
                if d_j == d_i:
                    continue
                for phase in _PHASE_PRIORITY:
                    pmap = clean_phases.get(phase)
                    if pmap and d_i in pmap and d_j in pmap:
                        t_i = pmap[d_i]
                        t_j = pmap[d_j]
                        sym_delta = -100.0 * (t_i - t_j) / (0.5 * (t_i + t_j))
                        pair_deltas.append(float(np.clip(sym_delta, -4.0, 4.0)))
                        used_phases.append(phase)
                        break
            if pair_deltas:
                results[d_i]["quali_teammate_delta_pct"] = float(np.median(pair_deltas))
                if used_phases:
                    results[d_i]["quali_session_used"] = used_phases[0]

    # Classic era fallback (1950-1993): grid-quantile normal score when lap times are absent
    if not clean_phases and driver_grids:
        valid_grids = {
            did: int(g)
            for did, g in driver_grids.items()
            if did in driver_teams and g is not None and int(g) >= 1
        }
        n_g = len(valid_grids)
        if n_g >= 4:
            # Assign average rank if ties exist in starting grid
            sorted_items = sorted(valid_grids.items(), key=lambda kv: kv[1])
            ranks: dict[int, float] = {}
            idx = 0
            while idx < n_g:
                end = idx
                while end + 1 < n_g and sorted_items[end + 1][1] == sorted_items[idx][1]:
                    end += 1
                avg_rank = 0.5 * (idx + 1 + end + 1)
                for k in range(idx, end + 1):
                    ranks[sorted_items[k][0]] = avg_rank
                idx = end + 1

            for did, r_i in ranks.items():
                p_i = (n_g + 1.0 - r_i - 0.375) / (n_g + 0.25)
                perf_pct = float(np.clip(norm.ppf(p_i) * 1.10, -3.5, 3.5))
                results[did]["quali_perf_pct"] = perf_pct
                results[did]["quali_session_used"] = "GRID"

            for team_drivers in by_team.values():
                if len(team_drivers) < 2:
                    continue
                for d_i in team_drivers:
                    if d_i not in ranks:
                        continue
                    pair_deltas = []
                    for d_j in team_drivers:
                        if d_j != d_i and d_j in ranks:
                            p_i = results[d_i]["quali_perf_pct"]
                            p_j = results[d_j]["quali_perf_pct"]
                            if p_i is not None and p_j is not None:
                                pair_deltas.append(float(np.clip(p_i - p_j, -3.5, 3.5)))
                    if pair_deltas:
                        results[d_i]["quali_teammate_delta_pct"] = float(np.median(pair_deltas))

    return results
