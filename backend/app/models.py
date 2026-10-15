"""SQLAlchemy models (SPEC §4)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    # Naive UTC (SQLite-friendly) without deprecated utcnow()
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Centre(Base):
    __tablename__ = "centre"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    district: Mapped[str] = mapped_column(String(120), default="Sehore")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StockLot(Base):
    __tablename__ = "stock_lot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centre.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    qty_bags: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_ref: Mapped[str] = mapped_column(String(120), default="MOCK-iFMS")


class StockPool(Base):
    __tablename__ = "stock_pool"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centre.id"), primary_key=True)
    product: Mapped[str] = mapped_column(String(20), primary_key=True)
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    discrepancy_total: Mapped[int] = mapped_column(Integer, default=0)


class StockLedger(Base):
    __tablename__ = "stock_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centre.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)  # RECEIVE|RESERVE|RELEASE|REDEEM|AUDIT_ADJUST
    ref_id: Mapped[str] = mapped_column(String(120), default="")
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Village(Base):
    __tablename__ = "village"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    district: Mapped[str] = mapped_column(String(120), default="Sehore")


class Farmer(Base):
    __tablename__ = "farmer"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    village_id: Mapped[int] = mapped_column(ForeignKey("village.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # LANDOWNER|TENANT|ASSISTED
    farmer_id_mock: Mapped[str | None] = mapped_column(String(60), nullable=True)
    acres: Mapped[float] = mapped_column(Float, nullable=False)
    verification: Mapped[str] = mapped_column(String(20), default="VERIFIED")  # VERIFIED|PROVISIONAL|REJECTED
    needs_audit: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    landowner_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Request(Base):
    __tablename__ = "request"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmer.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    crop: Mapped[str] = mapped_column(String(20), nullable=False)
    acres: Mapped[float] = mapped_column(Float, nullable=False)
    qty_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    sowing_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(String(20), default="ISSUED")  # ISSUED|WAITLISTED|REJECTED|CANCELLED|COMPLETED
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Token(Base):
    __tablename__ = "token"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id"), nullable=False)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmer.id"), nullable=False)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centre.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    qty_bags: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup_date: Mapped[str] = mapped_column(String(10), nullable=False)
    slot: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ISSUED")  # ISSUED|REDEEMED|EXPIRED|CANCELLED
    reschedules_used: Mapped[int] = mapped_column(Integer, default=0)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[str] = mapped_column(String(10), default="")
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_by: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ProvenanceEvent(Base):
    """Decision provenance (v3): which step was AI / rule engine / human."""
    __tablename__ = "provenance_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("token.id"), nullable=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id"), nullable=False)
    step: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False)  # AI|RULE|HUMAN
    actor_name: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id"), nullable=False)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmer.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[str] = mapped_column(String(10), nullable=False)
    priority_score: Mapped[str] = mapped_column(String(120), default="")
    eta_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    at_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    status: Mapped[str] = mapped_column(String(20), default="WAITING")  # WAITING|PROMOTED|EXPIRED


class Verification(Base):
    __tablename__ = "verification"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmer.id"), nullable=False)
    verifier_id: Mapped[str] = mapped_column(String(60), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED|REJECTED
    note: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(60), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Discrepancy(Base):
    __tablename__ = "discrepancy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centre.id"), nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    ledger_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[str] = mapped_column(String(60), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # FARMER|OPERATOR|VERIFIER|OFFICER
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    centre_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    village_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Meta(Base):
    """Singleton KV for demo clock etc."""
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
