"""FastAPI app, CORS, router mounting (SPEC §6). Phase 1: /health only."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .db import SessionLocal, init_db
from .models import Meta
from .schemas import HealthOut


def ensure_demo_today() -> str:
    init_db()
    db = SessionLocal()
    try:
        row = db.get(Meta, "demo_today")
        if row is None:
            db.add(Meta(key="demo_today", value=config.SEASON_START))
            db.commit()
            return config.SEASON_START
        return row.value
    finally:
        db.close()


def get_demo_today() -> str:
    try:
        return ensure_demo_today()
    except Exception:
        return config.SEASON_START


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_demo_today()
    yield


app = FastAPI(title="KhadSetu v2 (MOCK externals)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_demo_today() -> str:
    db = SessionLocal()
    try:
        row = db.get(Meta, "demo_today")
        if row is None:
            return config.SEASON_START
        return row.value
    finally:
        db.close()


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", demo_today=ensure_demo_today(), season_start=config.SEASON_START)


@app.get("/health", response_model=HealthOut)
def health_alias() -> HealthOut:
    return health()
