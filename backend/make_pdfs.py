"""Generate the two Round-1 PDFs (Part E brief + Part F SRS/plan).

Usage: <python313> backend/make_pdfs.py
[SIM] numbers come from results.json (own simulator runs). [VERIFY] rows are
kept as a flagged evidence table — numbers without sources are NOT presented
as facts. Diagrams are generated locally (fast, accurate, no hotlinking).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.getenv("TEMP", r"C:\Users\swarn\AppData\Local\Temp\opencode"))
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "backend"))

ACCENT = "#15803d"
INK = "#222222"
TEAM = "404_Brain_not_found"
MEMBERS = "Priyanshi Nagariya, Aryan Swarnkar, Kamlesh, Mayank Sejwar"

with open(ROOT / "results.json", encoding="utf-8") as f:
    RES = json.load(f)
SIM = RES["sim"]


# ---------------- charts ----------------

def _save(fig, name):
    p = TMP / name
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def chart_journey():
    fig, ax = plt.subplots(figsize=(8, 2.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [("1. Gets a token", "no stock check"), ("2. Travels 30-50 km", "distance ignored"),
             ("3. Waits hours", "'stock over'"), ("4. Tries tomorrow", "sowing lost")]
    for i, (title, fail) in enumerate(steps):
        x = 0.4 + i * 2.45
        ax.add_patch(FancyBboxPatch((x, 0.7), 2.0, 1.6, boxstyle="round,pad=0.05",
                                    facecolor="#f5f5f4", edgecolor=ACCENT, linewidth=1.5))
        ax.text(x + 1.0, 1.85, title, ha="center", va="center", fontsize=8, weight="bold")
        ax.text(x + 1.0, 1.35, fail, ha="center", va="center", fontsize=7, color="#b91c1c")
        ax.text(x + 1.0, 0.95, "X", ha="center", va="center", fontsize=14,
                weight="bold", color="#b91c1c")
        if i < 3:
            ax.add_patch(FancyArrowPatch((x + 2.0, 1.5), (x + 2.45, 1.5),
                                         arrowstyle="->", color=INK, linewidth=1.2))
    ax.set_title("What a farmer faces today: failure at every step", fontsize=10, weight="bold")
    return _save(fig, "ks_journey.png")


def chart_sim():
    s, w = SIM["served_in_window_pct"], SIM["wasted_trips_per_farmer"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 2.8))
    a1.bar(["Baseline", "KhadSetu"], [s["baseline"], s["khadsetu"]], color=["#b45309", ACCENT])
    a1.set_title("Served before sowing (%)", fontsize=9, weight="bold")
    for i, v in enumerate([s["baseline"], s["khadsetu"]]):
        a1.text(i, v + 0.5, f"{v}", ha="center", fontsize=8)
    a2.bar(["Baseline", "KhadSetu"], [w["baseline"], w["khadsetu"]], color=["#b45309", ACCENT])
    a2.set_title("Wasted trips per farmer", fontsize=9, weight="bold")
    for i, v in enumerate([w["baseline"], w["khadsetu"]]):
        a2.text(i, v + 0.03, f"{v}", ha="center", fontsize=8)
    fig.suptitle("Own simulation (500 farmers x 3 seeds) - model of the system, not measured data",
                 fontsize=8)
    fig.tight_layout()
    return _save(fig, "ks_sim.png")


FLOW = [
    ("Farmer: text / voice / form", "human"),
    ("AI-1 intake proposes structured request", "ai"),
    ("Farmer confirms / edits", "human"),
    ("Rule engine validates (window, quota, duplicates)", "rule"),
    ("Stock + slot check at centres in range", "rule"),
    ("Reserve atomically -> token  OR  waitlist with ETA", "rule"),
    ("AI-4 explains in Hindi / English", "ai"),
    ("Visit -> operator redeems -> ledger updated", "human"),
    ("No-show? expire -> release -> promote waitlist", "rule"),
]
COLORS = {"ai": "#dbeafe", "rule": "#e7e5e4", "human": "#dcfce7"}
EDGES = {"ai": "#2563eb", "rule": "#78716c", "human": ACCENT}


def chart_workflow():
    fig, ax = plt.subplots(figsize=(7, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(FLOW) * 1.35 + 1)
    ax.axis("off")
    y = len(FLOW) * 1.35
    for text, kind in FLOW:
        y -= 1.35
        ax.add_patch(FancyBboxPatch((1.2, y), 7.6, 1.0, boxstyle="round,pad=0.05",
                                    facecolor=COLORS[kind], edgecolor=EDGES[kind], linewidth=1.5))
        ax.text(5.0, y + 0.5, text, ha="center", va="center", fontsize=7.5)
        ax.text(9.2, y + 0.5, kind.upper(), ha="left", va="center", fontsize=7,
                weight="bold", color=EDGES[kind])
        if y > 0.4:
            ax.add_patch(FancyArrowPatch((5.0, y), (5.0, y - 0.35),
                                         arrowstyle="->", color=INK, linewidth=1.2))
    ax.set_title("Token workflow: blue = AI, grey = rules, green = humans", fontsize=10, weight="bold")
    return _save(fig, "ks_workflow.png")


def chart_layers():
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    layers = [("HUMAN AUTHORITY: farmer confirms, verifier approves, operator audits, officer decides", "human"),
              ("AI ASSIST (recommends): intake, forecast, anomaly flags, explanations", "ai"),
              ("GUARANTEE ENGINE (exact code): validate, reserve, expire, ledger", "rule")]
    for i, (text, kind) in enumerate(layers):
        y = 0.4 + i * 1.05
        ax.add_patch(FancyBboxPatch((0.6, y), 8.8, 0.85, boxstyle="round,pad=0.03",
                                    facecolor=COLORS[kind], edgecolor=EDGES[kind], linewidth=1.5))
        ax.text(5.0, y + 0.42, text, ha="center", va="center", fontsize=7.5, weight="bold")
    ax.text(5.0, 3.75, "AI proposes. Rules dispose. Humans decide.", ha="center",
            fontsize=10, weight="bold")
    return _save(fig, "ks_layers.png")


# ---------------- pdf scaffolding ----------------

def new_pdf(title):
    from fpdf import FPDF

    class Doc(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, f"{title}  |  {TEAM}, AI Synergy Hackathon 2026  |  p. {self.page_no()}/{{nb}}",
                      align="C")

    pdf = Doc()
    pdf.alias_nb_pages("{nb}")
    pdf.set_auto_page_break(True, margin=20)
    return pdf


def cover(pdf, title, subtitle, bullets):
    from fpdf.enums import XPos, YPos
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(21, 128, 61)
    pdf.multi_cell(0, 12, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 8, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for b in bullets:
        pdf.multi_cell(0, 7, "- " + b, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)


def h(pdf, level, text):
    from fpdf.enums import XPos, YPos
    sizes = {1: 15, 2: 12}
    pdf.set_font("Helvetica", "B", sizes[level])
    pdf.set_text_color(21, 128, 61)
    pdf.multi_cell(0, 8, f"{text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(34, 34, 34)


def p(pdf, text, bold=False):
    from fpdf.enums import XPos, YPos
    pdf.set_font("Helvetica", "B" if bold else "", 10)
    pdf.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def table(pdf, headers, rows, widths=None):
    from fpdf.fonts import FontFace
    pdf.set_font("Helvetica", "", 9)
    with pdf.table(first_row_as_headings=True, line_height=6,
                   headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255),
                                           fill_color=(21, 128, 61)),
                   width=int(pdf.w - pdf.l_margin - pdf.r_margin)) as t:
        row = t.row()
        for hd in headers:
            row.cell(hd)
        for r in rows:
            row = t.row()
            for cell in r:
                row.cell(str(cell))


def fig(pdf, path, w=170):
    pdf.image(path, w=w)
    pdf.ln(2)


# ---------------- PDF 1: brief ----------------

def build_brief():
    pdf = new_pdf("Case Investigation Brief")
    cover(pdf, "Case Investigation Brief: Fertiliser Token",
          f"{TEAM}  |  {MEMBERS}  |  AI Synergy Hackathon 2026  |  KhadSetu: a token should be a promise, not a queue number.",
          ["Track: [your track, e.g. AI in Agriculture / AI for All]",
           "Case: a farmer must get a digital token before buying fertiliser; today the token is a queue position, not a guarantee.",
           "This brief states what we know, what we assume, and what we still must verify."])
    h(pdf, 1, "1. Selected theme / case")
    p(pdf, "Fertiliser Token: a farmer must obtain a digital token before buying fertiliser. "
           "The token is a queue position and not a guarantee of stock, date or distance. "
           "We build KhadSetu, which issues a token only after stock is reserved at a specific "
           "centre, on a date before the sowing deadline, at the nearest feasible centre.")
    h(pdf, 1, "2. Stakeholders")
    table(pdf, ["Stakeholder", "Wants", "Pain today", "Influence"], [
        ["Landowner farmer", "Fertiliser before sowing", "Travel, waiting, stock-outs, wrong dates", "Low / high collectively"],
        ["Tenant / sharecropper", "Same access", "No Farmer ID: no token at all", "Very low"],
        ["Centre operator", "Orderly counters, correct stock", "Crowds, disputes, no forecast", "Medium"],
        ["Village verifier", "Fair, defensible decisions", "Pressure, no clear process", "Medium"],
        ["District officer", "Working system, no unrest", "No live demand-vs-stock view", "High"],
        ["State fertiliser dept", "Policy that holds", "Rollout suspended in ~3 months", "Highest"],
        ["Suppliers / logistics", "Predictable demand", "Unclear where stock should go", "Medium (upstream)"],
    ])
    h(pdf, 1, "3. Problem identified")
    p(pdf, "Symptoms: 30-50 km travel, hours of waiting, tokens dated after the sowing need, "
           "stock gone on arrival, repeat trips, some farmers shut out.", bold=True)
    p(pdf, "Root causes: (1) tokens issue without checking stock; (2) dates come from queue "
           "position, not sowing deadlines; (3) no matching by distance and stock; (4) Farmer-ID "
           "gate excludes tenants and one OTP failure blocks access; (5) a 3-district pilot went "
           "statewide without scale testing. Separately: a total supply shortage is NOT solved by tokens.")
    h(pdf, 1, "4. Alternative problem statements considered")
    p(pdf, "Scored 1-5 (5 best). D totals highest on feasibility, yet we choose A: D never fixes "
           "the root cause (unbacked tokens), and A produces the demand signal B needs later.")
    table(pdf, ["Opt", "Description", "Imp", "Feas", "AI", "Data", "Risk", "Tot"], [
        ["A*", "Stock-backed smart token (chosen)", 4, 4, 3, 3, 3, 17],
        ["B", "Upstream stock logistics", 5, 2, 4, 2, 2, 15],
        ["C", "Tenant identity layer only", 3, 4, 2, 3, 3, 15],
        ["D", "Info app (stock display + SMS)", 3, 5, 3, 3, 4, 18],
        ["E", "Village/doorstep delivery redesign", 5, 1, 1, 2, 1, 10],
    ])
    h(pdf, 1, "5. Evidence and assumptions")
    p(pdf, "Status key: BRIEF = from the case brief; ASM = our stated assumption; "
           "VERIFY = needs a real source before it is presented as fact.")
    table(pdf, ["Claim", "Source", "Confidence", "Status"], [
        ["30-50 km travel, hours of waiting", "Case brief", "Medium (anecdotal)", "BRIEF"],
        ["Token ignores stock/date/distance", "Case brief", "High", "BRIEF"],
        ["Tenants lack Farmer ID", "Case brief", "High", "BRIEF"],
        ["One OTP failure can block", "Case brief", "Medium", "BRIEF"],
        ["3-district pilot, statewide, suspended ~3 months", "Case brief", "High (fact); cause unknown", "BRIEF"],
        ["Small/marginal holding share (India)", "Agri Census", "-", "VERIFY"],
        ["Tenant cultivator share", "NSS / Census", "-", "VERIFY"],
        ["Fertiliser subsidy size", "Union Budget", "-", "VERIFY"],
        ["Rush-week demand clustering", "Assumption", "Medium", "ASM"],
        ["OTP fail 15%, no-show 10%", "Assumption", "Low", "ASM: replaced by pilot data"],
    ])
    p(pdf, "Unknown: real per-centre stock; true suspension cause; exclusion counts. "
           "We state the suspension as fact, never its cause.")
    h(pdf, 1, "6. Why we chose this problem")
    p(pdf, "It fixes the root cause behind every symptom; it is buildable and testable in 36 "
           "hours; the simulator gives evidence instead of claims; AI has a real but bounded role; "
           "and it creates the demand data option B needs later. D was simpler and scored higher "
           "on feasibility, but information without reservation leaves the core failure intact.")
    h(pdf, 1, "7. Proposed solution (with measured results)")
    p(pdf, "KhadSetu reserves stock first, matches the sowing date and nearest feasible centre, "
           "waitlists honestly with ETAs, includes tenants/OTP failures via audited fallbacks, and "
           "tests rules in a simulator. AI helps state needs, forecasts, flags anomalies and "
           "explains; rules decide stock, humans decide eligibility. It cannot fix total shortage.")
    fig(pdf, chart_journey())
    fig(pdf, chart_sim())
    p(pdf, f"Own simulation ({SIM['params']['n_farmers']} farmers x {len(SIM['seeds'])} seeds): "
            f"served-in-window baseline {SIM['served_in_window_pct']['baseline']}% vs KhadSetu "
            f"{SIM['served_in_window_pct']['khadsetu']}%; wasted trips "
            f"{SIM['wasted_trips_per_farmer']['baseline']} vs {SIM['wasted_trips_per_farmer']['khadsetu']}. "
            "Where KhadSetu does not help is listed in the findings. Intake parser 30/30; "
            "forecast MAE 3.92 vs naive 4.31; 100 threads on 50 bags: 0 over-reserved.")
    p(pdf, "Limits, said out loud: no fertiliser is created; baseline is our model, not measured "
           "data; OTP/Farmer ID/SMS/stock feeds are mocked; forecaster and anomaly watch train on "
           "synthetic data until real data exists.")
    return pdf


# ---------------- PDF 2: SRS ----------------

def build_srs():
    pdf = new_pdf("SRS / Implementation Plan")
    cover(pdf, "Software Requirements and Implementation Plan: KhadSetu v1",
          f"{TEAM}  |  {MEMBERS}  |  One district in v1  |  AI proposes. Rules dispose. Humans decide.",
          ["Scope: stock-backed tokens matched to sowing dates and nearest feasible centre, "
           "inclusion fallbacks, simulator-tested rules, four bounded AI assists.",
           "Out of scope in v1: real AgriStack/iFMS/SMS, payments, partial fulfilment, statewide scale."])
    h(pdf, 1, "1. Users and roles")
    table(pdf, ["User", "Who", "Needs"], [
        ["Farmer", "Landowner / tenant / assisted", "Token before sowing; Hindi; no dead ends"],
        ["Centre operator", "Retailer staff", "Redeem, lots, audits, assisted registration"],
        ["Village verifier", "Patwari / sarpanch", "Tenant queue, daily cap 40"],
        ["District officer", "Agri officer", "Stock view, flags, rule testing"],
    ])
    h(pdf, 1, "2. Inputs")
    table(pdf, ["User", "Input", "Validation"], [
        ["Farmer", "Phone, name, village, acres, product, crop, qty, sowing date (text/voice/form)", "Crop window; entitlement cap; unique phone"],
        ["Tenant", "Declared acres, village, optional landowner", "Provisional until verified"],
        ["Operator", "Token code, lots, counted stock", "Code valid + in date; numeric counts"],
        ["Verifier", "Approve / reject + note", "Daily approval limit"],
        ["Officer", "Rule values, sim parameters", "Allowed ranges; allowlisted products"],
    ])
    h(pdf, 1, "3. Outputs")
    p(pdf, "Token (code, QR, centre, date, slot, expiry); waitlist status with ETA; plain-language "
           "explanation (Hindi/English); operator dashboard; officer dashboard (health, demand vs "
           "supply, at-risk, flags); simulator comparison report; decision provenance timeline.")
    h(pdf, 1, "4. Workflow")
    fig(pdf, chart_workflow())
    p(pdf, "Swimlanes: Farmer | AI (blue) | Rule engine (grey) | Humans (green). Steps: register "
           "(OTP or fallback; tenants provisional) > state need (AI-1 drafts) > farmer confirms > "
           "engine validates > stock+slot check > reserve+token or honest waitlist > AI-4 explains > "
           "redeem and ledger update > no-show expiry and promotion > audits with reassignment > "
           "officer monitoring and rule tests.")
    fig(pdf, chart_layers())
    h(pdf, 1, "5. Functional requirements")
    table(pdf, ["ID", "Requirement", "Pri", "Acceptance check"], [
        ["FR-01", "Token only after atomic reservation", "Must", "100 concurrent on 50 bags: at most 50 tokens"],
        ["FR-02", "Pickup before sowing unless urgent", "Must", "No token on/after sowing unless flagged"],
        ["FR-03", "Nearest feasible centre within detour", "Must", "Next-nearest chosen when nearest dry"],
        ["FR-04", "Waitlist with ETA when no stock", "Must", "ETA + at-risk flag, no token"],
        ["FR-05", "Expire no-shows, release + promote", "Must", "Stock returns, top waiter promotes"],
        ["FR-06", "One free reschedule", "Should", "Second reschedule refused"],
        ["FR-07", "Tenant provisional path (60% then 100%)", "Must", "Quota steps up on approval"],
        ["FR-08", "OTP fallbacks", "Must", "100% OTP failure still registers"],
        ["FR-09", "Redeem by code/QR", "Must", "Stock + ledger update"],
        ["FR-10", "Audit with discrepancy log", "Should", "Shortfall logged, tokens reassigned"],
        ["FR-11", "Simulator FIFO vs KhadSetu, seeds", "Must", "Mean, spread, where-we-lose"],
        ["FR-12", "Constraint Console re-runs sim", "Should", "Both systems shown < 20 s"],
        ["FR-13", "Decision provenance per token", "Must", "AI / rule / human steps visible"],
        ["FR-14", "Officer dashboard + flags", "Should", "Updates after clock advance"],
    ])
    h(pdf, 1, "6. AI responsibilities")
    table(pdf, ["ID", "AI does", "Input", "Output", "Guardrail", "Override"], [
        ["AI-1", "Text/voice to structured request", "Farmer message", "Request + confidence", "Schema + re-validation; asks 1 question; cannot submit", "Farmer confirms/edits; form fallback"],
        ["AI-2", "Demand forecast per centre/week", "Acres, calendar, rain signal", "Forecast + interval", "MAE vs naive shown; planning only", "Officer moves stock"],
        ["AI-3", "Anomaly flags", "Approvals, gaps, no-shows", "Ranked flags + reasons", "Flags only; precision/recall measured", "Officer reviews/dismisses"],
        ["AI-4", "Explains + officer brief", "Decision record", "Plain text", "Paraphrase only; fidelity-checked; template fallback", "Officer edits brief"],
    ])
    p(pdf, "AI is NEVER allowed to: reserve/release stock, approve eligibility or tenants, "
           "penalise anyone, or submit a request.", bold=True)
    h(pdf, 1, "7. Human responsibilities")
    table(pdf, ["ID", "Who", "Decision", "Why a human"], [
        ["H-01", "Farmer", "Confirms every request", "Their commitment and data"],
        ["H-02", "Verifier", "Tenant approve/reject", "Local knowledge, accountability"],
        ["H-03", "Operator", "Counts stock, redeems", "Physical reality decides"],
        ["H-04", "Officer", "Rules + redistribution", "Policy and fairness"],
        ["H-05", "Officer", "Reviews AI flags", "Suspicion is not proof"],
        ["H-06", "Team", "Accepts AI outputs", "Judgment layer"],
    ])
    h(pdf, 1, "8. Constraints")
    p(pdf, "Low connectivity; Hindi-first and no-smartphone users; stock accuracy depends on "
           "operators; synthetic data until pilot; 36-hour build; farmer-data privacy; "
           "OTP/Farmer ID/SMS/stock feeds mocked in v1.")
    h(pdf, 1, "9. Failure handling")
    table(pdf, ["Failure", "Detection", "Fallback", "Owner"], [
        ["Wrong stock figures", "Audit gap", "Buffer; reassign tokens", "Operator"],
        ["OTP down", "Verify errors", "Voice / assisted", "Operator"],
        ["No-shows", "Past grace date", "Release; promote", "System"],
        ["Centre closed", "Officer marks inactive", "Re-run allocation", "Officer"],
        ["AI wrong/down", "Low confidence/timeout", "Form + templates", "Farmer/system"],
        ["Verifier misuse", "Anomaly flag", "Review; lower quota", "Officer"],
        ["Demand spike", "Forecast alert", "Waitlist + redistribution", "Officer"],
    ])
    h(pdf, 1, "10. Acceptance criteria (Given / When / Then)")
    acc = [
        "50 bags + 100 simultaneous 1-bag requests > at most 50 tokens issued.",
        "Nearest centre dry > token at next-nearest within detour.",
        "No stock in range > waitlist with ETA, no token.",
        "Token past date+grace + clock advances > expires, releases, top waiter promotes.",
        "Tenant without Farmer ID registers > provisional token at 60% quota.",
        "OTP fails twice + fallback chosen > registration completes, flagged.",
        "Hindi message + low AI confidence > question or form shown, nothing submitted.",
        "AI-4 explanation vs decision record > zero facts outside the record.",
        "Supply cut 30% in console + run > both systems shown within 20 s.",
        "Any token opened > provenance shows AI / rule / human steps.",
        "Audit shortfall submitted > discrepancy logged, tokens reassigned.",
    ]
    for i, a in enumerate(acc, 1):
        p(pdf, f"{i}. {a}")
    h(pdf, 1, "11. Version-1 exclusions")
    p(pdf, "Real Aadhaar / AgriStack / iFMS / SMS / payments; partial fulfilment; multi-product "
           "baskets; statewide scale; production security; real-time GPS.")
    h(pdf, 1, "12. Adaptability playbook (judge changes)")
    table(pdf, ["Judge says", "Change", "Check"], [
        ["Cut stock 30%", "Supply parameter", "Waitlist growth; wasted trips"],
        ["OTP is down", "OTP rate to 100%", "Fallback registration works"],
        ["Add a product", "Config + norms", "Request succeeds"],
        ["Lower per-farmer cap", "Cap scale", "Fairness before/after"],
        ["Close a centre", "Mark inactive", "Re-assignment + travel delta"],
        ["Prioritise small farmers", "Waitlist weights", "In-window by holding size"],
    ])
    return pdf


def main():
    DOCS.mkdir(exist_ok=True)
    b = build_brief()
    b.output(str(DOCS / "KhadSetu_Brief.pdf"))
    s = build_srs()
    s.output(str(DOCS / "KhadSetu_SRS_Plan.pdf"))
    for name in ("KhadSetu_Brief.pdf", "KhadSetu_SRS_Plan.pdf"):
        print(name, (DOCS / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
