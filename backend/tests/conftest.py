"""Shared pytest fixtures (Phase 1: fresh DB per test module)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# backend/ on path so `app.*` imports work when running from root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Hard-set test DB (never touch prod even if env already defines DATABASE_URL)
os.environ["DATABASE_URL"] = "sqlite:///./khadsetu_test.db"

from app import config  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Meta  # noqa: E402


@pytest.fixture()
def db():
    init_db()
    s = SessionLocal()
    try:
        # clean all rows for isolation
        for t in ["discrepancy", "audit_event", "verification", "waitlist_entry",
                  "token", "request", "farmer", "stock_ledger", "stock_pool",
                  "stock_lot", "village", "centre", "user", "meta"]:
            s.execute(text(f"DELETE FROM {t}"))
        s.merge(Meta(key="demo_today", value=config.SEASON_START))
        s.commit()
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    init_db()
    with TestClient(app) as c:
        yield c
