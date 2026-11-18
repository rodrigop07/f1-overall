"""Integration tests for FastAPI REST endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import config
from app.db.connection import get_connection
from app.db.schema import init_schema
from app.engine.pipeline import run_full_computation
from app.main import app


def test_api_endpoints_with_isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "api_test.sqlite"
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr("app.db.connection.DB_PATH", db_file)

    conn = get_connection(db_file)
    init_schema(conn)
    conn.execute("INSERT INTO seasons (id, year) VALUES (1, 2026)")
    conn.execute("INSERT INTO circuits (id, reference, name) VALUES (1, 'monza', 'Monza')")
    conn.executemany(
        "INSERT INTO drivers (id, reference, abbreviation, forename, surname, nationality) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "senna_test", "SEN", "Ayrton", "Senna", "Brazilian"),
            (2, "prost_test", "PRO", "Alain", "Prost", "French"),
        ],
    )
    conn.execute("INSERT INTO teams (id, reference, name, primary_color) VALUES (1, 'mclaren', 'McLaren', '#FF8000')")
    conn.executemany("INSERT INTO team_drivers (id, season_id, team_id, driver_id) VALUES (?, 1, 1, ?)", [(1, 1), (2, 2)])
    conn.execute("INSERT INTO rounds (id, season_id, circuit_id, number, race_number, name, date, is_cancelled) VALUES (1, 1, 1, 1, 1, 'Italian GP', '2026-09-06', 0)")
    conn.executemany("INSERT INTO round_entries (id, round_id, team_driver_id, car_number) VALUES (?, 1, ?, ?)", [(1, 1, 12), (2, 2, 11)])
    conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (1, 1, 'R', 0)")
    conn.execute("INSERT INTO sessions (id, round_id, type, is_cancelled) VALUES (2, 1, 'Q3', 0)")
    conn.executemany(
        "INSERT INTO session_entries (id, session_id, round_entry_id, position, is_classified, status, detail, grid, time_sec, laps_completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, 1, 1, 1, 1, 0, "Finished", 1, 5000.0, 53),
            (2, 1, 2, 2, 1, 0, "Finished", 2, 5012.0, 53),
            (3, 2, 1, 1, None, None, None, None, 80.1, None),
            (4, 2, 2, 2, None, None, None, None, 80.5, None),
        ],
    )
    conn.commit()
    run_full_computation(conn)
    conn.commit()
    conn.close()

    with TestClient(app) as client:
        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        assert r_health.json()["drivers_rated"] == 2

        r_curr = client.get("/api/v1/rankings/current")
        assert r_curr.status_code == 200
        assert len(r_curr.json()["drivers"]) == 2

        r_all = client.get("/api/v1/rankings/alltime")
        assert r_all.status_code == 200
        assert r_all.json()["total"] == 2

        r_prof = client.get("/api/v1/drivers/senna_test")
        assert r_prof.status_code == 200
        assert len(r_prof.json()["teammates"]) == 1

        r_comp = client.get("/api/v1/compare?driver_a=senna_test&driver_b=prost_test")
        assert r_comp.status_code == 200
        assert len(r_comp.json()["calibration_path"]) == 1

        r_net = client.get("/api/v1/network?min_shared_races=1&path_from=senna_test&path_to=prost_test")
        assert r_net.status_code == 200
        assert len(r_net.json()["nodes"]) == 2

        r_sim = client.post(
            "/api/v1/simulate",
            json={
                "scope": "current",
                "weights": {"pace": 0.5, "qualifying": 0.3, "consistency": 0.1, "racecraft": 0.05, "experience": 0.05},
                "shrinkage_m": 5.0,
            },
        )
        assert r_sim.status_code == 200
        assert r_sim.json()["elapsed_ms"] < 200.0
