"""Village verifier routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import config as default_config
from ..auth import require_roles
from ..db import SessionLocal
from ..errors import BusinessError
from ..models import Farmer
from ..schemas import VerifierDecideIn
from ..services.identity import verifier_decide

router = APIRouter(tags=["verifier"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/verifier/pending")
def pending(cur: dict = Depends(require_roles("VERIFIER")), db=Depends(_db)):
    rows = db.query(Farmer).filter(Farmer.verification == "PROVISIONAL").all()
    return [{"id": f.id, "name": f.name, "phone": f.phone, "village_id": f.village_id,
             "acres": f.acres, "type": f.type, "landowner_name": f.landowner_name,
             "needs_audit": f.needs_audit} for f in rows]


@router.post("/verifier/{fid}/decide")
def decide(fid: int, body: VerifierDecideIn,
           cur: dict = Depends(require_roles("VERIFIER")), db=Depends(_db)):
    if body.decision not in ("APPROVED", "REJECTED"):
        raise BusinessError("BAD_DECISION", "decision must be APPROVED or REJECTED",
                            "निर्णय APPROVED या REJECTED हो", 400)
    res = verifier_decide(db, farmer_id=fid, verifier_id=cur["user_id"],
                          decision=body.decision, note=body.note,
                          cfg=default_config.get_config())
    if res.get("ok") is False:
        code = res.get("error", "FAILED")
        raise BusinessError(code, res.get("message", code), "सीमा पूरी", 409
                            if code == "DAILY_LIMIT" else 404)
    return res
