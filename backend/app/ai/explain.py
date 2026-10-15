"""AI-4 explainer (SPEC v3): paraphrases ONLY the decision record it is given.

Template path is default (deterministic, tested). An LLM paraphrase is used
only if a key is set AND fidelity_check() proves the output adds no facts
(numbers / codes / names absent from the record). Otherwise the template is
shown. The decision itself is never touched.
"""
from __future__ import annotations

import json
import re

from . import llm

_TPL = {
    "ISSUED": ("Your {qty} bag(s) of {product} are reserved at {centre}, "
               "pickup {pickup_date} ({days_early} days before sowing).",
               "आपकी {qty} बोरी {product} {centre} में आरक्षित है, "
               "उठाव {pickup_date} (बुवाई से {days_early} दिन पहले)।"),
    "WAITLISTED": ("No stock and slot in your window yet; you are waitlisted "
                   "with ETA {eta_date}. We will notify you.",
                   "अभी विंडो में स्टॉक/स्लॉट नहीं; प्रतीक्षा सूची में हैं, "
                   "अनुमानित तिथि {eta_date}। सूचना मिलेगी।"),
    "REJECTED": ("This request was rejected ({reason_code}). "
                 "Check the reason and try again.",
                 "यह अनुरोध अस्वीकृत ({reason_code})। कारण देखें व पुनः प्रयास करें।"),
}


def template(record: dict) -> dict:
    outcome = record.get("outcome", "REJECTED")
    en, hi = _TPL.get(outcome, _TPL["REJECTED"])
    safe = {k: (v if v is not None else "—") for k, v in record.items()}
    try:
        en, hi = en.format(**safe), hi.format(**safe)
    except Exception:
        pass
    return {"text_en": en, "text_hi": hi, "template_used": True}


def _facts(record: dict) -> tuple[set[str], set[str]]:
    dump = json.dumps(record, default=str)
    numbers = set(re.findall(r"\d+(?:\.\d+)?", dump))
    codes = set(re.findall(r"\b[A-Z]{2,}\b", dump))  # UREA, DAP, centre codes…
    return numbers, codes


def fidelity_check(text: str, record: dict) -> bool:
    """True iff every number and ALL-CAPS token in text already exists in record."""
    numbers, codes = _facts(record)
    for n in re.findall(r"\d+(?:\.\d+)?", text):
        if n not in numbers and n.rstrip("0").rstrip(".") not in {x.rstrip("0").rstrip(".") for x in numbers}:
            return False
    for c in re.findall(r"\b[A-Z]{2,}\b", text):
        if c not in codes:
            return False
    return True


def explain(record: dict, use_llm: bool = True) -> dict:
    base = template(record)
    if not (use_llm and llm.enabled()):
        return base
    out = llm.chat_json(
        "Paraphrase this fertiliser decision for a farmer in one short "
        "English sentence plus one short Hindi sentence. Change NO facts, "
        "numbers, dates or names. Reply JSON {text_en, text_hi}.",
        json.dumps({"template": base["text_en"], "facts": record}, default=str))
    if isinstance(out, dict) and out.get("text_en") and out.get("text_hi") \
            and fidelity_check(out["text_en"], record) and fidelity_check(out["text_hi"], record):
        return {"text_en": out["text_en"], "text_hi": out["text_hi"], "template_used": False}
    return base
