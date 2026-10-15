"""Simulator routes: async runs with progress, sensitivity sweeps, presets."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..errors import BusinessError
from ..sim import runner

router = APIRouter(tags=["sim"])

PRESETS = {
    "normal": {"supply_ratio": 0.95, "otp_fail_rate": 0.15, "no_show_rate": 0.10,
               "shrinkage": 0.03, "tenant_share": 0.20},
    "shortage_20pct": {"supply_ratio": 0.80, "otp_fail_rate": 0.15, "no_show_rate": 0.10,
                       "shrinkage": 0.03, "tenant_share": 0.20},
    "high_otp_failure": {"supply_ratio": 0.95, "otp_fail_rate": 0.40, "no_show_rate": 0.10,
                         "shrinkage": 0.03, "tenant_share": 0.20},
    "rush_week": {"supply_ratio": 0.90, "otp_fail_rate": 0.15, "no_show_rate": 0.15,
                  "shrinkage": 0.03, "tenant_share": 0.20},
    "data_error_5pct": {"supply_ratio": 0.95, "otp_fail_rate": 0.15, "no_show_rate": 0.10,
                        "shrinkage": 0.05, "tenant_share": 0.20},
}

_RUNS: dict[str, dict] = {}


class RunIn(BaseModel):
    params: dict = {}
    seeds: list[int] = [1, 2, 3, 4, 5]


class SensitivityIn(BaseModel):
    param: str
    values: list[float]
    seeds: list[int] = [1, 2]
    params: dict = {}


def _do_run(run_id: str, params: dict, seeds: list[int]):
    rec = _RUNS[run_id]
    try:
        res = runner.run_scenario(params, seeds,
                                  progress_cb=lambda f: rec.update({"progress": f}))
        rec.update({"status": "done", "progress": 1.0, "result": res})
    except Exception as e:  # never leave a run stuck
        rec.update({"status": "failed", "error": str(e)})


@router.get("/sim/presets")
def presets():
    return {"presets": PRESETS,
            "note": "Baseline is our model of the described system, not measured data."}


def _validate_console_params(params: dict) -> None:
    """Constraint Console guardrails (v3): allowlisted products, sane ranges."""
    from ..core.norms import known_product
    prod = params.get("product", "UREA")
    if not known_product(prod):
        raise BusinessError("BAD_PRODUCT", f"Unknown product {prod!r}",
                            "अज्ञात उत्पाद", 400)
    mult = params.get("supply_multiplier", 1.0)
    if not (0 < mult <= 2.0):
        raise BusinessError("BAD_RANGE", "supply_multiplier must be in (0, 2]",
                            "आपूर्ति गुणक (0,2] में हो", 400)
    cap = params.get("cap_scale", 1.0)
    if not (0 < cap <= 1.0):
        raise BusinessError("BAD_RANGE", "cap_scale must be in (0, 1]",
                            "कैप (0,1] में हो", 400)
    closed = params.get("closed_centres", [])
    if not isinstance(closed, list) or any(not isinstance(c, int) for c in closed):
        raise BusinessError("BAD_RANGE", "closed_centres must be integer ids",
                            "बंद केंद्र पूर्णांक हों", 400)
    n_c = params.get("n_centres", 20)
    if any(c < 0 or c >= n_c for c in closed) or len(set(closed)) >= n_c:
        raise BusinessError("BAD_RANGE", "closed_centres out of range (keep ≥1 open)",
                            "केंद्र सीमा से बाहर", 400)
    for k in ("MAX_RADIUS_KM", "MAX_DETOUR_KM_OVER_NEAREST", "SAFETY_BUFFER_PCT",
              "W_DIST", "W_CROWD", "W_WAIT", "slot_capacity", "otp_fail_rate",
              "no_show_rate", "tenant_share", "shrinkage"):
        if k in params and not isinstance(params[k], (int, float)):
            raise BusinessError("BAD_RANGE", f"{k} must be a number",
                                "संख्या होनी चाहिए", 400)


@router.post("/sim/run")
def run(body: RunIn, bg: BackgroundTasks):
    if body.params.get("n_farmers", 5000) > 8000:
        raise BusinessError("TOO_BIG", "n_farmers capped at 8000 for demo runs",
                            "अधिकतम 8000 किसान", 400)
    _validate_console_params(body.params)
    run_id = uuid.uuid4().hex[:8]
    _RUNS[run_id] = {"status": "running", "progress": 0.0,
                     "params": body.params, "seeds": body.seeds}
    bg.add_task(_do_run, run_id, body.params, body.seeds)
    return {"run_id": run_id, "status": "running"}


@router.get("/sim/{run_id}")
def status(run_id: str):
    rec = _RUNS.get(run_id)
    if rec is None:
        raise BusinessError("NO_RUN", "Unknown run_id", "रन नहीं मिला", 404)
    return rec


@router.post("/sim/sensitivity")
def sensitivity(body: SensitivityIn):
    from ..core.norms import known_product
    if not body.values:
        raise BusinessError("BAD_VALUES", "values must be non-empty",
                            "मान खाली नहीं", 400)
    _validate_console_params(body.params)
    if body.param == "product" and not all(known_product(v) for v in body.values):
        raise BusinessError("BAD_PRODUCT", "Unknown product in values",
                            "अज्ञात उत्पाद", 400)
    return runner.sensitivity(body.param, body.values, body.seeds, body.params)
