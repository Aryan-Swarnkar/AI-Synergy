"""§10.1 MANDATORY: 100 concurrent reservations vs 50 bags must never oversell."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _setup_small_world(db):
    from app.models import Centre, Farmer, StockPool, Village
    c = Centre(name="Solo", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="V", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    # 50 bags on hand, buffer 3% -> ceil(1.5)=2 -> max reservable 48
    db.add(StockPool(centre_id=c.id, product="UREA", on_hand=50, reserved=0,
                     discrepancy_total=0))
    farmers = []
    for i in range(100):
        f = Farmer(name=f"F{i}", phone=f"90000{i:05d}", village_id=v.id,
                   type="LANDOWNER", farmer_id_mock=f"MP-{i}",
                   acres=2.0, verification="VERIFIED", needs_audit=False)
        db.add(f)
        farmers.append(f)
    db.flush()
    return c, v, farmers


def test_no_oversell_100_threads(db):
    import math
    from app import config
    from app.db import SessionLocal
    from app.models import StockPool, Token
    from app.services.tokens import request_token

    _setup_small_world(db)
    db.commit()
    cfg = config.get_config()
    # soybean 2 acres UREA: ceil(2*0.5)=1 bag each -> qty=1
    sowing = "2026-06-28"

    def _one(i: int):
        s = SessionLocal()
        try:
            # fresh farmer per thread (ids 1..100 in test db)
            f = s.query(__import__("app.models", fromlist=["Farmer"]).Farmer).filter_by(
                phone=f"90000{i:05d}").first()
            return request_token(s, farmer_id=f.id, product="UREA", crop="soybean",
                                 acres=2.0, qty=1, sowing_date=sowing,
                                 idempotency_key=f"conc-{i}", today="2026-06-16", cfg=cfg)
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(_one, range(100)))

    issued = [r for r in results if r.get("outcome") == "ISSUED"]
    # available = 50 - 2 buffer = 48 max
    max_allowed = 50 - math.ceil(50 * cfg["SAFETY_BUFFER_PCT"] / 100)
    assert len(issued) <= max_allowed, f"oversold: {len(issued)} > {max_allowed}"

    s2 = SessionLocal()
    try:
        pool = s2.query(StockPool).filter_by(product="UREA").first()
        active_qty = sum(t.qty_bags for t in s2.query(Token).filter_by(status="ISSUED").all())
        assert pool.reserved == active_qty, "reserved must equal active token qty"
        assert pool.reserved <= max_allowed
    finally:
        s2.close()
