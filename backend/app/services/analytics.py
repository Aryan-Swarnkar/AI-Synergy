"""Officer dashboard aggregates (read-only) + rule-preview replay."""
from __future__ import annotations

import math

from sqlalchemy import func

from .. import config as default_config
from ..core.allocator import decide
from ..core.types import CentreState, FarmerRequest
from ..models import AuditEvent, Centre, Discrepancy, Farmer, Request, StockPool, Token, Verification, Village, WaitlistEntry
from .tokens import _build_states


def _available(pool: StockPool | None, pct: float) -> int:
    if pool is None:
        return 0
    buf = math.ceil(max(0, pool.on_hand) * pct / 100.0)
    return pool.on_hand - pool.reserved - buf


def overview(db, today: str, cfg: dict | None = None) -> dict:
    cfg = cfg or default_config.get_config()
    pct = cfg.get("SAFETY_BUFFER_PCT", 3)
    centres = db.query(Centre).filter(Centre.active.is_(True)).all()
    pools = {(p.centre_id, p.product): p for p in db.query(StockPool).all()}
    products = sorted({p.product for p in pools.values()} or ["UREA", "DAP", "MOP", "NPK"])

    stock_health = []
    for c in centres:
        for prod in products:
            pool = pools.get((c.id, prod))
            av = _available(pool, pct)
            on = pool.on_hand if pool else 0
            health = "empty" if av <= 0 else ("low" if av < 0.2 * max(on, 1) else "ok")
            stock_health.append({"centre_id": c.id, "centre": c.name, "product": prod,
                                 "on_hand": on, "reserved": pool.reserved if pool else 0,
                                 "available": av, "health": health})

    demand, supply = {}, {}
    for prod in products:
        dq = db.query(func.coalesce(func.sum(Request.qty_requested), 0)).filter(
            Request.product == prod,
            Request.status.in_(["ISSUED", "WAITLISTED"])).scalar() or 0
        sq = sum(p.on_hand for (cid, pr), p in pools.items() if pr == prod)
        demand[prod], supply[prod] = int(dq), int(sq)

    waiting = db.query(WaitlistEntry).filter(WaitlistEntry.status == "WAITING").all()
    at_risk = [{"farmer_id": w.farmer_id, "product": w.product, "qty": w.qty,
                "eta_date": w.eta_date, "deadline": w.deadline}
               for w in waiting if w.at_risk]

    funnel = {s: db.query(func.count(Token.id)).filter(Token.status == s).scalar() or 0
              for s in ("ISSUED", "REDEEMED", "EXPIRED", "CANCELLED")}

    anomalies: list[dict] = []
    ver_rows = db.query(Verification.verifier_id, func.count(Verification.id)).group_by(
        Verification.verifier_id).all()
    for vid, n in ver_rows:
        if n > 30:
            anomalies.append({"kind": "verifier_volume",
                              "detail": f"Verifier {vid} decided {n} cases"})
    disc_rows = db.query(Discrepancy.centre_id, func.count(Discrepancy.id)).group_by(
        Discrepancy.centre_id).all()
    for cid, n in disc_rows:
        if n > 3:
            anomalies.append({"kind": "centre_discrepancies",
                              "detail": f"Centre {cid} has {n} discrepancies"})
    noshow_rows = db.query(Token.farmer_id, func.count(Token.id)).filter(
        Token.status == "EXPIRED").group_by(Token.farmer_id).all()
    for fid, n in noshow_rows:
        if n >= 3:
            anomalies.append({"kind": "repeated_no_show",
                              "detail": f"Farmer {fid} no-showed {n} times"})

    return {"demo_today": today, "stock_health": stock_health,
            "demand_vs_supply": {p: {"demand": demand[p], "supply": supply[p]}
                                 for p in products},
            "waitlist_size": len(waiting),
            "at_risk": at_risk, "token_funnel": funnel, "anomalies": anomalies,
            "mock_note": "MOCK externals: OTP / Farmer ID / SMS / iFMS feed are simulated"}


def map_data(db, cfg: dict | None = None) -> dict:
    cfg = cfg or default_config.get_config()
    pct = cfg.get("SAFETY_BUFFER_PCT", 3)
    centres = db.query(Centre).filter(Centre.active.is_(True)).all()
    pools = {(p.centre_id, p.product): p for p in db.query(StockPool).all()}
    cout = []
    for c in centres:
        av = sum(_available(pools.get((c.id, pr)), pct)
              for pr in ("UREA", "DAP", "MOP", "NPK"))
        on = sum((pools.get((c.id, pr)).on_hand if pools.get((c.id, pr)) else 0)
                 for pr in ("UREA", "DAP", "MOP", "NPK"))
        health = "empty" if av <= 0 else ("low" if av < 0.2 * max(on, 1) else "ok")
        cout.append({"id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon,
                     "health": health, "available": av})
    vout = []
    for v in db.query(Village).all():
        pend = db.query(func.count(Request.id)).join(
            Farmer, Farmer.id == Request.farmer_id).filter(
            Farmer.village_id == v.id,
            Request.status.in_(["ISSUED", "WAITLISTED"])).scalar() or 0
        vout.append({"id": v.id, "name": v.name, "lat": v.lat, "lon": v.lon,
                     "pending_demand": int(pend)})
    return {"centres": cout, "villages": vout}


def rule_preview(db, today: str, overrides: dict, base_cfg: dict | None = None) -> dict:
    """Read-only: replay current WAITING demand through decide() under base
    vs patched config; report how many would issue now. No writes."""
    base = base_cfg or default_config.get_config()
    patched = dict(base)
    patched.update(overrides or {})
    waiting = db.query(WaitlistEntry).filter(WaitlistEntry.status == "WAITING").all()
    base_states = {p: _build_states(db, p) for p in {w.product for w in waiting}}
    base_n = patched_n = 0
    for w in waiting:
        req = db.get(Request, w.request_id)
        farmer = db.get(Farmer, w.farmer_id)
        if req is None or farmer is None:
            continue
        village = db.get(Village, farmer.village_id)
        fr = FarmerRequest(farmer_id=farmer.id,
                           village_lat=village.lat if village else 0.0,
                           village_lon=village.lon if village else 0.0,
                           product=w.product, crop=req.crop, acres=req.acres, qty=w.qty,
                           sowing_date=req.sowing_date,
                           is_tenant_provisional=(farmer.type == "TENANT"
                                                  and farmer.verification == "PROVISIONAL"),
                           has_active_request=False, seasonal_remaining=w.qty,
                           created_at=str(w.created_at))
        if decide(fr, base_states[w.product], today, base).outcome == "ISSUED":
            base_n += 1
        if decide(fr, base_states[w.product], today, patched).outcome == "ISSUED":
            patched_n += 1
    return {"waiting": len(waiting), "would_issue_base": base_n,
            "would_issue_patched": patched_n, "delta": patched_n - base_n,
            "overrides": overrides or {}, "read_only": True}
