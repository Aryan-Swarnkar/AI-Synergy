"""Scenario runner: seeds, aggregation (mean ± std), sensitivity sweeps."""
from __future__ import annotations

from . import baseline, generator, khadsetu, metrics


def run_scenario(params: dict | None = None, seeds: list[int] | None = None,
                 progress_cb=None) -> dict:
    seeds = seeds or [1, 2, 3, 4, 5]
    per_seed = []
    for i, s in enumerate(seeds):
        d = generator.generate(s, params)
        b = metrics.summarize(baseline.simulate(d, s), d)
        k = metrics.summarize(khadsetu.simulate(d, s), d)
        per_seed.append({"seed": s, "baseline": b, "khadsetu": k})
        if progress_cb:
            progress_cb((i + 1) / len(seeds))
    keys = per_seed[0]["baseline"].keys()
    agg = {}
    for key in keys:
        bv = [r["baseline"][key] for r in per_seed]
        kv = [r["khadsetu"][key] for r in per_seed]
        agg[key] = {"base_mean": metrics._mean(bv), "base_std": metrics._std(bv),
                    "kh_mean": metrics._mean(kv), "kh_std": metrics._std(kv)}
    ratio = (params or {}).get("supply_ratio", generator.DEFAULTS["supply_ratio"])
    return {"params": params or {}, "seeds": seeds, "per_seed": per_seed,
            "agg": agg, "findings": metrics.honest_findings(agg, ratio)}


def sensitivity(param: str, values: list[float], seeds: list[int] | None = None,
                base_params: dict | None = None) -> dict:
    seeds = seeds or [1, 2]
    series = []
    for v in values:
        p = dict(base_params or {})
        p[param] = v
        r = run_scenario(p, seeds)
        row = {"value": v}
        for m in ("served_in_window_pct", "wasted_trips_per_farmer",
                  "avg_travel_km_per_served", "stockout_at_counter_events"):
            row[m] = {"base_mean": r["agg"][m]["base_mean"],
                      "base_std": r["agg"][m]["base_std"],
                      "kh_mean": r["agg"][m]["kh_mean"],
                      "kh_std": r["agg"][m]["kh_std"]}
        row["findings"] = r["findings"]
        series.append(row)
    return {"param": param, "series": series, "seeds": seeds}
