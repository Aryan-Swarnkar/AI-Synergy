"""Synthetic district generator (SPEC §7.1). Seeded RNG: same seed → identical
district. Single-product (UREA) model — demand is UREA entitlement per farmer.

Geography is modelled in km on a 100×100 grid; lat/lon passed to the pure
allocator are km/111 so haversine ≈ Euclidean km (relative order preserved,
which is all the allocator needs).
"""
from __future__ import annotations

import math
import random

from ..core.norms import BAGS_PER_ACRE

PRODUCT = "UREA"
CROPS = ["soybean", "paddy", "maize", "cotton", "wheat"]
CROP_W = [0.30, 0.25, 0.20, 0.15, 0.10]

DEFAULTS = {
    "n_farmers": 5000, "n_centres": 20, "n_villages": 200,
    "area_km": 100.0, "season_days": 30,
    "tenant_share": 0.20, "otp_fail_rate": 0.15, "no_show_rate": 0.10,
    "supply_ratio": 0.95, "shrinkage": 0.03, "slot_capacity": 25,
    "max_retries": 3,
}


def _entitlement(acres: float, crop: str) -> int:
    return math.ceil(acres * BAGS_PER_ACRE[crop][PRODUCT])


def generate(seed: int, params: dict | None = None) -> dict:
    p = dict(DEFAULTS)
    p.update(params or {})
    rng = random.Random(seed)
    n_f, n_c, n_v = p["n_farmers"], p["n_centres"], p["n_villages"]
    area = p["area_km"]

    # Centres: jittered grid
    centres = []
    side = math.ceil(math.sqrt(n_c))
    idx = 0
    for gx in range(side):
        for gy in range(side):
            if idx >= n_c:
                break
            centres.append({
                "id": idx,
                "x": (gx + 0.5) / side * area + rng.uniform(-4, 4),
                "y": (gy + 0.5) / side * area + rng.uniform(-4, 4),
            })
            idx += 1

    def _near(cx, cy, far=False):
        if far:
            ang = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(30, 50)
            return cx + math.cos(ang) * d, cy + math.sin(ang) * d
        return cx + rng.gauss(0, 8), cy + rng.gauss(0, 8)

    villages = []
    for i in range(n_v):
        c = centres[i % n_c]
        far = i >= n_v - max(3, n_v // 10)  # ~10% deliberately far
        x, y = _near(c["x"], c["y"], far)
        villages.append({"id": i, "x": x, "y": y})

    mu = math.log(1.5)  # median 1.5 acres
    farmers = []
    for i in range(n_f):
        v = villages[rng.randrange(n_v)]
        acres = round(min(12.0, max(0.2, rng.lognormvariate(mu, 0.7))), 1)
        crop = rng.choices(CROPS, weights=CROP_W)[0]
        tenant = rng.random() < p["tenant_share"]
        sow = int(min(28, max(1, round(rng.gauss(10, 6)))))
        lead = rng.randint(3, 14) if rng.random() < 0.8 else rng.randint(0, 2)
        req_day = max(1, sow - lead)
        farmers.append({
            "id": i, "village": v["id"], "x": v["x"], "y": v["y"],
            "acres": acres, "crop": crop, "tenant": tenant,
            "sowing_day": sow, "request_day": req_day,
            "qty_full": _entitlement(acres, crop),
        })

    # Supply sized to hit supply_ratio overall, uneven across centres
    total_demand = sum(f["qty_full"] for f in farmers)
    total_supply = int(round(total_demand * p["supply_ratio"]))
    weights = []
    for i in range(n_c):
        w = rng.uniform(0.4, 1.6)
        if i < max(2, n_c // 7):  # a few deliberately under-supplied centres
            w *= 0.3
        weights.append(w)
    s = sum(weights)
    arrivals: dict[int, list[tuple[int, int]]] = {}
    given = 0
    for i, c in enumerate(centres):
        target = total_supply * weights[i] / s
        n_lots = rng.randint(3, 6)
        days = sorted(rng.randint(1, p["season_days"]) for _ in range(n_lots))
        lots, acc = [], 0
        for j, d in enumerate(days):
            q = int(round(target / n_lots)) if j < n_lots - 1 else 0
            lots.append([d, q])
            acc += q
        lots[-1][1] = max(0, int(round(target - acc)))
        arrivals[c["id"]] = sorted((d, q) for d, q in lots if q > 0)
        given += sum(q for _, q in arrivals[c["id"]])
    return {"seed": seed, "params": p, "centres": centres, "villages": villages,
            "farmers": farmers, "arrivals": arrivals,
            "total_demand": total_demand, "total_supply": given}
