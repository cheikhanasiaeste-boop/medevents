# MedEvents TODO

_Last updated: 2026-04-22 — W2 closed, W3.1 spec merged, W3.1 plan open in PR #48 with changes requested; session paused for IDE restart before fixes were applied._

## Now

- [ ] **Answer two design questions on PR #48 before applying fixes** (they block the revision): (a) for Fix #1 (dev-DB wipe), use a dedicated `TEST_DATABASE_URL` env var or overload `DATABASE_URL` with shell-discipline-only? Assistant recommends `TEST_DATABASE_URL`. (b) for Fix #2 (content-derived year), also update spec §4 to name the logo-year signal, or keep it as plan-level implementation detail? Assistant recommends plan-level only.
- [ ] **Apply the four PR #48 fixes on branch `docs/w3-1-plan`** (full fix designs are in the `project_w3_1_in_progress.md` memory entry):
  - [ ] Fix #1 (High) — require a dedicated `medevents_test` DB for Phase 3; add destructive warning banner; Phase 5 re-points `DATABASE_URL` back at the dev DB for live smoke.
  - [ ] Fix #2 (High) — replace `_date.today()` year inference in `_parse_homepage` with `/images/logo-YYYY.png` extraction (content-derived, clock-independent). Add fifth classifier condition + two unit tests (logo-year assertion + homepage-without-logo returns empty).
  - [ ] Fix #3 (Medium) — append `--path ../../config/sources.yaml` to the Phase 4 `seed-sources` command so the relative path resolves correctly after the `cd services/ingest`.
  - [ ] Fix #4 (Medium) — drop the `--dry-run` smoke from Phase 4 Task 12 Step 2; replace with a real source-resolution probe via a `uv run python -c "..."` one-liner that calls `get_source_by_code` and asserts non-None.
- [ ] **Push to PR #48 + comment a change summary for re-review.** Do not merge until the user re-approves.
- [ ] **After PR #48 merges:** dispatch execution subagent-driven, one worker per task, starting with Phase 1 (normalize widening). Per standing `feedback_plan_execution_mode.md` preference.

## Next

- [ ] Execute W3.1 implementation plan task-by-task behind branch protection (each task → branch → PR → CI green → squash-merge). Same discipline as W2.
- [ ] Ship `docs/runbooks/w3.1-done-confirmation.md` as the last W3.1 step, mapping each §9 exit criterion to live-run / rerun / test evidence.
- [ ] Periodic scheduler story: `medevents-ingest run` currently runs manually or via the operator "Run now" button. Decide whether W3.2 wires a GitHub Actions schedule, a cron on the host, or a background worker.
- [ ] Decide whether to wire an existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement W2 `--dry-run` (currently exits 4). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the ADA schedule rows that returned `None` from `_row_to_event` — any should have landed in review_items per W2 spec §7? Currently silent-dropped. Not blocking W3.1.

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until the two-source pattern (ADA + GNYDM) is proven.
- [ ] Third-source onboarding (candidate order: `aap_annual_meeting` then `fdi_wdc`, per prep plan §3).
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

- [x] W3.1 sub-spec merged to `main` as `ed86dc9` (PR #46). Final spec reflects two review cycles: detail classifier tightened (URL + `h1.swiper-title` + Meeting Dates + venue), precedence pinned via a controlled-disagreement test double on `summary`, naming-convention sentence rewritten. `h1.swiper-title` residual-risk note carried forward.
- [x] W3.1 prep: GNYDM canary fixtures + robots/byte-stability review + source-code naming + stability-check protocol as default for future sources (PR #45, `a4cedb4`).
- [x] W3 direction decision: `gnydm` chosen as W3.1 second source before any scheduler or generic-fallback work.
- [x] W2 first-source ingestion (ADA) shipped: parser, pipeline, dedupe, review-item emission. Live smoke on main at `b0cd668`.
- [x] W2 spec + prep plan + W2 implementation plan all tracked on main.
- [x] W0+W1 foundation through Phase 10 is on `main`.
- [x] All schema migrations, indexes, and Drizzle introspection landed.
- [x] `seed-sources`, parser registry, and `run --source` CLI shape landed.
- [x] Admin auth, CSRF, audit, sources, review, and events operator surfaces landed.
- [x] Manual operator happy-path smoke completed on localhost.
- [x] PR `#28` fixed the three runtime bugs surfaced by that smoke.
- [x] Top-level `README.md` + `docs/runbooks/local-dev.md` (PR `#29`).
- [x] W1 done-confirmation against spec §10 (PR `#30`).
- [x] Branch protection on `main` with three required checks.
- [x] CI is green on `main` for TypeScript, Python, and schema drift.
