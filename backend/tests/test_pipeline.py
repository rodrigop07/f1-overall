"""Unit tests for Z-score standardization, Bayesian Shrinkage, and full pipeline consistency."""

from __future__ import annotations

import numpy as np

from app.db.connection import get_connection
from app.db.schema import init_schema
from app.engine.pipeline import _shrink_and_standardize_pillar, run_full_computation
from app.engine.simulator import OverallSimulator


def test_bayesian_shrinkage_convergence():
    # 5 established drivers + 1 extreme 1-race rookie outlier (+3.0 vs ~0.0 grid)
    obs = np.array([-0.5, -0.2, 0.0, 0.2, 0.5, 3.0])
    eff_n = np.array([24.0, 24.0, 24.0, 24.0, 24.0, 1.0])
    ref = np.array([True, True, True, True, True, False])

    z_m10, shrunk_m10 = _shrink_and_standardize_pillar(obs, eff_n, ref, shrinkage_m=10.0, baseline_z=-0.30)
    z_m0, shrunk_m0 = _shrink_and_standardize_pillar(obs, eff_n, ref, shrinkage_m=0.0, baseline_z=-0.30)

    # With m=10, 1-race outlier (+3.0) is heavily pulled toward baseline (< 0.35 instead of 3.0)
    assert shrunk_m10[-1] < 0.40
    assert z_m10[-1] < z_m0[-1]
    # Established drivers remain properly ordered
    assert z_m10[4] > z_m10[2] > z_m10[0]


def test_end_to_end_pipeline_and_simulator_on_synthetic_db(tmp_path):
    db_file = tmp_path / "test_f1.sqlite"
    conn = get_connection(db_file)
    init_schema(conn)

    # Seed 1 season (2025), 2 teams, 4 drivers, 4 rounds with realistic lap & quali data
    conn.execute("INSERT INTO seasons (id, year) VALUES (1, 2025)")
    conn.execute("INSERT INTO circuits (id, reference, name) VALUES (1, 'spa', 'Spa')")
    conn.executemany(
        "INSERT INTO drivers (id, reference, abbreviation, forename, surname, date_of_birth, nationality) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "alpha_ace", "ACE", "Alpha", "Ace", "1998-01-01", "Dutch"),
            (2, "alpha_wing", "WNG", "Alpha", "Wing", "1996-01-01", "Mexican"),
            (3, "beta_lead", "BLD", "Beta", "Lead", "1999-01-01", "British"),
            (4, "beta_rookie", "BRK", "Beta", "Rookie", "2005-01-01", "Brazilian"),
        ],
    )
    conn.executemany(
        "INSERT INTO teams (id, reference, name, primary_color) VALUES (?, ?, ?, ?)",
        [(1, "fast_team", "Fast Team", "#3671C6"), (2, "mid_team", "Mid Team", "#FF8000")],
    )
    conn.executemany(
        "INSERT INTO team_drivers (id, season_id, team_id, driver_id) VALUES (?, 1, ?, ?)",
        [(1, 1, 1), (2, 1, 2), (3, 2, 3), (4, 2, 4)],
    )

    se_id = 1
    lap_id = 1
    for rnd in range(1, 5):
        conn.execute(
            "INSERT INTO rounds (id, season_id, circuit_id, number, race_number, name, date, is_cancelled) VALUES (?, 1, 1, ?, ?, ?, ?, 0)",
            (rnd, rnd, rnd, f"GP {rnd}", f"2025-05-0{rnd}"),
        )
        for td_id in (1, 2, 3, 4):
            # Rookie only drives round 4 (n=1), others drive all 4
            if td_id == 4 and rnd < 4:
                continue
            re_id = rnd * 10 + td_id
            conn.execute(
                "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, ?, ?, ?)",
                (re_id, rnd, td_id, td_id),
            )

        # Sessions: R and Q1/Q3
        r_sid = rnd * 10 + 1
        q_sid = rnd * 10 + 2
        conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'R', 0)", (r_sid, rnd))
        conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'Q1', 0)", (q_sid, rnd))

        configs = [
            (1, 1, 1, 0, "Finished", 90.0, 88.2),
            (2, 2, 2, 0, "Finished", 90.5, 88.7),
            (3, 3, 3, 0, "Finished", 91.2, 89.4),
            (4, 4, 4, 11, "Engine", 91.9, 90.1),  # Mechanical DNF in round 4 must NOT count as driver error!
        ]
        for td_id, grid, pos, status, det, base_lap, q_time in configs:
            if td_id == 4 and rnd < 4:
                continue
            re_id = rnd * 10 + td_id
            conn.execute(
                "INSERT INTO session_entries (id, session_id, round_entry_id, position, is_classified, status, detail, grid, laps_completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 15)",
                (se_id, r_sid, re_id, pos, 1 if status == 0 else 0, status, det, grid),
            )
            r_se_id = se_id
            se_id += 1
            conn.execute(
                "INSERT INTO session_entries (id, session_id, round_entry_id, position, time_sec) VALUES (?, ?, ?, ?, ?)",
                (se_id, q_sid, re_id, grid, q_time),
            )
            se_id += 1

            for ln in range(1, 16):
                t = base_lap + (3.0 if ln == 1 else 0.02 * ln)
                conn.execute(
                    "INSERT INTO laps (id, session_entry_id, number, position, time_sec, is_deleted) VALUES (?, ?, ?, ?, ?, 0)",
                    (lap_id, r_se_id, ln, pos, t),
                )
                lap_id += 1

    conn.commit()
    diag = run_full_computation(conn)
    assert diag["coverage_stats"]["total_drivers_rated"] == 4

    at = {
        r["reference"]: dict(r)
        for r in conn.execute(
            "SELECT d.reference, a.* FROM driver_alltime_ratings a JOIN drivers d ON d.id = a.driver_id"
        ).fetchall()
    }
    assert at["alpha_ace"]["overall_raw"] > at["alpha_wing"]["overall_raw"]
    assert at["beta_rookie"]["mechanical_dnfs_excluded"] == 1
    assert at["beta_rookie"]["driver_error_dnfs"] == 0
    assert 60.0 <= at["beta_rookie"]["overall_raw"] <= 99.0

    # Simulator parity check
    sim = OverallSimulator()
    sim.reload_from_db(conn)
    res = sim.simulate(scope="season", year=2025)
    assert len(res["results"]) == 4
    for row in res["results"]:
        assert abs(row["delta_overall"]) < 0.05
    conn.close()


def test_historical_quali_null_lap_number_and_multi_qb(tmp_path):
    """Historical qualifying laps with number=NULL and two QB sessions per round must be extracted."""
    db_file = tmp_path / "hist_quali.sqlite"
    conn = get_connection(db_file)
    init_schema(conn)

    conn.execute("INSERT INTO seasons (id, year) VALUES (1, 1988)")
    conn.execute("INSERT INTO circuits (id, reference, name) VALUES (1, 'imola', 'Imola')")
    conn.executemany(
        "INSERT INTO drivers (id, reference, abbreviation, forename, surname, nationality) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "senna_h", "SEN", "Ayrton", "Senna", "Brazilian"),
            (2, "prost_h", "PRO", "Alain", "Prost", "French"),
            (3, "berger_h", "BER", "Gerhard", "Berger", "Austrian"),
        ],
    )
    conn.executemany(
        "INSERT INTO teams (id, reference, name) VALUES (?, ?, ?)",
        [(1, "mclaren", "McLaren"), (2, "ferrari", "Ferrari")],
    )
    conn.executemany(
        "INSERT INTO team_drivers (id, season_id, team_id, driver_id) VALUES (?, 1, ?, ?)",
        [(1, 1, 1), (2, 1, 2), (3, 2, 3)],
    )
    conn.execute(
        "INSERT INTO rounds (id, season_id, circuit_id, number, race_number, name, date, is_cancelled) VALUES (1, 1, 1, 1, 1, 'San Marino GP', '1988-05-01', 0)"
    )
    conn.executemany(
        "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, 1, ?, ?)",
        [(1, 1, 12), (2, 2, 11), (3, 3, 28)],
    )
    # Race + Friday QB + Saturday QB
    conn.executemany(
        "INSERT INTO sessions (id, round_id, type, number, is_cancelled) VALUES (?, 1, ?, ?, 0)",
        [(1, "R", 3), (2, "QB", 1), (3, "QB", 2)],
    )
    conn.executemany(
        "INSERT INTO session_entries (id, session_id, round_entry_id, position, is_classified, status, detail, grid, time_sec, laps_completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, 1, 1, 1, 1, 0, "Finished", 1, 5500.0, 60),
            (2, 1, 2, 2, 1, 0, "Finished", 2, 5502.3, 60),
            (3, 1, 3, 3, 1, 0, "Finished", 3, 5540.0, 60),
            # Quali session_entries have time_sec = NULL, just like Jolpica CSV dump
            (4, 2, 1, 1, None, None, None, None, None, None),
            (5, 2, 2, 2, None, None, None, None, None, None),
            (6, 2, 3, 3, None, None, None, None, None, None),
            (7, 3, 1, 1, None, None, None, None, None, None),
            (8, 3, 2, 2, None, None, None, None, None, None),
            (9, 3, 3, 3, None, None, None, None, None, None),
        ],
    )
    # Historical laps with number = NULL! Friday slower, Saturday faster for Senna
    conn.executemany(
        "INSERT INTO laps (id, session_entry_id, number, position, time_sec, is_deleted) VALUES (?, ?, NULL, ?, ?, 0)",
        [
            (1, 4, 1, 88.2),
            (2, 5, 2, 88.6),
            (3, 6, 3, 89.5),
            (4, 7, 1, 87.148),  # Faster Saturday QB
            (5, 8, 2, 87.919),
            (6, 9, 3, 89.100),
        ],
    )
    conn.commit()
    run_full_computation(conn)
    row = conn.execute(
        "SELECT quali_session_used, quali_teammate_delta_pct FROM race_driver_metrics WHERE driver_id = 1"
    ).fetchone()
    assert row["quali_session_used"] == "QB"
    assert row["quali_teammate_delta_pct"] is not None and row["quali_teammate_delta_pct"] > 0.7
    conn.close()


def test_classic_grid_fallback_and_survivor_racecraft():
    from app.engine.pillars.qualifying import compute_qualifying_metrics
    from app.engine.pillars.racecraft import compute_raw_racecraft_events, finalize_racecraft_scores

    # Pre-1994 grid fallback when no qualifying lap times exist
    qm = compute_qualifying_metrics(
        {},
        driver_teams={1: 10, 2: 10, 3: 20, 4: 20},
        driver_grids={1: 1, 2: 4, 3: 2, 4: 3},
    )
    assert qm[1]["quali_session_used"] == "GRID"
    assert qm[1]["quali_teammate_delta_pct"] > 0.5
    assert qm[2]["quali_teammate_delta_pct"] < -0.5

    # Survivor racecraft excludes mechanical DNF attrition ahead from inflating backmarkers
    entries = [
        {"driver_id": 1, "grid": 1, "position": 1, "status_category": "CLEAN_FINISH"},
        {"driver_id": 2, "grid": 2, "position": 10, "status_category": "MECHANICAL_DNF"},
        {"driver_id": 3, "grid": 3, "position": 2, "status_category": "CLEAN_FINISH"},
        {"driver_id": 4, "grid": 4, "position": 3, "status_category": "CLEAN_FINISH"},
    ]
    ev = compute_raw_racecraft_events(entries, {}, {}, set(), {})
    # Among clean finishers (drivers 1, 3, 4), driver 1 was grid_rank=1 -> fin_rank=1 (surv_gain=0),
    # driver 3 was grid_rank=2 -> fin_rank=2 (surv_gain=0, NOT +1 from driver 2's engine failure!)
    assert ev[1]["surv_gain"] == 0.0
    assert ev[3]["surv_gain"] == 0.0
    assert ev[4]["surv_gain"] == 0.0
    _, rc = finalize_racecraft_scores([
        {**ev[e["driver_id"]], "status_category": e["status_category"], "driver_fault_score": 0.0}
        for e in entries
    ])
    assert 0 in rc and 2 in rc and 3 in rc
