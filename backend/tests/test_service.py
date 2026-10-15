"""§10.2 token=>stock, §10.8 idempotency, §10.9 cap enforcement (service level)."""
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
    f = Farmer(name="Asha", phone="9111100001", village_id=v.id, type="LANDOWNER",
               farmer_id_mock="MP-1", acres=2.0, verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.flush()
    db.commit()
    return c, v, f


def test_token_implies_stock_ledger(db):
    from app import config
    from app.models import StockLedger, StockPool, Token
    from app.services.tokens import request_token
    _, _, f = _world(db)
    cfg = config.get_config()
    res = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                        qty=1, sowing_date="2026-06-28", idempotency_key="k-ledger-1",
                        today="2026-06-16", cfg=cfg)
    assert res["outcome"] == "ISSUED"
    pool = db.query(StockPool).first()
    toks = db.query(Token).filter_by(status="ISSUED").all()
    assert pool.reserved == sum(t.qty_bags for t in toks)
    rows = db.query(StockLedger).filter_by(reason="RESERVE").all()
    assert len(rows) == len(toks) and rows[0].delta == -1


def test_idempotency_no_second_token(db):
    from app import config
    from app.models import Token
    from app.services.tokens import request_token
    _, _, f = _world(db)
    cfg = config.get_config()
    kw = dict(farmer_id=f.id, product="UREA", crop="soybean", acres=2.0, qty=1,
              sowing_date="2026-06-28", idempotency_key="k-idem-1",
              today="2026-06-16", cfg=cfg)
    r1 = request_token(db, **kw)
    r2 = request_token(db, **kw)
    assert r1["outcome"] == "ISSUED" and r2.get("idempotent") is True
    assert r1["token_code"] == r2["token_code"]
    assert db.query(Token).filter_by(status="ISSUED").count() == 1


def test_cap_and_duplicate_rejected(db):
    from app import config
    from app.services.tokens import request_token
    _, _, f = _world(db, on_hand=500)
    cfg = config.get_config()
    # entitlement soybean/UREA 2ac = 1 bag; ask 10 -> REJECTED
    r = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                      qty=10, sowing_date="2026-06-28", idempotency_key="k-cap-1",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "REJECTED"
    # valid first request
    r1 = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                       qty=1, sowing_date="2026-06-28", idempotency_key="k-cap-2",
                       today="2026-06-16", cfg=cfg)
    assert r1["outcome"] == "ISSUED"
    # second active request same product -> REJECTED (different key)
    r2 = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                       qty=1, sowing_date="2026-06-28", idempotency_key="k-cap-3",
                       today="2026-06-16", cfg=cfg)
    assert r2["outcome"] == "REJECTED"
