"""AI-1 intake tests: 30-sentence accuracy, schema, clarifying, never-submits."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIELDS = ("product", "crop", "acres", "sowing_date", "qty")


def test_intake_accuracy():
    from app.ai import fixtures_intake as fx
    from app.ai import intake
    hits, total = 0, len(fx.SENTENCES)
    misses = []
    for text, exp in fx.SENTENCES:
        got = intake.parse_request(text, today=fx.TODAY)
        row = {k: getattr(got, k) for k in FIELDS}
        if row == exp:
            hits += 1
        else:
            misses.append((text, exp, row))
    acc = hits / total
    assert acc >= 0.80, f"accuracy {acc:.0%} ({hits}/{total}); misses: {misses[:5]}"
    print(f"\nintake accuracy: {hits}/{total} = {acc:.0%}")


def test_schema_and_confidence():
    from app.ai import fixtures_intake as fx
    from app.ai import intake
    for text, _ in fx.SENTENCES:
        got = intake.parse_request(text, today=fx.TODAY)
        assert 0.0 <= got.confidence <= 1.0
        assert got.parser in ("rule", "llm")
        for k in FIELDS:
            assert k in got.missing_fields or getattr(got, k) is not None


def test_low_confidence_asks_never_submits(db):
    from app.ai import intake
    from app.models import Request
    n_before = db.query(Request).count()
    got = intake.parse_request("mujhe urea chahiye", today="2026-06-15")
    assert got.confidence < 0.7
    assert got.clarifying_question, "must ask one clarifying question"
    assert got.missing_fields, "must list missing fields"
    # parse_request takes no db and creates nothing
    assert db.query(Request).count() == n_before


def test_api_parse_endpoint(client):
    r = client.post("/api/ai/parse", json={"text": "2 acre gehu ke liye 3 bori urea, 10 din me"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["crop"] == "wheat" and b["parser"] in ("rule", "llm")
    assert "mock_note" in b
