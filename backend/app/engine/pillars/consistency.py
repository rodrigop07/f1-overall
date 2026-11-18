"""Pillar 3 (20%): Consistency & Awareness (error-free completion + FIA penalties + low lap-time MAD)."""

from __future__ import annotations

import numpy as np

from app.engine.hygiene import robust_mad


def compute_race_consistency_metrics(
    race_entries: list[dict],
    pace_metrics: dict[int, dict],
) -> dict[int, dict]:
    """Compute intrastint MAD% and raw driver-error cost per race entry.

    Season-baseline adjustment for error cost is applied after all races are collected.
    """
    raw_mads: dict[int, float] = {}
    for entry in race_entries:
        did = entry["driver_id"]
        detrended_by_stint = pace_metrics.get(did, {}).get("detrended_by_stint", {})
        stint_mads: list[float] = []
        for s_vals in detrended_by_stint.values():
            if len(s_vals) >= 5:
                m = robust_mad(s_vals)
                if m is not None:
                    stint_mads.append(m)
        if stint_mads:
            raw_mads[did] = float(np.median(stint_mads))

    race_med_mad = float(np.median(list(raw_mads.values()))) if raw_mads else None
    out: dict[int, dict] = {}

    for entry in race_entries:
        did = entry["driver_id"]
        stint_mad = raw_mads.get(did)
        if stint_mad is not None and race_med_mad is not None:
            # Positive variance score = lower lap dispersion than race median
            var_score = float(np.clip(-(stint_mad - race_med_mad), -1.5, 1.5))
        else:
            var_score = None

        fault = float(entry.get("driver_fault_score") or 0.0)
        pen_cnt = int(entry.get("fia_driving_penalties") or 0)
        # Error cost combines own-fault DNF/incident + FIA driving penalties
        incident_cost = fault + 0.35 * min(pen_cnt, 2)

        out[did] = {
            "stint_mad_pct": stint_mad,
            "consistency_variance_score": var_score,
            "incident_cost": incident_cost,
        }

    return out
