"""Demo-clock helper (avoids main<->router import cycle)."""
from __future__ import annotations

from . import config
from .models import Meta


def demo_today_of(db) -> str:
    row = db.get(Meta, "demo_today")
    return row.value if row else config.SEASON_START
