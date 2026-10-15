"""AI endpoints (v3). Recommendations only — nothing here writes Requests,
reserves stock, or changes records. The farmer confirms via POST /requests.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..ai import intake
from ..demo import demo_today_of
from ..db import SessionLocal

router = APIRouter(tags=["ai"])


class ParseIn(BaseModel):
    text: str
    lang: str = "hi"


@router.post("/ai/parse")
def parse(body: ParseIn):
    db = SessionLocal()
    try:
        today = demo_today_of(db)
    finally:
        db.close()
    prop = intake.parse_request(body.text, body.lang, today)
    return {**prop.model_dump(), "mock_note": "rule-based stand-in; LLM plug-in ready"}


@router.get("/ai/status")
def status():
    from ..ai import llm
    return {"llm_enabled": llm.enabled(), "parser": "rule",
            "mock_note": "rule-based stand-in; LLM plug-in ready"}


@router.get("/ai/forecast")
def get_forecast(weeks_ahead: int = 4, seed: int = 42):
    from ..ai import forecast as fc
    weeks_ahead = max(1, min(8, weeks_ahead))
    rows = fc.history(seed)
    ev = fc.evaluate(seed)
    return {"forecast": fc.forecast(rows, weeks_ahead),
            "model_mae": ev["model_mae"], "naive_mae": ev["naive_mae"],
            "synthetic": True,
            "mock_note": "synthetic history until a pilot produces real data"}
