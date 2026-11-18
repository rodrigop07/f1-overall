"""Unit and integration tests for specialties, CI, Sprints, Race X-Ray, Lineages, Counterfactuals, and Portraits."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import config
from app.db.connection import get_connection
from app.db.schema import init_schema
from app.engine.pipeline import run_full_computation
from app.engine.specialties import (
    classify_circuit_type,
    compute_confidence_interval,
    detect_wet_rounds,
    generate_driver_badges,
)
from app.main import app


def test_circuit_classification_and_ci_and_badges():
    assert classify_circuit_type("monaco", "Circuit de Monaco") == "STREET"
    assert classify_circuit_type("monza", "Autodromo Nazionale di Monza") == "HIGH_SPEED"
    assert classify_circuit_type("hungaroring", "Hungaroring") == "TECHNICAL"
    assert classify_circuit_type(None, "Las Vegas Strip Street Circuit") == "STREET"

    ci_rookie = compute_confidence_interval(2.0)
    ci_mid = compute_confidence_interval(20.0)
    ci_vet = compute_confidence_interval(200.0)
    assert ci_rookie > ci_mid > ci_vet >= 0.5

    badges = generate_driver_badges(
        wet_ovr=94.0,
        wet_n=4,
        street_ovr=92.5,
        street_n=5,
        high_speed_ovr=91.0,
        high_speed_n=6,
        tyre_mgmt_ovr=90.0,
        tyre_n=8,
        quali_ovr=95.0,
        racecraft_ovr=93.0,
        consistency_ovr=94.0,
    )
    assert len(badges) == 4
    assert "Mestre da Chuva" in badges
    assert "Rei das Ruas" in badges


def test_detect_wet_rounds_both_compound_and_slowdown(tmp_path):
    db_file = tmp_path / "wet_test.sqlite"
    conn = get_connection(db_file)
    init_schema(conn)
    conn.executemany("INSERT INTO seasons (id, year) VALUES (?, ?)", [(1, 2022), (2, 2023), (3, 2024)])
    conn.execute("INSERT INTO circuits (id, reference, name) VALUES (1, 'spa', 'Spa')")
    conn.execute("INSERT INTO drivers (id, reference, forename, surname) VALUES (1, 'drv1', 'Max', 'V')")
    conn.execute("INSERT INTO teams (id, reference, name) VALUES (1, 'rbr', 'Red Bull')")
    conn.executemany(
        "INSERT INTO team_drivers (id, season_id, team_id, driver_id) VALUES (?, ?, 1, 1)",
        [(1, 1), (2, 2), (3, 3)],
    )
    conn.executemany(
        "INSERT INTO rounds (id, season_id, circuit_id, number, race_number, name, is_cancelled) VALUES (?, ?, 1, 1, 1, 'Belgian GP', 0)",
        [(1, 1), (2, 2), (3, 3)],
    )
    conn.executemany(
        "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, ?, ?, 1)",
        [(1, 1, 1), (2, 2, 2), (3, 3, 3)],
    )
    conn.executemany(
        "INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'R', 0)",
        [(1, 1), (2, 2), (3, 3)],
    )
    # Round 3 is ~15% slower average lap than dry rounds 1 & 2 (should detect slowdown as wet)
    # Round 1 gets explicit INTERMEDIATE stints (>=4 rows)
    conn.executemany(
        "INSERT INTO session_entries (id, session_id, round_entry_id, position, laps_completed, time_sec) VALUES (?, ?, ?, 1, 44, ?)",
        [(1, 1, 1, 4400.0), (2, 2, 2, 4420.0), (3, 3, 3, 5150.0)],
    )
    conn.executemany(
        "INSERT INTO stint_enrichments (round_id, driver_id, stint_number, lap_start, lap_end, compound, tyre_age_at_start, source) VALUES (1, 1, ?, ?, ?, 'INTERMEDIATE', 0, 'test')",
        [(1, 1, 10), (2, 11, 20), (3, 21, 30), (4, 31, 40)],
    )
    conn.commit()
    wet_ids = detect_wet_rounds(conn)
    conn.close()
    assert 1 in wet_ids
    assert 3 in wet_ids
    assert 2 not in wet_ids


def test_sprint_races_lineages_counterfactual_and_portraits_api(tmp_path, monkeypatch):
    db_file = tmp_path / "full_feature_test.sqlite"
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr("app.db.connection.DB_PATH", db_file)

    conn = get_connection(db_file)
    init_schema(conn)
    conn.execute("INSERT INTO seasons (id, year) VALUES (1, 2025)")
    conn.executemany(
        "INSERT INTO circuits (id, reference, name, country, locality) VALUES (?, ?, ?, ?, ?)",
        [(1, "monaco", "Circuit de Monaco", "Monaco", "Monte-Carlo"), (2, "monza", "Autodromo Monza", "Italy", "Monza")],
    )
    conn.executemany(
        "INSERT INTO drivers (id, reference, abbreviation, forename, surname, nationality, country_code, wikipedia) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "norris", "NOR", "Lando", "Norris", "British", "GBR", "https://en.wikipedia.org/wiki/Lando_Norris"),
            (2, "piastri", "PIA", "Oscar", "Piastri", "Australian", "AUS", "https://en.wikipedia.org/wiki/Oscar_Piastri"),
            (3, "leclerc", "LEC", "Charles", "Leclerc", "Monegasque", "MCO", "https://en.wikipedia.org/wiki/Charles_Leclerc"),
            (4, "hamilton", "HAM", "Lewis", "Hamilton", "British", "GBR", "https://en.wikipedia.org/wiki/Lewis_Hamilton"),
        ],
    )
    conn.executemany(
        "INSERT INTO teams (id, reference, name, primary_color) VALUES (?, ?, ?, ?)",
        [(1, "mclaren", "McLaren", "#FF8000"), (2, "ferrari", "Ferrari", "#E80020")],
    )
    conn.executemany(
        "INSERT INTO team_drivers (id, season_id, team_id, driver_id) VALUES (?, 1, ?, ?)",
        [(1, 1, 1), (2, 1, 2), (3, 2, 3), (4, 2, 4)],
    )

    re_id = 1
    se_id = 1
    sess_id = 1
    lap_id = 1
    # 2 rounds: R1 (street + sprint), R2 (high speed)
    for rnd_id, rnd_num, cid, name in [(1, 1, 1, "Monaco GP"), (2, 2, 2, "Italian GP")]:
        conn.execute(
            "INSERT INTO rounds (id, season_id, circuit_id, number, race_number, name, date, is_cancelled) VALUES (?, 1, ?, ?, ?, ?, ?, 0)",
            (rnd_id, cid, rnd_num, rnd_num, name, f"2025-05-0{rnd_num}"),
        )
        round_re_ids = {}
        for td_id, car_no in [(1, 4), (2, 81), (3, 16), (4, 44)]:
            conn.execute(
                "INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, ?, ?, ?)",
                (re_id, rnd_id, td_id, car_no),
            )
            round_re_ids[td_id] = re_id
            re_id += 1

        # Race & Quali Q3
        r_sess = sess_id
        q_sess = sess_id + 1
        conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'R', 0)", (r_sess, rnd_id))
        conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'Q3', 0)", (q_sess, rnd_id))
        sess_id += 2

        race_order = [(1, 1, 1, 4500.0, 25.0), (3, 2, 2, 4510.0, 18.0), (2, 3, 3, 4530.0, 15.0), (4, 4, 4, 4545.0, 12.0)]
        q_times = {1: 70.0, 3: 70.2, 2: 70.5, 4: 70.6}
        for td_id, pos, grid, t_tot, pts in race_order:
            r_se = se_id
            q_se = se_id + 1
            se_id += 2
            conn.execute(
                "INSERT INTO session_entries (id, session_id, round_entry_id, position, is_classified, status, detail, grid, time_sec, points, laps_completed) VALUES (?, ?, ?, ?, 1, 0, 'Finished', ?, ?, ?, 10)",
                (r_se, r_sess, round_re_ids[td_id], pos, grid, t_tot, pts),
            )
            conn.execute(
                "INSERT INTO session_entries (id, session_id, round_entry_id, position, time_sec) VALUES (?, ?, ?, ?, ?)",
                (q_se, q_sess, round_re_ids[td_id], grid, q_times[td_id]),
            )
            base_lap = t_tot / 10.0
            for ln in range(1, 11):
                conn.execute(
                    "INSERT INTO laps (id, session_entry_id, number, position, time_sec, is_deleted) VALUES (?, ?, ?, ?, ?, 0)",
                    (lap_id, r_se, ln, pos, base_lap + 0.05 * (ln % 2)),
                )
                lap_id += 1

        if rnd_id == 1:
            # Add Sprint Qualifying (SQ3) + Sprint Race (SR) on Round 1
            sq_sess = sess_id
            sr_sess = sess_id + 1
            sess_id += 2
            conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'SQ3', 0)", (sq_sess, rnd_id))
            conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (?, ?, 'SR', 0)", (sr_sess, rnd_id))
            for td_id, pos, st_t, sq_t in [(1, 1, 900.0, 70.1), (3, 2, 904.0, 70.3), (2, 3, 912.0, 70.6), (4, 4, 916.0, 70.8)]:
                sq_se = se_id
                sr_se = se_id + 1
                se_id += 2
                conn.execute("INSERT INTO session_entries (id, session_id, round_entry_id, position, time_sec) VALUES (?, ?, ?, ?, ?)", (sq_se, sq_sess, round_re_ids[td_id], pos, sq_t))
                conn.execute("INSERT INTO session_entries (id, session_id, round_entry_id, position, is_classified, status, grid, time_sec, laps_completed) VALUES (?, ?, ?, ?, 1, 0, ?, ?, 10)", (sr_se, sr_sess, round_re_ids[td_id], pos, pos, st_t))
                for ln in range(1, 11):
                    conn.execute("INSERT INTO laps (id, session_entry_id, number, position, time_sec, is_deleted) VALUES (?, ?, ?, ?, ?, 0)", (lap_id, sr_se, ln, pos, st_t / 10.0 + 0.04 * (ln % 2)))
                    lap_id += 1

    conn.commit()
    run_full_computation(conn)
    conn.commit()
    conn.close()

    # Mock httpx.get for portrait caching check
    fetch_calls = []

    def fake_httpx_get(url, **kwargs):
        fetch_calls.append(url)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"thumbnail": {"source": f"https://img.example.com/{url.rsplit('/', 1)[-1]}.jpg"}},
        )

    monkeypatch.setattr("app.api.routes.httpx.get", fake_httpx_get)

    with TestClient(app) as client:
        # 1. Races list + Race X-Ray (including Sprint deltas & weekend_score)
        r_list = client.get("/api/v1/races/2025")
        assert r_list.status_code == 200
        races = r_list.json()["races"]
        assert len(races) == 2
        assert races[0]["circuit_type"] == "STREET"
        assert races[1]["circuit_type"] == "HIGH_SPEED"

        r_xray = client.get("/api/v1/races/2025/1")
        assert r_xray.status_code == 200
        xray_body = r_xray.json()
        assert len(xray_body["drivers"]) == 4
        assert xray_body["drivers"][0]["sprint_quali_delta_pct"] is not None
        assert xray_body["drivers"][0]["sprint_pace_delta_pct"] is not None
        assert 60.0 <= xray_body["drivers"][0]["weekend_score"] <= 99.0

        # 2. Teams lineages + detail
        r_teams = client.get("/api/v1/teams")
        assert r_teams.status_code == 200
        slugs = [t["slug"] for t in r_teams.json()["lineages"]]
        assert "mclaren" in slugs and "ferrari" in slugs

        r_mcl = client.get("/api/v1/teams/mclaren")
        assert r_mcl.status_code == 200
        assert len(r_mcl.json()["timeline"]) == 1
        assert len(r_mcl.json()["hall_of_fame"]) == 2

        # 3. Counterfactual equal machinery + seat swap
        r_eq = client.get("/api/v1/counterfactual/season/2025")
        assert r_eq.status_code == 200
        assert len(r_eq.json()["standings"]) == 4

        r_swap = client.post(
            "/api/v1/counterfactual/seat-swap",
            json={"driver_ref": "leclerc", "target_team_id": 1, "year": 2025, "n_sims": 200},
        )
        assert r_swap.status_code == 200
        sw = r_swap.json()
        assert sw["driver"]["reference"] == "leclerc"
        assert 0.0 <= sw["driver"]["title_prob_pct"] <= 100.0
        assert len(sw["standings"]) == 4

        # 4. Portraits endpoint + cache verification (2nd request avoids HTTP call)
        r_p1 = client.get("/api/v1/portraits/norris")
        assert r_p1.status_code == 200
        assert "Lando_Norris.jpg" in r_p1.json()["thumbnail_url"]
        r_p2 = client.get("/api/v1/portraits/norris")
        assert r_p2.status_code == 200
        assert len(fetch_calls) == 1

        r_batch = client.get("/api/v1/portraits?refs=norris,piastri")
        assert r_batch.status_code == 200
        assert set(r_batch.json()["portraits"].keys()) == {"norris", "piastri"}
        assert len(fetch_calls) == 2
