"""AI-3 anomaly watch (SPEC v3): ranked flags with plain reasons.

Statistics over signals the system already keeps. Flags ONLY — never changes
records, applies no penalty. Dismissals are logged (AuditEvent) and honoured.
Thresholds mirror ASSUMPTIONS.md anomaly policy.
"""
from __future__ import annotations

from sqlalchemy import func

from ..models import AuditEvent, Discrepancy, Farmer, Token, Verification

LIMIT_VERIFIER_DAY = 30
LIMIT_CENTRE_DISC = 3
LIMIT_FARMER_NOSHOW = 3
LIMIT_OPERATOR_ASSISTED = 15


def _dismissed(db) -> set[str]:
    rows = db.query(AuditEvent).filter(AuditEvent.action == "FLAG_DISMISSED").all()
    out = set()
    for r in rows:
        d = r.detail or {}
        if d.get("kind") and d.get("entity") is not None:
            out.add(f"{d['kind']}:{d['entity']}")
    return out


def flag(db) -> list[dict]:
    done = _dismissed(db)
    flags: list[dict] = []

    def _add(kind, entity, score, reason):
        if f"{kind}:{entity}" not in done:
            flags.append({"kind": kind, "entity": str(entity),
                          "score": round(score, 2), "reason": reason})

    today = func.date(Verification.ts)
    for vid, n in db.query(Verification.verifier_id, func.count()).filter(
            Verification.decision == "APPROVED").group_by(
            Verification.verifier_id, today).all():
        if n > LIMIT_VERIFIER_DAY:
            _add("approval_velocity", vid, n / LIMIT_VERIFIER_DAY,
                 f"Verifier {vid} approved {n} tenants in one day (limit {LIMIT_VERIFIER_DAY})")
    for cid, n in db.query(Discrepancy.centre_id, func.count()).group_by(
            Discrepancy.centre_id).all():
        if n > LIMIT_CENTRE_DISC:
            _add("centre_discrepancies", cid, n / LIMIT_CENTRE_DISC,
                 f"Centre {cid} has {n} stock discrepancies (limit {LIMIT_CENTRE_DISC})")
    for fid, n in db.query(Token.farmer_id, func.count()).filter(
            Token.status == "EXPIRED").group_by(Token.farmer_id).all():
        if n >= LIMIT_FARMER_NOSHOW:
            _add("repeated_no_show", fid, n / LIMIT_FARMER_NOSHOW,
                 f"Farmer {fid} no-showed {n} times (limit {LIMIT_FARMER_NOSHOW})")
    for op, n in db.query(Farmer.registered_by, func.count()).filter(
            Farmer.type == "ASSISTED").group_by(Farmer.registered_by).all():
        if op and n > LIMIT_OPERATOR_ASSISTED:
            _add("assisted_concentration", op, n / LIMIT_OPERATOR_ASSISTED,
                 f"Operator {op} registered {n} assisted farmers (limit {LIMIT_OPERATOR_ASSISTED})")
    flags.sort(key=lambda f: -f["score"])
    return flags


def dismiss(db, *, kind: str, entity: str, officer_id: str = "officer") -> dict:
    db.add(AuditEvent(actor_role="OFFICER", actor_id=officer_id,
                      action="FLAG_DISMISSED", entity="flag", entity_id=f"{kind}:{entity}",
                      detail={"kind": kind, "entity": entity}))
    db.commit()
    return {"ok": True, "dismissed": f"{kind}:{entity}"}
