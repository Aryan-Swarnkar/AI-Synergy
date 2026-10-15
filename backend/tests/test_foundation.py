"""Phase-1 foundation tests: health, WAL mode, seed counts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "demo_today" in body and "season_start" in body


def test_health_alias(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_wal_mode():
    from sqlalchemy import text
    from app.db import engine

    with engine.connect() as c:
        mode = c.execute(text("PRAGMA journal_mode")).scalar()
    assert str(mode).lower() == "wal"


def test_seed_counts(db):
    from app.seed import seed
    from app.models import Centre, Farmer, Village

    out = seed()
    assert out["centres"] == 6
    assert out["villages"] == 40
    assert out["farmers"] == 60
    assert db.query(Centre).count() == 6
    assert db.query(Village).count() == 40
    assert db.query(Farmer).count() == 60
