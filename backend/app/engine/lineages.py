"""Constructor franchise lineages connecting historical F1 team evolutions (1950-2026)."""

from __future__ import annotations

import sqlite3

LINEAGE_DEFINITIONS: list[dict] = [
    {
        "slug": "ferrari",
        "name": "Scuderia Ferrari",
        "primary_color": "#E8002D",
        "refs": ["ferrari"],
    },
    {
        "slug": "mclaren",
        "name": "McLaren Racing",
        "primary_color": "#FF8000",
        "refs": ["mclaren", "mclaren-ford", "mclaren-brm", "mclaren-alfa_romeo"],
    },
    {
        "slug": "williams",
        "name": "Williams Racing",
        "primary_color": "#64C4FF",
        "refs": ["williams", "iso_marlboro"],
    },
    {
        "slug": "mercedes-tyrrell",
        "name": "Tyrrell → BAR → Honda → Brawn → Mercedes",
        "primary_color": "#27F4D2",
        "refs": ["tyrrell", "bar", "honda", "brawn", "mercedes"],
    },
    {
        "slug": "red-bull-stewart",
        "name": "Stewart → Jaguar → Red Bull Racing",
        "primary_color": "#3671C6",
        "refs": ["stewart", "jaguar", "red_bull"],
    },
    {
        "slug": "alpine-enstone",
        "name": "Toleman → Benetton → Renault → Lotus F1 → Alpine",
        "primary_color": "#00A1E8",
        "refs": ["toleman", "benetton", "renault", "lotus_f1", "alpine"],
    },
    {
        "slug": "aston-martin-silverstone",
        "name": "Jordan → MF1 → Spyker → Force India → Racing Point → Aston Martin",
        "primary_color": "#229971",
        "refs": ["jordan", "mf1", "spyker", "spyker_mf1", "force_india", "racing_point", "aston_martin"],
    },
    {
        "slug": "audi-sauber",
        "name": "Sauber → BMW Sauber → Alfa Romeo → Audi",
        "primary_color": "#52E252",
        "refs": ["sauber", "bmw_sauber", "audi"],
    },
    {
        "slug": "rb-faenza",
        "name": "Minardi → Toro Rosso → AlphaTauri → RB",
        "primary_color": "#6692FF",
        "refs": ["minardi", "toro_rosso", "alphatauri", "rb"],
    },
    {
        "slug": "team-lotus",
        "name": "Team Lotus (Clássica)",
        "primary_color": "#004225",
        "refs": ["team_lotus", "lotus-climax", "lotus-ford", "lotus-brm", "lotus-maserati"],
    },
    {
        "slug": "brabham",
        "name": "Brabham",
        "primary_color": "#0B3B2B",
        "refs": ["brabham", "brabham-repco", "brabham-climax", "brabham-alfa_romeo", "brabham-ford", "brabham-brm"],
    },
    {
        "slug": "cooper",
        "name": "Cooper Car Company",
        "primary_color": "#00593B",
        "refs": ["cooper", "cooper-climax", "cooper-maserati", "cooper-brm"],
    },
    {
        "slug": "haas",
        "name": "Haas F1 Team",
        "primary_color": "#B6BABD",
        "refs": ["haas"],
    },
    {
        "slug": "alfa-romeo",
        "name": "Alfa Romeo",
        "primary_color": "#9B0000",
        "refs": ["alfa"],
    },
    {
        "slug": "ligier-prost",
        "name": "Ligier → Prost",
        "primary_color": "#0066CC",
        "refs": ["ligier", "prost"],
    },
    {
        "slug": "brm",
        "name": "BRM",
        "primary_color": "#004D33",
        "refs": ["brm"],
    },
    {
        "slug": "arrows",
        "name": "Arrows → Footwork",
        "primary_color": "#FF6A00",
        "refs": ["arrows", "footwork"],
    },
    {
        "slug": "march-leyton",
        "name": "March → Leyton House",
        "primary_color": "#2CD4D9",
        "refs": ["march", "leyton"],
    },
    {
        "slug": "toyota",
        "name": "Toyota Racing",
        "primary_color": "#EB0A1E",
        "refs": ["toyota"],
    },
    {
        "slug": "matra",
        "name": "Matra",
        "primary_color": "#1E6BFF",
        "refs": ["matra", "matra-ford"],
    },
    {
        "slug": "maserati",
        "name": "Maserati",
        "primary_color": "#A61C1C",
        "refs": ["maserati"],
    },
    {
        "slug": "cadillac",
        "name": "Cadillac F1 Team",
        "primary_color": "#AAAAAD",
        "refs": ["cadillac"],
    },
]

_REF_TO_LINEAGE: dict[str, dict] = {}
_SLUG_TO_LINEAGE: dict[str, dict] = {}
for _lin in LINEAGE_DEFINITIONS:
    _SLUG_TO_LINEAGE[_lin["slug"]] = _lin
    for _ref in _lin["refs"]:
        _REF_TO_LINEAGE[_ref] = _lin


def list_lineages(conn: sqlite3.Connection) -> list[dict]:
    """Return summary cards for all constructor lineages sorted by wins & peak car rating."""
    teams_by_ref = {
        r["reference"]: dict(r)
        for r in conn.execute("SELECT id, reference, name, primary_color FROM teams WHERE reference IS NOT NULL").fetchall()
    }
    car_rows = conn.execute("SELECT year, team_id, team_name, car_rating FROM car_season_ratings").fetchall()
    cars_by_tid: dict[int, list[dict]] = {}
    for c in car_rows:
        cars_by_tid.setdefault(int(c["team_id"]), []).append(dict(c))

    # Driver stats per team_id
    drv_team_stats = conn.execute(
        """
        SELECT m.team_id, m.driver_id, d.reference, d.forename || ' ' || d.surname AS name,
               COUNT(*) AS starts,
               SUM(CASE WHEN m.finish_pos = 1 THEN 1 ELSE 0 END) AS wins,
               MAX(sr.overall_raw) AS peak_ovr
        FROM race_driver_metrics m
        JOIN drivers d ON d.id = m.driver_id
        LEFT JOIN driver_season_ratings sr ON sr.driver_id = m.driver_id AND sr.year = m.year AND sr.mode = 'season'
        WHERE m.status_category != 'DNS_OTHER'
        GROUP BY m.team_id, m.driver_id
        """
    ).fetchall()
    drv_by_tid: dict[int, list[dict]] = {}
    for r in drv_team_stats:
        drv_by_tid.setdefault(int(r["team_id"]), []).append(dict(r))

    out: list[dict] = []
    for lin in LINEAGE_DEFINITIONS:
        tids = [int(teams_by_ref[ref]["id"]) for ref in lin["refs"] if ref in teams_by_ref]
        if not tids:
            continue
        era_names = []
        seen_names = set()
        for ref in lin["refs"]:
            if ref in teams_by_ref:
                nm = teams_by_ref[ref]["name"]
                if nm not in seen_names:
                    seen_names.add(nm)
                    era_names.append(nm)

        yr_cars: dict[int, float] = {}
        for tid in tids:
            for c in cars_by_tid.get(tid, []):
                yr = int(c["year"])
                # Avoid double-counting same year if duplicate ref; keep max
                yr_cars[yr] = max(yr_cars.get(yr, 0.0), float(c["car_rating"]))

        if not yr_cars:
            continue

        # Aggregate driver wins & top driver in lineage
        wins_total = 0
        starts_total = 0
        by_drv: dict[int, dict] = {}
        for tid in tids:
            for drow in drv_by_tid.get(tid, []):
                wins_total += int(drow["wins"] or 0)
                starts_total += int(drow["starts"] or 0)
                did = int(drow["driver_id"])
                cur = by_drv.get(did)
                if cur is None:
                    by_drv[did] = {
                        "name": drow["name"],
                        "reference": drow["reference"],
                        "starts": int(drow["starts"]),
                        "wins": int(drow["wins"] or 0),
                        "peak_ovr": float(drow["peak_ovr"] or 80.0),
                    }
                else:
                    cur["starts"] += int(drow["starts"])
                    cur["wins"] += int(drow["wins"] or 0)
                    cur["peak_ovr"] = max(cur["peak_ovr"], float(drow["peak_ovr"] or 80.0))

        top_drv = None
        if by_drv:
            # Top representative driver with >= 10 starts if available
            cands = [v for v in by_drv.values() if v["starts"] >= 10] or list(by_drv.values())
            top_drv = max(cands, key=lambda v: (v["wins"] * 0.4 + v["peak_ovr"]))

        years = sorted(yr_cars.keys())
        ratings = list(yr_cars.values())
        out.append(
            {
                "slug": lin["slug"],
                "name": lin["name"],
                "primary_color": lin["primary_color"],
                "era_names": era_names,
                "first_year": years[0],
                "last_year": years[-1],
                "seasons_count": len(years),
                "total_starts": starts_total,
                "race_wins": wins_total,
                "peak_car_rating": round(max(ratings), 1),
                "avg_car_rating": round(sum(ratings) / len(ratings), 1),
                "top_driver_name": top_drv["name"] if top_drv else None,
                "top_driver_ref": top_drv["reference"] if top_drv else None,
            }
        )

    out.sort(key=lambda x: (x["race_wins"], x["peak_car_rating"], x["seasons_count"]), reverse=True)
    return out


def get_lineage_detail(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Return full yearly car_rating history and Hall of Fame drivers for a constructor lineage."""
    lin = _SLUG_TO_LINEAGE.get(slug)
    if not lin:
        return None

    teams_rows = conn.execute(
        f"""
        SELECT id, reference, name, primary_color
        FROM teams
        WHERE reference IN ({','.join('?' for _ in lin['refs'])})
        """,
        lin["refs"],
    ).fetchall()
    tids = [int(r["id"]) for r in teams_rows]
    if not tids:
        return None

    placeholders = ",".join("?" for _ in tids)
    car_history = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT year, team_id, team_name, team_color, car_rating, pace_car_pct, quali_car_pct
            FROM car_season_ratings
            WHERE team_id IN ({placeholders})
            ORDER BY year ASC
            """,
            tids,
        ).fetchall()
    ]

    # Deduplicate same year if multiple classic chassis refs existed in the same year
    by_year: dict[int, dict] = {}
    for ch in car_history:
        yr = int(ch["year"])
        if yr not in by_year or ch["car_rating"] > by_year[yr]["car_rating"]:
            by_year[yr] = ch
    timeline = [by_year[y] for y in sorted(by_year.keys())]

    hall_of_fame = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT
                d.id AS driver_id, d.reference, d.forename || ' ' || d.surname AS name,
                d.nationality, d.country_code,
                MIN(m.year) AS first_year, MAX(m.year) AS last_year,
                COUNT(*) AS starts_for_team,
                SUM(CASE WHEN m.finish_pos = 1 THEN 1 ELSE 0 END) AS wins_for_team,
                SUM(CASE WHEN m.finish_pos IN (1, 2, 3) THEN 1 ELSE 0 END) AS podiums_for_team,
                ROUND(MAX(sr.overall_raw), 1) AS peak_stint_ovr,
                a.overall AS alltime_overall
            FROM race_driver_metrics m
            JOIN drivers d ON d.id = m.driver_id
            LEFT JOIN driver_season_ratings sr ON sr.driver_id = m.driver_id AND sr.year = m.year AND sr.mode = 'season'
            LEFT JOIN driver_alltime_ratings a ON a.driver_id = m.driver_id
            WHERE m.team_id IN ({placeholders}) AND m.status_category != 'DNS_OTHER'
            GROUP BY d.id
            ORDER BY wins_for_team DESC, peak_stint_ovr DESC, starts_for_team DESC
            LIMIT 16
            """,
            tids,
        ).fetchall()
    ]

    return {
        "slug": lin["slug"],
        "name": lin["name"],
        "primary_color": lin["primary_color"],
        "era_names": [r["name"] for r in teams_rows],
        "timeline": timeline,
        "hall_of_fame": hall_of_fame,
    }
