"""Operator stock ops: receive-lot + audit with auto-reassign (SPEC §5.5).

Receive model: pending lots (received_at IS NULL) feed the allocator's
projection but are NOT in on_hand. Receiving consumes matching pending lots
(arrival_date <= given date) into on_hand plus the operator-declared qty
difference (rake shortfalls/surpluses stay honest).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .tokens import _buffer  # reuse buffer helper (pure logic)
from ..db import immediate_txn
from ..models import AuditEvent, Discrepancy, Farmer, Request, StockLedger, StockLot, StockPool, Token


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def receive_lot(db, *, centre_id: int, product: str, qty: int, arrival_date: str,
                source_ref: str = "MOCK-iFMS", operator_id: str = "op") -> dict:
    """Confirm a delivery: pending expectations become on-hand + declared qty."""
    with immediate_txn(db) as s:
        pending = s.query(StockLot).filter(
            StockLot.centre_id == centre_id, StockLot.product == product,
            StockLot.received_at.is_(None), StockLot.arrival_date <= arrival_date).all()
        for lot in pending:
            lot.received_at = _utcnow()
        pool = s.get(StockPool, (centre_id, product))
        if pool is None:
            pool = StockPool(centre_id=centre_id, product=product, on_hand=0,
                             reserved=0, discrepancy_total=0)
            s.add(pool)
        pool.on_hand += qty
        s.add(StockLot(centre_id=centre_id, product=product, qty_bags=qty,
                       arrival_date=arrival_date, received_at=_utcnow(),
                       source_ref=source_ref))
        s.add(StockLedger(centre_id=centre_id, product=product, delta=qty,
                          reason="RECEIVE", ref_id=source_ref, ts=_utcnow()))
        s.add(AuditEvent(actor_role="OPERATOR", actor_id=operator_id, action="RECEIVE",
                         entity="stock", entity_id=f"{centre_id}:{product}",
                         detail={"qty": qty, "arrival": arrival_date,
                                 "consumed_pending": len(pending)}))
    return {"ok": True, "consumed_pending": len(pending), "on_hand": pool.on_hand}


def audit(db, *, centre_id: int, product: str, counted_qty: int,
          operator_id: str, today: str, cfg: dict | None = None) -> dict:
    """Physical count wins. Logs discrepancy; if physical stock cannot cover
    reservations, cancels newest tokens until it can, then re-runs the
    allocator for each affected farmer (reassignment with notification text).

    SPEC §5.5 says 'if shortfall exceeds reserved'; implemented as
    `counted - buffer < reserved` (physical cannot cover holds), which is the
    operative condition — see ASSUMPTIONS.md.
    """
    from .tokens import request_token
    cfg = cfg or {}
    buf_pct = cfg.get("SAFETY_BUFFER_PCT", 3)
    cancelled: list[dict] = []
    reassigned: list[dict] = []
    delta_out = 0
    with immediate_txn(db) as s:
        pool = s.get(StockPool, (centre_id, product))
        ledger_qty = pool.on_hand if pool else 0
        delta = counted_qty - ledger_qty
        delta_out = delta
        s.add(Discrepancy(centre_id=centre_id, product=product, ledger_qty=ledger_qty,
                          counted_qty=counted_qty, delta=delta,
                          operator_id=operator_id, ts=_utcnow()))
        if pool is None:
            pool = StockPool(centre_id=centre_id, product=product, on_hand=counted_qty,
                             reserved=0, discrepancy_total=delta)
            s.add(pool)
        else:
            pool.on_hand = counted_qty
            pool.discrepancy_total += delta
        s.add(StockLedger(centre_id=centre_id, product=product, delta=delta,
                          reason="AUDIT_ADJUST", ref_id=f"audit-{operator_id}",
                          ts=_utcnow()))
        s.add(AuditEvent(actor_role="OPERATOR", actor_id=operator_id, action="AUDIT",
                         entity="stock", entity_id=f"{centre_id}:{product}",
                         detail={"ledger": ledger_qty, "counted": counted_qty,
                                 "delta": delta}))
        # Over-held? Cancel newest first until physical covers reservations.
        while pool.reserved > max(0, counted_qty - _buffer(counted_qty, buf_pct)):
            newest = s.query(Token).filter(
                Token.centre_id == centre_id, Token.product == product,
                Token.status == "ISSUED").order_by(Token.issued_at.desc()).first()
            if newest is None:
                break
            newest.status = "CANCELLED"
            pool.reserved = max(0, pool.reserved - newest.qty_bags)
            s.add(StockLedger(centre_id=centre_id, product=product,
                              delta=newest.qty_bags, reason="RELEASE",
                              ref_id=f"audit-{newest.code}", ts=_utcnow()))
            req = s.get(Request, newest.request_id)
            if req:
                req.status = "CANCELLED"
            cancelled.append({"code": newest.code, "farmer_id": newest.farmer_id,
                              "qty": newest.qty_bags,
                              "old_key": req.idempotency_key if req else ""})
    # Reassign outside the audit txn (each gets its own reservation txn).
    for c in cancelled:
        f = db.get(Farmer, c["farmer_id"])
        old_req = db.query(Request).filter(
            Request.idempotency_key == c["old_key"]).first() if c["old_key"] else None
        if f is None or old_req is None:
            continue
        res = request_token(db, farmer_id=f.id, product=product, crop=old_req.crop,
                            acres=old_req.acres, qty=c["qty"],
                            sowing_date=old_req.sowing_date,
                            idempotency_key=f"{c['old_key']}:audit:{c['code']}",
                            today=today, cfg=cfg or None)
        res["notification"] = ("Your centre reported less stock; "
                               f"we moved your token ({c['code']} cancelled).")
        reassigned.append(res)
    return {"ok": True, "delta": delta_out,
            "cancelled": cancelled, "reassigned": reassigned}
