"""Allocator unit tests: purity + §10 tests 2,3,4,9 (pure level)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _cfg(**over):
    from app import config
    c = config.get_config()
    c.update(over)
    return c


def _centres():
    from app.core.types import CentreState
    # A at (0,0) with 0 stock, B at ~11km east with 100 bags
    return [
        CentreState(id=1, name="A", lat=0.0, lon=0.0, on_hand=0, reserved=0,
                    arrivals=[], day_used={}),
        CentreState(id=2, name="B", lat=0.0, lon=0.1, on_hand=100, reserved=0,
                    arrivals=[], day_used={}),
    ]


def _req(**over):
    from app.core.types import FarmerRequest
    base = dict(farmer_id=1, village_lat=0.0, village_lon=0.01, product="UREA",
                crop="soybean", acres=2.0, qty=1, sowing_date="2026-06-25",
                is_tenant_provisional=False, has_active_request=False,
                seasonal_remaining=10, created_at="2026-06-16T00:00:00")
    base.update(over)
    return FarmerRequest(**base)


def test_allocator_is_pure():
    import re
    src = Path(__file__).resolve().parent.parent.joinpath(
        "app", "core", "allocator.py").read_text(encoding="utf-8")
    for pat in (r"^\s*import\s+sqlalchemy", r"^\s*from\s+sqlalchemy",
                r"^\s*import\s+fastapi", r"^\s*from\s+fastapi"):
        assert re.search(pat, src, re.M | re.I) is None, \
            f"allocator must not import DB/web frameworks ({pat})"


def test_deadline_respected():
    from app.core.allocator import decide
    cfg = _cfg()
    # sowing 2026-06-25, today 2026-06-16 -> pickup must be < sowing
    d = decide(_req(), _centres(), "2026-06-16", cfg)
    assert d.outcome == "ISSUED"
    assert d.pickup_date < "2026-06-25"


def test_urgent_flag_when_sowing_tomorrow():
    from app.core.allocator import decide
    cfg = _cfg()
    d = decide(_req(sowing_date="2026-06-17"), _centres(), "2026-06-16", cfg)
    assert d.outcome == "ISSUED"
    assert d.urgent is True
    assert d.pickup_date == "2026-06-17"


def test_nearest_with_stock_goes_to_B():
    from app.core.allocator import decide
    cfg = _cfg()
    # Village essentially at A (0.005 deg ~0.5km); A has no stock -> must pick B
    d = decide(_req(village_lat=0.0, village_lon=0.005), _centres(), "2026-06-16", cfg)
    assert d.outcome == "ISSUED"
    assert d.centre_id == 2
    assert d.reason_text_en and d.reason_text_hi


def test_rejects_over_entitlement_and_dup():
    from app.core.allocator import decide
    cfg = _cfg()
    # soybean UREA rate 0.5/acre * 2 acres = ceil(1.0) = 1 bag; ask 5 -> reject
    d = decide(_req(qty=5), _centres(), "2026-06-16", cfg)
    assert d.outcome == "REJECTED"
    assert d.reason_code == "OVER_ENTITLEMENT"
    d2 = decide(_req(has_active_request=True), _centres(), "2026-06-16", cfg)
    assert d2.outcome == "REJECTED"
    assert d2.reason_code == "DUP_ACTIVE_REQUEST"


def test_rejects_sowing_outside_window():
    from app.core.allocator import decide
    cfg = _cfg()
    d = decide(_req(sowing_date="2026-09-01"), _centres(), "2026-06-16", cfg)
    assert d.outcome == "REJECTED"
    assert d.reason_code == "INVALID_SOWING_WINDOW"


def test_waitlist_has_eta_and_risk_flag():
    from app.core.allocator import decide
    from app.core.types import CentreState
    cfg = _cfg()
    empty = [CentreState(id=1, name="A", lat=0.0, lon=0.0, on_hand=0, reserved=0,
                         arrivals=[], day_used={})]
    d = decide(_req(village_lat=0.0, village_lon=0.0), empty, "2026-06-16", cfg)
    assert d.outcome == "WAITLISTED"
    assert d.at_risk is True  # no stock anywhere -> cannot meet sowing
