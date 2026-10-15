"""Demo auth routes (MOCK)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import ROLES, get_current, make_token
from ..errors import BusinessError
from ..schemas import DemoLoginIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/demo-login")
def demo_login(body: DemoLoginIn):
    if body.role not in ROLES:
        raise BusinessError("BAD_ROLE", f"Role must be one of {', '.join(ROLES)}",
                            "गलत भूमिका", 400)
    return {"token": make_token(body.role, body.user_id), "role": body.role,
            "user_id": body.user_id, "mock": True}


@router.get("/me")
def me(cur: dict = Depends(get_current)):
    return {**cur, "mock": True}
