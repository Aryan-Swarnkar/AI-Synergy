"""Metrics per policy/seed + honest-findings engine (SPEC §7.4-7.5)."""
from __future__ import annotations

import math


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _gini(xs: list[float]) -> float:
    xs = sorted(x for x in xs if x > 0)
    n = len(xs)
    if n < 2:
        return 0.0
    total = sum(xs)
    if total <= 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * total) - (n + 1) / n


def _terciles(vals: list[float]) -> tuple[float, float]:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return (0.0, 0.0)
    return (s[n // 3], s[2 * n // 3])


def summarize(res: dict, district: dict) -> dict:
    pf = res["per_farmer"]
    n = len(pf)
    served = [r for r in pf if r["served"]]
    inwin = [r for r in pf if r["served"] and r["in_window"]]
    m: dict = {}
    m["n"] = n
    m["served_pct"] = 100.0 * len(served) / n
    m["served_in_window_pct"] = 100.0 * len(inwin) / n
    m["never_served_pct"] = 100.0 * (n - len(served)) / n
    m["avg_travel_km_per_served"] = _mean([r["travel"] for r in served])
    m["total_travel_km"] = res["total_travel"]
    m["wasted_trips_per_farmer"] = sum(r["wasted"] for r in pf) / n
    m["wasted_trips_total"] = sum(r["wasted"] for r in pf)
    m["stockout_at_counter_events"] = res["stockouts"]
    m["tokens_issued_without_stock"] = res["tokens_issued_without_stock"]
    m["tokens_issued"] = res["tokens_issued"]
    early = [(r["sowing"] - r["served_day"]) for r in served if r["served_day"]]
    m["avg_days_early"] = _mean(early)
    for flag, name in ((True, "tenant"), (False, "landowner")):
        sub = [r for r in pf if r["tenant"] == flag]
        m[f"in_window_pct_{name}"] = 100.0 * len(
            [r for r in sub if r["served"] and r["in_window"]]) / max(1, len(sub))
    dlo, dhi = _terciles([r["nearest_km"] for r in pf])
    for lo, hi, name in ((0, dlo, "near"), (dlo, dhi, "mid"), (dhi, 1e18, "far")):
        sub = [r for r in pf if lo <= r["nearest_km"] < hi or (hi > 1e17 and r["nearest_km"] >= lo)]
        m[f"in_window_pct_dist_{name}"] = 100.0 * len(
            [r for r in sub if r["served"] and r["in_window"]]) / max(1, len(sub))
    alo, ahi = _terciles([r["acres"] for r in pf])
    for lo, hi, name in ((0, alo, "small"), (alo, ahi, "mid"), (ahi, 1e18, "large")):
        sub = [r for r in pf if lo <= r["acres"] < hi or (hi > 1e17 and r["acres"] >= lo)]
        m[f"in_window_pct_hold_{name}"] = 100.0 * len(
            [r for r in sub if r["served"] and r["in_window"]]) / max(1, len(sub))
    m["distance_gini"] = _gini([r["travel"] for r in served])
    supplied = district["total_supply"]
    per_c = res["centre_served_qty"]
    # served_centre is positional; match district order, not ids (ids shift on closure)
    utils = [(per_c.get(i, 0) / max(1, supplied / max(1, len(district["centres"]))))
             for i in range(len(district["centres"]))]
    m["centre_util_max"] = max(utils) if utils else 0.0
    m["centre_util_mean"] = _mean(utils)
    m["supply_ratio"] = district["params"]["supply_ratio"]
    gap = max(0.0, 1.0 - district["params"]["supply_ratio"])
    never = n - len(served)
    m["unserved_due_to_supply_shortage"] = min(never, round(n * gap))
    m["unserved_due_to_process"] = never - m["unserved_due_to_supply_shortage"]
    return m


# metric -> (better direction, meaningful margin)
BETTER = {
    "served_in_window_pct": ("up", 2.0),
    "served_pct": ("up", 2.0),
    "avg_travel_km_per_served": ("down", 0.5),
    "wasted_trips_per_farmer": ("down", 0.05),
    "stockout_at_counter_events": ("down", 1.0),
    "tokens_issued_without_stock": ("down", 1.0),
    "unserved_due_to_process": ("down", 5.0),
}

EXPLAIN = {
    "served_in_window_pct": "in-window service is similar; shortage binds both systems",
    "served_pct": "overall service is similar; supply is the binding constraint",
    "avg_travel_km_per_served": "travel is similar; detour tolerance trades distance for stock certainty",
    "wasted_trips_per_farmer": "wasted trips are similar; shrinkage still bites at the counter",
    "stockout_at_counter_events": "counter stockouts are similar; ledger ≠ physical under shrinkage",
    "tokens_issued_without_stock": "unbacked tokens are similar",
    "unserved_due_to_process": "process-driven exclusion is similar",
}


def honest_findings(agg: dict, supply_ratio: float) -> list[str]:
    """Where KhadSetu does NOT help (SPEC §7.5). agg maps metric ->
    {base_mean, kh_mean}. Always honest under scarcity."""
    out = []
    for metric, (direction, margin) in BETTER.items():
        b, k = agg[metric]["base_mean"], agg[metric]["kh_mean"]
        better = (k - b) if direction == "up" else (b - k)
        if better < margin:
            verb = "worse" if better < 0 else "not meaningfully better"
            out.append(f"Where KhadSetu does not help — {metric}: KhadSetu {verb} "
                       f"(baseline {b:.1f} vs KhadSetu {k:.1f}). {EXPLAIN[metric]}.")
    if supply_ratio <= 0.8:
        out.append("Under supply_ratio {:.2f}, shortage-driven non-service is similar "
                   "in both systems (about {:.0f}% of farmers cannot be served no "
                   "matter the policy); the difference is that KhadSetu tells them "
                   "on day 1 instead of after wasted trips.".format(
                       supply_ratio,
                       100 * (1 - supply_ratio)))
    out.append("Honesty note: KhadSetu cannot create fertiliser; it removes wasted "
               "trips and makes shortage visible and fair.")
    return out
