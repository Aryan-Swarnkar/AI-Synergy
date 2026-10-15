"""§10.11 determinism, §10.12 sanity, §10.13 honest report + API wiring."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SMALL = {"n_farmers": 300, "n_centres": 6, "n_villages": 30}


def test_sim_determinism():
    from app.sim import runner
    a = runner.run_scenario({**SMALL}, [1, 2])
    b = runner.run_scenario({**SMALL}, [1, 2])
    assert a["agg"] == b["agg"]
    assert a["per_seed"] == b["per_seed"]


def test_sim_sanity_ample_supply():
    from app.sim import runner
    r = runner.run_scenario({**SMALL, "shrinkage": 0.0, "supply_ratio": 1.1}, [1, 2])
    kh_stockouts = sum(s["khadsetu"]["stockout_at_counter_events"] for s in r["per_seed"])
    assert kh_stockouts == 0
    assert r["agg"]["served_in_window_pct"]["kh_mean"] >= \
        r["agg"]["served_in_window_pct"]["base_mean"]


def test_honest_report_under_scarcity():
    from app.sim import runner
    r = runner.run_scenario({**SMALL, "supply_ratio": 0.7}, [1, 2])
    text = " ".join(r["findings"])
    assert "shortage-driven non-service is similar" in text


def test_sensitivity_shape():
    from app.sim import runner
    s = runner.sensitivity("supply_ratio", [0.8, 1.0], [1],
                           {**SMALL})
    assert [row["value"] for row in s["series"]] == [0.8, 1.0]
    assert "served_in_window_pct" in s["series"][0]


def test_sim_api_run_and_sensitivity(client):
    r = client.post("/api/sim/run", json={"params": SMALL, "seeds": [1]})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    deadline = time.time() + 60
    while time.time() < deadline:
        st = client.get(f"/api/sim/{run_id}").json()
        if st["status"] == "done":
            break
        assert st["status"] == "running"
        time.sleep(0.5)
    assert st["status"] == "done"
    assert "agg" in st["result"] and "findings" in st["result"]
    s = client.post("/api/sim/sensitivity",
                    json={"param": "supply_ratio", "values": [0.8, 1.0],
                          "seeds": [1], "params": SMALL})
    assert s.status_code == 200, s.text
    assert len(s.json()["series"]) == 2
