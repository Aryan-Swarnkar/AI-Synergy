"""AI-1 intake: free text -> structured request proposal (SPEC v3 §2).

Rule-based parser is the DEFAULT (offline, deterministic, tested). If
LLM_API_KEY is set, the LLM is tried first and its output must satisfy the
same schema + sanity checks, else we fall back to rules. Output is a
PROPOSAL: the API never creates a Request from it — the farmer confirms
(first via POST /requests, which re-validates everything).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from pydantic import BaseModel

from . import llm

PRODUCTS = {
    "UREA": ["urea", "यूरिया"],
    "DAP": ["dap", "डीएपी", "डीएपी"],
    "MOP": ["mop", "potash", "पोटाश", "mop "],
    "NPK": ["npk", "एनपीके"],
}

CROPS = {
    "wheat": ["wheat", "gehu", "gehun", "गेहूं", "गेहूँ"],
    "paddy": ["paddy", "dhaan", "dhan", "धान"],
    "soybean": ["soybean", "soya", "सोयाबीन", "सोया"],
    "maize": ["maize", "makka", "makki", "मक्का", "मक्की"],
    "cotton": ["cotton", "kapas", "कपास"],
}

HI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
WORD_NUM = {
    "ek": 1, "do": 2, "teen": 3, "tin": 3, "chaar": 4, "char": 4,
    "paanch": 5, "panch": 5, "cheh": 6, "chhah": 6, "saat": 7,
    "aath": 8, "ath": 8, "nau": 9, "nav": 9, "das": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
}
ACRE_WORDS = ["acre", "acres", "ekad", "एकड़", "एकड"]
BAG_WORDS = ["bag", "bags", "bori", "boriyan", "boriya", "बोरी", "बोरियां", "बोरा"]
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
          "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
          "november": 11, "december": 12, "जून": 6, "जुलाई": 7, "अगस्त": 8}


class IntakeProposal(BaseModel):
    product: str | None = None
    crop: str | None = None
    acres: float | None = None
    sowing_date: str | None = None  # YYYY-MM-DD
    qty: int | None = None
    confidence: float = 0.0
    missing_fields: list[str] = []
    clarifying_question: str | None = None
    parser: str = "rule"  # rule | llm


def _norm(text: str) -> str:
    return text.translate(HI_DIGITS).lower()


def _num_at(tokens: list[str], i: int) -> float | None:
    t = tokens[i]
    m = re.fullmatch(r"\d+(?:\.\d+)?", t)
    if m:
        return float(t)
    return WORD_NUM.get(t)


def _numbers(tokens: list[str]) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for i in range(len(tokens)):
        v = _num_at(tokens, i)
        if v is not None:
            out.append((i, v))
    return out


def _dist_to(tokens: list[str], i: int, words: list[str],
             radius: int = 4) -> tuple[int, int] | None:
    """(distance, after_flag): after_flag 0 when the keyword follows the
    number ("2 acres"), 1 when it precedes it. Forward attachment wins ties."""
    best: tuple[int, int] | None = None
    for j in range(max(0, i - radius), min(len(tokens), i + radius + 1)):
        if tokens[j] in words:
            cand = (abs(j - i), 0 if j > i else 1)
            if best is None or cand < best:
                best = cand
    return best


def _rule_parse(text: str, today: str) -> IntakeProposal:
    t = _norm(text)

    # ISO dates first, blanked out so 2026/06/25 never become quantities.
    sowing = None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        sowing = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        t = t[:m.start()] + " " + t[m.end():]
    tokens = re.findall(r"[\w\u0900-\u097F.]+", t)
    nums = _numbers(tokens)

    product = next((p for p, ws in PRODUCTS.items() if any(w.strip() in t for w in ws)), None)
    crop = next((c for c, ws in CROPS.items() if any(w in t for w in ws)), None)

    # Assign each number to the NEAREST keyword (acres vs bags), not acre-first.
    acres = qty = None
    for i, v in nums:
        da, db = _dist_to(tokens, i, ACRE_WORDS), _dist_to(tokens, i, BAG_WORDS)
        if da is None and db is None:
            continue
        if db is not None and (da is None or db <= da):
            if qty is None:
                qty = int(v)
        elif acres is None:
            acres = v
    if acres is None and qty is None and len(nums) == 1:
        acres = nums[0][1]  # single bare number reads as acres

    if sowing is None:
        m = re.search(r"(\d+)\s*(?:din|दिन)\s*(?:mein|me|main|men|में)?", t) or \
            re.search(r"in\s+(\d+)\s*days?", t)
        if m:
            y, mo, d = (int(x) for x in today.split("-"))
            sowing = (date(y, mo, d) + timedelta(days=int(m.group(1)))).isoformat()
    if sowing is None:
        for m in re.finditer(r"(\d{1,2})\s+([a-z\u0900-\u097F]+)", t):
            if m.group(2) in MONTHS:
                sowing = f"2026-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
                break

    fields = {"product": product, "crop": crop, "acres": acres,
              "sowing_date": sowing, "qty": qty}
    filled = sum(1 for v in fields.values() if v is not None)
    conf = min(0.95, 0.35 + 0.13 * filled)
    if len(nums) > 2:
        conf -= 0.1
    missing = [k for k, v in fields.items() if v is None]
    question = None
    if conf < 0.7 and missing:
        ask = {"product": "Which product do you need (UREA/DAP/MOP/NPK)?",
               "crop": "Which crop is this for?",
               "acres": "How many acres?",
               "sowing_date": "When is sowing (date or in how many days)?",
               "qty": "How many bags?"}
        question = ask[missing[0]]
    return IntakeProposal(**fields, confidence=round(max(0.0, conf), 2),
                          missing_fields=missing,
                          clarifying_question=question, parser="rule")


def _llm_parse(text: str) -> IntakeProposal | None:
    raw = llm.chat_json(llm.SYSTEM_INTAKE, text)
    if not raw:
        return None
    try:
        prop = IntakeProposal(**{k: raw.get(k) for k in
                                 ("product", "crop", "acres", "sowing_date", "qty")},
                              parser="llm")
    except Exception:
        return None
    if prop.product is not None and prop.product not in PRODUCTS:
        return None
    if prop.crop is not None and prop.crop not in CROPS:
        return None
    filled = sum(1 for k in ("product", "crop", "acres", "sowing_date", "qty")
                 if getattr(prop, k) is not None)
    prop.confidence = round(min(0.95, 0.35 + 0.13 * filled), 2)
    prop.missing_fields = [k for k in ("product", "crop", "acres", "sowing_date", "qty")
                           if getattr(prop, k) is None]
    return prop


def parse_request(text: str, lang: str = "hi", today: str = "2026-06-15") -> IntakeProposal:
    """Propose a structured request. Never creates anything persistent."""
    if llm.enabled():
        got = _llm_parse(text)
        if got is not None:
            return got
    return _rule_parse(text, today)
