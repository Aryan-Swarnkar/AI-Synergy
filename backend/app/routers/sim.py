"""Simulator routes. Full runner lands in Phase 6; presets are real data now,
run/sensitivity return a well-formed 501 until then (accepted by smoke test).
"""
from __future__ import annotations

from fastapi import APIRouter

from ..errors import BusinessError

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


@router.get("/sim/presets")
def presets():
    return {"presets": PRESETS,
            "note": "Baseline is our model of the described system, not measured data."}


@router.post("/sim/run")
def run():
    raise BusinessError("SIM_NOT_READY", "Simulator runner lands in Phase 6",
                        "सिम्युलेटर चरण 6 में", 501)


@router.post("/sim/sensitivity")
def sensitivity():
    raise BusinessError("SIM_NOT_READY", "Sensitivity lands in Phase 6",
                        "सिम्युलेटर चरण 6 में", 501)


@router.get("/sim/{run_id}")
def status(run_id: str):
    raise BusinessError("SIM_NOT_READY", "Simulator runner lands in Phase 6",
                        "सिम्युलेटर चरण 6 में", 501)
