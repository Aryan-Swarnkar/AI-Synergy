"""Labelled intake sentences (HI/Hinglish/EN). expected=None means: expect missing.

Relative sowing dates resolve against TODAY = 2026-06-15.
Kept at 30 sentences per the Round-1 plan; accuracy target >= 80%.
"""
from __future__ import annotations

TODAY = "2026-06-15"

# (text, expected{product, crop, acres, sowing_date, qty})
SENTENCES: list[tuple[str, dict]] = [
    # --- English, fully specified (10) ---
    ("I need 2 bags of urea for 2 acres of wheat, sowing on 2026-06-27",
     {"product": "UREA", "crop": "wheat", "acres": 2.0, "sowing_date": "2026-06-27", "qty": 2}),
    ("Please give me 5 bags DAP for 3 acre paddy, sowing 30 June",
     {"product": "DAP", "crop": "paddy", "acres": 3.0, "sowing_date": "2026-06-30", "qty": 5}),
    ("1 acre cotton needs 2 bags urea, sowing in 12 days",
     {"product": "UREA", "crop": "cotton", "acres": 1.0, "sowing_date": "2026-06-27", "qty": 2}),
    ("MOP 1 bag for my 0.5 acre maize, sowing 2026-07-01",
     {"product": "MOP", "crop": "maize", "acres": 0.5, "sowing_date": "2026-07-01", "qty": 1}),
    ("Need NPK 3 bags, 2 acres wheat, sowing 2026-06-25",
     {"product": "NPK", "crop": "wheat", "acres": 2.0, "sowing_date": "2026-06-25", "qty": 3}),
    ("2 acres soybean, 1 bag urea, sowing in 9 days",
     {"product": "UREA", "crop": "soybean", "acres": 2.0, "sowing_date": "2026-06-24", "qty": 1}),
    ("For 4 acres of paddy I want 4 bags of DAP, sowing on 2026-07-05",
     {"product": "DAP", "crop": "paddy", "acres": 4.0, "sowing_date": "2026-07-05", "qty": 4}),
    ("urea 6 bags, maize 2.5 acres, sow 28 June",
     {"product": "UREA", "crop": "maize", "acres": 2.5, "sowing_date": "2026-06-28", "qty": 6}),
    ("I want 1 bag of MOP for 1 acre cotton sowing 2026-06-20",
     {"product": "MOP", "crop": "cotton", "acres": 1.0, "sowing_date": "2026-06-20", "qty": 1}),
    ("wheat 5 acres needs 13 bags urea sowing in 20 days",
     {"product": "UREA", "crop": "wheat", "acres": 5.0, "sowing_date": "2026-07-05", "qty": 13}),
    # --- Hinglish (10) ---
    ("mujhe 2 acre gehu ke liye urea chahiye, 10 din mein bona hai",
     {"product": "UREA", "crop": "wheat", "acres": 2.0, "sowing_date": "2026-06-25", "qty": None}),
    ("3 bori DAP chahiye 1.5 acre soybean ke liye, sowing 25 June",
     {"product": "DAP", "crop": "soybean", "acres": 1.5, "sowing_date": "2026-06-25", "qty": 3}),
    ("do acre dhaan ke liye 5 bori urea, 12 din me sowing",
     {"product": "UREA", "crop": "paddy", "acres": 2.0, "sowing_date": "2026-06-27", "qty": 5}),
    ("1 acre kapas ke liye 1 bori MOP chahiye, sowing 2026-06-22",
     {"product": "MOP", "crop": "cotton", "acres": 1.0, "sowing_date": "2026-06-22", "qty": 1}),
    ("makka 2 acre me 5 urea bori dalna hai, 8 din mein bona",
     {"product": "UREA", "crop": "maize", "acres": 2.0, "sowing_date": "2026-06-23", "qty": 5}),
    ("5 acre gehu, 13 bori urea, 20 din me sowing",
     {"product": "UREA", "crop": "wheat", "acres": 5.0, "sowing_date": "2026-07-05", "qty": 13}),
    ("soybean ek acre ke liye DAP ek bori, sowing 30 june",
     {"product": "DAP", "crop": "soybean", "acres": 1.0, "sowing_date": "2026-06-30", "qty": 1}),
    ("teen bori NPK, do acre kapas, 15 din mein",
     {"product": "NPK", "crop": "cotton", "acres": 2.0, "sowing_date": "2026-06-30", "qty": 3}),
    ("mujhe potash 2 bori chahiye, 1 acre makka, sowing 2026-07-02",
     {"product": "MOP", "crop": "maize", "acres": 1.0, "sowing_date": "2026-07-02", "qty": 2}),
    ("4 acre dhaan DAP 4 bori 5 july bona",
     {"product": "DAP", "crop": "paddy", "acres": 4.0, "sowing_date": "2026-07-05", "qty": 4}),
    # --- Hindi (6) ---
    ("मुझे 2 एकड़ गेहूं के लिए 4 बोरी यूरिया चाहिए, बुवाई 27 जून",
     {"product": "UREA", "crop": "wheat", "acres": 2.0, "sowing_date": "2026-06-27", "qty": 4}),
    ("1.5 एकड़ सोयाबीन हेतु 2 बोरी डीएपी, 10 दिन में बुवाई",
     {"product": "DAP", "crop": "soybean", "acres": 1.5, "sowing_date": "2026-06-25", "qty": 2}),
    ("दो एकड़ धान के लिए 5 बोरी यूरिया",
     {"product": "UREA", "crop": "paddy", "acres": 2.0, "sowing_date": None, "qty": 5}),
    ("३ बोरी एनपीके, २ एकड़ कपास",
     {"product": "NPK", "crop": "cotton", "acres": 2.0, "sowing_date": None, "qty": 3}),
    ("मक्का 3 एकड़, यूरिया 8 बोरी, 2026-07-03",
     {"product": "UREA", "crop": "maize", "acres": 3.0, "sowing_date": "2026-07-03", "qty": 8}),
    ("कपास एक एकड़ MOP एक बोरी",
     {"product": "MOP", "crop": "cotton", "acres": 1.0, "sowing_date": None, "qty": 1}),
    # --- Ambiguous / invalid (4): must stay missing, must ask, never submit ---
    ("mujhe urea chahiye",
     {"product": "UREA", "crop": None, "acres": None, "sowing_date": None, "qty": None}),
    ("I need 2 bags of XYZ crop",
     {"product": None, "crop": None, "acres": None, "sowing_date": None, "qty": 2}),
    ("sowing kal hai, 2 acre gehu",
     {"product": None, "crop": "wheat", "acres": 2.0, "sowing_date": None, "qty": None}),
    ("5 bori dedo",
     {"product": None, "crop": None, "acres": None, "sowing_date": None, "qty": 5}),
]
