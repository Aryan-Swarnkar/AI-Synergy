"""Demo auth (SPEC §6): base64 role:user_id bearer tokens. No real security —
production would use JWT + AgriStack. Every login surface is MOCK-labelled.
"""
from __future__ import annotations

import base64

from fastapi import Depends, Header

from .errors import BusinessError

ROLES = ("FARMER", "OPERATOR", "VERIFIER", "OFFICER")


def make_token(role: str, user_id: str) -> str:
    raw = f"{role}:{user_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def parse_token(token: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        role, user_id = raw.split(":", 1)
    except Exception:
        raise BusinessError("INVALID_TOKEN", "Invalid demo token",
                            "अमान्य डेमो टोकन", 401)
    if role not in ROLES:
        raise BusinessError("INVALID_TOKEN", "Invalid demo token",
                            "अमान्य डेमो टोकन", 401)
    return {"role": role, "user_id": user_id}


def get_current(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessError("UNAUTHENTICATED", "Missing bearer token",
                            "टोकन नहीं मिला", 401)
    return parse_token(authorization.removeprefix("Bearer ").strip())


def require_roles(*roles: str):
    def _dep(cur: dict = Depends(get_current)) -> dict:
        if cur["role"] not in roles:
            raise BusinessError("FORBIDDEN", f"Requires role {', '.join(roles)}",
                                "अनुमति नहीं है", 403)
        return cur
    return _dep
