"""§10.5 expiry releases stock + promotes highest-priority waitlist entry."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _world(db, on_hand=2):
    from app.models import Centre, Farmer, StockPool, Village
    c = Centre(name="C1", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="V1", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    db.add(StockPool(centre_id=c.id, product="UREA", on_hand=on_hand, reserved=0,
                     discrepancy_total=0))
    db.flush()
    db.commit()
    return c, v


def _farmer(db, v, phone, acres=2.0, sowing="2026-06-28"):
    from app.models import Farmer
    f = Farmer(name=f"N-{phone}", phone=phone, village_id=v.id, type="LANDOWNER",
               farmer_id_mock=f"MP-{phone}", acres=acres,
               verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.flush()
    db.commit()
    return f


def test_expiry_and_promotion_priority(db):
    from app import config
    from app.models import Token, WaitlistEntry
    from app.services.tokens import expire_and_promote, request_token
    c, v = _world(db, on_hand=2)  # buffer ceil(2*3%)=1 -> only 1 bag reservable
    cfg = config.get_config()
    today = "2026-06-16"
    # F1 gets the single reservable bag (earlier sowing -> higher priority anyway)
    f1 = _farmer(db, v, "9222200001", sowing="2026-06-25")
    r1 = request_token(db, farmer_id=f1.id, product="UREA", crop="soybean", acres=2.0,
                       qty=1, sowing_date="2026-06-25", idempotency_key="k-exp-1",
                       today=today, cfg=cfg)
    assert r1["outcome"] == "ISSUED"
    # F2 (urgent, sowing sooner) and F3 waitlist — F2 deadline sooner => promotes first
    f2 = _farmer(db, v, "9222200002", sowing="2026-06-20")
    f3 = _farmer(db, v, "9222200003", sowing="2026-06-28")
    r2 = request_token(db, farmer_id=f2.id, product="UREA", crop="soybean", acres=2.0,
                       qty=1, sowing_date="2026-06-20", idempotency_key="k-exp-2",
                       today=today, cfg=cfg)
    r3 = request_token(db, farmer_id=f3.id, product="UREA", crop="soybean", acres=2.0,
                       qty=1, sowing_date="2026-06-28", idempotency_key="k-exp-3",
                       today=today, cfg=cfg)
    assert r2["outcome"] == "WAITLISTED" and r3["outcome"] == "WAITLISTED"

    # Advance past grace: pickup was ~2026-06-17, grace 1 -> expires 06-18; tick 06-20
    out = expire_and_promote(db, "2026-06-20", cfg)
    assert out["expired"] >= 1
    assert out["promoted"] >= 1
    # Highest priority (soonest deadline f2) must be the promoted one
    f2tok = db.query(Token).filter(Token.farmer_id == f2.id, Token.status == "ISSUED").all()
    assert len(f2tok) == 1, "soonest-deadline waiter promotes first"
    still_waiting = db.query(WaitlistEntry).filter_by(status="WAITING").all()
    assert any(w.farmer_id == f3.id for w in still_waiting)
