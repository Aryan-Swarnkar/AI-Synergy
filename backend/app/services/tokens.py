"""DB-backed reserve / expire / promote (SPEC §5.4-5.5).

The reservation transaction is commented thoroughly: SQLite deferred writers
can both read stale state, so we take BEGIN IMMEDIATE up-front (second writer
blocks on busy_timeout) + a conditional UPDATE that only succeeds when stock
still covers the request. Zero rows updated => state changed => re-run the
pure allocator once, else fall back to WAITLIST. This is what makes the
100-thread no-oversell test pass.
"""
from __future__ import annotations

import math
import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, text

from .. import config as default_config
from ..core.allocator import decide
from ..core.norms import entitlement
from ..core.types import CentreState, FarmerRequest
from ..db import immediate_txn
from ..models import AuditEvent, Farmer, Request, StockLedger, StockLot, StockPool, Token, Village, WaitlistEntry

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0O1I


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gen_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def _parse(s: str) -> date:
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


def _add_days(s: str, n: int) -> str:
    return (_parse(s) + timedelta(days=n)).isoformat()


def _buffer(on_hand: int, pct: float) -> int:
    return math.ceil(max(0, on_hand) * pct / 100.0)


def _day_used(db, centre_id: int, pickup_date: str) -> int:
    return db.query(func.count(Token.id)).filter(
        Token.centre_id == centre_id, Token.pickup_date == pickup_date,
        Token.status == "ISSUED").scalar() or 0


def _pending_arrivals(db, centre_id: int, product: str) -> list[tuple[str, int]]:
    """Only lots NOT yet received count as future arrivals (received ones are
    already inside StockPool.on_hand; counting them again would double-count)."""
    lots = db.query(StockLot).filter(
        StockLot.centre_id == centre_id, StockLot.product == product,
        StockLot.received_at.is_(None)).all()
    return [(l.arrival_date, l.qty_bags) for l in lots]


def _build_states(db, product: str) -> list[CentreState]:
    from ..models import Centre
    centres = db.query(Centre).filter(Centre.active.is_(True)).all()
    states: list[CentreState] = []
    for c in centres:
        pool = db.get(StockPool, (c.id, product))
        on_hand = pool.on_hand if pool else 0
        reserved = pool.reserved if pool else 0
        arrivals = _pending_arrivals(db, c.id, product)
        # day_used for all dates with active tokens (small demo scale: one query)
        rows = db.query(Token.pickup_date, func.count(Token.id)).filter(
            Token.centre_id == c.id, Token.product == product,
            Token.status == "ISSUED").group_by(Token.pickup_date).all()
        states.append(CentreState(id=c.id, name=c.name, lat=c.lat, lon=c.lon,
                                  on_hand=on_hand, reserved=reserved,
                                  arrivals=arrivals, day_used={d: n for d, n in rows}))
    return states


def _seasonal_remaining(db, farmer: Farmer, product: str, crop: str, acres: float) -> int:
    full = entitlement(acres, crop, product)
    used = db.query(func.coalesce(func.sum(Request.qty_requested), 0)).filter(
        Request.farmer_id == farmer.id, Request.product == product,
        Request.status.in_(["ISSUED", "WAITLISTED", "COMPLETED"])).scalar() or 0
    return max(0, full - int(used))


def request_token(db, *, farmer_id: int, product: str, crop: str, acres: float,
                  qty: int, sowing_date: str, idempotency_key: str,
                  today: str, cfg: dict | None = None) -> dict:
    """Main entry: idempotent reserve-or-waitlist-or-reject. Returns JSON-able dict."""
    cfg = cfg or default_config.get_config()

    # ---- Idempotency: same key returns original result, never a second token ----
    existing = db.query(Request).filter(Request.idempotency_key == idempotency_key).first()
    if existing is not None:
        tok = db.query(Token).filter(Token.request_id == existing.id).first()
        wl = db.query(WaitlistEntry).filter(WaitlistEntry.request_id == existing.id).first()
        return {"outcome": existing.status, "request_id": existing.id,
                "token_code": tok.code if tok else None,
                "centre_id": tok.centre_id if tok else None,
                "pickup_date": tok.pickup_date if tok else None,
                "slot": tok.slot if tok else None,
                "eta_date": wl.eta_date if wl else None,
                "at_risk": bool(wl.at_risk) if wl else False,
                "reason": existing.reason, "idempotent": True}

    farmer = db.get(Farmer, farmer_id)
    if farmer is None:
        raise ValueError("farmer not found")
    village = db.get(Village, farmer.village_id)

    active = db.query(Request).filter(
        Request.farmer_id == farmer_id, Request.product == product,
        Request.status.in_(["ISSUED", "WAITLISTED"])).first()
    remaining = _seasonal_remaining(db, farmer, product, crop, acres)

    req = FarmerRequest(
        farmer_id=farmer_id,
        village_lat=village.lat if village else 0.0,
        village_lon=village.lon if village else 0.0,
        product=product, crop=crop, acres=acres, qty=qty, sowing_date=sowing_date,
        is_tenant_provisional=(farmer.type == "TENANT" and farmer.verification == "PROVISIONAL"),
        has_active_request=active is not None,
        seasonal_remaining=remaining,
        created_at=_utcnow().isoformat(),
    )
    states = _build_states(db, product)
    decision = decide(req, states, today, cfg)

    if decision.outcome == "REJECTED":
        with immediate_txn(db) as s:
            # re-check idempotency inside txn (thread race on same key)
            dup = s.query(Request).filter(Request.idempotency_key == idempotency_key).first()
            if dup is not None:
                return {"outcome": dup.status, "request_id": dup.id, "idempotent": True,
                        "reason": dup.reason}
            r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                        qty_requested=qty, sowing_date=sowing_date, status="REJECTED",
                        reason=f"{decision.reason_code}: {decision.reason_text_en}",
                        idempotency_key=idempotency_key)
            s.add(r)
        return {"outcome": "REJECTED", "request_id": r.id, "reason_code": decision.reason_code,
                "reason_en": decision.reason_text_en, "reason_hi": decision.reason_text_hi}

    if decision.outcome == "WAITLISTED":
        with immediate_txn(db) as s:
            dup = s.query(Request).filter(Request.idempotency_key == idempotency_key).first()
            if dup is not None:
                return {"outcome": dup.status, "request_id": dup.id, "idempotent": True,
                        "reason": dup.reason}
            r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                        qty_requested=qty, sowing_date=sowing_date, status="WAITLISTED",
                        reason=f"{decision.reason_code}: {decision.reason_text_en}",
                        idempotency_key=idempotency_key)
            s.add(r)
            s.flush()
            s.add(WaitlistEntry(request_id=r.id, farmer_id=farmer_id, product=product,
                                qty=qty, deadline=sowing_date,
                                priority_score=f"{sowing_date}|{acres}|{r.created_at}",
                                eta_date=decision.eta_date, at_risk=decision.at_risk,
                                status="WAITING"))
            s.add(AuditEvent(actor_role="SYSTEM", actor_id="allocator", action="WAITLIST",
                             entity="request", entity_id=str(r.id),
                             detail={"reason": decision.reason_code}))
        return {"outcome": "WAITLISTED", "request_id": r.id, "eta_date": decision.eta_date,
                "at_risk": decision.at_risk, "reason_code": decision.reason_code,
                "reason_en": decision.reason_text_en, "reason_hi": decision.reason_text_hi}

    # ---- ISSUED: atomic conditional reserve ----
    assert decision.centre_id is not None and decision.pickup_date
    return _reserve_issued(db, farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                           qty=qty, sowing_date=sowing_date,
                           idempotency_key=idempotency_key, today=today, cfg=cfg,
                           centre_id=decision.centre_id, pickup_date=decision.pickup_date,
                           urgent=decision.urgent, reason_code=decision.reason_code,
                           reason_en=decision.reason_text_en)


def _reserve_issued(db, *, farmer_id: int, product: str, crop: str, acres: float,
                    qty: int, sowing_date: str, idempotency_key: str, today: str,
                    cfg: dict, centre_id: int, pickup_date: str,
                    urgent: bool, reason_code: str, reason_en: str) -> dict:
    """Try the allocator's chosen (centre, date) atomically; on a lost race,
    re-run the allocator ONCE with fresh state (new txn, no nesting)."""
    blocks: list[str] = cfg.get("SLOT_BLOCKS", ["08-10"])
    cap_block: int = cfg.get("SLOT_CAPACITY", 25)
    pct: float = cfg.get("SAFETY_BUFFER_PCT", 3)

    cur_centre, cur_date = centre_id, pickup_date
    cur_urgent, cur_code, cur_en = urgent, reason_code, reason_en
    for _attempt in range(2):
        with immediate_txn(db) as s:
            dup = s.query(Request).filter(Request.idempotency_key == idempotency_key).first()
            if dup is not None:
                tok = s.query(Token).filter(Token.request_id == dup.id).first()
                return {"outcome": dup.status, "request_id": dup.id,
                        "token_code": tok.code if tok else None, "idempotent": True,
                        "reason": dup.reason}
            pool = s.get(StockPool, (cur_centre, product))
            on_hand = pool.on_hand if pool else 0
            buf = _buffer(on_hand, pct)
            pend = s.query(StockLot).filter(
                StockLot.centre_id == cur_centre, StockLot.product == product,
                StockLot.received_at.is_(None), StockLot.arrival_date <= cur_date).all()
            arrivals = sum(l.qty_bags for l in pend)
            over = cfg.get("OVERBOOK_FACTOR", 1.0)
            # Conditional UPDATE: succeeds only if projected stock still covers qty.
            # Concurrent threads serialise on BEGIN IMMEDIATE; losers see 0 rows.
            res = s.execute(text(
                "UPDATE stock_pool SET reserved = reserved + :qty "
                "WHERE centre_id = :c AND product = :p "
                "AND (:on_hand * :over - reserved - :buf + :arr) >= :qty"),
                {"qty": qty, "c": cur_centre, "p": product,
                 "on_hand": on_hand, "over": over, "buf": buf, "arr": arrivals})
            if res.rowcount == 0:
                retry_decision = None
                # State changed under us -> fall through to single allocator retry
                # (read fresh state in a NEW session-less query on same session
                #  after the context commits nothing; retry happens next loop).
                states = _build_states(s, product)
                farmer = s.get(Farmer, farmer_id)
                village = s.get(Village, farmer.village_id) if farmer else None
                active = s.query(Request).filter(
                    Request.farmer_id == farmer_id, Request.product == product,
                    Request.status.in_(["ISSUED", "WAITLISTED"])).first()
                req2 = FarmerRequest(
                    farmer_id=farmer_id, village_lat=village.lat if village else 0.0,
                    village_lon=village.lon if village else 0.0,
                    product=product, crop=crop, acres=acres, qty=qty, sowing_date=sowing_date,
                    is_tenant_provisional=(farmer.type == "TENANT"
                                           and farmer.verification == "PROVISIONAL") if farmer else False,
                    has_active_request=active is not None,
                    seasonal_remaining=_seasonal_remaining(s, farmer, product, crop, acres) if farmer else qty,
                    created_at=_utcnow().isoformat())
                retry_decision = decide(req2, states, today, cfg)
                if retry_decision.outcome == "ISSUED" and retry_decision.centre_id \
                        and retry_decision.pickup_date:
                    cur_centre = retry_decision.centre_id
                    cur_date = retry_decision.pickup_date
                    cur_urgent = retry_decision.urgent
                    cur_code = retry_decision.reason_code
                    cur_en = retry_decision.reason_text_en
                    continue  # next loop iteration = the one allowed retry
                # Retry also failed -> honest waitlist, never oversell.
                # Fall through: insert waitlist rows in THIS txn (nothing reserved yet).
                r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                            qty_requested=qty, sowing_date=sowing_date, status="WAITLISTED",
                            reason="RETRY_STATE_CHANGED: stock taken concurrently; waitlisted",
                            idempotency_key=idempotency_key)
                s.add(r)
                s.flush()
                s.add(WaitlistEntry(request_id=r.id, farmer_id=farmer_id, product=product,
                                    qty=qty, deadline=sowing_date,
                                    priority_score=f"{sowing_date}|{acres}|{r.created_at}",
                                    eta_date=retry_decision.eta_date, at_risk=True,
                                    status="WAITING"))
                return {"outcome": "WAITLISTED", "request_id": r.id,
                        "eta_date": retry_decision.eta_date,
                        "at_risk": True, "reason_code": "RETRY_STATE_CHANGED"}

            # Slot must still have room on the chosen date
            used = s.query(func.count(Token.id)).filter(
                Token.centre_id == cur_centre, Token.pickup_date == cur_date,
                Token.status == "ISSUED").scalar() or 0
            if used >= cap_block * len(blocks):
                # Day filled concurrently: undo the reserve increment in this txn
                # by decrementing back before the context commits.
                s.execute(text("UPDATE stock_pool SET reserved = reserved - :qty "
                               "WHERE centre_id = :c AND product = :p"),
                          {"qty": qty, "c": cur_centre, "p": product})
                # Persist a waitlist request instead (reuse current txn).
                r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                            qty_requested=qty, sowing_date=sowing_date, status="WAITLISTED",
                            reason="SLOT_FULL: day filled concurrently; waitlisted",
                            idempotency_key=idempotency_key)
                s.add(r)
                return {"outcome": "WAITLISTED", "reason_code": "SLOT_FULL",
                        "reason_en": "Day filled concurrently; waitlisted."}
            slot = blocks[min(used // cap_block, len(blocks) - 1)]

            r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                        qty_requested=qty, sowing_date=sowing_date, status="ISSUED",
                        reason=f"{cur_code}: {cur_en}", idempotency_key=idempotency_key)
            s.add(r)
            s.flush()
            code = gen_code()
            while s.query(Token).filter(Token.code == code).first() is not None:
                code = gen_code()
            expires = _add_days(cur_date, cfg.get("TOKEN_GRACE_DAYS", 1))
            t = Token(code=code, request_id=r.id, farmer_id=farmer_id, centre_id=cur_centre,
                      product=product, qty_bags=qty, pickup_date=cur_date, slot=slot,
                      status="ISSUED", urgent=cur_urgent, expires_at=expires)
            s.add(t)
            s.add(StockLedger(centre_id=cur_centre, product=product, delta=-qty,
                              reason="RESERVE", ref_id=code, ts=_utcnow()))
            s.add(AuditEvent(actor_role="SYSTEM", actor_id="allocator", action="RESERVE",
                             entity="token", entity_id=code,
                             detail={"centre": cur_centre, "qty": qty, "pickup": cur_date}))
            return {"outcome": "ISSUED", "request_id": r.id, "token_code": code,
                    "centre_id": cur_centre, "pickup_date": cur_date, "slot": slot,
                    "urgent": cur_urgent, "reason_code": cur_code, "reason_en": cur_en}
    # Second attempt also lost the race (extremely rare) -> honest waitlist
    with immediate_txn(db) as s:
        r = Request(farmer_id=farmer_id, product=product, crop=crop, acres=acres,
                    qty_requested=qty, sowing_date=sowing_date, status="WAITLISTED",
                    reason="RETRY_STATE_CHANGED: stock taken concurrently; waitlisted",
                    idempotency_key=idempotency_key)
        s.add(r)
    return {"outcome": "WAITLISTED", "reason_code": "RETRY_STATE_CHANGED"}


def expire_and_promote(db, today: str, cfg: dict | None = None) -> dict:
    """Expire past-grace tokens (release stock) then promote waitlist in priority
    order using freed/new stock. Minimal version for Phase 2; /admin/tick wraps
    it in Phase 4."""
    cfg = cfg or default_config.get_config()
    grace: int = cfg.get("TOKEN_GRACE_DAYS", 1)
    expired, promoted = 0, 0
    with immediate_txn(db) as s:
        # Expire: pickup_date + grace < today
        toks = s.query(Token).filter(Token.status == "ISSUED").all()
        for t in toks:
            if _add_days(t.pickup_date, grace) < today:
                t.status = "EXPIRED"
                pool = s.get(StockPool, (t.centre_id, t.product))
                if pool:
                    pool.reserved = max(0, pool.reserved - t.qty_bags)
                s.add(StockLedger(centre_id=t.centre_id, product=t.product, delta=t.qty_bags,
                                  reason="RELEASE", ref_id=t.code, ts=_utcnow()))
                req = s.get(Request, t.request_id)
                if req:
                    req.status = "CANCELLED"
                expired += 1
    # Promote outside the expiry txn to reuse request_token's own transactions
    entries = db.query(WaitlistEntry).filter(WaitlistEntry.status == "WAITING").all()

    def _key(e: WaitlistEntry):
        f = db.get(Farmer, e.farmer_id)
        return (e.deadline, f.acres if f else 0, str(e.created_at))

    for e in sorted(entries, key=_key):
        req = db.get(Request, e.request_id)
        if req is None:
            continue
        farmer = db.get(Farmer, e.farmer_id)
        if farmer is None:
            continue
        states = _build_states(db, e.product)
        village = db.get(Village, farmer.village_id)
        fr = FarmerRequest(farmer_id=farmer.id, village_lat=village.lat if village else 0.0,
                           village_lon=village.lon if village else 0.0,
                           product=e.product, crop=req.crop, acres=req.acres, qty=e.qty,
                           sowing_date=req.sowing_date,
                           is_tenant_provisional=(farmer.type == "TENANT"
                                                  and farmer.verification == "PROVISIONAL"),
                           has_active_request=False,  # promoting its own waitlist slot
                           seasonal_remaining=e.qty, created_at=str(e.created_at))
        d = decide(fr, states, today, cfg)
        if d.outcome == "ISSUED" and d.centre_id and d.pickup_date:
            # Temporarily clear the old waitlist request so dup-check passes, then
            # cancel it and issue a fresh token under a derived idempotency key.
            old_key = req.idempotency_key
            req.status = "CANCELLED"
            e.status = "PROMOTED"
            db.commit()
            res = request_token(db, farmer_id=farmer.id, product=e.product, crop=req.crop,
                                acres=req.acres, qty=e.qty, sowing_date=req.sowing_date,
                                idempotency_key=f"{old_key}:promote:{e.id}",
                                today=today, cfg=cfg)
            if res.get("outcome") == "ISSUED":
                promoted += 1
            else:  # could not fulfil after all -> restore waiting state
                e.status = "WAITING"
                req.status = "WAITLISTED"
                db.commit()
        # else: still no stock — stays WAITING
    return {"expired": expired, "promoted": promoted}
