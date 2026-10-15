"""Identity: OTP mock (MOCK-labelled), fallbacks, tenant/verifier, assisted (SPEC §3.2-3.3).

Everything external is mocked: OTP codes are fixed, Farmer ID is a formatted
string, voice callback "speaks" a code in the API response, assisted bypasses
OTP with an audited operator record. All fallbacks write AuditEvent rows so
they cannot become silent loopholes (§1.4).
"""
from __future__ import annotations

import random
import secrets
from datetime import datetime, timezone

from .. import config as default_config
from ..db import immediate_txn
from ..models import AuditEvent, Farmer, Request, StockLedger, StockPool, Token, Verification, Village

# In-memory mock OTP store: {phone: {code, attempts}}. Mock only — real impl
# would call an SMS gateway; the UI labels every OTP surface MOCK.
_OTP: dict[str, dict] = {}
_VOICE_CODE = "654321"
_OTP_CODE = "123456"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _should_fail(phone: str, cfg: dict) -> bool:
    if phone.endswith("000"):
        return True
    return random.random() < cfg.get("OTP_FAIL_RATE", 0.15)


def send_otp(phone: str, cfg: dict | None = None) -> dict:
    """Mock send. Deterministic fail for phones ending 000 (demo path)."""
    cfg = cfg or default_config.get_config()
    _OTP[phone] = {"code": _OTP_CODE, "attempts": 0, "fail": _should_fail(phone, cfg)}
    return {"sent": True, "mock": True, "hint": "MOCK OTP — code is 123456 unless failing"}


def verify_otp(db, phone: str, code: str, cfg: dict | None = None) -> dict:
    """Verify; after the 2nd failure return never-blocking fallback_options."""
    cfg = cfg or default_config.get_config()
    st = _OTP.get(phone, {"code": _OTP_CODE, "attempts": 0, "fail": _should_fail(phone, cfg)})
    st["attempts"] = st.get("attempts", 0) + 1
    _OTP[phone] = st
    ok = (code == st["code"]) and not st.get("fail", False)
    if ok:
        _OTP.pop(phone, None)
        return {"verified": True, "mock": True}
    if st["attempts"] >= 2:
        db.add(AuditEvent(actor_role="FARMER", actor_id=phone, action="OTP_FALLBACK_SHOWN",
                          entity="otp", entity_id=phone,
                          detail={"attempts": st["attempts"]}))
        db.commit()
        return {"verified": False, "mock": True, "attempts": st["attempts"],
                "fallback_options": ["RETRY_LATER", "VOICE_CALLBACK", "ASSISTED_AT_CENTRE"]}
    return {"verified": False, "mock": True, "attempts": st["attempts"]}


def voice_callback(phone: str) -> dict:
    """MOCK voice fallback: the 'spoken' code is returned in the response."""
    _OTP[phone] = {"code": _VOICE_CODE, "attempts": 0, "fail": False}
    return {"mock": True, "spoken_code": _VOICE_CODE,
            "message": "MOCK voice call — use 654321 as the OTP code"}


def assisted_prereg_code() -> str:
    return "AST-" + secrets.token_hex(3).upper()


def register_farmer(db, *, name: str, phone: str, village_id: int, acres: float,
                    ftype: str, farmer_id_mock: str | None = None,
                    landowner_name: str | None = None, language: str = "en",
                    registered_by: str | None = None) -> Farmer:
    """Register LANDOWNER (VERIFIED) / TENANT (PROVISIONAL, needs_audit) /
    ASSISTED (PROVISIONAL, needs_audit, operator recorded). Phone unique."""
    verification = "VERIFIED" if ftype == "LANDOWNER" else "PROVISIONAL"
    needs_audit = ftype in ("TENANT", "ASSISTED")
    with immediate_txn(db) as s:
        f = Farmer(name=name, phone=phone, village_id=village_id, type=ftype,
                   farmer_id_mock=farmer_id_mock, acres=acres,
                   verification=verification, needs_audit=needs_audit,
                   registered_by=registered_by, language=language,
                   landowner_name=landowner_name)
        s.add(f)
        s.flush()
        s.add(AuditEvent(actor_role="OPERATOR" if registered_by else "FARMER",
                         actor_id=registered_by or phone, action="REGISTER",
                         entity="farmer", entity_id=str(f.id),
                         detail={"type": ftype, "verification": verification}))
    return f


def assisted_register(db, *, name: str, phone: str, village_id: int, acres: float,
                      operator_id: str) -> Farmer:
    """Operator/VLE path: bypasses OTP, always audited."""
    return register_farmer(db, name=name, phone=phone, village_id=village_id,
                           acres=acres, ftype="ASSISTED", registered_by=operator_id)


def verifier_decide(db, *, farmer_id: int, verifier_id: str, decision: str,
                    note: str = "", cfg: dict | None = None) -> dict:
    """Approve (PROVISIONAL->VERIFIED, future requests at 100%) or reject
    (cancels unredeemed tokens + releases reservations). Enforces daily limit."""
    cfg = cfg or default_config.get_config()
    limit: int = cfg.get("VERIFIER_DAILY_LIMIT", 40)
    with immediate_txn(db) as s:
        today = _utcnow().date().isoformat()
        # Daily APPROVAL limit per SPEC §3.2 (rejections never count against it)
        done = s.query(Verification).filter(
            Verification.verifier_id == verifier_id,
            Verification.decision == "APPROVED",
            Verification.ts >= today).count()
        if decision == "APPROVED" and done >= limit:
            return {"ok": False, "error": "DAILY_LIMIT",
                    "message": f"Verifier daily limit ({limit}) reached"}
        farmer = s.get(Farmer, farmer_id)
        if farmer is None:
            return {"ok": False, "error": "NOT_FOUND"}
        s.add(Verification(farmer_id=farmer_id, verifier_id=verifier_id,
                           decision=decision, note=note, ts=_utcnow()))
        if decision == "APPROVED":
            farmer.verification = "VERIFIED"
        elif decision == "REJECTED":
            farmer.verification = "REJECTED"
            # Cancel unredeemed tokens, release stock (ledger RELEASE each)
            toks = s.query(Token).filter(Token.farmer_id == farmer_id,
                                         Token.status == "ISSUED").all()
            for t in toks:
                t.status = "CANCELLED"
                pool = s.get(StockPool, (t.centre_id, t.product))
                if pool:
                    pool.reserved = max(0, pool.reserved - t.qty_bags)
                s.add(StockLedger(centre_id=t.centre_id, product=t.product,
                                  delta=t.qty_bags, reason="RELEASE",
                                  ref_id=f"reject-{t.code}", ts=_utcnow()))
                req = s.get(Request, t.request_id)
                if req:
                    req.status = "CANCELLED"
            # Waiting entries expire
            from ..models import WaitlistEntry
            for w in s.query(WaitlistEntry).filter(
                    WaitlistEntry.farmer_id == farmer_id,
                    WaitlistEntry.status == "WAITING").all():
                w.status = "EXPIRED"
        s.add(AuditEvent(actor_role="VERIFIER", actor_id=verifier_id,
                         action=f"VERIFY_{decision}", entity="farmer",
                         entity_id=str(farmer_id), detail={"note": note}))
    return {"ok": True, "decision": decision}
