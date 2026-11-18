"""Data Hygiene: DNF classification, FIA penalty extraction, and anomalous lap filtering."""

from __future__ import annotations

import numpy as np

_TECH_DSQ_KEYWORDS = (
    "underweight",
    "weight",
    "plank",
    "skid",
    "fuel",
    "wing",
    "technical",
    "exhaust",
    "floor",
    "diffuser",
    "tyre",
    "tire",
    "drs",
    "ride height",
    "car",
)

_DRIVING_DSQ_KEYWORDS = (
    "ignored",
    "black flag",
    "dangerous",
    "collision",
    "pit exit",
    "red light",
    "unsportsmanlike",
    "reversing",
)

_DNS_KEYWORDS = (
    "withdrawn",
    "did not start",
    "did not qualify",
    "did not prequalify",
    "injury",
    "injured",
    "illness",
    "ill",
    "not restarted",
    "excluded",
)


def robust_median(values: np.ndarray | list[float]) -> float | None:
    """Return median of finite values, or None if empty."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return float(np.median(arr))


def trimmed_mean(values: np.ndarray | list[float], proportion: float = 0.10) -> float | None:
    """Return symmetric trimmed mean of finite values."""
    arr = np.asarray(values, dtype=float)
    arr = np.sort(arr[np.isfinite(arr)])
    n = arr.size
    if n == 0:
        return None
    k = int(np.floor(n * proportion))
    if 2 * k >= n:
        return float(np.mean(arr))
    return float(np.mean(arr[k : n - k]))


def robust_mad(values: np.ndarray | list[float]) -> float | None:
    """Return normalized Median Absolute Deviation (1.4826 * MAD)."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return 1.4826 * mad


def classify_entry_status(
    status: int | None,
    detail: str | None,
    is_classified: int | None = None,
    has_driving_penalty: bool = False,
) -> tuple[str, float]:
    """Classify a race SessionEntry into (status_category, driver_fault_score).

    Categories:
    - CLEAN_FINISH: Finished / Lapped / Classified without accident or DSQ.
    - MECHANICAL_DNF: Mechanical/team/reliability retirement (EXCLUDED from error penalties).
    - DNS_OTHER: Withdrawn, DNS, DNQ, DNPQ, illness (EXCLUDED from race sample).
    - DRIVER_ERROR: Accident, spin, or penalized driving infraction.
    """
    det = (detail or "").strip().lower()

    if status in (30, 40, 41) or any(k in det for k in _DNS_KEYWORDS):
        return "DNS_OTHER", 0.0

    if status in (0, 1):
        return "CLEAN_FINISH", 0.0

    if status == 10 or any(k in det for k in ("spun off", "accident", "collision")):
        if "collision damage" in det:
            return ("DRIVER_ERROR", 1.0) if has_driving_penalty else ("DRIVER_ERROR", 0.20)
        if "collision" in det and "accident" not in det and "spun" not in det:
            return ("DRIVER_ERROR", 1.0) if has_driving_penalty else ("DRIVER_ERROR", 0.65)
        return "DRIVER_ERROR", 1.0

    if status == 20 or "disqualified" in det:
        if any(k in det for k in _DRIVING_DSQ_KEYWORDS):
            return "DRIVER_ERROR", 1.0
        if any(k in det for k in _TECH_DSQ_KEYWORDS):
            return "MECHANICAL_DNF", 0.0
        # Unspecified Ergast DSQs are predominantly technical scrutineering exclusions
        return "MECHANICAL_DNF", 0.0

    if status == 11:
        return "MECHANICAL_DNF", 0.0

    if is_classified == 1:
        return "CLEAN_FINISH", 0.0

    # Unknown status fallback
    return "MECHANICAL_DNF", 0.0


def identify_neutralized_laps(
    laps_by_number: dict[int, list[float]],
    explicit_intervals: list[tuple[int, int]],
) -> tuple[set[int], dict[int, float], float | None]:
    """Identify SC/VSC/Red Flag/weather-spike laps plus field median per lap.

    Returns (neutralized_lap_numbers, field_lap_median_dict, race_baseline_median).
    """
    field_medians: dict[int, float] = {}
    for lnum, times in laps_by_number.items():
        if lnum <= 0:
            continue
        arr = [t for t in times if t is not None and 30.0 <= t <= 600.0]
        if arr:
            field_medians[lnum] = float(np.median(arr))

    if not field_medians:
        return set(), {}, None

    non_lap1_medians = [v for k, v in field_medians.items() if k >= 2]
    if not non_lap1_medians:
        non_lap1_medians = list(field_medians.values())

    race_baseline = float(np.percentile(non_lap1_medians, 25))
    neutralized: set[int] = set()

    for ls, le in explicit_intervals:
        for lnum in range(max(1, ls), le + 1):
            neutralized.add(lnum)

    # Field-wide SC/VSC/rain spike detector
    for lnum, med in field_medians.items():
        if med > 1.055 * race_baseline:
            neutralized.add(lnum)

    return neutralized, field_medians, race_baseline


def filter_driver_clean_laps(
    driver_laps: list[tuple[int, float]],
    explicit_pit_in_laps: set[int],
    neutralized_laps: set[int],
    field_medians: dict[int, float],
    race_baseline: float | None,
) -> tuple[list[tuple[int, float, int, int]], set[int]]:
    """Filter anomalous laps and return clean laps with stint tracking.

    Args:
        driver_laps: sorted list of (lap_number, time_sec) with lap_number >= 1.
        explicit_pit_in_laps: lap numbers recorded in pit_stops.
        neutralized_laps: SC/VSC/red-flag/rain-spike lap numbers.
        field_medians: field median lap time per lap_number.
        race_baseline: 25th percentile green-flag pace baseline for the race.

    Returns:
        clean_laps: list of (lap_number, time_sec, stint_number, lap_in_stint)
        all_pit_in_laps: set of inferred + explicit pit-in lap numbers (for racecraft filtering).
    """
    if not driver_laps or race_baseline is None:
        return [], set(explicit_pit_in_laps)

    valid_times = [t for ln, t in driver_laps if ln >= 2 and t is not None and 30.0 <= t <= 600.0]
    drv_med = float(np.median(valid_times)) if valid_times else race_baseline

    # Infer pit stops for 1996-2010 races lacking pit_stops records
    inferred_pit_ins: set[int] = set(explicit_pit_in_laps)
    if not explicit_pit_in_laps:
        for ln, t in driver_laps:
            if ln < 2 or ln in neutralized_laps or t is None:
                continue
            fmed = field_medians.get(ln, race_baseline)
            # Pit transit adds ~13-28s relative to driver & field normal pace
            if t > drv_med + 13.0 and t > fmed * 1.12:
                inferred_pit_ins.add(ln)

    pit_out_laps = {p + 1 for p in inferred_pit_ins}
    clean_laps: list[tuple[int, float, int, int]] = []
    stint_num = 1
    lap_in_stint = 0

    for ln, t in driver_laps:
        lap_in_stint += 1
        is_in_lap = ln in inferred_pit_ins
        is_out_lap = ln in pit_out_laps

        if ln <= 1 or t is None or t <= 0:
            if is_in_lap:
                stint_num += 1
                lap_in_stint = 0
            continue

        if is_in_lap:
            # Exclude in-lap, advance stint counter for next lap
            stint_num += 1
            lap_in_stint = 0
            continue

        if is_out_lap or ln in neutralized_laps:
            continue

        fmed = field_medians.get(ln, race_baseline)
        if t > 1.07 * fmed or t < 0.85 * race_baseline:
            continue

        clean_laps.append((ln, t, stint_num, lap_in_stint))

    return clean_laps, inferred_pit_ins
