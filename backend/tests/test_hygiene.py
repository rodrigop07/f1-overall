"""Unit tests for Data Hygiene rules: DNF separation, SC/VSC neutralization & pit-lap filtering."""

from __future__ import annotations

from app.engine.hygiene import (
    classify_entry_status,
    filter_driver_clean_laps,
    identify_neutralized_laps,
    robust_mad,
    trimmed_mean,
)


def test_mechanical_dnfs_are_excluded_from_driver_fault():
    for status, detail in [
        (11, "Engine"),
        (11, "Gearbox"),
        (11, "Hydraulics"),
        (11, "Electrical"),
        (11, "Suspension"),
        (20, "Underweight"),
        (20, "Plank wear"),
    ]:
        cat, fault = classify_entry_status(status, detail, is_classified=0, has_driving_penalty=False)
        assert cat == "MECHANICAL_DNF", f"Expected MECHANICAL_DNF for {detail}"
        assert fault == 0.0


def test_driver_errors_and_penalties_are_penalized():
    cat1, fault1 = classify_entry_status(10, "Spun off", is_classified=0, has_driving_penalty=False)
    assert cat1 == "DRIVER_ERROR" and fault1 == 1.0

    cat2, fault2 = classify_entry_status(10, "Accident", is_classified=0, has_driving_penalty=False)
    assert cat2 == "DRIVER_ERROR" and fault2 == 1.0

    cat_col_pen, fault_col_pen = classify_entry_status(10, "Collision", is_classified=0, has_driving_penalty=True)
    assert cat_col_pen == "DRIVER_ERROR" and fault_col_pen == 1.0

    cat_col_amb, fault_col_amb = classify_entry_status(10, "Collision", is_classified=0, has_driving_penalty=False)
    assert cat_col_amb == "DRIVER_ERROR" and 0.5 <= fault_col_amb < 1.0

    cat_dmg, fault_dmg = classify_entry_status(10, "Collision damage", is_classified=0, has_driving_penalty=False)
    assert cat_dmg == "DRIVER_ERROR" and fault_dmg <= 0.25


def test_dns_and_clean_finish():
    assert classify_entry_status(30, "Withdrawn", 0, False) == ("DNS_OTHER", 0.0)
    assert classify_entry_status(0, "Finished", 1, False) == ("CLEAN_FINISH", 0.0)
    assert classify_entry_status(1, "+1 Lap", 1, False) == ("CLEAN_FINISH", 0.0)


def test_neutralized_and_pit_lap_filtering():
    # Normal laps ~90s, Lap 10 & 11 under Safety Car (~128s), Lap 15 explicit VSC
    laps_by_num = {ln: [90.0, 90.2, 89.8, 90.5] for ln in range(1, 21)}
    laps_by_num[1] = [96.0, 96.5, 97.0, 97.2]
    laps_by_num[10] = [128.0, 128.5, 127.8, 129.0]
    laps_by_num[11] = [125.0, 125.4, 124.9, 126.0]

    neutral, fmed, baseline = identify_neutralized_laps(laps_by_num, explicit_intervals=[(15, 15)])
    assert baseline is not None and 89.0 <= baseline <= 91.0
    assert {10, 11, 15}.issubset(neutral)

    # Driver pits on lap 6 -> lap 6 (in-lap) & lap 7 (out-lap) must be excluded; lap 1 is excluded
    driver_laps = [(ln, 90.0 if ln not in (6, 7, 10, 11, 15) else 108.0) for ln in range(1, 21)]
    clean, pit_ins = filter_driver_clean_laps(driver_laps, {6}, neutral, fmed, baseline)
    clean_nums = {x[0] for x in clean}
    assert 1 not in clean_nums
    assert 6 not in clean_nums
    assert 7 not in clean_nums
    assert 10 not in clean_nums
    assert 11 not in clean_nums
    assert 15 not in clean_nums
    assert 8 in clean_nums
    assert 6 in pit_ins

    # Check stint transition: lap 5 is stint 1, lap 8 is stint 2
    stints = {x[0]: x[2] for x in clean}
    assert stints[5] == 1
    assert stints[8] == 2


def test_robust_aggregators():
    vals = [90.0, 90.1, 89.9, 90.2, 140.0, 89.8, 90.0, 90.1, 89.9, 90.0]
    tm = trimmed_mean(vals, 0.10)
    assert tm is not None and abs(tm - 90.01) < 0.1
    mad = robust_mad(vals)
    assert mad is not None and mad < 0.3
