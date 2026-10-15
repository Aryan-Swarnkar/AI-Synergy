"""Pure allocation logic (SPEC §5). No SQLAlchemy/FastAPI imports — simulator-safe.

Implements §5.3 steps 1-9 exactly. All dates are ISO YYYY-MM-DD strings so the
demo clock can be compared lexicographically and without timezones.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

from .geo import haversine_km
from .norms import CROP_CALENDAR, entitlement, provisional_cap
from .types import CentreState, Decision, FarmerRequest

REASON_TEXT: dict[str, tuple[str, str]] = {
    "OK_ASSIGNED": (
        "Assigned {centre} {dist_km} km away, pickup {pickup}, {days_early} days before sowing.",
        "केंद्र {centre} {dist_km} किमी, उठाव {pickup}, बुवाई से {days_early} दिन पहले।",
    ),
    "OK_URGENT": (
        "Urgent: sowing is very close; assigned earliest possible pickup {pickup} at {centre}.",
        "जरूरी: बुवाई बहुत नज़दीक; सबसे जल्द उठाव {pickup} केंद्र {centre}।",
    ),
    "NO_STOCK_WAITLIST": (
        "No stock+slot in window; waitlisted with ETA {eta}. We will notify you (MOCK SMS).",
        "विंडो में स्टॉक/स्लॉट नहीं; प्रतीक्षा सूची, अनुमानित तिथि {eta}। सूचना मिलेगी (MOCK SMS)।",
    ),
    "AT_RISK": (
        "Waitlisted and may miss sowing window (ETA {eta}); officer notified.",
        "प्रतीक्षा सूची और बुवाई छूट सकती है (अनुमान {eta}); अधिकारी को सूचित।",
    ),
    "INVALID_SOWING_WINDOW": (
        "Sowing date outside plausible window for this crop; check crop calendar.",
        "बुवाई तिथि इस फसल की संभावित विंडो के बाहर है।",
    ),
    "OVER_ENTITLEMENT": (
        "Requested qty exceeds your seasonal entitlement ({max_allowed} bags).",
        "मांगी मात्रा आपके हक ({max_allowed} बोरी) से अधिक है।",
    ),
    "DUP_ACTIVE_REQUEST": (
        "You already have an active request for this product this season.",
        "इस उत्पाद के लिए आपका एक सक्रिय अनुरोध पहले से है।",
    ),
    "INVALID_QTY": (
        "Quantity must be at least 1 bag.",
        "मात्रा कम से कम 1 बोरी होनी चाहिए।",
    ),
    "NO_CENTRE_IN_RADIUS": (
        "No centre within reach; waitlisted with extended search.",
        "पहुंच में कोई केंद्र नहीं; विस्तारित खोज के साथ प्रतीक्षा सूची।",
    ),
}


def _reason(code: str, **kw) -> tuple[str, str]:
    en, hi = REASON_TEXT.get(code, ("", ""))
    try:
        return en.format(**kw), hi.format(**kw)
    except Exception:
        return en, hi


def _parse(s: str) -> date:
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


def _iso(d: date) -> str:
    return d.isoformat()


def _add_days(s: str, n: int) -> str:
    return _iso(_parse(s) + timedelta(days=n))


def _days_between(a: str, b: str) -> int:
    return (_parse(b) - _parse(a)).days


def _buffer(on_hand: int, pct: float) -> int:
    return math.ceil(max(0, on_hand) * pct / 100.0)


def _arrivals_by(c: CentreState, d: str) -> int:
    return sum(q for (ad, q) in c.arrivals if ad <= d)


def _projected(c: CentreState, d: str, cfg: dict) -> int:
    buf = _buffer(c.on_hand, cfg.get("SAFETY_BUFFER_PCT", 3))
    over = cfg.get("OVERBOOK_FACTOR", 1.0)
    return math.floor(c.on_hand * over) - c.reserved - buf + _arrivals_by(c, d)


def _slot_for(c: CentreState, d: str, cfg: dict) -> tuple[str | None, float]:
    blocks: list[str] = cfg.get("SLOT_BLOCKS", ["08-10"])
    cap_block: int = cfg.get("SLOT_CAPACITY", 25)
    cap_day = cap_block * len(blocks)
    used = c.day_used.get(d, 0)
    if used >= cap_day:
        return None, 100.0
    idx = min(used // cap_block, len(blocks) - 1)
    return blocks[idx], (used / cap_day * 100.0 if cap_day else 0.0)


def _window(today: str, sowing: str) -> tuple[list[str], bool]:
    start = _add_days(today, 1)
    end = _add_days(sowing, -1)
    if end < start:
        return [_add_days(today, 1)], True
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = _add_days(cur, 1)
    return out, False


def _eta_in_radius(centres: list[CentreState], dists: dict[int, float],
                   in_radius: list[CentreState], window: list[str],
                   sowing: str, qty: int, cfg: dict) -> str | None:
    # 1) inside window 2) up to 30 days past sowing (to report at-risk ETA)
    for d in window:
        for c in in_radius:
            if _projected(c, d, cfg) >= qty:
                return d
    cur = window[-1] if window else sowing
    for _ in range(30):
        cur = _add_days(cur, 1)
        for c in in_radius:
            if _projected(c, cur, cfg) >= qty:
                return cur
    return None


def decide(req: FarmerRequest, centres: list[CentreState], today: str, cfg: dict) -> Decision:
    # ---- 1. Validate ----
    cal = CROP_CALENDAR.get(req.crop)
    if cal is None:
        en, hi = _reason("INVALID_SOWING_WINDOW")
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="INVALID_SOWING_WINDOW",
                        reason_text_en=en, reason_text_hi=hi)
    season_start: str = cfg.get("SEASON_START", today)
    try:
        off = _days_between(season_start, req.sowing_date)
    except Exception:
        en, hi = _reason("INVALID_SOWING_WINDOW")
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="INVALID_SOWING_WINDOW",
                        reason_text_en=en, reason_text_hi=hi)
    if off < cal[0] or off > cal[1]:
        en, hi = _reason("INVALID_SOWING_WINDOW")
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="INVALID_SOWING_WINDOW",
                        reason_text_en=en, reason_text_hi=hi)
    if req.qty <= 0:
        en, hi = _reason("INVALID_QTY")
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="INVALID_QTY",
                        reason_text_en=en, reason_text_hi=hi)
    full = entitlement(req.acres, req.crop, req.product)
    max_allowed = provisional_cap(full, cfg.get("TENANT_PROVISIONAL_FACTOR", 0.6)) \
        if req.is_tenant_provisional else full
    if req.qty > max_allowed:
        en, hi = _reason("OVER_ENTITLEMENT", max_allowed=max_allowed)
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="OVER_ENTITLEMENT",
                        reason_text_en=en, reason_text_hi=hi)
    if req.seasonal_remaining is not None and req.qty > req.seasonal_remaining:
        en, hi = _reason("OVER_ENTITLEMENT", max_allowed=req.seasonal_remaining)
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="OVER_ENTITLEMENT",
                        reason_text_en=en, reason_text_hi=hi)
    if req.has_active_request:
        en, hi = _reason("DUP_ACTIVE_REQUEST")
        return Decision(outcome="REJECTED", qty=req.qty, reason_code="DUP_ACTIVE_REQUEST",
                        reason_text_en=en, reason_text_hi=hi)

    # ---- 2. Window ----
    window, urgent = _window(today, req.sowing_date)

    # ---- 3. Candidates within radius ----
    if not centres:
        en, hi = _reason("NO_CENTRE_IN_RADIUS")
        return Decision(outcome="WAITLISTED", qty=req.qty, eta_date=None, at_risk=True,
                        urgent=urgent, reason_code="NO_CENTRE_IN_RADIUS",
                        reason_text_en=en, reason_text_hi=hi)
    lats = np.array([c.lat for c in centres])
    lons = np.array([c.lon for c in centres])
    dist_arr = haversine_km(req.village_lat, req.village_lon, lats, lons)
    dists = {c.id: float(dist_arr[i]) for i, c in enumerate(centres)}
    nearest_km = min(dists.values())

    def in_radius_set(radius: float) -> list[CentreState]:
        return [c for c in centres if dists[c.id] <= radius + 1e-9]

    max_radius: float = cfg.get("MAX_RADIUS_KM", 40)
    in_radius = in_radius_set(max_radius)
    extended = False
    if not in_radius:
        in_radius = in_radius_set(max_radius * 1.5)
        extended = True

    # ---- 4. Earliest feasible date per centre ----
    cands: list[dict] = []
    for c in in_radius:
        for d in window:
            if _projected(c, d, cfg) < req.qty:
                continue
            slot, util = _slot_for(c, d, cfg)
            if slot is None:
                continue
            cands.append({"centre": c, "dist_km": dists[c.id], "date": d,
                          "slot": slot, "util": util})
            break  # earliest feasible per centre only

    # ---- 5. Detour filter ----
    max_detour: float = cfg.get("MAX_DETOUR_KM_OVER_NEAREST", 15)
    filtered = [x for x in cands if x["dist_km"] <= nearest_km + max_detour + 1e-9]
    if filtered:
        cands = filtered
    # else keep all (nothing else works — SPEC §5.3.5)

    # ---- 6-7. Score + pick ----
    if cands:
        w_dist: float = cfg.get("W_DIST", 1.0)
        w_crowd: float = cfg.get("W_CROWD", 8.0)
        w_wait: float = cfg.get("W_WAIT", 3.0)
        for x in cands:
            wait_days = _days_between(today, x["date"])
            x["score"] = w_dist * x["dist_km"] + w_crowd * (x["util"] / 10.0) + w_wait * wait_days
        cands.sort(key=lambda x: (x["score"], x["date"], x["centre"].id))
        best = cands[0]
        days_early = _days_between(best["date"], req.sowing_date)
        code = "OK_URGENT" if urgent else "OK_ASSIGNED"
        en, hi = _reason(code, centre=best["centre"].name,
                         dist_km=round(best["dist_km"], 1),
                         pickup=best["date"], days_early=days_early)
        alts = [{"centre_id": x["centre"].id, "dist_km": round(x["dist_km"], 2),
                 "pickup_date": x["date"]} for x in cands[:3]]
        return Decision(outcome="ISSUED", centre_id=best["centre"].id,
                        pickup_date=best["date"], slot=best["slot"], qty=req.qty,
                        urgent=urgent, extended_radius=extended,
                        reason_code=code, reason_text_en=en, reason_text_hi=hi,
                        alternatives=alts)

    # ---- 8. Waitlist ----
    if not cfg.get("WAITLIST_ENABLED", True):
        en, hi = _reason("NO_STOCK_WAITLIST", eta="—")
        return Decision(outcome="REJECTED", qty=req.qty, urgent=urgent,
                        extended_radius=extended, reason_code="NO_STOCK_WAITLIST",
                        reason_text_en=en, reason_text_hi=hi)
    eta = _eta_in_radius(centres, dists, in_radius, window, req.sowing_date, req.qty, cfg)
    at_risk = eta is None or not (eta < req.sowing_date)
    code = "AT_RISK" if at_risk else "NO_STOCK_WAITLIST"
    en, hi = _reason(code, eta=eta or "—")
    return Decision(outcome="WAITLISTED", qty=req.qty, eta_date=eta, at_risk=at_risk,
                    urgent=urgent, extended_radius=extended,
                    reason_code=code, reason_text_en=en, reason_text_hi=hi)


def waitlist_key(deadline: str, acres: float, created_at: str) -> tuple:
    """Priority (lower promotes first): soonest deadline, smaller holding, FIFO."""
    return (deadline, acres, created_at)
