"""P7 Constraint Console: closed centres, supply multiplier, new product, timing."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SMALL = {"n_farmers": 300, "n_centres": 6, "n_villages": 30}


def test_closed_centre_reassigns():
    from app.sim import runner
    open_r = runner.run_scenario({**SMALL}, [1])
    shut_r = runner.run_scenario({**SMALL, "closed_centres": [0]}, [1])
    a = open_r["agg"]["served_in_window_pct"]
    b = shut_r["agg"]["served_in_window_pct"]
    assert abs(a["kh_mean"] - b["kh_mean"]) < 10.0, (a, b)  # stock moved, service holds
    from app.sim import generator
    assert generator.generate(1, {**SMALL, "closed_centres": [0]})["total_supply"] == \
        generator.generate(1, SMALL)["total_supply"]  # lots moved, none lost


def test_supply_multiplier_moves_results():
    from app.sim import runner
    full = runner.run_scenario({**SMALL, "supply_multiplier": 1.0}, [1])
    cut = runner.run_scenario({**SMALL, "supply_multiplier": 0.7}, [1])
    assert cut["agg"]["served_in_window_pct"]["kh_mean"] < \
        full["agg"]["served_in_window_pct"]["kh_mean"]


def test_new_product_zinc_end_to_end(db):
    from app import config
    from app.models import Centre, Farmer, Village
    from app.services.stock import receive_lot
    from app.services.tokens import request_token
    c = Centre(name="CZ", lat=23.2, lon=77.08, district="Sehore", active=True)
    db.add(c)
    v = Village(name="VZ", lat=23.21, lon=77.09, district="Sehore")
    db.add(v)
    db.flush()
    f = Farmer(name="Zed", phone="9630000001", village_id=v.id, type="LANDOWNER",
               farmer_id_mock="MP-Z", acres=2.0, verification="VERIFIED", needs_audit=False)
    db.add(f)
    db.commit()
    receive_lot(db, centre_id=c.id, product="ZINC", qty=50,
                arrival_date="2026-06-16", operator_id="op1")
    res = request_token(db, farmer_id=f.id, product="ZINC", crop="soybean",
                        acres=2.0, qty=1, sowing_date="2026-06-28",
                        idempotency_key="k-zinc-1", today="2026-06-16",
                        cfg=config.get_config())
    assert res["outcome"] == "ISSUED", res


def test_allocator_cfg_passthrough():
    from app.sim import generator, khadsetu
    base = {"n_farmers": 300, "n_centres": 6, "n_villages": 30}
    d = generator.generate(1, base)
    a = khadsetu.simulate(d, 1)
    d2 = generator.generate(1, {**base, "MAX_DETOUR_KM_OVER_NEAREST": 0.1})
    b = khadsetu.simulate(d2, 1)
    # The console key must reach the allocator: assignments differ.
    # (Direction is intentionally unasserted — tighter detours can serve more
    # locally while travelling worse; the console shows both.)
    assert [r["served"] for r in a["per_farmer"]] != [r["served"] for r in b["per_farmer"]]


def test_console_run_under_20s():
    from app.sim import runner
    t0 = time.time()
    runner.run_scenario({"n_farmers": 800, "n_centres": 8, "n_villages": 40,
                         "supply_multiplier": 0.7, "closed_centres": [0]}, [1, 2])
    assert time.time() - t0 < 20.0


def test_console_api_validation_and_run(client):
    bad = client.post("/api/sim/run", json={"params": {**SMALL, "product": "NOPE"},
                                            "seeds": [1]})
    assert bad.status_code == 400 and bad.json()["error_code"] == "BAD_PRODUCT"
    r = client.post("/api/sim/run", json={
        "params": {**SMALL, "product": "ZINC", "supply_multiplier": 0.7,
                   "closed_centres": [0]}, "seeds": [1]})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    deadline = time.time() + 90
    while time.time() < deadline:
        st = client.get(f"/api/sim/{run_id}").json()
        if st["status"] == "done":
            break
        assert st["status"] == "running", st
        time.sleep(0.5)
    assert st["status"] == "done", st
