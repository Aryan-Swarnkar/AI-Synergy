# KhadSetu v2 — Stock-Backed Fertiliser Token System

A token is a **commitment**: stock atomically reserved at a specific centre,
for a specific date and slot, before the farmer's sowing deadline. If that is
impossible, the farmer gets an honest **waitlist with ETA**, never a useless
token. Tenants, farmers without a Farmer ID, and failed OTPs go through
audited fallbacks — nobody is ever blocked.

> **Honesty note:** KhadSetu cannot create fertiliser. It removes wasted trips
> and makes shortage visible and fair. The simulator proves it — including
> where KhadSetu does *not* help.

All externals are **MOCK** and labelled in the UI: OTP (`123456`, voice
`654321`), Farmer ID (`MP-…`), SMS previews, iFMS feed (`receive-lot` form).

## Run

Prereqs: Python 3.11+ with `uv`, Node 18+.

```bash
# install
./make.ps1 install      # or: make install (Git-Bash)

# seed demo district (Bhopal/Sehore: 6 centres, 40 villages, 60 farmers)
./make.ps1 seed

# dev servers — backend :8000, frontend :5173
./make.ps1 dev          # or: make dev

# tests (30 backend tests incl. 100-thread no-oversell) + simulator CLI
./make.ps1 test
./make.ps1 sim
```

`uv run --directory backend …` is canonical from repo root
(`--project backend` does not chdir, so `python -m app.*` fails with it).

## Demo script (SPEC §11 — verified end to end)

1. **Officer view** (`/officer`): map shows Centre A nearly out of UREA
   (2 bags on hand), Centre B with a 200-bag rake arriving in 3 days
   (`MOCK-iFMS-rake-ETA3d`).
2. **Ramesh** (tenant, far village, phone `9876500000`): register on
   `/login` → OTP fails twice → fallback cards appear → assisted/voice path
   → provisional registration (60% quota, `needs_audit`).
3. **Ramesh requests UREA**, sowing +12 days → token at the next-nearest
   centre with stock + plain-language "why this centre" box.
4. **Second farmer**, sowing in 2 days, requests UREA → WAITLISTED with
   at-risk warning; visible in officer at-risk list.
5. **Advance clock 3 days** (top bar) → operator `receive-lot` for the rake
   → waitlisted farmer auto-promoted → "🎉 You got a token!" banner on
   `/tokens`.
6. **Redeem** Ramesh's code on `/operator` → stock drops live.
7. **Audit** with a ~3% shortfall → discrepancy logged, officer sees it;
   over-held tokens auto-reassigned with notification text.
8. **Simulator** (`/sim`): run `normal` → baseline-vs-KhadSetu charts +
   "Where KhadSetu does not help" panel; run `shortage_20pct` for honesty
   under scarcity (shortage-driven non-service is similar in both systems).

## v3 AI layer (AI proposes. Rules dispose. Humans decide.)

Four AI components, each a recommendation with guardrails + human override.
Rule-based paths are default and tested; LLM is optional via `backend/.env`
(gitignored — never commit keys; see `backend/.env.example`):

- **AI-1 intake** (`/intake` page, `POST /ai/parse`): Hindi/Hinglish/English
  text or voice → structured request + confidence; farmer edits and taps
  Confirm (plain form always available). Parser accuracy 30/30 on labelled
  fixtures (`backend/app/ai/fixtures_intake.py`).
- **AI-2 forecast** (Officer page, `GET /ai/forecast`): per centre/product/week
  demand with interval; MAE reported vs naive baseline (synthetic history).
- **AI-3 anomaly watch** (Officer page, `GET /ai/anomalies`): ranked flags
  with reasons; dismissals logged. Flags only — never penalises.
- **AI-4 explainer** (`POST /ai/explain`, shown on token cards): paraphrases
  only the decision record; fidelity-checked, template fallback.
- **Decision provenance**: every token carries an AI/RULE/HUMAN timeline
  (`GET /tokens/{code}/provenance`, shown in app).
- **Constraint Console** (Simulator page): supply −30%, OTP/no-show, cap,
  detour, closed centres (stock redistributed), new product (allowlisted,
  e.g. ZINC) → before/after for both policies in seconds.

Measured results (`results.json`, via `uv run --directory backend python make_results.py`):
500 farmers × 3 seeds — served-in-window baseline 19.7% vs KhadSetu 37.8%;
wasted trips/farmer 1.31 vs 0.02; intake 30/30; forecast MAE 3.92 vs naive
4.31; 100 threads on 50 bags: 0 over-reserved. Where KhadSetu does not help
(e.g. travel 22.1 vs 22.9 km) is listed in the findings.

## What is mocked / integration-ready

| Mock (MOCK badge) | Real integration point |
|---|---|
| OTP / voice / SMS | SMS gateway + IVR (Bhashini-class) |
| Farmer ID `MP-…` | AgriStack farmer registry |
| iFMS stock feed | operator `receive-lot` form |
| Demo bearer auth | real JWT + role service |

Not included: real Aadhaar/AgriStack/iFMS/SMS, payments, production
security, partial fulfilment, multi-product baskets.

## Layout

`backend/app/{config,db,models,auth,errors,demo,main,seed}.py`
`backend/app/core/` (PURE allocator: `types,geo,norms,allocator` — no DB/web imports)
`backend/app/services/` (`tokens,identity,stock,analytics`)
`backend/app/routers/` (`auth,farmers,tokens,centres,verifier,officer,admin,sim,ai`)
`backend/app/ai/` (`llm,intake,forecast,anomaly,explain` + fixtures)
`backend/app/sim/` (`generator,baseline,khadsetu,runner,metrics`)
`backend/tests/` (58 tests) · `frontend/src/` (9 pages + EN/HI locales)

See `ASSUMPTIONS.md` for every silent-spec decision.
`backend/verify_demo.py` replays the script above against a live server
(start backend on `:8001`, run `uv run --directory backend python verify_demo.py`).
