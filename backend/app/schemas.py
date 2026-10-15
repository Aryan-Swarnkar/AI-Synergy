"""Pydantic schemas. Phase 1: minimal; extended in later phases."""
from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    demo_today: str
    season_start: str
