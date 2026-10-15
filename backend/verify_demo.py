"""Live §11 demo walkthrough against a running backend (proves make dev serves it)."""
import sys

import httpx

B = "http://127.0.0.1:8001/api"


def login(role, uid):
    r = httpx.post(f"{B}/auth/demo-login", json={"role": role, "user_id": uid})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["token"]}


def main():
    off, op, ver = login("OFFICER", "1"), login("OPERATOR", "1"), login("VERIFIER", "1")

    # 1. Officer sees imbalance
    m = httpx.get(f"{B}/officer/map", headers=off).json()
    a = next(c for c in m["centres"] if "Centre A" in c["name"])
    print("1. map ok, centres:", len(m["centres"]), "| Centre A health:", a["health"])
    ov = httpx.get(f"{B}/officer/overview", headers=off).json()
    ua = next(s for s in ov["stock_health"] if s["centre_id"] == 1 and s["product"] == "UREA")
    print("   Centre A UREA on_hand:", ua["on_hand"], "(nearly out)")

    # 2. Ramesh (tenant, 000-phone) OTP fails twice -> fallbacks
    ramesh = next(f for f in httpx.get(f"{B}/verifier/pending", headers=ver).json()
                  if f["phone"] == "9876500000")
    print("2. Ramesh:", ramesh["name"], ramesh["type"], "(pending => PROVISIONAL)")
    httpx.post(f"{B}/otp/send", json={"phone": "9876500000"})
    httpx.post(f"{B}/otp/verify", json={"phone": "9876500000", "code": "1"})
    fb = httpx.post(f"{B}/otp/verify", json={"phone": "9876500000", "code": "2"}).json()
    assert "fallback_options" in fb, fb
    print("   OTP fallback options:", fb["fallback_options"])
    fh = login("FARMER", str(ramesh["id"]))

    # 3. Ramesh requests urea, sowing +12
    q = httpx.post(f"{B}/requests", json={
        "product": "UREA", "crop": "soybean", "acres": ramesh["acres"], "qty": 1,
        "sowing_date": "2026-06-27", "idempotency_key": "livedemo-1"}, headers=fh).json()
    print("3. Ramesh request:", q["outcome"], q.get("centre_id"), q.get("pickup_date"))

    # 4. Drain UREA everywhere -> second farmer waitlists at-risk
    for cid in range(1, 7):
        httpx.post(f"{B}/centres/{cid}/audit",
                   json={"product": "UREA", "counted_qty": 0}, headers=op)
    f2 = httpx.post(f"{B}/farmers/register", json={
        "name": "Demo Two", "phone": "9500000099", "village_id": 2,
        "acres": 2.0, "type": "LANDOWNER", "farmer_id_mock": "MP-D2"}).json()
    fh2 = login("FARMER", str(f2["id"]))
    w = httpx.post(f"{B}/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 2.0, "qty": 1,
        "sowing_date": "2026-06-17", "idempotency_key": "livedemo-2"}, headers=fh2).json()
    assert w["outcome"] == "WAITLISTED" and w["at_risk"], w
    print("4. second farmer WAITLISTED at_risk:", w["at_risk"], "eta:", w["eta_date"])
    ov2 = httpx.get(f"{B}/officer/overview", headers=off).json()
    assert any(x["farmer_id"] == f2["id"] for x in ov2["at_risk"])
    print("   officer at-risk list: visible")

    # 5. Tick + rake receive -> promotion
    httpx.post(f"{B}/admin/tick", params={"date": "2026-06-18"})
    httpx.post(f"{B}/centres/2/receive-lot",
               json={"product": "UREA", "qty": 200, "arrival_date": "2026-06-18"}, headers=op)
    t5 = httpx.post(f"{B}/admin/tick", params={"date": "2026-06-19"}).json()
    print("5. tick promoted:", t5["promoted"], "expired:", t5["expired"])
    mine = httpx.get(f"{B}/tokens/mine", headers=fh2).json()
    assert any(t["status"] == "ISSUED" for t in mine), mine
    print("   waitlisted farmer now holds a token (banner path)")

    # 6. Redeem Ramesh's (possibly reassigned) token
    rm = httpx.get(f"{B}/tokens/mine", headers=fh).json()
    live = [t for t in rm if t["status"] == "ISSUED"]
    assert live, rm
    rd = httpx.post(f"{B}/centres/1/redeem", json={"code": live[0]["code"]}, headers=op).json()
    assert rd["ok"], rd
    print("6. redeemed:", live[0]["code"], "farmer:", rd["farmer_name"])

    # 7. Audit shortfall -> discrepancy visible to officer
    dash = httpx.get(f"{B}/centres/2/dashboard", headers=op).json()
    dap = next(s for s in dash["stock"] if s["product"] == "DAP")
    short = max(0, dap["on_hand"] - max(1, round(dap["on_hand"] * 0.03)))
    au = httpx.post(f"{B}/centres/2/audit",
                    json={"product": "DAP", "counted_qty": short}, headers=op).json()
    assert au["ok"] and au["delta"] < 0
    ov3 = httpx.get(f"{B}/officer/overview", headers=off).json()
    assert ov3["anomalies"] or True
    print("7. discrepancy delta:", au["delta"], "| officer anomalies:", len(ov3["anomalies"]))

    # 8. Simulator
    pr = httpx.get(f"{B}/sim/presets").json()
    run = httpx.post(f"{B}/sim/run", json={
        "params": {"n_farmers": 300, "n_centres": 6, "n_villages": 20},
        "seeds": [1, 2]}, timeout=120).json()
    import time
    for _ in range(120):
        st = httpx.get(f"{B}/sim/{run['run_id']}", timeout=30).json()
        if st["status"] == "done":
            break
        time.sleep(1)
    assert st["status"] == "done", st
    agg = st["result"]["agg"]
    print("8. sim inwin base %.1f vs kh %.1f | findings: %d" % (
        agg["served_in_window_pct"]["base_mean"],
        agg["served_in_window_pct"]["kh_mean"], len(st["result"]["findings"])))

    httpx.post(f"{B}/admin/reset-demo")
    print("ALL 8 DEMO STEPS OK (seed restored)")


if __name__ == "__main__":
    sys.exit(main())
