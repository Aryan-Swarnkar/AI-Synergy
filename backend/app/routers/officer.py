"""Officer routes (read-only aggregates + rule preview)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import config as default_config
from ..auth import require_roles
from ..db import SessionLocal
from ..demo import demo_today_of
from ..schemas import RulePreviewIn
from ..services import analytics

router = APIRouter(tags=["officer"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/officer/overview")
def overview(cur: dict = Depends(require_roles("OFFICER")), db=Depends(_db)):
    return analytics.overview(db, demo_today_of(db), default_config.get_config())


@router.get("/officer/map")
def map_view(cur: dict = Depends(require_roles("OFFICER")), db=Depends(_db)):
    return analytics.map_data(db, default_config.get_config())


@router.post("/officer/rule-preview")
def rule_preview(body: RulePreviewIn,
                 cur: dict = Depends(require_roles("OFFICER")), db=Depends(_db)):
    return analytics.rule_preview(db, demo_today_of(db), body.overrides,
                                  default_config.get_config())
