"""P2 provenance: ordered AI/RULE/HUMAN chain per token (acceptance #10)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROV = {"ai_proposal": {"product": "UREA", "crop": "soybean", "acres": 2.0,
                        "sowing_date": "2026-06-28", "qty": 1,
                        "confidence": 0.91, "parser": "rule"},
        "confirmed_edits": {"qty": 1}}


def _world(db, on_hand=100):
    from app.models import Centre, Farmer, StockPool, Village
    c = Centre(name="C1", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="V1", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    db.add(StockPool(centre_id=c.id, product="UREA", on_hand=on_hand, reserved=0,
                     discrepancy_total=0))
    f = Farmer(name="Prov Asha", phone="9510000001", village_id=v.id,
               type="LANDOWNER", farmer_id_mock="MP-P1", acres=2.0,
               verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.flush()
    db.commit()
    return c, v, f


def _chain(db, code):
    from app.models import ProvenanceEvent, Token
    t = db.query(Token).filter(Token.code == code).first()
    rows = db.query(ProvenanceEvent).filter(
        ProvenanceEvent.token_id.is_(None),
        ProvenanceEvent.request_id == t.request_id).order_by(ProvenanceEvent.id).all()
    rows += db.query(ProvenanceEvent).filter(
        ProvenanceEvent.token_id == t.id).order_by(ProvenanceEvent.id).all()
    return [(e.step, e.actor_type) for e in rows]


def test_full_chain_with_ai_proposal(db):
    from app import config
    from app.services.tokens import request_token
    _, _, f = _world(db)
    res = request_token(db, farmer_id=f.id, product="UREA", crop="soybean",
                        acres=2.0, qty=1, sowing_date="2026-06-28",
                        idempotency_key="k-prov-1", today="2026-06-16",
                        cfg=config.get_config(), provenance=PROV)
    assert res["outcome"] == "ISSUED"
    assert _chain(db, res["token_code"]) == [
        ("intake_proposed", "AI"), ("farmer_confirmed", "HUMAN"),
        ("validated", "RULE"), ("reserved", "RULE")]


def test_rule_only_chain(db):
    from app import config
    from app.services.tokens import request_token
    _, _, f = _world(db)
    res = request_token(db, farmer_id=f.id, product="UREA", crop="soybean",
                        acres=2.0, qty=1, sowing_date="2026-06-28",
                        idempotency_key="k-prov-2", today="2026-06-16",
                        cfg=config.get_config())
    assert _chain(db, res["token_code"]) == [("validated", "RULE"), ("reserved", "RULE")]


def test_lifecycle_extends_chain(db):
    from app import config
    from app.services.identity import register_farmer, verifier_decide
    from app.services.tokens import redeem_token, request_token
    c, v = _world(db)[:2]
    from app.models import Farmer
    t = Farmer(name="Tenant P", phone="9510000002", village_id=v.id, type="TENANT",
               acres=2.0, verification="PROVISIONAL", needs_audit=True)
    db.add(t)
    db.commit()
    cfg = config.get_config()
    r = request_token(db, farmer_id=t.id, product="UREA", crop="paddy", acres=2.0,
                      qty=3, sowing_date="2026-06-28", idempotency_key="k-prov-3",
                      today="2026-06-16", cfg=cfg)
    assert r["outcome"] == "ISSUED"
    assert verifier_decide(db, farmer_id=t.id, verifier_id="ver1",
                           decision="APPROVED")["ok"] is True
    chain = _chain(db, r["token_code"])
    assert ("tenant_approved", "HUMAN") in chain
    rd = redeem_token(db, r["token_code"], "op1", r["pickup_date"], cfg)
    assert rd["ok"] is True
    assert _chain(db, r["token_code"])[-1] == ("redeemed", "HUMAN")


def test_provenance_endpoint(client):
    from app.seed import seed
    seed()
    f = client.post("/api/farmers/register", json={
        "name": "EP", "phone": "9510000003", "village_id": 1, "acres": 2.0,
        "type": "LANDOWNER", "farmer_id_mock": "MP-EP"}).json()
    tok = client.post("/api/auth/demo-login",
                      json={"role": "FARMER", "user_id": str(f["id"])}).json()["token"]
    q = client.post("/api/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 2.0, "qty": 1,
        "sowing_date": "2026-06-28", "idempotency_key": "k-prov-ep",
        "provenance": PROV}, headers={"Authorization": f"Bearer {tok}"}).json()
    assert q["outcome"] == "ISSUED", q
    p = client.get(f"/api/tokens/{q['token_code']}/provenance")
    assert p.status_code == 200, p.text
    steps = [(e["step"], e["actor_type"]) for e in p.json()["timeline"]]
    assert steps == [("intake_proposed", "AI"), ("farmer_confirmed", "HUMAN"),
                     ("validated", "RULE"), ("reserved", "RULE")]
    assert client.get("/api/tokens/ZZZZZZZZ/provenance").status_code == 404
