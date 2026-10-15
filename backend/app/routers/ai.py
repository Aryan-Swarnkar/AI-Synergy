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
