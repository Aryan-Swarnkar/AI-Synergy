"""KhadSetu policy in the simulator: calls the SAME pure allocator
(core.allocator.decide) with the same lifecycle rules (expiry via no-show
release, waitlist promotion). Tenants use the provisional 60% path; OTP
failure adds a 0-1 day assisted delay, never a block. Shrinkage still applies
to real counter stock, so rare wasted trips are honestly reported.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np

from .. import config as default_config
from ..core.allocator import decide
from ..core.norms import provisional_cap
from ..core.types import CentreState, FarmerRequest

_SEASON = "2026-06-15"
_Y, _M, _D = (int(x) for x in _SEASON.split("-"))
_BASE = date(_Y, _M, _D)


def _dstr(day: int) -> str:
    return (_BASE + timedelta(days=day - 1)).isoformat()


def _pday(datestr: str) -> int:
    y, m, d = (int(x) for x in datestr.split("-"))
    return (date(y, m, d) - _BASE).days + 1


def simulate(d: dict, seed: int, _waste_log: list | None = None) -> dict:
    p = d["params"]
    rng = random.Random(seed * 104729 + 7)
    # Console-tunable allocator keys pass straight through (v3 adaptability).
    _passthrough = ("SLOT_CAPACITY", "OTP_FAIL_RATE", "MAX_RADIUS_KM",
                    "MAX_DETOUR_KM_OVER_NEAREST", "SAFETY_BUFFER_PCT", "W_DIST",
                    "W_CROWD", "W_WAIT", "TOKEN_GRACE_DAYS",
                    "TENANT_PROVISIONAL_FACTOR", "WAITLIST_ENABLED",
                    "OVERBOOK_FACTOR")
    _over = {k: p[k] for k in _passthrough if k in p}
    _over["SLOT_CAPACITY"] = p["slot_capacity"]  # generator key ≠ config key
    _over["OTP_FAIL_RATE"] = p["otp_fail_rate"]
    cfg = default_config.get_config(_over)
    farmers, centres = d["farmers"], d["centres"]
    n_c = len(centres)
    fx = np.array([f["x"] for f in farmers])
    fy = np.array([f["y"] for f in farmers])
    cx = np.array([c["x"] for c in centres])
    cy = np.array([c["y"] for c in centres])
    dist = np.sqrt((fx[:, None] - cx[None, :]) ** 2 + (fy[:, None] - cy[None, :]) ** 2)
    nearest_km = dist.min(axis=1)
    clat = np.array([c["y"] / 111.0 for c in centres])
    clon = np.array([c["x"] / 111.0 for c in centres])
    flat = np.array([f["y"] / 111.0 for f in farmers])
    flon = np.array([f["x"] / 111.0 for f in farmers])

    season = p["season_days"]
    tail = season + 10
    ledger = [0] * n_c
    real = [0] * n_c
    reserved = [0] * n_c
    pending: list[list] = [[] for _ in range(n_c)]  # [day, qty]
    used: list[dict] = [{} for _ in range(n_c)]
    pos = {c["id"]: i for i, c in enumerate(centres)}  # ids ≠ positions when centres close
    for cid, lots in d["arrivals"].items():
        if cid not in pos:
            continue
        for day, q in lots:
            pending[pos[cid]].append([day, q])

    PF = [{"status": "pending", "retries": 0, "waste_retries": 0, "travel": 0.0,
           "wasted": 0, "served_day": None, "token": None,
           "qty": (provisional_cap(f["qty_full"], cfg["TENANT_PROVISIONAL_FACTOR"])
                   if f["tenant"] else f["qty_full"])} for f in farmers]
    req_by_day: dict[int, list[int]] = {}
    for f in farmers:
        req_by_day.setdefault(f["request_day"], []).append(f["id"])
    pick_by_day: dict[int, list[int]] = {}
    waitlist: list[int] = []  # farmer idx in priority order (re-sorted as needed)
    tokens_issued = wasted_stock = stockouts = no_shows = 0

    def states() -> list[CentreState]:
        out = []
        for i, c in enumerate(centres):
            out.append(CentreState(
                id=i, name=f"C{i}", lat=float(clat[i]), lon=float(clon[i]),
                on_hand=ledger[i], reserved=reserved[i],
                arrivals=[(_dstr(dd), q) for dd, q in pending[i]],
                day_used=dict(used[i])))
        return out

    def frequest(fi: int, today: str) -> FarmerRequest:
        f = farmers[fi]
        active = PF[fi]["status"] in ("queued", "waiting")
        return FarmerRequest(
            farmer_id=fi, village_lat=float(flat[fi]), village_lon=float(flon[fi]),
            product=p.get("product", "UREA"), crop=f["crop"], acres=f["acres"], qty=PF[fi]["qty"],
            sowing_date=_dstr(f["sowing_day"]),
            is_tenant_provisional=f["tenant"], has_active_request=active,
            seasonal_remaining=PF[fi]["qty"], created_at=f"{today}T00:00:00")

    for day in range(1, tail + 1):
        today = _dstr(day)
        for cid in range(n_c):
            due = [l for l in pending[cid] if l[0] <= day]
            pending[cid] = [l for l in pending[cid] if l[0] > day]
            for _, q in due:
                ledger[cid] += q
                real[cid] += int(q * (1 - p["shrinkage"]))
        for fi in req_by_day.get(day, []):
            st = PF[fi]
            if st["status"] in ("served", "unserved"):
                continue
            if rng.random() < p["otp_fail_rate"]:
                # Fallback path: assisted delay, never a block
                if rng.randint(0, 1) == 1:
                    req_by_day.setdefault(day + 1, []).append(fi)
                    continue
            dec = decide(frequest(fi, today), states(), today, cfg)
            if dec.outcome == "ISSUED":
                reserved[dec.centre_id] += st["qty"]
                used[dec.centre_id][dec.pickup_date] = \
                    used[dec.centre_id].get(dec.pickup_date, 0) + 1
                st["token"] = (dec.pickup_date, dec.centre_id)
                st["status"] = "queued"
                tokens_issued += 1
                pick_by_day.setdefault(_pday(dec.pickup_date), []).append(fi)
            elif dec.outcome == "WAITLISTED":
                st["status"] = "waiting"
                if fi not in waitlist:
                    waitlist.append(fi)
            else:
                st["status"] = "unserved"
                st["reason"] = "rejected:" + dec.reason_code
        for fi in pick_by_day.get(day, []):
            st = PF[fi]
            if st["status"] != "queued" or st["token"] is None:
                continue
            _, c = st["token"]
            st["token"] = None
            if rng.random() < p["no_show_rate"]:
                reserved[c] = max(0, reserved[c] - st["qty"])
                no_shows += 1
                st["status"] = "unserved"
                st["reason"] = "no_show"
                continue
            st["travel"] += float(dist[fi, c])
            if real[c] >= st["qty"]:
                # Goods leave the godown: ledger AND real AND hold all drop,
                # exactly like the live redeem path (on_hand -= qty).
                real[c] -= st["qty"]
                ledger[c] = max(0, ledger[c] - st["qty"])
                reserved[c] = max(0, reserved[c] - st["qty"])
                st["status"] = "served"
                st["served_day"] = day
                st["served_centre"] = c
            else:
                st["wasted"] += 1
                wasted_stock += 1
                stockouts += 1
                if _waste_log is not None:
                    _waste_log.append({"day": day, "centre": c, "qty": st["qty"],
                                       "real": real[c], "reserved": reserved[c],
                                       "ledger": ledger[c]})
                reserved[c] = max(0, reserved[c] - st["qty"])
                st["waste_retries"] += 1
                if st["waste_retries"] <= 1:
                    # Smart retry (mirrors the live API): re-decide instead of
                    # blindly travelling again — waitlist rather than waste.
                    dec2 = decide(frequest(fi, today), states(), today, cfg)
                    if dec2.outcome == "ISSUED":
                        reserved[dec2.centre_id] += st["qty"]
                        used[dec2.centre_id][dec2.pickup_date] = \
                            used[dec2.centre_id].get(dec2.pickup_date, 0) + 1
                        st["token"] = (dec2.pickup_date, dec2.centre_id)
                        st["status"] = "queued"
                        tokens_issued += 1
                        pick_by_day.setdefault(_pday(dec2.pickup_date), []).append(fi)
                    elif dec2.outcome == "WAITLISTED":
                        st["status"] = "waiting"
                        if fi not in waitlist:
                            waitlist.append(fi)
                    else:
                        st["status"] = "unserved"
                        st["reason"] = "rejected:" + dec2.reason_code
                else:
                    st["status"] = "unserved"
                    st["reason"] = "counter_short"
        # Promotion in priority order (only when something changed today)
        if waitlist:
            waitlist.sort(key=lambda i: (farmers[i]["sowing_day"],
                                         farmers[i]["acres"], i))
            still = []
            for fi in waitlist:
                st = PF[fi]
                if st["status"] != "waiting":
                    continue
                dec = decide(frequest(fi, today), states(), today, cfg)
                if dec.outcome == "ISSUED":
                    reserved[dec.centre_id] += st["qty"]
                    used[dec.centre_id][dec.pickup_date] = \
                        used[dec.centre_id].get(dec.pickup_date, 0) + 1
                    st["token"] = (dec.pickup_date, dec.centre_id)
                    st["status"] = "queued"
                    tokens_issued += 1
                    pick_by_day.setdefault(_pday(dec.pickup_date), []).append(fi)
                else:
                    still.append(fi)
            waitlist = still
    for st in PF:
        if st["status"] not in ("served", "unserved"):
            st["status"] = "unserved"
            st["reason"] = "season_end"
    per = []
    for i, f in enumerate(farmers):
        st = PF[i]
        per.append({
            "served": st["status"] == "served",
            "served_day": st["served_day"],
            "in_window": st["served_day"] is not None and st["served_day"] < f["sowing_day"],
            "travel": st["travel"], "wasted": st["wasted"],
            "tenant": f["tenant"], "acres": f["acres"],
            "nearest_km": float(nearest_km[i]), "sowing": f["sowing_day"],
            "qty": st["qty"],
        })
    agg: dict[int, int] = {}
    for i, f in enumerate(farmers):
        c = PF[i].get("served_centre")
        if c is not None:
            agg[c] = agg.get(c, 0) + PF[i]["qty"]
    return {"per_farmer": per, "tokens_issued": tokens_issued,
            "tokens_issued_without_stock": wasted_stock,
            "wasted_stock_visits": wasted_stock, "stockouts": stockouts,
            "no_shows": no_shows,
            "total_travel": float(sum(s["travel"] for s in PF)),
            "centre_served_qty": agg}
