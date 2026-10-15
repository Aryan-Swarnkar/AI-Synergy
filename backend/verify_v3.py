import sys

sys.path.insert(0, ".")
import httpx

B = "http://127.0.0.1:8001/api"


def login(role, uid):
    r = httpx.post(f"{B}/auth/demo-login", json={"role": role, "user_id": uid})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["token"]}


def main():
    # AI-1 parse (no key -> rule path, labelled stand-in)
    p = httpx.post(f"{B}/ai/parse", json={
        "text": "mujhe 2 acre gehu ke liye urea chahiye, 10 din mein bona hai"}).json()
    assert p["crop"] == "wheat" and p["parser"] == "rule", p
    assert "mock_note" in p
    print("parse ok:", p["product"], p["crop"], p["acres"], p["sowing_date"], f"conf={p['confidence']}")
    st = httpx.get(f"{B}/ai/status").json()
    assert st["llm_enabled"] is False
    print("llm_enabled:", st["llm_enabled"], "(rule default, correct without key)")

    # parse -> confirm with provenance payload
    f = httpx.post(f"{B}/farmers/register", json={
        "name": "AI Raju", "phone": "9640000001", "village_id": 1, "acres": 2.0,
        "type": "LANDOWNER", "farmer_id_mock": "MP-AI"}).json()
    fh = login("FARMER", str(f["id"]))
    q = httpx.post(f"{B}/requests", json={
        "product": "UREA", "crop": "soybean", "acres": 2.0, "qty": 1,
        "sowing_date": "2026-06-28", "idempotency_key": "v3-live-1",
        "provenance": {"ai_proposal": p, "confirmed_edits": {"qty": 1}}}, headers=fh).json()
    assert q["outcome"] == "ISSUED", q
    tl = httpx.get(f"{B}/tokens/{q['token_code']}/provenance").json()["timeline"]
    steps = [(e["step"], e["actor_type"]) for e in tl]
    assert steps == [("intake_proposed", "AI"), ("farmer_confirmed", "HUMAN"),
                     ("validated", "RULE"), ("reserved", "RULE")], steps
    print("provenance chain ok:", " -> ".join(s for s, _ in steps))

    # explainer + forecast + anomalies + console-size run
    ex = httpx.post(f"{B}/ai/explain", json={"record": {
        "outcome": "ISSUED", "qty": 1, "product": "UREA", "centre": "Centre A",
        "pickup_date": "2026-06-16", "days_early": 12}}).json()
    assert "Centre A" in ex["text_en"] and ex["template_used"] is True
    print("explain ok (template, no key)")
    fc = httpx.get(f"{B}/ai/forecast", params={"weeks_ahead": 2}).json()
    print(f"forecast ok: model MAE {fc['model_mae']} vs naive {fc['naive_mae']}")
    an = httpx.get(f"{B}/ai/anomalies").json()
    print("anomaly flags:", len(an["flags"]))
    run = httpx.post(f"{B}/sim/run", json={
        "params": {"n_farmers": 300, "n_centres": 6, "n_villages": 20,
                   "supply_multiplier": 0.7, "closed_centres": [0],
                   "product": "UREA"}, "seeds": [1]}, timeout=120).json()
    import time
    for _ in range(120):
        s = httpx.get(f"{B}/sim/{run['run_id']}", timeout=30).json()
        if s["status"] == "done":
            break
        time.sleep(1)
    assert s["status"] == "done", s
    a = s["result"]["agg"]
    print("console run ok: inwin base %.1f vs kh %.1f" % (
        a["served_in_window_pct"]["base_mean"], a["served_in_window_pct"]["kh_mean"]))
    httpx.post(f"{B}/admin/reset-demo")
    print("V3 LIVE PATHS OK (seed restored)")


if __name__ == "__main__":
    main()
