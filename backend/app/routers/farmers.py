"""Farmer + OTP (MOCK) routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError

from ..auth import require_roles
from ..core.norms import entitlement, provisional_cap
from ..db import SessionLocal
from ..errors import BusinessError
from ..models import Farmer, Village
from ..schemas import AssistedIn, FarmerRegisterIn, OtpSendIn, OtpVerifyIn
from ..services.identity import assisted_register, register_farmer, send_otp, verify_otp, voice_callback

router = APIRouter(tags=["farmers"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _farmer_out(f: Farmer) -> dict:
    return {"id": f.id, "name": f.name, "phone": f.phone, "village_id": f.village_id,
            "type": f.type, "verification": f.verification,
            "needs_audit": f.needs_audit, "acres": f.acres,
            "language": f.language, "mock_farmer_id": f.farmer_id_mock}


@router.post("/farmers/register")
def register(body: FarmerRegisterIn, db=Depends(_db)):
    if body.type not in ("LANDOWNER", "TENANT"):
        raise BusinessError("BAD_TYPE", "type must be LANDOWNER or TENANT",
                            "प्रकार LANDOWNER या TENANT हो", 400)
    if db.get(Village, body.village_id) is None:
        raise BusinessError("NO_VILLAGE", "Unknown village_id", "गाँव नहीं मिला", 404)
    try:
        f = register_farmer(db, name=body.name, phone=body.phone,
                            village_id=body.village_id, acres=body.acres,
                            ftype=body.type, farmer_id_mock=body.farmer_id_mock,
                            landowner_name=body.landowner_name, language=body.language)
    except IntegrityError:
        raise BusinessError("PHONE_EXISTS", "Phone already registered",
                            "यह फ़ोन पहले से पंजीकृत है", 409)
    return {**_farmer_out(f), "mock": True}


@router.post("/otp/send")
def otp_send(body: OtpSendIn):
    return send_otp(body.phone)


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyIn, db=Depends(_db)):
    return verify_otp(db, body.phone, body.code)


@router.post("/otp/voice-callback")
def otp_voice(body: OtpSendIn):
    return voice_callback(body.phone)


@router.post("/farmers/assisted-register")
def assisted(body: AssistedIn, cur: dict = Depends(require_roles("OPERATOR")),
             db=Depends(_db)):
    if db.get(Village, body.village_id) is None:
        raise BusinessError("NO_VILLAGE", "Unknown village_id", "गाँव नहीं मिला", 404)
    try:
        f = assisted_register(db, name=body.name, phone=body.phone,
                              village_id=body.village_id, acres=body.acres,
                              operator_id=cur["user_id"])
    except IntegrityError:
        raise BusinessError("PHONE_EXISTS", "Phone already registered",
                            "यह फ़ोन पहले से पंजीकृत है", 409)
    return {**_farmer_out(f), "mock": True}


@router.get("/farmers/{fid}")
def get_farmer(fid: int, db=Depends(_db)):
    f = db.get(Farmer, fid)
    if f is None:
        raise BusinessError("FARMER_NOT_FOUND", "Farmer not found",
                            "किसान नहीं मिला", 404)
    return _farmer_out(f)


@router.get("/farmers/{fid}/entitlement")
def get_entitlement(fid: int, product: str, crop: str, db=Depends(_db)):
    from .. import config
    f = db.get(Farmer, fid)
    if f is None:
        raise BusinessError("FARMER_NOT_FOUND", "Farmer not found",
                            "किसान नहीं मिला", 404)
    full = entitlement(f.acres, crop, product)
    prov = provisional_cap(full, config.TENANT_PROVISIONAL_FACTOR)
    return {"farmer_id": fid, "product": product, "crop": crop, "acres": f.acres,
            "full_entitlement": full, "provisional_cap": prov,
            "applies_provisional": f.type == "TENANT" and f.verification == "PROVISIONAL",
            "disclaimer": "Demo dose values, not agronomic advice."}
