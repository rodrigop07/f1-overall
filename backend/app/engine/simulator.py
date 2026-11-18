"""Fast in-memory NumPy simulator for real-time Sandbox methodology experiments (<30 ms)."""

from __future__ import annotations

import sqlite3
import time

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
from app.engine.pipeline import _map_z_to_ovr, _shrink_and_standardize_pillar, _winsorized_mean_std


class OverallSimulator:
    """Preloads compact driver pillar Z/observation arrays for sub-30ms ranking recalculation."""

    def __init__(self) -> None:
        self.loaded: bool = False
        self.latest_year: int = 2026
        # Preloaded All-Time arrays
        self.at_meta: list[dict] = []
        self.at_z: dict[str, np.ndarray] = {}
        self.at_eff_n: dict[str, np.ndarray] = {}
        self.at_ref: np.ndarray = np.array([], dtype=bool)
        self.at_baseline_ovr: dict[int, float] = {}
        self.at_baseline_rank: dict[int, int] = {}

        # Preloaded Season / Current Race rows for fast temporal-decay simulation
        self.race_rows_by_year: dict[int, dict[str, np.ndarray]] = {}
        self.drivers_info: dict[int, dict] = {}
        self.season_baseline: dict[tuple[int, str], dict[int, tuple[float, int]]] = {}

    def reload_from_db(self, conn: sqlite3.Connection) -> None:
        """Load compact NumPy arrays from SQLite into memory."""
        self.drivers_info = {
            int(r["id"]): {
                "driver_id": int(r["id"]),
                "reference": r["reference"],
                "abbreviation": r["abbreviation"],
                "name": f"{r['forename']} {r['surname']}".strip(),
                "nationality": r["nationality"],
                "country_code": r["country_code"],
            }
            for r in conn.execute(
                "SELECT id, reference, abbreviation, forename, surname, nationality, country_code FROM drivers"
            ).fetchall()
        }

        max_yr_row = conn.execute("SELECT MAX(year) FROM driver_season_ratings").fetchone()
        self.latest_year = int(max_yr_row[0]) if max_yr_row and max_yr_row[0] else 2026

        # Load All-Time baselines & standardized Z-pillars
        at_rows = conn.execute(
            """
            SELECT a.*, d.reference, d.abbreviation, d.forename, d.surname, d.nationality, d.country_code
            FROM driver_alltime_ratings a
            JOIN drivers d ON d.id = a.driver_id
            ORDER BY a.overall_raw DESC, a.career_wins DESC
            """
        ).fetchall()

        self.at_meta = []
        zp, zq, zc, zr, ze = [], [], [], [], []
        starts_arr = []
        self.at_baseline_ovr = {}
        self.at_baseline_rank = {}

        for rank_idx, r in enumerate(at_rows, start=1):
            did = int(r["driver_id"])
            self.at_baseline_ovr[did] = float(r["overall_raw"])
            self.at_baseline_rank[did] = rank_idx
            self.at_meta.append(
                {
                    "driver_id": did,
                    "reference": r["reference"],
                    "abbreviation": r["abbreviation"],
                    "name": f"{r['forename']} {r['surname']}".strip(),
                    "nationality": r["nationality"],
                    "country_code": r["country_code"],
                    "team_name": r["primary_team_name"],
                    "team_color": r["primary_team_color"],
                    "career_starts": int(r["career_starts"]),
                    "career_wins": int(r["career_wins"]),
                    "championships": int(r["championships"]),
                    "first_year": int(r["first_year"]),
                    "last_year": int(r["last_year"]),
                    "peak_years": r["peak_years"],
                    "data_tier": r["data_tier"],
                }
            )
            zp.append(float(r["z_pace"]))
            zq.append(float(r["z_quali"]))
            zc.append(float(r["z_consistency"]))
            zr.append(float(r["z_racecraft"]))
            ze.append(float(r["z_experience"]))
            starts_arr.append(int(r["career_starts"]))

        self.at_z = {
            "pace": np.asarray(zp, dtype=float),
            "qualifying": np.asarray(zq, dtype=float),
            "consistency": np.asarray(zc, dtype=float),
            "racecraft": np.asarray(zr, dtype=float),
            "experience": np.asarray(ze, dtype=float),
        }
        s_np = np.asarray(starts_arr, dtype=float)
        self.at_ref = s_np >= 10
        if np.sum(self.at_ref) < 20:
            self.at_ref = np.ones_like(s_np, dtype=bool)
        self.at_eff_n = {
            "pace": s_np,
            "qualifying": s_np,
            "consistency": s_np,
            "racecraft": s_np,
        }

        # Load Season baselines (for delta_rank and delta_overall comparisons)
        self.season_baseline = {}
        sr_rows = conn.execute(
            """
            SELECT year, mode, driver_id, overall_raw
            FROM driver_season_ratings
            ORDER BY year, mode, overall_raw DESC
            """
        ).fetchall()
        rank_counters: dict[tuple[int, str], int] = {}
        for r in sr_rows:
            k = (int(r["year"]), r["mode"])
            rank_counters[k] = rank_counters.get(k, 0) + 1
            self.season_baseline.setdefault(k, {})[int(r["driver_id"])] = (
                float(r["overall_raw"]),
                rank_counters[k],
            )

        # Load precomputed per-driver season ratings Z-pillars as compact fallback for all years,
        # PLUS race-level arrays for recent window / fast re-decay simulation
        self.season_z_cache: dict[tuple[int, str], dict] = {}
        for (yr, mode) in self.season_baseline:
            rows = conn.execute(
                """
                SELECT s.*, d.reference, d.abbreviation, d.forename, d.surname, d.nationality, d.country_code
                FROM driver_season_ratings s
                JOIN drivers d ON d.id = s.driver_id
                WHERE s.year = ? AND s.mode = ?
                ORDER BY s.overall_raw DESC
                """,
                (yr, mode),
            ).fetchall()
            if not rows:
                continue
            self.season_z_cache[(yr, mode)] = {
                "meta": [
                    {
                        "driver_id": int(r["driver_id"]),
                        "reference": r["reference"],
                        "abbreviation": r["abbreviation"],
                        "name": f"{r['forename']} {r['surname']}".strip(),
                        "nationality": r["nationality"],
                        "country_code": r["country_code"],
                        "team_name": r["team_name"],
                        "team_color": r["team_color"],
                        "races_count": int(r["races_count"]),
                        "car_rating": float(r["car_rating"]),
                        "data_tier": r["data_tier"],
                    }
                    for r in rows
                ],
                "z": {
                    "pace": np.array([float(r["z_pace"]) for r in rows], dtype=float),
                    "qualifying": np.array([float(r["z_quali"]) for r in rows], dtype=float),
                    "consistency": np.array([float(r["z_consistency"]) for r in rows], dtype=float),
                    "racecraft": np.array([float(r["z_racecraft"]) for r in rows], dtype=float),
                    "experience": np.array([float(r["z_experience"]) for r in rows], dtype=float),
                },
                "races": np.array([float(r["races_count"]) for r in rows], dtype=float),
            }

        # Load per-race metrics for exact half_life_races & shrinkage_m simulation on any season / current grid
        self.race_metrics_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                    m.round_id, m.driver_id, m.team_id, m.year, m.status_category,
                    m.pace_isolated, m.quali_isolated, m.pace_sample_weight,
                    m.pace_teammate_delta_pct, m.quali_teammate_delta_pct,
                    m.consistency_error_score, m.consistency_variance_score,
                    m.racecraft_score, m.cumulative_starts, m.data_tier,
                    t.name AS team_name, t.primary_color AS team_color
                FROM race_driver_metrics m
                JOIN teams t ON t.id = m.team_id
                WHERE NOT (m.round_name = 'Indianapolis 500' AND m.year BETWEEN 1950 AND 1960)
                ORDER BY m.year ASC, m.round_number ASC
                """
            ).fetchall()
        ]
        # Attach car_rating map
        self.car_rating_map = {
            (int(r["year"]), int(r["team_id"])): (float(r["car_rating"]), float(r["pace_car_pct"]), float(r["quali_car_pct"]))
            for r in conn.execute("SELECT year, team_id, car_rating, pace_car_pct, quali_car_pct FROM car_season_ratings").fetchall()
        }
        self.loaded = True

    def simulate(
        self,
        scope: str = "current",
        year: int | None = None,
        weights: dict[str, float] | None = None,
        shrinkage_m: float = DEFAULT_SHRINKAGE_M,
        half_life_races: float | None = None,
        base_ovr: float = DEFAULT_BASE_OVR,
        scale_factor: float = DEFAULT_SCALE_FACTOR,
        min_starts: int = 0,
        limit: int = 50,
    ) -> dict:
        """Recalculate rankings in memory and return deltas vs default methodology."""
        t0 = time.perf_counter()
        w = dict(weights or DEFAULT_WEIGHTS)
        w_sum = sum(max(0.0, float(v)) for v in w.values()) or 1.0
        w_norm = {k: max(0.0, float(v)) / w_sum for k, v in w.items()}

        if scope == "alltime":
            return self._simulate_alltime(
                w_norm, shrinkage_m, base_ovr, scale_factor, min_starts, limit, t0
            )

        target_year = year or self.latest_year
        mode = "rolling_current" if scope == "current" else "season"
        hl = half_life_races if half_life_races is not None else (
            DEFAULT_HALF_LIFE_CURRENT if mode == "rolling_current" else DEFAULT_HALF_LIFE_SEASON
        )
        return self._simulate_season_or_current(
            target_year, mode, w_norm, shrinkage_m, hl, base_ovr, scale_factor, limit, t0
        )

    def _simulate_alltime(
        self,
        w_norm: dict[str, float],
        shrinkage_m: float,
        base_ovr: float,
        scale_factor: float,
        min_starts: int,
        limit: int,
        t0: float,
    ) -> dict:
        if not self.at_meta:
            return {"results": [], "elapsed_ms": 0.0}

        # Adjust shrinkage sensitivity relative to default m=10
        adj_factor = {}
        n_arr = self.at_eff_n["pace"]
        # Re-shrink each Z-pillar when shrinkage_m != default
        ratio_default = (n_arr + DEFAULT_SHRINKAGE_M) / np.maximum(n_arr, 1.0)
        new_weight = n_arr / np.maximum(n_arr + shrinkage_m, 1.0)
        default_weight = n_arr / np.maximum(n_arr + DEFAULT_SHRINKAGE_M, 1.0)

        re_z: dict[str, np.ndarray] = {}
        for pk in ("pace", "qualifying", "consistency", "racecraft"):
            z_def = self.at_z[pk]
            if abs(shrinkage_m - DEFAULT_SHRINKAGE_M) < 1e-6:
                re_z[pk] = z_def
            else:
                # Approximate inverse of default shrinkage toward baseline, then apply new shrinkage_m
                inferred_obs = (z_def - DEFAULT_BASELINE_Z * (1.0 - default_weight)) / np.maximum(default_weight, 0.05)
                shrunk_z = new_weight * inferred_obs + (1.0 - new_weight) * DEFAULT_BASELINE_Z
                mu_s, sd_s = _winsorized_mean_std(shrunk_z[self.at_ref], z_limit=None)
                re_z[pk] = np.clip((shrunk_z - mu_s) / sd_s, -6.0, 6.0)
        re_z["experience"] = self.at_z["experience"]

        z_raw = (
            w_norm["pace"] * re_z["pace"]
            + w_norm["qualifying"] * re_z["qualifying"]
            + w_norm["consistency"] * re_z["consistency"]
            + w_norm["racecraft"] * re_z["racecraft"]
            + w_norm["experience"] * re_z["experience"]
        )
        mu_r, sd_r = _winsorized_mean_std(z_raw[self.at_ref], z_limit=None)
        z_fin = np.clip((z_raw - mu_r) / sd_r, -3.8, 3.8)
        ovr_raw = _map_z_to_ovr(z_fin, base_ovr, scale_factor)

        # Rank all matching drivers
        indices = [i for i, m in enumerate(self.at_meta) if m["career_starts"] >= min_starts]
        indices.sort(key=lambda idx: (float(ovr_raw[idx]), self.at_meta[idx]["career_wins"]), reverse=True)

        # Baseline ranks among filtered subset
        base_sorted = sorted(
            indices,
            key=lambda idx: (self.at_baseline_ovr.get(self.at_meta[idx]["driver_id"], 0.0), self.at_meta[idx]["career_wins"]),
            reverse=True,
        )
        base_pos_map = {self.at_meta[idx]["driver_id"]: pos for pos, idx in enumerate(base_sorted, start=1)}

        results = []
        for new_rank, idx in enumerate(indices[:limit], start=1):
            m = self.at_meta[idx]
            did = m["driver_id"]
            base_ovr_val = self.at_baseline_ovr.get(did, float(ovr_raw[idx]))
            base_rank = base_pos_map.get(did, new_rank)
            new_ovr_val = round(float(ovr_raw[idx]), 2)
            results.append(
                {
                    "rank": new_rank,
                    "baseline_rank": base_rank,
                    "delta_rank": base_rank - new_rank,
                    "driver_id": did,
                    "reference": m["reference"],
                    "abbreviation": m["abbreviation"],
                    "name": m["name"],
                    "nationality": m["nationality"],
                    "country_code": m["country_code"],
                    "team_name": m["team_name"],
                    "team_color": m["team_color"],
                    "races_count": m["career_starts"],
                    "overall": int(round(new_ovr_val)),
                    "overall_raw": new_ovr_val,
                    "baseline_overall": round(base_ovr_val, 2),
                    "delta_overall": round(new_ovr_val - base_ovr_val, 2),
                    "pace_ovr": round(float(_map_z_to_ovr(re_z["pace"][idx], base_ovr, scale_factor)), 1),
                    "quali_ovr": round(float(_map_z_to_ovr(re_z["qualifying"][idx], base_ovr, scale_factor)), 1),
                    "consistency_ovr": round(float(_map_z_to_ovr(re_z["consistency"][idx], base_ovr, scale_factor)), 1),
                    "racecraft_ovr": round(float(_map_z_to_ovr(re_z["racecraft"][idx], base_ovr, scale_factor)), 1),
                    "experience_ovr": round(float(_map_z_to_ovr(re_z["experience"][idx], base_ovr, scale_factor)), 1),
                }
            )

        elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
        return {"scope": "alltime", "results": results, "elapsed_ms": elapsed}

    def _simulate_season_or_current(
        self,
        year: int,
        mode: str,
        w_norm: dict[str, float],
        shrinkage_m: float,
        half_life_races: float,
        base_ovr: float,
        scale_factor: float,
        limit: int,
        t0: float,
    ) -> dict:
        win_back = 2 if mode == "rolling_current" else 1
        win_rows = [
            r for r in self.race_metrics_rows
            if (year - win_back) <= r["year"] <= year
        ]
        active_ids = {r["driver_id"] for r in win_rows if r["year"] == year}
        if not active_ids:
            return {"scope": mode, "year": year, "results": [], "elapsed_ms": 0.0}

        by_d: dict[int, list[dict]] = {}
        for r in win_rows:
            if r["driver_id"] in active_ids:
                by_d.setdefault(r["driver_id"], []).append(r)

        distinct_rounds = sorted({r["round_id"] for r in win_rows})
        round_seq = {rid: i for i, rid in enumerate(distinct_rounds)}
        max_seq = max(round_seq.values()) if round_seq else 0

        cand_ids = sorted(by_d.keys())
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
        exp_n = np.full(n_drv, 100.0)
        meta_list = []

        for i, did in enumerate(cand_ids):
            drows = by_d[did]
            w_dec = np.array(
                [2.0 ** (-(max_seq - round_seq[r["round_id"]]) / max(half_life_races, 1.0)) for r in drows],
                dtype=float,
            )

            # Car-adjusted race observations
            p_vals, p_ws = [], []
            q_vals, q_ws = [], []
            c_vals, c_ws = [], []
            r_vals, r_ws = [], []
            for idx_r, r in enumerate(drows):
                dec = w_dec[idx_r]
                if r["pace_isolated"] is not None and (r["pace_sample_weight"] or 0) > 0:
                    eff_pw = max(0.45, float(r["pace_sample_weight"])) if r["pace_teammate_delta_pct"] is not None else 0.5 * float(r["pace_sample_weight"])
                    p_vals.append(r["pace_isolated"])
                    p_ws.append(eff_pw * dec)
                if r["quali_isolated"] is not None:
                    eff_qw = 1.0 if r["quali_teammate_delta_pct"] is not None else 0.5
                    q_vals.append(r["quali_isolated"])
                    q_ws.append(eff_qw * dec)
                if r["consistency_error_score"] is not None:
                    es = r["consistency_error_score"] / 0.35
                    vs = r["consistency_variance_score"]
                    comb = (0.60 * es + 0.40 * (vs / 0.22)) if vs is not None else es
                    c_vals.append(comb)
                    c_ws.append((1.0 if vs is not None else 0.7) * dec)
                if r["racecraft_score"] is not None:
                    r_vals.append(r["racecraft_score"])
                    r_ws.append(dec)

            def _avg(vals, ws):
                if not vals or sum(ws) <= 0:
                    return np.nan, 0.0
                return float(np.dot(vals, ws) / sum(ws)), float(sum(ws))

            pace_obs[i], pace_n[i] = _avg(p_vals, p_ws)
            quali_obs[i], quali_n[i] = _avg(q_vals, q_ws)
            cons_obs[i], cons_n[i] = _avg(c_vals, c_ws)
            rc_obs[i], rc_n[i] = _avg(r_vals, r_ws)
            exp_obs[i] = np.log1p(min(max(r["cumulative_starts"] for r in drows), 350))

            target_rows = [r for r in drows if r["year"] == year] or drows
            tcounts: dict[int, int] = {}
            for tr in target_rows:
                tcounts[tr["team_id"]] = tcounts.get(tr["team_id"], 0) + 1
            prim_tid = max(tcounts.items(), key=lambda kv: kv[1])[0]
            prim_row = next(tr for tr in reversed(target_rows) if tr["team_id"] == prim_tid)
            starts_yr = sum(1 for tr in target_rows if tr["status_category"] != "DNS_OTHER")
            meta_list.append(
                {
                    "driver_id": did,
                    "team_name": prim_row["team_name"],
                    "team_color": prim_row["team_color"],
                    "races_count": starts_yr,
                    "car_rating": self.car_rating_map.get((year, prim_tid), (82.0, 0.0, 0.0))[0],
                }
            )

        ref_mask = np.array([m["races_count"] >= 3 for m in meta_list], dtype=bool)
        if np.sum(ref_mask) < min(10, n_drv):
            ref_mask = np.ones(n_drv, dtype=bool)

        zp, _ = _shrink_and_standardize_pillar(pace_obs, pace_n, ref_mask, shrinkage_m, DEFAULT_BASELINE_Z)
        zq, _ = _shrink_and_standardize_pillar(quali_obs, quali_n, ref_mask, shrinkage_m, DEFAULT_BASELINE_Z)
        zc, _ = _shrink_and_standardize_pillar(cons_obs, cons_n, ref_mask, shrinkage_m, DEFAULT_BASELINE_Z)
        zr, _ = _shrink_and_standardize_pillar(rc_obs, rc_n, ref_mask, shrinkage_m, DEFAULT_BASELINE_Z)
        ze, _ = _shrink_and_standardize_pillar(exp_obs, exp_n, ref_mask, 0.0, 0.0)

        z_raw = (
            w_norm["pace"] * zp
            + w_norm["qualifying"] * zq
            + w_norm["consistency"] * zc
            + w_norm["racecraft"] * zr
            + w_norm["experience"] * ze
        )
        mu_r, sd_r = _winsorized_mean_std(z_raw[ref_mask] if np.sum(ref_mask) >= 2 else z_raw)
        z_fin = np.clip((z_raw - mu_r) / sd_r, -3.8, 3.8)
        ovr_raw = _map_z_to_ovr(z_fin, base_ovr, scale_factor)

        order = sorted(range(n_drv), key=lambda idx: float(ovr_raw[idx]), reverse=True)
        base_map = self.season_baseline.get((year, mode), {})

        results = []
        for new_rank, idx in enumerate(order[:limit], start=1):
            m = meta_list[idx]
            did = m["driver_id"]
            dinfo = self.drivers_info.get(did, {})
            new_val = round(float(ovr_raw[idx]), 2)
            base_val, base_rank = base_map.get(did, (new_val, new_rank))
            results.append(
                {
                    "rank": new_rank,
                    "baseline_rank": base_rank,
                    "delta_rank": base_rank - new_rank,
                    "driver_id": did,
                    "reference": dinfo.get("reference", str(did)),
                    "abbreviation": dinfo.get("abbreviation"),
                    "name": dinfo.get("name", str(did)),
                    "nationality": dinfo.get("nationality"),
                    "country_code": dinfo.get("country_code"),
                    "team_name": m["team_name"],
                    "team_color": m["team_color"],
                    "races_count": m["races_count"],
                    "car_rating": round(m["car_rating"], 1),
                    "overall": int(round(new_val)),
                    "overall_raw": new_val,
                    "baseline_overall": round(base_val, 2),
                    "delta_overall": round(new_val - base_val, 2),
                    "pace_ovr": round(float(_map_z_to_ovr(zp[idx], base_ovr, scale_factor)), 1),
                    "quali_ovr": round(float(_map_z_to_ovr(zq[idx], base_ovr, scale_factor)), 1),
                    "consistency_ovr": round(float(_map_z_to_ovr(zc[idx], base_ovr, scale_factor)), 1),
                    "racecraft_ovr": round(float(_map_z_to_ovr(zr[idx], base_ovr, scale_factor)), 1),
                    "experience_ovr": round(float(_map_z_to_ovr(ze[idx], base_ovr, scale_factor)), 1),
                }
            )

        elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
        return {"scope": mode, "year": year, "results": results, "elapsed_ms": elapsed}
