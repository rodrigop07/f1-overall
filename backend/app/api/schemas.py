"""Pydantic request/response models for the F1 Overall API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeightsPayload(BaseModel):
    pace: float = Field(0.35, ge=0.0, le=1.0)
    qualifying: float = Field(0.25, ge=0.0, le=1.0)
    consistency: float = Field(0.20, ge=0.0, le=1.0)
    racecraft: float = Field(0.15, ge=0.0, le=1.0)
    experience: float = Field(0.05, ge=0.0, le=1.0)


class SimulateRequest(BaseModel):
    scope: str = Field("current", pattern="^(current|season|alltime)$")
    year: int | None = None
    weights: WeightsPayload = Field(default_factory=WeightsPayload)
    shrinkage_m: float = Field(10.0, ge=0.0, le=50.0)
    half_life_races: float = Field(16.0, ge=2.0, le=100.0)
    base_ovr: float = Field(82.0, ge=70.0, le=90.0)
    scale_factor: float = Field(6.0, ge=2.0, le=12.0)
    min_starts: int = Field(0, ge=0, le=300)
    limit: int = Field(60, ge=5, le=200)


class SeatSwapRequest(BaseModel):
    driver_ref: str
    target_team_id: int
    year: int = Field(2026, ge=1950, le=2026)
    replace_driver_ref: str | None = None
    n_sims: int = Field(500, ge=100, le=2000)
