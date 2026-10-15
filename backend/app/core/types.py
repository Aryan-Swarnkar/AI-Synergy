"""Plain dataclasses for the pure allocator (no DB/FastAPI imports — SPEC §5.1)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CentreState:
    id: int
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    on_hand: int = 0
    reserved: int = 0
    # future (or past) arrivals not yet in on_hand: [(YYYY-MM-DD, qty)]
    arrivals: list[tuple[str, int]] = field(default_factory=list)
    # tokens already issued per date: {YYYY-MM-DD: used_count}
    day_used: dict[str, int] = field(default_factory=dict)


@dataclass
class FarmerRequest:
    farmer_id: int = 0
    village_lat: float = 0.0
    village_lon: float = 0.0
    product: str = "UREA"
    crop: str = "soybean"
    acres: float = 1.0
    qty: int = 1
    sowing_date: str = ""  # YYYY-MM-DD
    is_tenant_provisional: bool = False
    has_active_request: bool = False
    seasonal_remaining: int | None = None
    created_at: str = ""  # ISO datetime for waitlist tie-break


@dataclass
class Decision:
    outcome: str  # ISSUED | WAITLISTED | REJECTED
    centre_id: int | None = None
    pickup_date: str | None = None
    slot: str | None = None
    qty: int = 0
    eta_date: str | None = None
    at_risk: bool = False
    urgent: bool = False
    extended_radius: bool = False
    reason_code: str = ""
    reason_text_en: str = ""
    reason_text_hi: str = ""
    alternatives: list[dict] = field(default_factory=list)
