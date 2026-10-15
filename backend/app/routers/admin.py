"""Demo-clock + reseed (system)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from ..db import SessionLocal
from ..demo import demo_today_of
from ..errors import BusinessError
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
    from datetime import date
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except (ValueError, TypeError):
        raise BusinessError("BAD_DATE", f"Date must be YYYY-MM-DD, got {s!r}",
                            "तिथि YYYY-MM-DD होनी चाहिए", 400)


@router.post("/admin/tick")
def tick(date: str | None = None, db=Depends(_db)):
    from .. import config
    cfg = config.get_config()
    today = demo_today_of(db)
    if date is not None:
        _parse(date)  # validate before persisting (garbage would corrupt the clock)
        nxt = date
    else:
        nxt = (_parse(today) + timedelta(days=1)).isoformat()
    db.merge(Meta(key="demo_today", value=nxt))
    db.commit()
    res = expire_and_promote(db, nxt, cfg)
    return {"demo_today": nxt, **res}


@router.post("/admin/reset-demo")
def reset_demo():
    from ..seed import seed
    return {"reset": True, **seed()}
