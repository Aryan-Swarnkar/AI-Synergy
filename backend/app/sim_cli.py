"""`make sim`: quick honest comparison on a mid-size district (SPEC §7)."""
from __future__ import annotations

from .sim import runner

PARAMS = {"n_farmers": 1500, "n_centres": 12, "n_villages": 60}
SEEDS = [1, 2, 3]


def main() -> None:
    r = runner.run_scenario(PARAMS, SEEDS)
    a = r["agg"]
    print(f"seeds {SEEDS} n={PARAMS['n_farmers']}")
    for m in ("served_in_window_pct", "served_pct", "wasted_trips_per_farmer",
              "avg_travel_km_per_served", "stockout_at_counter_events"):
        v = a[m]
        print(f"  {m}: base {v['base_mean']:.1f}±{v['base_std']:.1f} "
              f"vs khadsetu {v['kh_mean']:.1f}±{v['kh_std']:.1f}")
    print(f"  findings: {len(r['findings'])} statements "
          f"(see simulator page / API for text)")


if __name__ == "__main__":
    main()
