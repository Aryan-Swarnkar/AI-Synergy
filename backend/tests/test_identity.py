"""§10.6 tenant path + §10.7 OTP never blocks."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _world(db, on_hand=200):
    from app.models import Centre, StockPool, Village
    c = Centre(name="C1", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="V1", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    db.add(StockPool(centre_id=c.id, product="UREA", on_hand=on_hand, reserved=0,
                     discrepancy_total=0))
    db.commit()
    return c, v


def test_tenant_provisional_60_then_100(db):
    from app import config
    from app.services.identity import register_farmer, verifier_decide
    from app.services.tokens import request_token
    _, v = _world(db)
    cfg = config.get_config()
    # paddy/UREA 2ac: full=ceil(2*2.5)=5, provisional=floor(5*.6)=3
    t1 = register_farmer(db, name="Tenant One", phone="9300000001", village_id=v.id,
                         acres=2.0, ftype="TENANT", landowner_name="Hari Singh")
    assert t1.verification == "PROVISIONAL" and t1.needs_audit
    # Full qty while provisional -> REJECTED
    r = request_token(db, farmer_id=t1.id, product="UREA", crop="paddy", acres=2.0,
                      qty=5, sowing_date="2026-06-28", idempotency_key="k-ten-1",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "REJECTED"
    # 60% qty -> ISSUED
    r2 = request_token(db, farmer_id=t1.id, product="UREA", crop="paddy", acres=2.0,
                       qty=3, sowing_date="2026-06-28", idempotency_key="k-ten-2",
                       today="2026-06-16", cfg=cfg)
    assert r2["outcome"] == "ISSUED"
    # Second tenant approved BEFORE requesting -> 100%
    t2 = register_farmer(db, name="Tenant Two", phone="9300000002", village_id=v.id,
                         acres=2.0, ftype="TENANT")
    out = verifier_decide(db, farmer_id=t2.id, verifier_id="ver1", decision="APPROVED")
    assert out["ok"] is True
    r3 = request_token(db, farmer_id=t2.id, product="UREA", crop="paddy", acres=2.0,
                       qty=5, sowing_date="2026-06-28", idempotency_key="k-ten-3",
                       today="2026-06-16", cfg=cfg)
    assert r3["outcome"] == "ISSUED"


def test_rejection_cancels_tokens_and_releases(db):
    from app.models import StockPool, Token
    from app.services.identity import register_farmer, verifier_decide
    from app.services.tokens import request_token
    from app import config
    _, v = _world(db)
    cfg = config.get_config()
    t = register_farmer(db, name="Tenant X", phone="9300000003", village_id=v.id,
                        acres=2.0, ftype="TENANT")
    r = request_token(db, farmer_id=t.id, product="UREA", crop="paddy", acres=2.0,
                      qty=3, sowing_date="2026-06-28", idempotency_key="k-ten-4",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "ISSUED"
    assert db.query(StockPool).first().reserved == 3
    out = verifier_decide(db, farmer_id=t.id, verifier_id="ver1", decision="REJECTED",
                          note="not a genuine tenant")
    assert out["ok"] is True
    assert db.query(Token).filter_by(status="ISSUED").count() == 0
    assert db.query(StockPool).first().reserved == 0


def test_otp_never_blocks_with_fail_rate_1(db):
    from app import config
    from app.services.identity import assisted_register, send_otp, verify_otp, voice_callback
    from app.services.tokens import request_token
    _, v = _world(db)
    cfg = config.get_config({"OTP_FAIL_RATE": 1.0})
    phone = "9310000000"  # ends 000 -> always fails too
    send_otp(phone, cfg)
    r1 = verify_otp(db, phone, "123456", cfg)
    assert r1["verified"] is False and "fallback_options" not in r1
    r2 = verify_otp(db, phone, "wrong", cfg)
    assert r2["verified"] is False
    assert set(r2["fallback_options"]) == {"RETRY_LATER", "VOICE_CALLBACK", "ASSISTED_AT_CENTRE"}
    # Voice path works
    voice_callback(phone)
    r3 = verify_otp(db, phone, "654321", cfg)
    assert r3["verified"] is True
    # Assisted path bypasses OTP entirely and still gets a token, flagged
    f = assisted_register(db, name="Assisted A", phone="9320000001",
                          village_id=v.id, acres=2.0, operator_id="op1")
    assert f.needs_audit is True
    res = request_token(db, farmer_id=f.id, product="UREA", crop="soybean", acres=2.0,
                        qty=1, sowing_date="2026-06-28", idempotency_key="k-otp-1",
                        today="2026-06-16", cfg=config.get_config())
    assert res["outcome"] == "ISSUED"
