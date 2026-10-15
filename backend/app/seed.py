"""Seed demo district near Bhopal/Sehore (SPEC §9).

6 centres, 40 villages (fictional), 60 farmers (landowner/tenant/assisted),
deliberate imbalance: Centre A nearly out of UREA, Centre B rake in +3 days.
Idempotent: wipes KhadSetu tables then reseeds. Run: `make seed`.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlalchemy import text

from . import config
from .db import SessionLocal, init_db
from .models import Centre, Farmer, Meta, StockLot, StockPool, StockLedger, User, Village


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

PRODUCTS = ["UREA", "DAP", "MOP", "NPK"]

CENTRES = [
    # (name, lat, lon) — Centre A nearly out of urea; Centre B future rake
    ("Centre A — Sehore PACS", 23.20, 77.08),
    ("Centre B — Ashta Mandi", 23.02, 77.28),
    ("Centre C — Ichhawar PACS", 23.35, 77.45),
    ("Centre D — Nasrullaganj", 22.95, 77.60),
    ("Centre E — Budhni Depot", 23.50, 77.70),
    ("Centre F — Bhopal Road", 23.10, 77.85),
]

VILLAGE_NAMES = [
    "Rampur Kalan", "Chandbad", "Mogra", "Pipaliya", "Barkheda", "Sehore Gaon",
    "Dewas Naka", "Kotra", "Silwani", "Berasia Rd", "Kolar Kalan", "Hata",
    "Shahganj", "Rehti", "Jawar", "Bilkisganj", "Doraha", "Narsinghgarh Rd",
    "Parwalia", "Gyaraspur Rd", "Kurawar", "Siddiqganj", "Satpipalya", "Amalya",
    "Badiyakhedi", "Chhapri", "Dhamanda", "Gopalpur", "Hasanpur", "Itarsi Rd",
    "Jaitpura", "Kankarkheda", "Lasudiya", "Mundikhedi", "Nipaniya", "Pangra",
    "Rolan", "Semli", "Talen Rd", "Umarpura",
]


def _date(offset_days: int) -> str:
    from datetime import date

    y, m, d = (int(x) for x in config.SEASON_START.split("-"))
    base = date(y, m, d)
    from datetime import timedelta

    return (base + timedelta(days=offset_days)).isoformat()


def seed() -> dict:
    init_db()
    rng = random.Random(42)
    db = SessionLocal()
    try:
        # Wipe (child -> parent order)
        for t in ["provenance_event", "discrepancy", "audit_event", "verification",
                  "waitlist_entry",
                  "token", "request", "farmer", "stock_ledger", "stock_pool",
                  "stock_lot", "village", "centre", "user", "meta"]:
            db.execute(text(f"DELETE FROM {t}"))
        db.commit()

        # Centres
        centres: list[Centre] = []
        for name, lat, lon in CENTRES:
            c = Centre(name=name, lat=lat, lon=lon, district="Sehore", active=True)
            db.add(c)
            centres.append(c)
        db.flush()

        # Villages: clustered around centres, last 3 deliberately far
        villages: list[Village] = []
        for i, vname in enumerate(VILLAGE_NAMES):
            ci = i % len(centres)
            clat, clon = CENTRES[ci][1], CENTRES[ci][2]
            if i >= 37:  # far villages 30-50 km away
                lat = clat + rng.uniform(0.28, 0.42)
                lon = clon + rng.uniform(0.28, 0.42)
            else:
                lat = clat + rng.uniform(-0.12, 0.12)
                lon = clon + rng.uniform(-0.12, 0.12)
            v = Village(name=vname, lat=lat, lon=lon, district="Sehore")
            db.add(v)
            villages.append(v)
        db.flush()

        # Stock: on-hand lots (arrival day 0, received) + Centre B future rake day+3
        for ci, c in enumerate(centres):
            for p in PRODUCTS:
                if ci == 0 and p == "UREA":
                    on_hand = 2  # nearly out
                elif p == "UREA":
                    on_hand = rng.randint(60, 140)
                else:
                    on_hand = rng.randint(40, 100)
                lot = StockLot(centre_id=c.id, product=p, qty_bags=on_hand,
                               arrival_date=_date(0), received_at=_utcnow(),
                               source_ref="MOCK-iFMS-rake-01")
                db.add(lot)
                db.add(StockPool(centre_id=c.id, product=p, on_hand=on_hand,
                                 reserved=0, discrepancy_total=0))
                db.add(StockLedger(centre_id=c.id, product=p, delta=on_hand,
                                   reason="RECEIVE", ref_id="seed", ts=_utcnow()))
        # Future rake for Centre B (+3 days, UREA 200 bags, not yet received)
        db.add(StockLot(centre_id=centres[1].id, product="UREA", qty_bags=200,
                        arrival_date=_date(3), received_at=None,
                        source_ref="MOCK-iFMS-rake-ETA3d"))
        db.flush()

        # Farmers: 60 = 40 landowner / 12 tenant / 8 assisted
        first = ["Ramesh", "Suresh", "Mohan", "Geeta", "Sunita", "Raju", "Kalu",
                 "Bhagwan", "Rekha", "Asha", "Vikram", "Anil", "Prakash", "Meena"]
        last = ["Verma", "Patel", "Yadav", "Lodhi", "Meena", "Gurjar", "Thakur"]
        for i in range(60):
            v = villages[i % len(villages)]
            if i < 40:
                ftype, verif, audit = "LANDOWNER", "VERIFIED", False
            elif i < 52:
                ftype, verif, audit = "TENANT", "PROVISIONAL", True
            else:
                ftype, verif, audit = "ASSISTED", "PROVISIONAL", True
            phone = f"98765{i:05d}"
            if i in (1, 7):  # demo OTP-fail phones ending 000
                phone = f"98765{i:02d}000"
            name = f"{first[i % len(first)]} {last[(i * 3) % len(last)]}"
            if i == 0:
                # Demo hero per SPEC §11: tenant + OTP must fail -> explicit 000 phone
                name = "Ramesh Patel"
                phone = "9876500000"
                ftype, verif, audit = "TENANT", "PROVISIONAL", True
                v = villages[37]  # far village ~38km from Centre A
            db.add(Farmer(
                name=name, phone=phone, village_id=v.id, type=ftype,
                farmer_id_mock=f"MP-{100000 + i}" if ftype == "LANDOWNER" else None,
                acres=round(rng.uniform(0.5, 4.0), 1),
                verification=verif, needs_audit=audit,
                registered_by="op1" if ftype == "ASSISTED" else None,
                language="hi" if i % 3 == 0 else "en",
                landowner_name="Hari Singh" if ftype == "TENANT" and i % 2 == 0 else None,
            ))
        # Users: 2 operators, 2 verifiers, 1 officer (+farmers implicit)
        db.add_all([
            User(role="OPERATOR", name="Op One (Centre A)", centre_id=centres[0].id),
            User(role="OPERATOR", name="Op Two (Centre B)", centre_id=centres[1].id),
            User(role="VERIFIER", name="Verifier One", village_id=villages[0].id),
            User(role="VERIFIER", name="Verifier Two", village_id=villages[1].id),
            User(role="OFFICER", name="District Officer"),
        ])
        # Demo clock -> season start (day 1)
        db.merge(Meta(key="demo_today", value=config.SEASON_START))
        db.commit()
        return {"centres": len(centres), "villages": len(villages), "farmers": 60,
                "demo_today": config.SEASON_START}
    finally:
        db.close()


if __name__ == "__main__":
    print(seed())
