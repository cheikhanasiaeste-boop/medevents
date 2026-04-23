# MedEvents TODO

_Last updated: 2026-04-23 — W3.2f (`--dry-run`) + W3.2g (ADA silent-drop aggregate review_items) + testseed cleanup all shipped. Autonomous queue is clear. Two open items: W3.2d live Fly deploy (operator-gated) and the Playwright CI decision (awaiting user input — options preserved below)._

## Now

**Two tracks in parallel:**

### Track A (operator-gated) — W3.2d live deployment

Repo artifacts on `main`:

- `services/ingest/Dockerfile` — multi-stage Python 3.12 + uv image; default CMD = `medevents-ingest run --all`.
- `fly.toml` at repo root — scheduled machine config, hourly wake, 256MB / shared CPU.
- `docs/runbooks/w3.2d-fly-scheduler-deploy.md` — step-by-step operator runbook.
- `docs/runbooks/w3.2d-done-confirmation.md` — skeleton the operator fills in after the first autonomous run.

**Operator action required** (not autonomously runnable — needs Fly.io account + billing + credentials):

1. `fly apps create medevents-ingest` (or operator-chosen name).
2. Provision / attach Postgres (Fly PG or external cloud PG).
3. `fly secrets set DATABASE_URL=...`.
4. `fly deploy` from repo root.
5. Verify first scheduled run via `fly logs`.
6. Fill in `w3.2d-done-confirmation.md` and commit.

### Track B (user-gated) — Playwright CI decision

See "Open decisions" below. Four options audited on 2026-04-23; recommendation D. Waiting on user input before proceeding.

### Track C (autonomous) — exhausted for now

The autonomous queue through W3.2g + testseed cleanup is complete. Optional waves that no longer block product value:

- Fourth source `fdi_wdc` — operator discretion.
- Generic fallback parser — operator discretion.
- Migrate the remaining 6 DB-gated test files (`test_pipeline.py`, `test_repositories*.py`) to `TEST_DATABASE_URL` like `test_seed.py` was in PR #73 — operator discretion (nice hygiene but no active pain since they don't leak seed rows).

## Open decisions

### Playwright CI wiring (audited 2026-04-23)

Existing specs: [`apps/web/tests/e2e/admin-login.spec.ts`](../apps/web/tests/e2e/admin-login.spec.ts) (3 tests, no DB fixtures) and [`apps/web/tests/e2e/happy-path-smoke.spec.ts`](../apps/web/tests/e2e/happy-path-smoke.spec.ts) (opt-in via `RUN_FULL_SMOKE=1`, requires ADA/review_item/event fixtures). Neither runs in CI today — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) has no `playwright` / `test:e2e` step.

| Option | Scope                                                    | Incremental CI time             | Flakiness risk                                | Catch radius                            |
| ------ | -------------------------------------------------------- | ------------------------------- | --------------------------------------------- | --------------------------------------- |
| A      | Keep opt-in local-only (status quo)                      | 0                               | n/a                                           | None from UI layer                      |
| B      | admin-login in CI (PR-gate); happy-path stays opt-in     | ~2 min                          | Low                                           | Middleware / auth / iron-session config |
| C      | Both in CI (PR-gate)                                     | ~10-12 min                      | Medium (Next.js dev-mode compiles, long loop) | Full operator happy-path integration    |
| D      | admin-login PR-gate + happy-path nightly/manual-dispatch | ~2 min per PR + nightly ~10 min | Low on PRs, medium nightly                    | auth on every PR; full-stack on nightly |

**Recommendation: D.** admin-login is cheap and catches common auth/middleware regressions; happy-path is expensive and flaky for a PR gate. Implementation sketch: ~20 lines in `ci.yml` for a new `e2e-admin-login` job + a new `.github/workflows/nightly-smoke.yml` for the happy-path. Full writeup in [`docs/state.md`](state.md#open-decisions-awaiting-user-input).

**Alternatives:**

- B if CI minutes are precious but we still want a PR-gate signal.
- A if the preference is minimum ongoing CI investment (we already run the specs manually anyway).
- C only if we accept ~10 min slower PR latency in exchange for full-stack PR coverage.

_Waiting on user._ No autonomous progress without a decision because implementation paths diverge significantly across A/B/C/D.

## Next

_Autonomous queue is empty. Any further work needs user input (Playwright) or operator action (W3.2d Fly deploy)._

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until a third curated source either lands or proves infeasible.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).
- [ ] Migrate the 6 remaining DB-gated test files (`test_pipeline.py`, `test_repositories*.py`) to `TEST_DATABASE_URL`. No recurring pain; pure hygiene. Pattern established by PR #73.

## Shipped on Main

- [x] Testseed cleanup (PR #73, `99a9629`) — migrated `test_seed.py` to `TEST_DATABASE_URL` + `_alias_test_database_url` fixture; deleted leftover `testseed` row from dev DB. Dev sources now lists only three live sources (`aap_annual_meeting`, `ada`, `gnydm`). Six other DB-gated test files still TRUNCATE the dev DB but don't seed leftovers; migration queued in "Later" as hygiene.
- [x] W3.2g ADA silent-drop aggregate `parser_failure` (PR #72, `71193eb`) — closes W2 §7 drift-observability gap: ADA parser now emits `ParserReviewRequest(kind='parser_failure', details={rows_seen, rows_yielded, drops_by_reason})` at end-of-stream whenever `_row_to_event` returns None for one or more rows. Pipeline routes to `insert_review_item` (real) or preview line (dry-run). New `ParserReviewRequest` dataclass in `parsers/base.py`; `Parser.parse()` return widened to `Iterator[ParsedEvent | ParserReviewRequest]` — gnydm/aap source unchanged (covariant). `_row_to_event`'s five None guards kept byte-for-byte identical. Surfaced a pre-existing silent-drop in `fixtures/ada/continuing-education.html` (7 rows all fail `parse_date_range`). 1 focused test; 139 passing.
- [x] W3.2f `--dry-run` implementation — `medevents-ingest run --dry-run` previews exactly what `run` would do (per-page status + per-candidate action + summary) with zero DB writes at any boundary. `dry_run=False` kwarg threaded through `run_source` / `run_all` / `_run_source_inner` / `_persist_event`; belt-and-braces `session.rollback()` in CLI for defense-in-depth. Added `get_last_content_hash_by_url(source_id, url)` so the dry-run content-hash gate stays read-only and still returns `would_skip_unchanged` on unchanged pages (spec §4 D5). 21 new tests (10 unit + 4 DB-gated + 4 CLI + 3 repo); full suite 138 passed, 0 xfails. Live-smoke on ADA + GNYDM + AAP confirmed zero writes, all preview lines emitted correctly. See `docs/runbooks/w3.2f-done-confirmation.md`.
- [x] W3.2e third curated source: AAP Annual Meeting 2026 — parser module (`parsers/aap.py`) with `_normalize_body_for_hashing` addressing Cloudflare email-obfuscation rotation + homepage base64 data-dbsrc noise; 8 new tests (6 unit + 2 DB-gated); `config/sources.yaml` entry; live smoke on `am2026.perio.org` confirmed 1 events row + 2 event_sources rows; re-run idempotence verified. See `docs/runbooks/w3.2e-done-confirmation.md`.
- [x] W3.2e prep — AAP fixtures + robots + byte-stability review (identified the cfemail rotation problem before implementation). See `docs/runbooks/aap-fixtures.md`.
- [x] test-harness mypy cleanup — 27 pre-existing mypy errors across `test_ada_parser.py`, `test_gnydm_parser.py`, `test_gnydm_pipeline.py`, `test_drift_observability.py`, `test_pipeline.py`, `test_repositories_event_sources.py` resolved by typing `_get_parser() -> Parser`, `_seed_*(session: Session)`, `_fresh_event(...) -> UUID`, and narrowing a `BeautifulSoup.select_one()` result. `uv run mypy .` (repo-wide) now clean; CI unaffected (CI scope is `medevents_ingest` only).
- [x] W3.2c `_diff_event_fields` None-as-clear fix addresses the partial-page precedence drift risk flagged in earlier TODO snapshots; item closed.
- [x] W3.2d repo artifacts — `services/ingest/Dockerfile` (multi-stage Python 3.12 + uv + non-root user, CMD = `medevents-ingest run --all`), `fly.toml` at repo root (scheduled-machine config, hourly wake, 256MB / shared CPU), `docs/runbooks/w3.2d-fly-scheduler-deploy.md` (operator deploy runbook with Fly PG + external PG strategies + rollback), `docs/runbooks/w3.2d-done-confirmation.md` (skeleton). Live deploy requires operator action; PR body + runbook explicit about the boundary.
- [x] W3.2c drift observability + None-rule + raw_title provenance — detail-page zero-yield now fires `parser_failure` (symmetric with listing, carries `page_kind` in details_json); `_diff_event_fields` treats candidate None as "no contribution" (preserves existing non-null fields); GNYDM `raw_title` is now a real source excerpt (listing = year + meeting-dates; homepage = `h1.swiper-title` text). 4 new tests. See `docs/runbooks/w3.2c-done-confirmation.md`.
- [x] W3.2b `run --all` + due-selection — CLI gains `medevents-ingest run --all`; iterates `is_active` + schedule-due sources via SQL-side CASE filter; continues on per-source failure; `--force` bypasses due check (but STILL respects `is_active=false`); `--source`/`--all` mutex validated; batch summary + per-source stdout + per-source stderr on failures. 8 new tests (4 DB-gated integration + 4 unit parametrized across all 4 `crawl_frequency` boundaries). See `docs/runbooks/w3.2b-done-confirmation.md`.
- [x] W3.2a source-run bookkeeping + `--force` plumbing — pipeline now writes `last_crawled_at` / `last_success_at` on success and `last_crawled_at` / `last_error_at` / `last_error_message` on error (via a fresh session so writes survive rollback). Admin UI sources pages display real timestamps for the first time. See `docs/runbooks/w3.2a-done-confirmation.md`.
- [x] W3.1 GNYDM second-source onboarding shipped end-to-end — 5 phases, 5 PRs (#50, #51, #52, #53, #54). Two sources now live; intra-source dedupe + detail-over-listing precedence proven on real data. See `docs/runbooks/w3.1-done-confirmation.md`.
- [x] W3.1 plan + sub-spec merged (PR #48 + PR #46).
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
