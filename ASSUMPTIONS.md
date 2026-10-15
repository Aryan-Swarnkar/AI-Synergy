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
20. **Concurrent same-farmer/different-key race:** dup-active check is read-then-write (TOCTOU); two concurrent keys for one farmer could both issue. Out of the 14-test scope; API layer (Phase 5) keeps sequential behaviour. A partial unique index is a future hardening.
21. **`uv --directory backend` is canonical** from repo root (`--project backend` does not chdir, so `python -m app.*` fails with it). `Makefile`/`make.ps1` use `--directory`.

## Phase 3 — Identity and inclusion
22. **Mock OTP store is in-memory** (`identity._OTP`, codes 123456 / voice 654321). Real SMS gateway replaces `send/verify_otp`; every UI surface carries a MOCK badge (Phase 7).
23. **Fail flag frozen at send:** `verify_otp` honours the `fail` bit stored by `send_otp`, so a session is consistent (no re-roll per attempt).
24. **Verifier daily limit counts APPROVALS only** (rejections never consume quota), per §3.2 wording; enforced inside the same `BEGIN IMMEDIATE` txn as the decision.
25. **Rejection cleanup:** all ISSUED tokens → CANCELLED with per-bag RELEASE ledger + pool decrement; WAITING entries → EXPIRED; farmer → REJECTED. Approval only flips PROVISIONAL → VERIFIED (future requests at 100%; existing provisional tokens stand).

## Phase 4 — Operator + lifecycle
26. **Receive consumes expectations:** pending lots (arrival ≤ given date) are marked received; only the operator-declared `qty` enters `on_hand`. A short rake (180 vs expected 200) honestly lowers projection by 20.
27. **Audit cancel condition** is `reserved > counted - buffer` (physical cannot cover holds), not the literal §5.5 'shortfall exceeds reserved' (which would miss counted < reserved cases). Newest-issued cancelled first, each with RELEASE ledger; farmers re-run through `request_token` under `{old}:audit:{code}` with notification text.
28. **Redeem window** is `[pickup, pickup+grace]` inclusive; success does `on_hand -= qty; reserved -= qty` + REDEEM ledger + Request COMPLETED and returns farmer name+village for the operator's visual ID check (no hard biometric in MVP).
29. **Reschedule** releases the old hold then reserves afresh (new key `{old}:resched:{n}`, `reschedules_used` carried over); beyond FREE_RESCHEDULES the API must say cancel + new request. No partial fulfilment.
