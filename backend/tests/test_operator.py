"""Phase 4: redeem / receive-lot / audit + auto-reassign (§10.10)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _world(db, on_hand=100):
    from app.models import Centre, Farmer, StockPool, Village
    c = Centre(name="C1", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="V1", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    db.add(StockPool(centre_id=c.id, product="UREA", on_hand=on_hand, reserved=0,
                     discrepancy_total=0))
    f = Farmer(name="Asha", phone="9410000001", village_id=v.id, type="LANDOWNER",
               farmer_id_mock="MP-1", acres=2.0, verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.flush()
    db.commit()
    return c, v, f


def test_receive_lot_adds_stock(db):
    from app.models import StockPool
    from app.services.stock import receive_lot
    c, _, _ = _world(db, on_hand=50)
    out = receive_lot(db, centre_id=c.id, product="UREA", qty=30,
                      arrival_date="2026-06-18")
    assert out["ok"] and out["on_hand"] == 80
    assert db.query(StockPool).first().on_hand == 80


def test_receive_consumes_pending_eta(db):
    from app import config
    from app.models import StockLot
    from app.services.stock import receive_lot
    from app.services.tokens import request_token
    c, v, _ = _world(db, on_hand=2)
    cfg = config.get_config()
    # Pending future lot of 200 (not in on_hand)
    db.add(StockLot(centre_id=c.id, product="UREA", qty_bags=200,
                    arrival_date="2026-06-19", received_at=None,
                    source_ref="MOCK-iFMS-rake-ETA"))
    db.commit()
    # Farmer waitlisted? No — projected covers via pending, so ISSUED (forward reserve)
    from app.models import Farmer
    f = Farmer(name="W", phone="9410000002", village_id=v.id, type="LANDOWNER",
               farmer_id_mock="MP-2", acres=2.0, verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.commit()
    r = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                      qty=1, sowing_date="2026-06-28", idempotency_key="k-rec-1",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "ISSUED"
    out = receive_lot(db, centre_id=c.id, product="UREA", qty=200,
                      arrival_date="2026-06-19")
    assert out["consumed_pending"] >= 1


def test_redeem_happy_and_guards(db):
    from app import config
    from app.models import StockPool
    from app.services.tokens import redeem_token, request_token
    c, _, f = _world(db)
    cfg = config.get_config()
    r = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                      qty=1, sowing_date="2026-06-28", idempotency_key="k-red-1",
                      today="2026-06-16", cfg=cfg)
    code, pickup = r["token_code"], r["pickup_date"]
    # Too early -> OUT_OF_WINDOW
    bad = redeem_token(db, code, "op1", "2026-06-16", cfg)
    assert bad["ok"] is False and bad["error"] == "OUT_OF_WINDOW"
    good = redeem_token(db, code, "op1", pickup, cfg)
    assert good["ok"] is True and good["farmer_name"] == "Asha"
    pool = db.query(StockPool).first()
    assert pool.on_hand == 99 and pool.reserved == 0
    # Double redeem blocked
    again = redeem_token(db, code, "op1", pickup, cfg)
    assert again["ok"] is False


def test_audit_shortfall_reassigns(db):
    """§10.10: counted < ledger logs discrepancy and reassigns affected tokens."""
    from app import config
    from app.models import Discrepancy, StockPool, Token
    from app.services.identity import register_farmer
    from app.services.stock import audit
    from app.services.tokens import request_token
    c, v, _f0 = _world(db, on_hand=10)
    # Second centre with plenty of stock to receive reassigned farmers.
    # Slightly farther than C1 so the initial request still picks C1.
    from app.models import Centre
    c2 = Centre(name="C2", lat=23.25, lon=77.15, district="Sehore", active=True)
    db.add(c2)
    db.flush()
    db.add(StockPool(centre_id=c2.id, product="UREA", on_hand=500, reserved=0,
                     discrepancy_total=0))
    db.commit()
    cfg = config.get_config()
    # Use paddy (2.5 bags/acre) so two farmers can hold 5+5=10 of 10 on hand.
    # Buffer on 10 = ceil(0.3) = 1 -> reservable 9; second request forward?
    # Keep simple: one farmer holds 5, audit drops physical to 2 -> must cancel.
    f1 = register_farmer(db, name="F1", phone="9420000001", village_id=v.id,
                         acres=2.0, ftype="LANDOWNER", farmer_id_mock="MP-11")
    r1 = request_token(db, farmer_id=f1.id, product="UREA", crop="paddy", acres=2.0,
                       qty=5, sowing_date="2026-06-28", idempotency_key="k-aud-1",
                       today="2026-06-16", cfg=cfg)
    assert r1["outcome"] == "ISSUED"
    out = audit(db, centre_id=c.id, product="UREA", counted_qty=2,
                operator_id="op1", today="2026-06-16", cfg=cfg)
    assert out["ok"] is True and out["delta"] == 2 - 10
    assert db.query(Discrepancy).count() == 1
    # Original token cancelled...
    assert db.query(Token).filter_by(code=r1["token_code"]).first().status == "CANCELLED"
    # ...and the farmer was reassigned (C2 has stock)
    assert len(out["reassigned"]) == 1
    assert out["reassigned"][0]["outcome"] == "ISSUED"


def test_reschedule_free_then_blocked(db):
    from app import config
    from app.services.tokens import request_token, reschedule_token
    _, _, f = _world(db, on_hand=500)
    cfg = config.get_config()
    r = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                      qty=1, sowing_date="2026-06-28", idempotency_key="k-res-1",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "ISSUED"
    r2 = reschedule_token(db, r["token_code"], "2026-06-16", cfg)
    assert r2["ok"] is True and r2["outcome"] == "ISSUED"
    r3 = reschedule_token(db, r2["token_code"], "2026-06-16", cfg)
    assert r3["ok"] is False and r3["error"] == "NO_FREE_RESCHEDULES"
