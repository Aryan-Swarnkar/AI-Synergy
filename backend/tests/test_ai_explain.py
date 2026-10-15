"""AI-4 tests: template fidelity, tampered-LLM fallback, decision untouched."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REC = {"outcome": "ISSUED", "qty": 5, "product": "UREA", "centre": "Centre B",
       "pickup_date": "2026-06-20", "days_early": 4}


def test_template_contains_only_record_facts():
    from app.ai import explain as ex
    out = ex.explain(dict(REC), use_llm=False)
    assert out["template_used"] is True
    assert ex.fidelity_check(out["text_en"], REC)
    assert ex.fidelity_check(out["text_hi"], REC)


def test_tampered_llm_falls_back_and_record_untouched(monkeypatch):
    from app.ai import explain as ex
    from app.ai import llm
    before = dict(REC)
    monkeypatch.setattr(llm, "chat_json",
                        lambda *a, **k: {"text_en": "Go to Centre ZZZ for 99 bags",
                                         "text_hi": "99 बोरी लें"})
    monkeypatch.setattr(llm, "enabled", lambda: True)
    out = ex.explain(dict(REC), use_llm=True)
    assert out["template_used"] is True  # hallucinated facts rejected
    assert REC == before  # decision record never mutated


def test_api_explain(client):
    r = client.post("/api/ai/explain", json={"record": REC})
    assert r.status_code == 200, r.text
    b = r.json()
    assert "Centre B" in b["text_en"] and b["template_used"] is True
