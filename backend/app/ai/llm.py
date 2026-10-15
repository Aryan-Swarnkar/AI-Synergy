"""Optional LLM adapter (SPEC v3 AI layer). Env-gated, stdlib-only, never required.

Set backend/.env (gitignored) to enable the live-LLM path:
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  LLM_API_KEY=<your key>   # never commit, never paste in shared chats
  LLM_MODEL=gemini-2.0-flash
Without a key every AI module uses its deterministic rule/template path,
which is what the tests exercise. Any LLM failure falls back silently.
"""
from __future__ import annotations

import json
import os
import urllib.request

SYSTEM_INTAKE = (
    "Extract a fertiliser request as JSON with keys: product (UREA/DAP/MOP/NPK), "
    "crop (wheat/soybean/paddy/maize/cotton), acres (number), sowing_date "
    "(YYYY-MM-DD), qty (bags number). Use null for anything not stated. "
    "Reply with JSON only."
)


def enabled() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def chat_json(system: str, user: str, timeout_s: float = 15.0) -> dict | None:
    """POST to an OpenAI-compatible /chat/completions endpoint. None on any failure."""
    key = os.getenv("LLM_API_KEY")
    if not key:
        return None
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_S", str(timeout_s)))
    except ValueError:
        timeout = timeout_s
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        content = body["choices"][0]["message"]["content"]
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end < 0:
            return None
        parsed = json.loads(content[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
