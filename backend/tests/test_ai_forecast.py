"""AI-2 forecast tests: beats the naive baseline on synthetic history."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_model_beats_naive():
    from app.ai import forecast as fc
    ev = fc.evaluate(42)
    assert ev["model_mae"] < ev["naive_mae"], ev
    print(f"\nforecast MAE {ev['model_mae']} vs naive {ev['naive_mae']}")


def test_forecast_shape_and_interval():
    from app.ai import forecast as fc
    rows = fc.history(7)
    out = fc.forecast(rows, 3)
    assert len(out) == 6 * 4 * 3  # centres * products * weeks
    for r in out:
        assert r["lo"] <= r["qty"] <= r["hi"]
        assert set(r) >= {"centre_id", "product", "week", "qty", "lo", "hi"}


def test_api_forecast(client):
    r = client.get("/api/ai/forecast", params={"weeks_ahead": 2})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["synthetic"] is True and b["model_mae"] < b["naive_mae"]
    assert len(b["forecast"]) == 6 * 4 * 2
