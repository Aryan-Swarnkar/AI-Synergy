"""Pydantic schemas. Phase 1: minimal; extended in later phases."""
from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    demo_today: str
    season_start: str


class DemoLoginIn(BaseModel):
    role: str
    user_id: str


class FarmerRegisterIn(BaseModel):
    name: str
    phone: str
    village_id: int
    acres: float
    type: str = "LANDOWNER"  # LANDOWNER | TENANT
    farmer_id_mock: str | None = None
    landowner_name: str | None = None
    language: str = "en"


class OtpSendIn(BaseModel):
    phone: str


class OtpVerifyIn(BaseModel):
    phone: str
    code: str


class AssistedIn(BaseModel):
    name: str
    phone: str
    village_id: int
    acres: float


class RequestIn(BaseModel):
    product: str
    crop: str
    acres: float
    qty: int
    sowing_date: str
    idempotency_key: str
    provenance: dict | None = None  # v3: {ai_proposal, confirmed_edits}


class VerifierDecideIn(BaseModel):
    decision: str  # APPROVED | REJECTED
    note: str = ""


class RedeemIn(BaseModel):
    code: str


class ReceiveLotIn(BaseModel):
    product: str
    qty: int
    arrival_date: str


class AuditIn(BaseModel):
    product: str
    counted_qty: int


class RulePreviewIn(BaseModel):
    overrides: dict = {}
