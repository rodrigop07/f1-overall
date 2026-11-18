"""Pillar 5 (5%): Experience (logarithmic curve of cumulative GP starts)."""

from __future__ import annotations

import math


def compute_experience_score(cumulative_starts: int) -> float:
    """Compute logarithmic experience score from cumulative Grand Prix starts."""
    capped = max(0, min(int(cumulative_starts), 350))
    return math.log1p(capped)
