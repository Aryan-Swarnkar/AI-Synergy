"""Centre operator routes."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends

from .. import config as default_config
from ..auth import require_roles
from ..db import SessionLocal
from ..demo import demo_today_of
from ..errors import BusinessError
from ..models import Centre, StockLot, StockPool, Token
from ..schemas import AuditIn, ReceiveLotIn, RedeemIn
from ..services.stock import audit as audit_svc
from ..services.stock import receive_lot as receive_svc
from ..services.tokens import redeem_token

router = APIRouter(tags=["centres"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _centre(db, cid: int) -> Centre:
    c = db.get(Centre, cid)
    if c is None:
        raise BusinessError("CENTRE_NOT_FOUND", "Centre not found",
                            "केंद्र नहीं मिला", 404)
    return c


@router.get("/centres/{cid}/dashboard")
def dashboard(cid: int, date: str | None = None,
              cur: dict = Depends(require_roles("OPERATOR")), db=Depends(_db)):
    from .. import config
    c = _centre(db, cid)
    day = date or demo_today_of(db)
    toks = db.query(Token).filter(Token.centre_id == cid, Token.pickup_date == day,
                                  Token.status == "ISSUED").all()
    by_slot: dict[str, list] = {}
    for t in toks:
        by_slot.setdefault(t.slot, []).append({"code": t.code, "qty": t.qty_bags,
                                               "product": t.product})
    stock = []
    for p in db.query(StockPool).filter(StockPool.centre_id == cid).all():
        buf = math.ceil(p.on_hand * config.SAFETY_BUFFER_PCT / 100)
        stock.append({"product": p.product, "on_hand": p.on_hand,
                      "reserved": p.reserved, "available": p.on_hand - p.reserved - buf})
    arrivals = [{"product": l.product, "qty": l.qty_bags, "arrival_date": l.arrival_date}
                for l in db.query(StockLot).filter(
                    StockLot.centre_id == cid, StockLot.received_at.is_(None)).all()]
    return {"centre": c.name, "date": day, "tokens_by_slot": by_slot,
            "stock": stock, "expected_arrivals": arrivals, "mock_feed": "MOCK-iFMS"}


@router.post("/centres/{cid}/redeem")
def redeem(cid: int, body: RedeemIn,
           cur: dict = Depends(require_roles("OPERATOR")), db=Depends(_db)):
    _centre(db, cid)
    res = redeem_token(db, body.code, cur["user_id"], demo_today_of(db),
                       default_config.get_config())
    if res.get("ok") is False:
        raise BusinessError("REDEEM_" + str(res.get("error", "FAILED")),
                            f"Redeem failed: {res.get('error')}", "वितरण विफल", 409
                            if res.get("error") != "NOT_FOUND" else 404)
    return res


@router.post("/centres/{cid}/receive-lot")
def receive(cid: int, body: ReceiveLotIn,
            cur: dict = Depends(require_roles("OPERATOR")), db=Depends(_db)):
    _centre(db, cid)
    if body.qty <= 0:
        raise BusinessError("BAD_QTY", "Delivery qty must be positive",
                            "मात्रा धनात्मक होनी चाहिए", 400)
    try:
        y, m, d = (int(x) for x in body.arrival_date.split("-"))
        from datetime import date
        date(y, m, d)
    except (ValueError, TypeError):
        raise BusinessError("BAD_DATE", "arrival_date must be YYYY-MM-DD",
                            "तिथि YYYY-MM-DD होनी चाहिए", 400)
    return receive_svc(db, centre_id=cid, product=body.product, qty=body.qty,
                       arrival_date=body.arrival_date, operator_id=cur["user_id"])


@router.post("/centres/{cid}/audit")
def audit(cid: int, body: AuditIn,
          cur: dict = Depends(require_roles("OPERATOR")), db=Depends(_db)):
    from .. import config
    _centre(db, cid)
    if body.counted_qty < 0:
        raise BusinessError("BAD_QTY", "Counted qty cannot be negative",
                            "गिनती ऋणात्मक नहीं हो सकती", 400)
    return audit_svc(db, centre_id=cid, product=body.product,
                     counted_qty=body.counted_qty, operator_id=cur["user_id"],
                     today=demo_today_of(db), cfg=config.get_config())
