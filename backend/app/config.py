"""All tunable parameters (SPEC §3.4). Overridable by env and by the simulator."""
from __future__ import annotations

import os


def _getenv(key: str, default):
    val = os.getenv(key)
    if val is None:
        return default
    # bool handling
    if isinstance(default, bool):
        return val.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(val)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(val)
        except ValueError:
            return default
    if isinstance(default, list):
        return [s.strip() for s in val.split(",") if s.strip()]
    return val


MAX_RADIUS_KM: float = float(_getenv("MAX_RADIUS_KM", 40))
MAX_DETOUR_KM_OVER_NEAREST: float = float(_getenv("MAX_DETOUR_KM_OVER_NEAREST", 15))
SLOT_BLOCKS: list[str] = _getenv("SLOT_BLOCKS", ["08-10", "10-12", "12-14", "14-16"])  # type: ignore[arg-type]
if isinstance(SLOT_BLOCKS, str):  # env override path
    SLOT_BLOCKS = [s.strip() for s in SLOT_BLOCKS.split(",")]
SLOT_CAPACITY: int = int(_getenv("SLOT_CAPACITY", 25))
TOKEN_GRACE_DAYS: int = int(_getenv("TOKEN_GRACE_DAYS", 1))
SAFETY_BUFFER_PCT: float = float(_getenv("SAFETY_BUFFER_PCT", 3))
FREE_RESCHEDULES: int = int(_getenv("FREE_RESCHEDULES", 1))
TENANT_PROVISIONAL_FACTOR: float = float(_getenv("TENANT_PROVISIONAL_FACTOR", 0.6))
W_DIST: float = float(_getenv("W_DIST", 1.0))
W_CROWD: float = float(_getenv("W_CROWD", 8.0))
W_WAIT: float = float(_getenv("W_WAIT", 3.0))
OVERBOOK_FACTOR: float = float(_getenv("OVERBOOK_FACTOR", 1.0))
WAITLIST_ENABLED: bool = _getenv("WAITLIST_ENABLED", True)  # type: ignore[assignment]
SEASON_START: str = str(_getenv("SEASON_START", "2026-06-15"))
OTP_FAIL_RATE: float = float(_getenv("OTP_FAIL_RATE", 0.15))
VERIFIER_DAILY_LIMIT: int = int(_getenv("VERIFIER_DAILY_LIMIT", 40))
DATABASE_URL: str = str(_getenv("DATABASE_URL", "sqlite:///./khadsetu.db"))

# Console-addable products (v3): DEMO rates, not agronomic advice. New product
# names are validated against this allowlist — never free text.
EXTRA_PRODUCTS: dict[str, dict[str, float]] = {
    "ZINC": {"wheat": 0.5, "soybean": 0.5, "paddy": 0.5, "maize": 0.5, "cotton": 0.5},
}


def get_config(overrides: dict | None = None) -> dict:
    """Return config dict; simulator passes overrides without touching globals."""
    base = {
        "MAX_RADIUS_KM": MAX_RADIUS_KM,
        "MAX_DETOUR_KM_OVER_NEAREST": MAX_DETOUR_KM_OVER_NEAREST,
        "SLOT_BLOCKS": list(SLOT_BLOCKS),
        "SLOT_CAPACITY": SLOT_CAPACITY,
        "TOKEN_GRACE_DAYS": TOKEN_GRACE_DAYS,
        "SAFETY_BUFFER_PCT": SAFETY_BUFFER_PCT,
        "FREE_RESCHEDULES": FREE_RESCHEDULES,
        "TENANT_PROVISIONAL_FACTOR": TENANT_PROVISIONAL_FACTOR,
        "W_DIST": W_DIST,
        "W_CROWD": W_CROWD,
        "W_WAIT": W_WAIT,
        "OVERBOOK_FACTOR": OVERBOOK_FACTOR,
        "WAITLIST_ENABLED": WAITLIST_ENABLED,
        "SEASON_START": SEASON_START,
        "OTP_FAIL_RATE": OTP_FAIL_RATE,
        "VERIFIER_DAILY_LIMIT": VERIFIER_DAILY_LIMIT,
    }
    if overrides:
        base.update(overrides)
    return base
