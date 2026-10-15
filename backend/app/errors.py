"""Consistent error bodies {error_code, message, message_hi} (SPEC §6).

Business-rule failures never become bare 500s: services return dicts, routers
raise BusinessError, and the handler below renders the envelope.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

HI_FALLBACK = "कुछ गलत हुआ। कृपया पुनः प्रयास करें।"


class BusinessError(Exception):
    def __init__(self, error_code: str, message: str, message_hi: str = "",
                 status: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.message_hi = message_hi or HI_FALLBACK
        self.status = status


async def business_handler(_: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={
        "error_code": exc.error_code, "message": exc.message,
        "message_hi": exc.message_hi})
