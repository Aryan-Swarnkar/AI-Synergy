"""Guards: token ownership + registered-acres entitlement."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(c, role, uid):
    return c.post("/api/auth/demo-login", json={"role": role, "user_id": uid}).json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_token_ownership_enforced(client):
    from app.seed import seed
    seed()
    fa = client.post("/api/farmers/register", json={
        "name": "Owner A", "phone": "9600000001", "village_id": 1,
        "acres": 2.0, "type": "LANDOWNER", "farmer_id_mock": "MP-A"}).json()
    fb = client.post("/api/farmers/register", json={
        "name": "Intruder B", "phone": "9600000002", "village_id": 1,
        "acres": 2.0, "type": "LANDOWNER", "farmer_id_mock": "MP-B"}).json()
    ta, tb = _login(client, "FARMER", str(fa["id"])), _login(client, "FARMER", str(fb["id"]))
    q = client.post("/api/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 2.0, "qty": 1,
        "sowing_date": "2026-06-28", "idempotency_key": "own-1"}, headers=_h(ta)).json()
    assert q["outcome"] == "ISSUED"
    code = q["token_code"]
    for op in ("reschedule", "cancel"):
        r = client.post(f"/api/tokens/{code}/{op}", headers=_h(tb))
        assert r.status_code == 403, (op, r.text)
        assert r.json()["error_code"] == "FORBIDDEN"


def test_tick_rejects_garbage_date(client):
    r = client.post("/api/admin/tick", params={"date": "abc"})
    assert r.status_code == 400, r.text
    assert r.json()["error_code"] == "BAD_DATE"
    assert client.get("/api/health").json()["demo_today"] == "2026-06-15"


def test_operator_input_validation(client):
    from app.seed import seed
    seed()
    op = _login(client, "OPERATOR", "1")
    r = client.post("/api/centres/1/receive-lot",
                    json={"product": "UREA", "qty": -50, "arrival_date": "2026-06-16"},
                    headers=_h(op))
    assert r.status_code == 400 and r.json()["error_code"] == "BAD_QTY"
    r = client.post("/api/centres/1/receive-lot",
                    json={"product": "UREA", "qty": 10, "arrival_date": "tomorrow"},
                    headers=_h(op))
    assert r.status_code == 400 and r.json()["error_code"] == "BAD_DATE"
    r = client.post("/api/centres/1/audit",
                    json={"product": "UREA", "counted_qty": -1}, headers=_h(op))
    assert r.status_code == 400
    r = client.post("/api/sim/run", json={"params": {"n_farmers": 99999}, "seeds": [1]})
    assert r.status_code == 400 and r.json()["error_code"] == "TOO_BIG"


def test_registered_acres_cap_client_inflation(client):
    from app.seed import seed
    seed()
    f = client.post("/api/farmers/register", json={
        "name": "Smallholder", "phone": "9600000003", "village_id": 1,
        "acres": 1.0, "type": "LANDOWNER", "farmer_id_mock": "MP-C"}).json()
    t = _login(client, "FARMER", str(f["id"]))
    # 1 acre soybean/UREA -> entitlement 1 bag; client claims 50 acres for 25 bags
    r = client.post("/api/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 50.0, "qty": 25,
        "sowing_date": "2026-06-28", "idempotency_key": "acres-1"}, headers=_h(t)).json()
    assert r["outcome"] == "REJECTED", r
    assert r["reason_code"] == "OVER_ENTITLEMENT"
