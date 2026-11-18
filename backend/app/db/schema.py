"""SQLite relational schema for raw F1 tables and computed analytical ratings."""

from __future__ import annotations

import sqlite3

RAW_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY,
    year INTEGER UNIQUE NOT NULL,
    wikipedia TEXT
);

CREATE TABLE IF NOT EXISTS circuits (
    id INTEGER PRIMARY KEY,
    reference TEXT,
    name TEXT NOT NULL,
    country TEXT,
    country_code TEXT,
    locality TEXT
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY,
    reference TEXT UNIQUE NOT NULL,
    api_id TEXT,
    abbreviation TEXT,
    forename TEXT NOT NULL,
    surname TEXT NOT NULL,
    date_of_birth TEXT,
    nationality TEXT,
    country_code TEXT,
    permanent_car_number INTEGER,
    wikipedia TEXT
);

CREATE TABLE IF NOT EXISTS base_teams (
    id INTEGER PRIMARY KEY,
    api_id TEXT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    reference TEXT,
    api_id TEXT,
    base_team_id INTEGER,
    name TEXT NOT NULL,
    nationality TEXT,
    country_code TEXT,
    primary_color TEXT,
    wikipedia TEXT
);

CREATE TABLE IF NOT EXISTS team_drivers (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    role INTEGER
);

CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    circuit_id INTEGER,
    number INTEGER,
    race_number INTEGER,
    name TEXT NOT NULL,
    date TEXT,
    is_cancelled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS round_entries (
    id INTEGER PRIMARY KEY,
    round_id INTEGER NOT NULL,
    team_driver_id INTEGER NOT NULL,
    car_number INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    round_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    number INTEGER,
    scheduled_laps INTEGER,
    completed_laps INTEGER,
    timestamp TEXT,
    is_cancelled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session_entries (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    round_entry_id INTEGER NOT NULL,
    position INTEGER,
    is_classified INTEGER,
    status INTEGER,
    detail TEXT,
    points REAL,
    grid INTEGER,
    time_sec REAL,
    laps_completed INTEGER,
    fastest_lap_rank INTEGER
);

CREATE TABLE IF NOT EXISTS laps (
    id INTEGER PRIMARY KEY,
    session_entry_id INTEGER NOT NULL,
    number INTEGER,
    position INTEGER,
    time_sec REAL,
    is_deleted INTEGER DEFAULT 0,
    is_entry_fastest_lap INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pit_stops (
    id INTEGER PRIMARY KEY,
    session_entry_id INTEGER NOT NULL,
    number INTEGER,
    lap_id INTEGER,
    duration_sec REAL
);

CREATE TABLE IF NOT EXISTS penalties (
    id INTEGER PRIMARY KEY,
    earned_id INTEGER,
    served_id INTEGER,
    license_points INTEGER,
    position INTEGER,
    time_sec REAL,
    is_time_served_in_pit INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS driver_championships (
    id INTEGER PRIMARY KEY,
    driver_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    round_id INTEGER,
    position INTEGER,
    points REAL,
    win_count INTEGER,
    year INTEGER,
    round_number INTEGER,
    session_number INTEGER
);

CREATE TABLE IF NOT EXISTS stint_enrichments (
    round_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    stint_number INTEGER NOT NULL,
    lap_start INTEGER,
    lap_end INTEGER,
    compound TEXT,
    tyre_age_at_start INTEGER DEFAULT 0,
    source TEXT NOT NULL,
    PRIMARY KEY (round_id, driver_id, stint_number)
);

CREATE TABLE IF NOT EXISTS track_neutralizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    lap_start INTEGER NOT NULL,
    lap_end INTEGER NOT NULL,
    status_type TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS openf1_penalties (
    round_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    penalty_count INTEGER NOT NULL DEFAULT 0,
    messages_json TEXT NOT NULL,
    PRIMARY KEY (round_id, driver_id)
);

CREATE TABLE IF NOT EXISTS ingestion_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

COMPUTED_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS race_driver_metrics (
    round_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    round_number INTEGER,
    round_name TEXT,
    round_date TEXT,
    grid INTEGER,
    finish_pos INTEGER,
    points REAL,
    status_category TEXT NOT NULL,
    driver_fault_score REAL DEFAULT 0.0,
    fia_driving_penalties INTEGER DEFAULT 0,
    quali_session_used TEXT,
    quali_teammate_delta_pct REAL,
    quali_perf_pct REAL,
    clean_air_laps INTEGER DEFAULT 0,
    clean_laps_total INTEGER DEFAULT 0,
    pace_residual_pct REAL,
    stint_deg_bonus_pct REAL DEFAULT 0.0,
    pace_teammate_delta_pct REAL,
    pace_isolated REAL,
    quali_isolated REAL,
    pace_sample_weight REAL DEFAULT 1.0,
    stint_mad_pct REAL,
    consistency_error_score REAL,
    consistency_variance_score REAL,
    lap1_pos INTEGER,
    lap1_net_gain REAL,
    on_track_overtakes INTEGER DEFAULT 0,
    on_track_overtaken INTEGER DEFAULT 0,
    defense_laps INTEGER DEFAULT 0,
    racecraft_score REAL,
    cumulative_starts INTEGER DEFAULT 1,
    age_years REAL,
    data_tier TEXT NOT NULL,
    PRIMARY KEY (round_id, driver_id)
);

CREATE TABLE IF NOT EXISTS driver_season_ratings (
    year INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    team_id INTEGER,
    team_name TEXT,
    team_color TEXT,
    races_count INTEGER NOT NULL,
    clean_races_count INTEGER NOT NULL,
    overall INTEGER NOT NULL,
    overall_raw REAL NOT NULL,
    z_final REAL NOT NULL,
    pace_ovr REAL NOT NULL,
    quali_ovr REAL NOT NULL,
    consistency_ovr REAL NOT NULL,
    racecraft_ovr REAL NOT NULL,
    experience_ovr REAL NOT NULL,
    z_pace REAL NOT NULL,
    z_quali REAL NOT NULL,
    z_consistency REAL NOT NULL,
    z_racecraft REAL NOT NULL,
    z_experience REAL NOT NULL,
    car_rating REAL NOT NULL,
    shrinkage_weight REAL NOT NULL,
    delta_vs_prev REAL,
    data_tier TEXT NOT NULL,
    PRIMARY KEY (year, driver_id, mode)
);

CREATE TABLE IF NOT EXISTS driver_alltime_ratings (
    driver_id INTEGER PRIMARY KEY,
    career_starts INTEGER NOT NULL,
    career_wins INTEGER NOT NULL,
    career_podiums INTEGER NOT NULL,
    championships INTEGER NOT NULL,
    first_year INTEGER NOT NULL,
    last_year INTEGER NOT NULL,
    peak_years TEXT,
    primary_team_name TEXT,
    primary_team_color TEXT,
    overall INTEGER NOT NULL,
    overall_raw REAL NOT NULL,
    peak_overall REAL NOT NULL,
    longevity_overall REAL NOT NULL,
    pace_ovr REAL NOT NULL,
    quali_ovr REAL NOT NULL,
    consistency_ovr REAL NOT NULL,
    racecraft_ovr REAL NOT NULL,
    experience_ovr REAL NOT NULL,
    z_pace REAL NOT NULL,
    z_quali REAL NOT NULL,
    z_consistency REAL NOT NULL,
    z_racecraft REAL NOT NULL,
    z_experience REAL NOT NULL,
    mechanical_dnfs_excluded INTEGER DEFAULT 0,
    driver_error_dnfs INTEGER DEFAULT 0,
    fia_penalties_count INTEGER DEFAULT 0,
    clean_air_laps_total INTEGER DEFAULT 0,
    data_tier TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS car_season_ratings (
    year INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    team_color TEXT,
    car_rating REAL NOT NULL,
    pace_car_pct REAL NOT NULL,
    quali_car_pct REAL NOT NULL,
    PRIMARY KEY (year, team_id)
);

CREATE TABLE IF NOT EXISTS teammate_network_edges (
    driver_a_id INTEGER NOT NULL,
    driver_b_id INTEGER NOT NULL,
    shared_races INTEGER NOT NULL,
    shared_quali INTEGER NOT NULL,
    seasons_json TEXT NOT NULL,
    teams_json TEXT NOT NULL,
    median_quali_delta_pct REAL,
    median_pace_delta_pct REAL,
    quali_wins_a INTEGER DEFAULT 0,
    quali_wins_b INTEGER DEFAULT 0,
    race_wins_a INTEGER DEFAULT 0,
    race_wins_b INTEGER DEFAULT 0,
    PRIMARY KEY (driver_a_id, driver_b_id)
);

CREATE TABLE IF NOT EXISTS model_diagnostics (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_drivers_reference ON drivers(reference);
CREATE INDEX IF NOT EXISTS idx_team_drivers_season ON team_drivers(season_id, team_id, driver_id);
CREATE INDEX IF NOT EXISTS idx_rounds_season ON rounds(season_id, number);
CREATE INDEX IF NOT EXISTS idx_round_entries_round ON round_entries(round_id, team_driver_id);
CREATE INDEX IF NOT EXISTS idx_sessions_round_type ON sessions(round_id, type);
CREATE INDEX IF NOT EXISTS idx_session_entries_session ON session_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_session_entries_round_entry ON session_entries(round_entry_id);
CREATE INDEX IF NOT EXISTS idx_laps_se_num ON laps(session_entry_id, number);
CREATE INDEX IF NOT EXISTS idx_pit_stops_se ON pit_stops(session_entry_id);
CREATE INDEX IF NOT EXISTS idx_pit_stops_lap ON pit_stops(lap_id);
CREATE INDEX IF NOT EXISTS idx_penalties_earned ON penalties(earned_id);
CREATE INDEX IF NOT EXISTS idx_stint_enrich_round ON stint_enrichments(round_id, driver_id);
CREATE INDEX IF NOT EXISTS idx_neutralizations_round ON track_neutralizations(round_id);
CREATE INDEX IF NOT EXISTS idx_rdm_year_driver ON race_driver_metrics(year, driver_id);
CREATE INDEX IF NOT EXISTS idx_dsr_year_mode ON driver_season_ratings(year, mode, overall_raw DESC);
CREATE INDEX IF NOT EXISTS idx_edges_a ON teammate_network_edges(driver_a_id);
CREATE INDEX IF NOT EXISTS idx_edges_b ON teammate_network_edges(driver_b_id);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all raw and analytical tables and indexes if absent."""
    conn.executescript(RAW_TABLES_SQL)
    conn.executescript(COMPUTED_TABLES_SQL)
    conn.executescript(INDEXES_SQL)


def reset_computed_tables(conn: sqlite3.Connection) -> None:
    """Clear computed analytical tables before recomputation."""
    for table in (
        "race_driver_metrics",
        "driver_season_ratings",
        "driver_alltime_ratings",
        "car_season_ratings",
        "teammate_network_edges",
        "model_diagnostics",
    ):
        conn.execute(f"DELETE FROM {table}")
