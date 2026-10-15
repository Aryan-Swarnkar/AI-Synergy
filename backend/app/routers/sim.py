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


@router.post("/sim/run")
def run(body: RunIn, bg: BackgroundTasks):
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
    if not body.values:
        raise BusinessError("BAD_VALUES", "values must be non-empty",
                            "मान खाली नहीं", 400)
    return runner.sensitivity(body.param, body.values, body.seeds, body.params)
