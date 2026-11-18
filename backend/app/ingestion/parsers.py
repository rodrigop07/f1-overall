"""Shared parsing utilities for CSV dumps, Ergast/Jolpica JSON, and team color defaults."""

from __future__ import annotations

import re

_DURATION_DAY_RE = re.compile(
    r"^(?:(?P<days>-?\d+)\s+days?,?\s+)?(?P<hms>\d+:\d+:\d+(?:\.\d+)?)$"
)
_MIN_SEC_RE = re.compile(r"^(?P<mins>\d+):(?P<secs>\d+(?:\.\d+)?)$")

CLASSIC_TEAM_COLORS: dict[str, str] = {
    "ferrari": "#E8002D",
    "mclaren": "#FF8000",
    "mercedes": "#27F4D2",
    "red_bull": "#3671C6",
    "aston_martin": "#229971",
    "williams": "#64C4FF",
    "alpine": "#00A1E8",
    "haas": "#B6BABD",
    "rb": "#6692FF",
    "sauber": "#52E252",
    "kick_sauber": "#52E252",
    "audi": "#FF2D00",
    "cadillac": "#AAAAAD",
    "alphatauri": "#5E8FAA",
    "toro_rosso": "#469BFF",
    "racing_point": "#F596C8",
    "force_india": "#F596C8",
    "renault": "#FFF500",
    "lotus_f1": "#FFB800",
    "team_lotus": "#004225",
    "lotus": "#004225",
    "brawn": "#B8FF00",
    "benetton": "#0099DC",
    "jordan": "#EFC800",
    "bra": "#3E6B48",
    "brabham": "#0B3B2B",
    "tyrrell": "#0033A0",
    "ligier": "#0066CC",
    "matra": "#1E6BFF",
    "march": "#D92B2B",
    "brm": "#004D33",
    "cooper": "#00593B",
    "vanwall": "#0B5345",
    "alfa": "#9B0000",
    "maserati": "#A61C1C",
    "bmw_sauber": "#1E5BC6",
    "toyota": "#EB0A1E",
    "honda": "#CC0000",
    "bar": "#E0E0E0",
    "stewart": "#F0F4F8",
    "jaguar": "#006644",
    "prost": "#1B46C2",
    "arrows": "#FF6A00",
    "minardi": "#222222",
    "shadow": "#303030",
    "hesketh": "#E6E6E6",
    "wolf": "#C8A43C",
    "auto_union": "#C0C0C0",
    "lancia": "#B01E28",
    "gordini": "#2D68C4",
    "connaught": "#1B6E41",
    "marussia": "#6E0000",
    "manor": "#D62828",
    "caterham": "#0B6623",
    "virgin": "#C8102E",
    "hrt": "#8B7D6B",
}


def resolve_team_color(reference: str | None, primary_color: str | None, name: str | None = None) -> str:
    """Return official primary hex color or a cohesive heritage palette fallback."""
    if primary_color and primary_color.strip():
        c = primary_color.strip()
        return c if c.startswith("#") else f"#{c}"
    ref = (reference or "").strip().lower()
    if ref in CLASSIC_TEAM_COLORS:
        return CLASSIC_TEAM_COLORS[ref]
    lname = (name or "").lower()
    for key, color in CLASSIC_TEAM_COLORS.items():
        if key.replace("_", " ") in lname:
            return color
    return "#94A3B8"


def parse_int(val: str | int | float | None) -> int | None:
    """Parse optional integer safely."""
    if val is None:
        return None
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_float(val: str | int | float | None) -> float | None:
    """Parse optional float safely."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_bool(val: str | int | bool | None) -> int:
    """Parse PostgreSQL CSV / Python booleans into SQLite 0/1 integer."""
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, (int, float)):
        return 1 if val else 0
    if val is None:
        return 0
    s = str(val).strip().lower()
    return 1 if s in ("t", "true", "1", "yes", "y") else 0


def parse_duration_seconds(val: str | int | float | None) -> float | None:
    """Parse duration strings like '00:01:24.312', '1:24.312', '1 day, 00:02:10', or '+12.345'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    # Handle leading '+' sometimes found in gap strings (caller must check relative vs absolute)
    if s.startswith("+"):
        s = s[1:].strip()

    m = _DURATION_DAY_RE.match(s)
    if m:
        days = int(m.group("days")) if m.group("days") is not None else 0
        parts = m.group("hms").split(":")
        hours = int(parts[0])
        mins = int(parts[1])
        secs = float(parts[2])
        return days * 86400.0 + hours * 3600.0 + mins * 60.0 + secs

    m2 = _MIN_SEC_RE.match(s)
    if m2:
        mins = int(m2.group("mins"))
        secs = float(m2.group("secs"))
        return mins * 60.0 + secs

    try:
        return float(s)
    except ValueError:
        return None


def clean_str(val: str | None) -> str | None:
    """Strip string and normalize empty string to None."""
    if val is None:
        return None
    s = val.strip()
    return s if s else None
