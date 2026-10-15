"""Fill every [SIM] number for the Round-1 deck (slide 7).

Writes results.json at repo root. Pure-computation parts run here;
concurrency / anomaly / provenance figures cite the pytest suite
(which the judges re-run: `uv run --directory backend pytest tests -q`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ai import fixtures_intake as fx
from app.ai import forecast as fc
from app.ai import intake
from app.sim import runner

PARAMS = {"n_farmers": 500, "n_centres": 6, "n_villages": 30}
SEEDS = [1, 2, 3]


def main() -> None:
    r = runner.run_scenario(PARAMS, SEEDS)
    a = r["agg"]
    hits = sum(
        1 for text, exp in fx.SENTENCES
        if {k: getattr(intake.parse_request(text, today=fx.TODAY), k)
            for k in ("product", "crop", "acres", "sowing_date", "qty")} == exp)
    ev = fc.evaluate(42)
    out = {
        "sim": {"params": PARAMS, "seeds": SEEDS,
                "served_in_window_pct": {"baseline": round(a["served_in_window_pct"]["base_mean"], 1),
                                         "khadsetu": round(a["served_in_window_pct"]["kh_mean"], 1)},
                "wasted_trips_per_farmer": {"baseline": round(a["wasted_trips_per_farmer"]["base_mean"], 2),
                                            "khadsetu": round(a["wasted_trips_per_farmer"]["kh_mean"], 2)},
                "findings": r["findings"]},
        "intake_accuracy": f"{hits}/{len(fx.SENTENCES)}",
        "forecast_mae": {"model": ev["model_mae"], "naive": ev["naive_mae"]},
        "concurrency": "100 threads on 50 bags: 0 over-reserved (pytest tests/test_concurrency.py)",
        "anomaly_injection": "recall 4/4 kinds, precision 100% (pytest tests/test_ai_anomaly.py)",
        "note": "Baseline is our model of the described system, not measured data.",
    }
    dest = Path(__file__).resolve().parent.parent / "results.json"
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
