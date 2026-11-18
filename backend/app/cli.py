"""CLI entrypoint for ingesting F1 data, computing ratings, and auditing results."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from app.db.connection import db_session
from app.db.schema import init_schema
from app.engine.pipeline import run_full_computation
from app.ingestion.fastf1_ingestor import enrich_from_fastf1
from app.ingestion.jolpica_dump import download_jolpica_dump, load_jolpica_dump_into_db
from app.ingestion.jolpica_incremental import sync_missing_recent_rounds
from app.ingestion.openf1_ingestor import enrich_from_openf1

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("f1-overall-cli")


def cmd_bootstrap(args: argparse.Namespace) -> None:
    logger.info("1/5 Downloading/verifying Jolpica-F1 official CSV dump (1950-2026)...")
    zip_path, dump_info = download_jolpica_dump(force=args.force_dump)
    logger.info("Dump verified (%s, uploaded_at=%s).", zip_path.name, dump_info.get("uploaded_at"))

    with db_session() as conn:
        init_schema(conn)
        logger.info("2/5 Loading historical CSV tables into SQLite...")
        counts = load_jolpica_dump_into_db(conn, zip_path, dump_info)
        conn.commit()
        logger.info("Loaded counts: %s", counts)

        logger.info("3/5 Syncing incremental 2026 rounds via Jolpica REST API...")
        inc = sync_missing_recent_rounds(conn, year=2026)
        conn.commit()
        logger.info("Incremental sync: %s", inc)

        logger.info("4/5 Enriching 2023-2026 compounds, SC/VSC & FIA penalties via OpenF1...")
        of1 = enrich_from_openf1(conn)
        conn.commit()
        logger.info("OpenF1 enrichment: %s", of1)

        if not args.skip_fastf1:
            ff1 = enrich_from_fastf1(conn)
            conn.commit()
            logger.info("FastF1 enrichment: %s", ff1)

        logger.info("5/5 Running full Network LMM + 5-Pillar + Bayesian Shrinkage computation...")
        diag = run_full_computation(conn)
        conn.commit()
        logger.info("Computation finished! Coverage: %s", diag["coverage_stats"])


def cmd_sync(args: argparse.Namespace) -> None:
    with db_session() as conn:
        init_schema(conn)
        inc = sync_missing_recent_rounds(conn, year=args.year)
        logger.info("Incremental sync: %s", inc)
        of1 = enrich_from_openf1(conn, years=(args.year,))
        logger.info("OpenF1 enrichment: %s", of1)
        diag = run_full_computation(conn)
        logger.info("Recomputation finished: %s", diag["coverage_stats"])


def cmd_recompute(_args: argparse.Namespace) -> None:
    with db_session() as conn:
        init_schema(conn)
        diag = run_full_computation(conn)
        logger.info("Recomputation complete: %s", diag["coverage_stats"])


def cmd_sync_fastf1(args: argparse.Namespace) -> None:
    with db_session() as conn:
        init_schema(conn)
        res = enrich_from_fastf1(conn, force_live=True)
        logger.info("FastF1 sync result: %s", res)
        if res.get("sessions_enriched", 0) > 0:
            run_full_computation(conn)


def cmd_audit(_args: argparse.Namespace) -> None:
    with db_session() as conn:
        diag_rows = {
            r["key"]: json.loads(r["value_json"])
            for r in conn.execute("SELECT key, value_json FROM model_diagnostics").fetchall()
        }
        cov = diag_rows.get("coverage_stats", {})
        vd = diag_rows.get("variance_decomposition", {})
        print("=== COVERAGE ===")
        print(json.dumps(cov, indent=2))
        print("\n=== VARIANCE DECOMPOSITION (CAR VS DRIVER) ===")
        print(json.dumps(vd, indent=2))

        max_yr = cov.get("latest_season", 2026)
        print(f"\n=== TOP 15 CURRENT GRID ({max_yr} ROLLING FORM) ===")
        for i, r in enumerate(
            conn.execute(
                """
                SELECT d.forename || ' ' || d.surname AS name, sr.team_name, sr.overall, sr.overall_raw,
                       sr.pace_ovr, sr.quali_ovr, sr.consistency_ovr, sr.racecraft_ovr, sr.experience_ovr,
                       sr.car_rating, sr.races_count, sr.shrinkage_weight
                FROM driver_season_ratings sr
                JOIN drivers d ON d.id = sr.driver_id
                WHERE sr.year = ? AND sr.mode = 'rolling_current'
                ORDER BY sr.overall_raw DESC
                LIMIT 15
                """,
                (max_yr,),
            ).fetchall(),
            start=1,
        ):
            print(
                f"{i:2d}. {r['name']:24s} ({r['team_name']:18s}) | OVR {r['overall']:2d} ({r['overall_raw']:5.2f}) "
                f"| P:{r['pace_ovr']:4.1f} Q:{r['quali_ovr']:4.1f} C:{r['consistency_ovr']:4.1f} R:{r['racecraft_ovr']:4.1f} E:{r['experience_ovr']:4.1f} "
                f"| Car:{r['car_rating']:4.1f} | n={r['races_count']} w={r['shrinkage_weight']:.2f}"
            )

        print("\n=== TOP 20 ALL-TIME HISTORICAL (1950-2026) ===")
        for i, r in enumerate(
            conn.execute(
                """
                SELECT d.forename || ' ' || d.surname AS name, a.first_year, a.last_year, a.peak_years,
                       a.overall, a.overall_raw, a.peak_overall, a.championships, a.career_wins, a.career_starts,
                       a.pace_ovr, a.quali_ovr, a.consistency_ovr, a.racecraft_ovr, a.experience_ovr
                FROM driver_alltime_ratings a
                JOIN drivers d ON d.id = a.driver_id
                ORDER BY a.overall_raw DESC, a.career_wins DESC, a.career_starts DESC
                LIMIT 20
                """
            ).fetchall(),
            start=1,
        ):
            print(
                f"{i:2d}. {r['name']:24s} ({r['first_year']}-{r['last_year']}, peak {r['peak_years']}) "
                f"| OVR {r['overall']:2d} ({r['overall_raw']:5.2f}, Peak {r['peak_overall']:5.2f}) "
                f"| WDC:{r['championships']} Wins:{r['career_wins']:3d}/{r['career_starts']:3d} "
                f"| P:{r['pace_ovr']:4.1f} Q:{r['quali_ovr']:4.1f} C:{r['consistency_ovr']:4.1f} R:{r['racecraft_ovr']:4.1f}"
            )

        # Sanity stats
        stats = conn.execute(
            """
            SELECT AVG(overall_raw) AS mean_ovr, MIN(overall_raw) AS min_ovr, MAX(overall_raw) AS max_ovr
            FROM driver_season_ratings WHERE year = ? AND mode = 'rolling_current'
            """,
            (max_yr,),
        ).fetchone()
        print(f"\nCurrent Grid Mean={stats['mean_ovr']:.2f}, Min={stats['min_ovr']:.2f}, Max={stats['max_ovr']:.2f}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="F1 Driver Overall Engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap", help="Full historical download, enrichment & model computation")
    p_boot.add_argument("--force-dump", action="store_true", help="Force re-download of Jolpica dump")
    p_boot.add_argument("--skip-fastf1", action="store_true", help="Skip FastF1 live/cache enrichment")
    p_boot.set_defaults(func=cmd_bootstrap)

    p_sync = sub.add_parser("sync", help="Incremental REST + OpenF1 sync for latest season")
    p_sync.add_argument("--year", type=int, default=2026)
    p_sync.set_defaults(func=cmd_sync)

    p_rec = sub.add_parser("recompute", help="Recompute statistical model from existing SQLite DB")
    p_rec.set_defaults(func=cmd_recompute)

    p_ff1 = sub.add_parser("sync-fastf1", help="Enrich 2018-2026 with FastF1 (requires F1 TV auth or cache)")
    p_ff1.set_defaults(func=cmd_sync_fastf1)

    p_aud = sub.add_parser("audit", help="Print statistical audit and top rankings")
    p_aud.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
