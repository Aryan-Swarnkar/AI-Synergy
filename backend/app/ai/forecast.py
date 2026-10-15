"""AI-2 demand forecaster (SPEC v3): per centre/product/week demand with
interval, plus error vs a naive baseline. Planning only — never approves or
rejects an individual request.

History is SYNTHETIC until a pilot produces real data (mock rainfall signal
included as an assumption). The officer decides whether to move stock.
"""
from __future__ import annotations

import math
import random

PRODUCTS = ("UREA", "DAP", "MOP", "NPK")
WEEKS_HISTORY = 12


def history(seed: int = 42, centres: int = 6, weeks: int = WEEKS_HISTORY) -> list[dict]:
    """Synthetic weekly demand: base + seasonal rush + noise + rain dip."""
    rng = random.Random(seed)
    rows = []
    for c in range(1, centres + 1):
        base = rng.uniform(40, 120)
        for p in PRODUCTS:
            scale = {"UREA": 1.0, "DAP": 0.5, "MOP": 0.25, "NPK": 0.2}[p]
            for w in range(weeks):
                seasonal = 1.0 + 0.6 * math.exp(-((w - 3) ** 2) / 4)  # rush week ~3
                rain_dip = 0.85 if w in (5, 6) else 1.0  # mock rainfall signal
                qty = base * scale * seasonal * rain_dip * rng.uniform(0.85, 1.15)
                rows.append({"centre_id": c, "product": p, "week": w,
                             "qty": round(qty, 1)})
    return rows


def forecast(rows: list[dict], weeks_ahead: int = 4, alpha: float = 0.7) -> list[dict]:
    """Exponentially-weighted recent level ± 1 std. Deterministic."""
    by_key: dict[tuple, list[float]] = {}
    for r in rows:
        by_key.setdefault((r["centre_id"], r["product"]), []).append(r["qty"])
    last_week = max(r["week"] for r in rows)
    out = []
    for (cid, prod), qtys in sorted(by_key.items()):
        level = qtys[0]
        for q in qtys[1:]:
            level = alpha * q + (1 - alpha) * level
        mean = level
        recent = qtys[-4:]
        var = sum((q - mean) ** 2 for q in recent) / max(1, len(recent) - 1)
        std = math.sqrt(var)
        for k in range(1, weeks_ahead + 1):
            out.append({"centre_id": cid, "product": prod,
                        "week": last_week + k,
                        "qty": round(mean, 1),
                        "lo": round(max(0.0, mean - std), 1),
                        "hi": round(mean + std, 1)})
    return out


def naive(rows: list[dict], weeks_ahead: int = 4) -> list[dict]:
    """Baseline: carry forward the last observed week."""
    last = {}
    for r in rows:
        last[(r["centre_id"], r["product"])] = r["qty"]
    last_week = max(r["week"] for r in rows)
    return [{"centre_id": c, "product": p, "week": last_week + k, "qty": q}
            for (c, p), q in sorted(last.items()) for k in range(1, weeks_ahead + 1)]


def mae(preds: list[dict], actual: dict[tuple, float]) -> float:
    errs = [abs(p["qty"] - actual[(p["centre_id"], p["product"], p["week"])])
            for p in preds if (p["centre_id"], p["product"], p["week"]) in actual]
    return sum(errs) / len(errs) if errs else 0.0


def evaluate(seed: int = 42, holdout: int = 4) -> dict:
    """Train on all but last `holdout` weeks; MAE of model vs naive on holdout."""
    full = history(seed)
    last = max(r["week"] for r in full)
    train = [r for r in full if r["week"] < last - holdout + 1]
    actual = {(r["centre_id"], r["product"], r["week"]): r["qty"]
              for r in full if r["week"] >= last - holdout + 1}
    return {"model_mae": round(mae(forecast(train, holdout), actual), 2),
            "naive_mae": round(mae(naive(train, holdout), actual), 2),
            "holdout_weeks": holdout, "synthetic": True}
