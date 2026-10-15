"""FIFO-token baseline: our model of the described queue system (SPEC §7.2).

- Token needs Farmer ID -> tenants excluded entirely.
- OTP failure blocks that day (retry next day, up to max_retries).
- Token = queue position only: nearest centre, next date with daily token
  capacity, NO stock check. Counter stockouts -> wasted trip + retry.
- No-shows consume the token (farmer unserved).
"Baseline is our model of the described system, not measured data."
"""
from __future__ import annotations

import random

import numpy as np


def simulate(d: dict, seed: int) -> dict:
    p = d["params"]
    rng = random.Random(seed * 7919 + 11)
    farmers, centres = d["farmers"], d["centres"]
    n_c = len(centres)
    fx = np.array([f["x"] for f in farmers])
    fy = np.array([f["y"] for f in farmers])
    cx = np.array([c["x"] for c in centres])
    cy = np.array([c["y"] for c in centres])
    dist = np.sqrt((fx[:, None] - cx[None, :]) ** 2 + (fy[:, None] - cy[None, :]) ** 2)
    nearest = dist.argmin(axis=1)
    nearest_km = dist.min(axis=1)

    daily_cap = p["slot_capacity"] * 4
    season = p["season_days"]
    tail = season + 10
    real = [0] * n_c
    arr_by_day: dict[int, list[tuple[int, int]]] = {}
    for cid, lots in d["arrivals"].items():
        for day, q in lots:
            arr_by_day.setdefault(day, []).append(
                (cid, int(q * (1 - p["shrinkage"]))))
    used: list[dict[int, int]] = [{} for _ in range(n_c)]

    PF = [{"status": "pending", "retries": 0, "travel": 0.0, "wasted": 0,
           "served_day": None, "token": None} for _ in farmers]
    req_by_day: dict[int, list[int]] = {}
    for f in farmers:
        req_by_day.setdefault(f["request_day"], []).append(f["id"])
    pick_by_day: dict[int, list[int]] = {}
    tokens_issued = wasted_stock = stockouts = no_shows = 0

    def next_slot(c, fro):
        dd = fro
        while dd <= tail:
            if used[c].get(dd, 0) < daily_cap:
                return dd
            dd += 1
        return None

    for day in range(1, tail + 1):
        for cid, q in arr_by_day.get(day, []):
            real[cid] += q
        for fi in req_by_day.get(day, []):
            st, f = PF[fi], farmers[fi]
            if st["status"] in ("served", "unserved"):
                continue
            if f["tenant"]:
                st["status"] = "unserved"
                st["reason"] = "tenant_excluded"
                continue
            if rng.random() < p["otp_fail_rate"]:
                st["retries"] += 1
                if st["retries"] <= p["max_retries"]:
                    req_by_day.setdefault(day + 1, []).append(fi)
                else:
                    st["status"] = "unserved"
                    st["reason"] = "otp_blocked"
                continue
            c = int(nearest[fi])
            dd = next_slot(c, day + 1)
            if dd is None:
                st["status"] = "unserved"
                st["reason"] = "no_slot"
                continue
            used[c][dd] = used[c].get(dd, 0) + 1
            st["token"] = (dd, c)
            tokens_issued += 1
            pick_by_day.setdefault(dd, []).append(fi)
        for fi in pick_by_day.get(day, []):
            st, f = PF[fi], farmers[fi]
            if st["status"] in ("served", "unserved") or st["token"] is None:
                continue
            _, c = st["token"]
            st["token"] = None
            if rng.random() < p["no_show_rate"]:
                no_shows += 1
                st["status"] = "unserved"
                st["reason"] = "no_show"
                continue
            st["travel"] += float(dist[fi, c])
            if real[c] >= f["qty_full"]:
                real[c] -= f["qty_full"]
                st["status"] = "served"
                st["served_day"] = day
                st["served_centre"] = c
            else:
                st["wasted"] += 1
                wasted_stock += 1
                stockouts += 1
                st["retries"] += 1
                if st["retries"] <= p["max_retries"]:
                    req_by_day.setdefault(day + 1, []).append(fi)
                else:
                    st["status"] = "unserved"
                    st["reason"] = "stockout_retries"
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
            "qty": f["qty_full"], "served_centre": st.get("served_centre"),
        })
    agg: dict[int, int] = {}
    for i, f in enumerate(farmers):
        c = PF[i].get("served_centre")
        if c is not None:
            agg[c] = agg.get(c, 0) + f["qty_full"]
    return {"per_farmer": per, "tokens_issued": tokens_issued,
            "tokens_issued_without_stock": wasted_stock,
            "wasted_stock_visits": wasted_stock, "stockouts": stockouts,
            "no_shows": no_shows,
            "total_travel": float(sum(s["travel"] for s in PF)),
            "centre_served_qty": agg}
