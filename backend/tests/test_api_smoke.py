"""§10.14 API smoke: every §6 endpoint returns a valid response, happy path."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(c, role, user_id):
    r = c.post("/api/auth/demo-login", json={"role": role, "user_id": user_id})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _err_format(r):
    assert r.status_code in (400, 401, 403, 404, 409, 429, 501), r.text
    b = r.json()
    assert {"error_code", "message", "message_hi"} <= set(b), b


def test_api_smoke(client):
    from app.seed import seed
    seed()

    # --- health + auth ---
    assert client.get("/api/health").status_code == 200
    ftok = _login(client, "FARMER", "1")
    op = _login(client, "OPERATOR", "1")
    ver = _login(client, "VERIFIER", "1")
    off = _login(client, "OFFICER", "1")
    assert client.get("/api/auth/me", headers=_h(ftok)).json()["role"] == "FARMER"
    _err_format(client.post("/api/auth/demo-login", json={"role": "KING", "user_id": "1"}))
    _err_format(client.get("/api/auth/me"))

    # --- farmer register + OTP (MOCK) ---
    fr = client.post("/api/farmers/register", json={
        "name": "Smoke Asha", "phone": "9500000001", "village_id": 1,
        "acres": 2.0, "type": "LANDOWNER", "farmer_id_mock": "MP-SMOKE"})
    assert fr.status_code == 200, fr.text
    fid = fr.json()["id"]
    assert client.post("/api/otp/send", json={"phone": "9500000001"}).status_code == 200
    assert client.post("/api/otp/voice-callback",
                       json={"phone": "9500000001"}).status_code == 200
    v = client.post("/api/otp/verify", json={"phone": "9500000001", "code": "654321"})
    assert v.json()["verified"] is True
    client.post("/api/otp/send", json={"phone": "9599900000"})
    client.post("/api/otp/verify", json={"phone": "9599900000", "code": "x"})
    fb = client.post("/api/otp/verify", json={"phone": "9599900000", "code": "y"})
    assert "fallback_options" in fb.json()
    assert client.get(f"/api/farmers/{fid}").status_code == 200
    ent = client.get(f"/api/farmers/{fid}/entitlement",
                     params={"product": "UREA", "crop": "soybean"})
    assert ent.json()["full_entitlement"] == 1
    ar = client.post("/api/farmers/assisted-register", json={
        "name": "Smoke Assist", "phone": "9500000003", "village_id": 1, "acres": 1.0},
        headers=_h(op))
    assert ar.status_code == 200, ar.text

    # --- requests + tokens (as the registered farmer) ---
    ftok = _login(client, "FARMER", str(fid))
    q1 = client.post("/api/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 2.0, "qty": 1,
        "sowing_date": "2026-06-28", "idempotency_key": "smoke-1"}, headers=_h(ftok))
    assert q1.status_code == 200, q1.text
    assert q1.json()["outcome"] == "ISSUED"
    code, pickup = q1.json()["token_code"], q1.json()["pickup_date"]
    assert client.get("/api/requests/mine", headers=_h(ftok)).status_code == 200
    assert client.get("/api/tokens/mine", headers=_h(ftok)).status_code == 200
    assert client.get(f"/api/tokens/{code}").status_code == 200
    _err_format(client.get("/api/tokens/ZZZZZZZZ"))
    assert client.get("/api/waitlist/mine", headers=_h(ftok)).status_code == 200
    rs = client.post(f"/api/tokens/{code}/reschedule", headers=_h(ftok))
    assert rs.json()["ok"] is True
    code, pickup = rs.json()["token_code"], rs.json()["pickup_date"]
    q2 = client.post("/api/requests", json={
        "product": "DAP", "crop": "soybean", "acres": 2.0, "qty": 2,
        "sowing_date": "2026-06-28", "idempotency_key": "smoke-2"}, headers=_h(ftok))
    assert q2.json()["outcome"] == "ISSUED"
    assert client.post(f"/api/tokens/{q2.json()['token_code']}/cancel",
                       headers=_h(ftok)).json()["ok"] is True

    # --- operator: tick to pickup day, redeem, stock ops ---
    tk = client.post("/api/admin/tick", params={"date": pickup})
    assert tk.json()["demo_today"] == pickup
    # redeem is centre-agnostic in the service (operator sees ID match instead)
    rd = client.post("/api/centres/1/redeem", json={"code": code}, headers=_h(op))
    assert rd.json()["ok"] is True, rd.text
    dash = client.get("/api/centres/1/dashboard", headers=_h(op))
    assert dash.status_code == 200
    rl = client.post("/api/centres/1/receive-lot",
                     json={"product": "DAP", "qty": 10, "arrival_date": pickup},
                     headers=_h(op))
    assert rl.json()["ok"] is True
    dash2 = client.get("/api/centres/1/dashboard", headers=_h(op)).json()
    dap_on = next(s["on_hand"] for s in dash2["stock"] if s["product"] == "DAP")
    au = client.post("/api/centres/1/audit",
                     json={"product": "DAP", "counted_qty": dap_on}, headers=_h(op))
    assert au.json()["ok"] is True

    # --- verifier ---
    tn = client.post("/api/farmers/register", json={
        "name": "Smoke Tenant", "phone": "9500000002", "village_id": 2,
        "acres": 2.0, "type": "TENANT"})
    tid = tn.json()["id"]
    pend = client.get("/api/verifier/pending", headers=_h(ver))
    assert any(p["id"] == tid for p in pend.json())
    dc = client.post(f"/api/verifier/{tid}/decide",
                     json={"decision": "APPROVED", "note": "ok"}, headers=_h(ver))
    assert dc.json()["ok"] is True

    # --- officer ---
    ov = client.get("/api/officer/overview", headers=_h(off))
    assert {"stock_health", "token_funnel", "at_risk", "anomalies"} <= set(ov.json())
    assert client.get("/api/officer/map", headers=_h(off)).status_code == 200
    rp = client.post("/api/officer/rule-preview",
                     json={"overrides": {"MAX_DETOUR_KM_OVER_NEAREST": 25}},
                     headers=_h(off))
    assert rp.json()["read_only"] is True

    # --- simulator (live since Phase 6) ---
    pr = client.get("/api/sim/presets")
    assert len(pr.json()["presets"]) == 5
    tiny = {"n_farmers": 100, "n_centres": 4, "n_villages": 12}
    r = client.post("/api/sim/run", json={"params": tiny, "seeds": [1]})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/sim/{r.json()['run_id']}").status_code == 200
    s = client.post("/api/sim/sensitivity",
                    json={"param": "supply_ratio", "values": [0.8, 1.0],
                          "seeds": [1], "params": tiny})
    assert s.status_code == 200, s.text
    _err_format(client.get("/api/sim/nope"))

    # --- reset demo LAST (wipes) ---
    assert client.post("/api/admin/reset-demo").json()["reset"] is True
    assert client.get("/api/health").json()["demo_today"] == "2026-06-15"
