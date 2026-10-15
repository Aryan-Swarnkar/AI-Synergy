"""Request / token / waitlist routes (farmer)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_roles
from ..db import SessionLocal
from ..errors import BusinessError
from ..demo import demo_today_of
from ..models import Centre, Farmer, Request, Token, Village, WaitlistEntry
from ..schemas import RequestIn
from ..services.tokens import cancel_token, request_token, reschedule_token

router = APIRouter(tags=["tokens"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _farmer_id(cur: dict, db) -> int:
    try:
        fid = int(cur["user_id"])
    except ValueError:
        raise BusinessError("BAD_FARMER", "Farmer login user_id must be the farmer id",
                            "किसान लॉगिन गलत है", 400)
    if db.get(Farmer, fid) is None:
        raise BusinessError("FARMER_NOT_FOUND", "Farmer not found",
                            "किसान नहीं मिला", 404)
    return fid


def _token_out(db, t: Token) -> dict:
    c = db.get(Centre, t.centre_id)
    return {"code": t.code, "centre_id": t.centre_id, "centre": c.name if c else "?",
            "product": t.product, "qty": t.qty_bags, "pickup_date": t.pickup_date,
            "slot": t.slot, "status": t.status, "expires_at": t.expires_at,
            "urgent": t.urgent, "reschedules_used": t.reschedules_used}


@router.post("/requests")
def create_request(body: RequestIn, cur: dict = Depends(require_roles("FARMER")),
                   db=Depends(_db)):
    from .. import config
    fid = _farmer_id(cur, db)
    res = request_token(db, farmer_id=fid, product=body.product, crop=body.crop,
                        acres=body.acres, qty=body.qty, sowing_date=body.sowing_date,
                        idempotency_key=body.idempotency_key,
                        today=demo_today_of(db), cfg=config.get_config())
    if res.get("outcome") == "ISSUED":
        t = db.query(Token).filter(Token.code == res["token_code"]).first()
        res["token"] = _token_out(db, t) if t else None
    return res


@router.get("/requests/mine")
def my_requests(cur: dict = Depends(require_roles("FARMER")), db=Depends(_db)):
    fid = _farmer_id(cur, db)
    rows = db.query(Request).filter(Request.farmer_id == fid).order_by(Request.id).all()
    return [{"id": r.id, "product": r.product, "qty": r.qty_requested,
             "status": r.status, "reason": r.reason} for r in rows]


@router.get("/tokens/mine")
def my_tokens(cur: dict = Depends(require_roles("FARMER")), db=Depends(_db)):
    fid = _farmer_id(cur, db)
    return [_token_out(db, t) for t in db.query(Token).filter(
        Token.farmer_id == fid).order_by(Token.id).all()]


@router.get("/tokens/{code}")
def get_token(code: str, db=Depends(_db)):
    t = db.query(Token).filter(Token.code == code).first()
    if t is None:
        raise BusinessError("TOKEN_NOT_FOUND", "Token not found", "टोकन नहीं मिला", 404)
    farmer = db.get(Farmer, t.farmer_id)
    village = db.get(Village, farmer.village_id) if farmer else None
    out = _token_out(db, t)
    out["farmer_name"] = farmer.name if farmer else "?"
    out["village"] = village.name if village else "?"
    return out


@router.post("/tokens/{code}/reschedule")
def reschedule(code: str, cur: dict = Depends(require_roles("FARMER")),
               db=Depends(_db)):
    from .. import config
    _farmer_id(cur, db)
    res = reschedule_token(db, code, demo_today_of(db), config.get_config())
    if res.get("ok") is False and res.get("error") in ("NOT_FOUND",):
        raise BusinessError("TOKEN_NOT_FOUND", "Token not found", "टोकन नहीं मिला", 404)
    return res


@router.post("/tokens/{code}/cancel")
def cancel(code: str, cur: dict = Depends(require_roles("FARMER")), db=Depends(_db)):
    _farmer_id(cur, db)
    res = cancel_token(db, code)
    if res.get("ok") is False:
        raise BusinessError("TOKEN_NOT_FOUND" if res.get("error") == "NOT_FOUND" else "TOKEN_STATE",
                            "Cannot cancel this token", "रद्द नहीं हो सकता", 404
                            if res.get("error") == "NOT_FOUND" else 409)
    return res


@router.get("/waitlist/mine")
def my_waitlist(cur: dict = Depends(require_roles("FARMER")), db=Depends(_db)):
    fid = _farmer_id(cur, db)
    entries = db.query(WaitlistEntry).filter(
        WaitlistEntry.farmer_id == fid, WaitlistEntry.status == "WAITING").all()

    def _key(e: WaitlistEntry):
        f = db.get(Farmer, e.farmer_id)
        return (e.deadline, f.acres if f else 0, str(e.created_at))

    out = []
    for e in entries:
        peers = db.query(WaitlistEntry).filter(
            WaitlistEntry.product == e.product,
            WaitlistEntry.status == "WAITING").all()
        rank = sorted(peers, key=_key).index(e) + 1
        out.append({"product": e.product, "qty": e.qty, "position": rank,
                    "of": len(peers), "eta_date": e.eta_date, "at_risk": e.at_risk,
                    "mock_sms": f"MOCK SMS: ETA {e.eta_date or '—'}"})
    return out
