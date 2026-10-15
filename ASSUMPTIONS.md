# ASSUMPTIONS.md

Logged per SPEC §14: where the spec is silent, simplest option consistent with §1 is chosen.

## Phase 1 — Foundation
1. **Repo root = `khadsetu/` root.** Current dir `synergy/` is treated as spec's `khadsetu/`. Existing `main.py` / `pyproject.toml` at root left untouched; backend lives in `backend/`, frontend in `frontend/`.
2. **Demo clock storage:** new `Meta(key, value)` table, `demo_today` defaults to `SEASON_START`. `POST /api/admin/tick` advances it. Needed because SPEC §5.5 requires a persistent simulated "today".
3. **Crop calendar values (SPEC §3.1 silent on offsets):** `soybean (0,30)`, `paddy (0,35)`, `maize (0,30)`, `cotton (0,40)`, `wheat (0,45)` days from `SEASON_START`. Wide/relaxed so demo requests are not spuriously rejected; enforced in allocator Phase 2.
4. **Windows `make`:** `make` is not preinstalled on Windows. Makefile is canonical; README documents Git-Bash or `choco install make`. A `make.ps1` shim is provided that forwards `dev/test/seed/sim` to the same commands.
5. **SQLite file location:** `backend/khadsetu.db` (WAL mode + `busy_timeout=5000`). Single-node only — production would need Postgres.
6. **Auth (demo only):** bearer tokens are base64 `role:user_id`, no real security. Production would use real JWT + AgriStack.
7. **Forward reservations:** `projected(d) = on_hand - reserved - buffer + arrivals_by(d)`. Reservation increments `reserved` immediately even if covered only by a future-dated lot; `receive-lot` later increments `on_hand`. Keeps Phase-2 conditional UPDATE simple and matches SPEC §5.4 wording.
8. **Baseline policy (§7.2):** daily token cap = `SLOT_CAPACITY * len(SLOT_BLOCKS)` (=100). Tenants excluded, OTP fail = retry next day up to `max_retries`. Labelled in UI as "our model, not measured data".
9. **Partial fulfilment:** not supported (SPEC §5.5 MVP note). Exact qty or waitlist.
10. **Anomaly thresholds:** verifier >30 approvals/day, centre >3 discrepancies/season, farmer >=3 expired/no-show tokens.
