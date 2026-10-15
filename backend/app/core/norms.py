"""Dose tables + crop calendars (SPEC §3.1). DEMO VALUES — not agronomic advice.

The UI must show this disclaimer next to any entitlement figure.
"""
from __future__ import annotations

import math

DISCLAIMER_EN = "Demo dose values, not agronomic advice. Follow your local agri officer."
DISCLAIMER_HI = "डेमो मात्रा है, कृषि सलाह नहीं। स्थानीय कृषि अधिकारी की सलाह लें।"

BAGS_PER_ACRE: dict[str, dict[str, float]] = {
    "wheat": {"UREA": 2.5, "DAP": 1.0, "MOP": 0.3, "NPK": 0.0},
    "soybean": {"UREA": 0.5, "DAP": 1.0, "MOP": 0.3, "NPK": 0.0},
    "paddy": {"UREA": 2.5, "DAP": 1.0, "MOP": 0.5, "NPK": 0.0},
    "maize": {"UREA": 2.5, "DAP": 1.0, "MOP": 0.3, "NPK": 0.0},
    "cotton": {"UREA": 2.0, "DAP": 1.0, "MOP": 0.5, "NPK": 0.0},
}

# (earliest_offset_days, latest_offset_days) from SEASON_START — see ASSUMPTIONS.md
CROP_CALENDAR: dict[str, tuple[int, int]] = {
    "soybean": (0, 30),
    "paddy": (0, 35),
    "maize": (0, 30),
    "cotton": (0, 40),
    "wheat": (0, 45),
}


def entitlement(acres: float, crop: str, product: str) -> int:
    rate = BAGS_PER_ACRE.get(crop, {}).get(product, 0.0)
    return math.ceil(max(0.0, acres) * rate)


def provisional_cap(full_entitlement: int, factor: float) -> int:
    """Provisional tenants get factor×entitlement, at least 1 bag if entitled."""
    if full_entitlement <= 0:
        return 0
    return max(1, math.floor(full_entitlement * factor))
