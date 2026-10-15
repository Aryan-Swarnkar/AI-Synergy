"""Demo-clock + reseed (system)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from ..auth import require_roles
from ..db import SessionLocal
from ..demo import demo_today_of
from ..models import Meta
from ..services.tokens import expire_and_promote

router = APIRouter(tags=["admin"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse(s: str):
    y, m, d = (int(x) for x in s.split("-"))
    from datetime import date
    return date(y, m, d)


@router.post("/admin/tick")
def tick(date: str | None = None, db=Depends(_db)):
    from .. import config
    cfg = config.get_config()
    today = demo_today_of(db)
    nxt = date if date else (_parse(today) + timedelta(days=1)).isoformat()
    db.merge(Meta(key="demo_today", value=nxt))
    db.commit()
    res = expire_and_promote(db, nxt, cfg)
    return {"demo_today": nxt, **res}


@router.post("/admin/reset-demo")
def reset_demo():
    from ..seed import seed
    return {"reset": True, **seed()}
