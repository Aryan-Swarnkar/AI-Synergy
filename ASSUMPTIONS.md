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
11. **All Python via `uv`:** `Makefile`/`make.ps1` use `uv pip install --system` + `uv run pytest/python/uvicorn`. Fixes SENTINAL `.venv` shadowing on this machine.
12. **Naive UTC datetimes:** `_now() = now(timezone.utc).replace(tzinfo=None)` keeps SQLite-friendly naive values without `utcnow()` deprecation warnings.
13. **Ramesh OTP phone explicit:** `9876500000` (ends 000 → always fails OTP per §3.3) so the §11 demo works deterministically.

## Phase 2 — Allocator + reservation
14. **Slot model:** per-day used = count of ISSUED tokens for (centre, date); `slot = BLOCKS[used // SLOT_CAPACITY]`, day cap = `SLOT_CAPACITY × len(BLOCKS)`. First-with-room block wins. No separate slot table.
15. **Pending arrivals only:** `CentreState.arrivals` = lots with `received_at IS NULL`. Received lots are already inside `on_hand`; counting them again would double-count.
16. **Lost-race retry:** conditional `UPDATE ... WHERE (on_hand*OVERBOOK - reserved - buf + arrivals) >= qty`; 0 rows → re-run `decide()` once with fresh state in a NEW txn (no nesting), else honest WAITLIST. Never oversells.
17. **Slot-full race:** reserve increment undone via compensating `UPDATE reserved - qty` in the same txn, then a WAITLIST request is persisted instead.
18. **Promotion (minimal):** `expire_and_promote()` expires `pickup+grace < today` (RELEASE ledger), then promotes WAITING entries sorted by `(deadline, acres, created_at)`; old waitlist request is CANCELLED and a fresh token issued under `{old_key}:promote:{entry}`. Full `/admin/tick` endpoint lands in Phase 4.
19. **Purity enforced by test:** `allocator.py` must contain no `import/from sqlalchemy|fastapi` (docstring mentions allowed; import statements fail the test).
