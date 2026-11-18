"""Circuit classification, wet-weather detection, uncertainty CI, specialty sub-ratings & badges."""

from __future__ import annotations

import math
import sqlite3

import numpy as np

STREET_CIRCUITS = {
    "monaco",
    "marina_bay",
    "baku",
    "jeddah",
    "vegas",
    "las_vegas",
    "miami",
    "albert_park",
    "adelaide",
    "detroit",
    "phoenix",
    "long_beach",
    "dallas",
    "montjuic",
    "boavista",
    "pescara",
    "pedralbes",
    "valencia",
    "sochi",
}

HIGH_SPEED_CIRCUITS = {
    "monza",
    "spa",
    "silverstone",
    "suzuka",
    "red_bull_ring",
    "oesterreichring",
    "watkins_glen",
    "interlagos",
    "villeneuve",
    "hockenheimring",
    "reims",
    "rouen",
    "zeltweg",
    "kyalami",
    "fuji",
    "indianapolis",
    "avus",
    "bremgarten",
}


def classify_circuit_type(circuit_ref: str | None, circuit_name: str | None = None) -> str:
    """Classify circuit into STREET, HIGH_SPEED, or TECHNICAL."""
    ref = (circuit_ref or "").strip().lower()
    if ref in STREET_CIRCUITS:
        return "STREET"
    if ref in HIGH_SPEED_CIRCUITS:
        return "HIGH_SPEED"
    lname = (circuit_name or "").lower()
    if any(k in lname for k in ("street", "las vegas", "jeddah", "baku", "marina bay", "monaco")):
        return "STREET"
    if any(k in lname for k in ("monza", "spa-francorchamps", "silverstone", "suzuka", "red bull ring")):
        return "HIGH_SPEED"
    return "TECHNICAL"


def detect_wet_rounds(conn: sqlite3.Connection) -> set[int]:
    """Identify wet/mixed-condition Grands Prix using tyre compounds and pace slowdowns."""
    wet_rounds: set[int] = set()

    # 1. Explicit INTERMEDIATE / WET stints from OpenF1 or FastF1
    for row in conn.execute(
        """
        SELECT round_id, COUNT(*) AS cnt
        FROM stint_enrichments
        WHERE compound IN ('INTERMEDIATE', 'WET')
        GROUP BY round_id
        HAVING cnt >= 4
        """
    ).fetchall():
        wet_rounds.add(int(row["round_id"]))

    # 2. Historical/modern winner avg lap time slowdown vs same circuit within +-3 years
    pace_rows = conn.execute(
        """
        SELECT r.id AS round_id, r.circuit_id, s.year,
               se.time_sec / se.laps_completed AS avg_lap
        FROM session_entries se
        JOIN sessions ss ON ss.id = se.session_id
        JOIN rounds r ON r.id = ss.round_id
        JOIN seasons s ON s.id = r.season_id
        WHERE ss.type = 'R' AND ss.is_cancelled = 0 AND r.is_cancelled = 0
          AND se.position = 1 AND se.laps_completed >= 10 AND se.time_sec > 600
          AND r.circuit_id IS NOT NULL
        """
    ).fetchall()

    by_circuit: dict[int, list[tuple[int, int, float]]] = {}
    for r in pace_rows:
        by_circuit.setdefault(int(r["circuit_id"]), []).append(
            (int(r["round_id"]), int(r["year"]), float(r["avg_lap"]))
        )

    for items in by_circuit.values():
        for rid, yr, avg_lap in items:
            nearby = [
                other_lap
                for other_rid, other_yr, other_lap in items
                if other_rid != rid and abs(other_yr - yr) <= 3
            ]
            if len(nearby) >= 2 and avg_lap >= 1.095 * min(nearby):
                wet_rounds.add(rid)

    # 3. Clean race median vs best qualifying lap slowdown (catches one-off wet classics like Donington 1993)
    q_best = {
        int(r["round_id"]): float(r["best_q"])
        for r in conn.execute(
            """
            SELECT ss.round_id, MIN(l.time_sec) AS best_q
            FROM laps l
            JOIN session_entries se ON se.id = l.session_entry_id
            JOIN sessions ss ON ss.id = se.session_id
            WHERE ss.type IN ('Q1','Q2','Q3','QB','QA') AND l.is_deleted = 0 AND l.time_sec BETWEEN 40 AND 240
            GROUP BY ss.round_id
            """
        ).fetchall()
        if r["best_q"] is not None
    }
    r_avg = {
        int(r["round_id"]): float(r["avg_r"])
        for r in conn.execute(
            """
            SELECT ss.round_id, MIN(se.time_sec / se.laps_completed) AS avg_r
            FROM session_entries se
            JOIN sessions ss ON ss.id = se.session_id
            WHERE ss.type = 'R' AND se.position = 1 AND se.laps_completed >= 15 AND se.time_sec > 600
            GROUP BY ss.round_id
            """
        ).fetchall()
        if r["avg_r"] is not None
    }
    for rid, r_lap in r_avg.items():
        q_lap = q_best.get(rid)
        if q_lap and r_lap >= 1.15 * q_lap:
            wet_rounds.add(rid)

    return wet_rounds


def compute_confidence_interval(eff_n: float, shrinkage_m: float = 10.0) -> float:
    """Compute 90% uncertainty interval (+/- sigma) on the 0-99 Overall scale."""
    n = max(float(eff_n), 0.0)
    ci = 1.645 * 6.0 * math.sqrt(
        0.18 * (shrinkage_m / (n + shrinkage_m)) + 0.65 / (n + 6.0)
    )
    return round(float(np.clip(ci, 0.5, 4.8)), 1)


def generate_driver_badges(
    wet_ovr: float,
    wet_n: int,
    street_ovr: float,
    street_n: int,
    high_speed_ovr: float,
    high_speed_n: int,
    tyre_mgmt_ovr: float,
    tyre_n: int,
    quali_ovr: float,
    racecraft_ovr: float,
    consistency_ovr: float,
) -> list[str]:
    """Select up to 4 prominent PT-BR specialization badges earned from objective thresholds."""
    candidates: list[tuple[float, str]] = []
    if wet_n >= 2 and wet_ovr >= 88.5:
        candidates.append((wet_ovr + 1.5, "Mestre da Chuva"))
    if street_n >= 3 and street_ovr >= 88.5:
        candidates.append((street_ovr + 1.0, "Rei das Ruas"))
    if high_speed_n >= 4 and high_speed_ovr >= 88.5:
        candidates.append((high_speed_ovr, "Especialista em Alta Velocidade"))
    if tyre_n >= 5 and tyre_mgmt_ovr >= 87.5:
        candidates.append((tyre_mgmt_ovr + 0.5, "Poupador de Pneus"))
    if quali_ovr >= 91.5:
        candidates.append((quali_ovr - 1.0, "Rei da Classificação"))
    if racecraft_ovr >= 90.5:
        candidates.append((racecraft_ovr - 1.0, "Combatente Nato"))
    if consistency_ovr >= 91.5:
        candidates.append((consistency_ovr - 1.5, "Metrônomo"))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [label for _, label in candidates[:4]]
