"""FastAPI app, CORS, router mounting (SPEC §6)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .db import SessionLocal, init_db
from .demo import demo_today_of
from .errors import BusinessError, business_handler
from .models import Meta
from .routers import admin, auth, centres, farmers, officer, sim, tokens, verifier
from .schemas import HealthOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        if db.get(Meta, "demo_today") is None:
            db.add(Meta(key="demo_today", value=config.SEASON_START))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="KhadSetu v2 (MOCK externals)", lifespan=lifespan)
app.add_exception_handler(BusinessError, business_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _r in (auth.router, farmers.router, tokens.router, centres.router,
           verifier.router, officer.router, admin.router, sim.router):
    app.include_router(_r, prefix="/api")


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    db = SessionLocal()
    try:
        return HealthOut(status="ok", demo_today=demo_today_of(db),
                         season_start=config.SEASON_START)
    finally:
        db.close()


@app.get("/health", response_model=HealthOut)
def health_alias() -> HealthOut:
    return health()