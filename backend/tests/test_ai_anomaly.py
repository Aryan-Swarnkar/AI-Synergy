"""AI-3 tests: injected anomalies recalled, precision sane, dismiss works."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _inject(db):
    from datetime import datetime, timezone

    from app.models import Discrepancy, Farmer, Token, Verification
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for _ in range(50):  # rogue verifier (bypasses the 40/day service cap)
        db.add(Verification(farmer_id=1, verifier_id="rogue-ver",
                            decision="APPROVED", note="x", ts=now))
    for _ in range(5):  # discrepancy spike at centre 1
        db.add(Discrepancy(centre_id=1, product="UREA", ledger_qty=100,
                           counted_qty=90, delta=-10, operator_id="op1", ts=now))
    f = db.query(Farmer).first()
    for i in range(4):  # repeat no-show farmer
        db.add(Token(code=f"NS{i}XXXX", request_id=1, farmer_id=f.id, centre_id=1,
                     product="UREA", qty_bags=1, pickup_date="2026-06-16",
                     slot="08-10", status="EXPIRED"))
    for i in range(20):  # assisted concentration, one operator
        db.add(Farmer(name=f"AX{i}", phone=f"96200{i:05d}", village_id=f.village_id,
                      type="ASSISTED", acres=1.0, verification="PROVISIONAL",
                      needs_audit=True, registered_by="rogue-op"))
    db.commit()
    return f.id


def test_injection_recall_and_precision(db):
    from app.ai import anomaly as an
    from app.seed import seed
    seed()
    fid = _inject(db)
    flags = an.flag(db)
    kinds = {(f["kind"], f["entity"]) for f in flags}
    assert ("approval_velocity", "rogue-ver") in kinds
    assert ("centre_discrepancies", "1") in kinds
    assert ("repeated_no_show", str(fid)) in kinds
    assert ("assisted_concentration", "rogue-op") in kinds
    injected = 4
    precision = injected / max(1, len(flags))
    assert precision >= 0.5, [f for f in flags]
    print(f"\nanomaly precision: {precision:.0%} ({injected}/{len(flags)})")


def test_dismiss_is_logged_and_honoured(db):
    from app.ai import anomaly as an
    from app.seed import seed
    seed()
    _inject(db)
    assert any(f["entity"] == "rogue-ver" for f in an.flag(db))
    out = an.dismiss(db, kind="approval_velocity", entity="rogue-ver")
    assert out["ok"] is True
    assert not any(f["entity"] == "rogue-ver" for f in an.flag(db))


def test_api_anomaly_endpoints(client):
    r = client.get("/api/ai/anomalies")
    assert r.status_code == 200, r.text
    assert "flags" in r.json()
    d = client.post("/api/ai/anomalies/dismiss",
                    json={"kind": "approval_velocity", "entity": "e2e-ver"})
    assert d.json()["ok"] is True
