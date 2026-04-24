# MedEvents — Current State

_Last updated: 2026-04-24 — W3.2k (`dentex_algeria`) shipped end-to-end; Playwright option D is wired in repo workflows; DB-gated ingest suites use `TEST_DATABASE_URL`. Main ingests seven curated sources with operator-safe preview mode. W3.2d live deploy remains the only required operator-gated blocker, and the concrete stop is still Fly billing setup._

## Status

**W0+W1 foundation + W2 ADA + W3.1 GNYDM + W3.2a bookkeeping + W3.2b scheduler-primitive CLI + W3.2c drift observability + provenance + W3.2e third source (AAP Annual Meeting) + W3.2f preview mode + W3.2g ADA silent-drop aggregate review items + W3.2h fourth source (`fdi_wdc`) + W3.2i fifth source (`eao_congress`) + W3.2j sixth source (`cds_midwinter`) + W3.2k seventh source (`dentex_algeria`) are all complete.** Ingest exposes `medevents-ingest run --all [--force] [--dry-run]` with belt-and-braces read-only safety; operator can preview any real run against production with zero DB writes. The ADA parser now emits a drift signal (`ParserReviewRequest` → `parser_failure` review_item) if any schedule row silently drops — closing the W2 spec §7 observability gap. Admin UI shows real timestamps from W3.2a. See [`docs/runbooks/w3.2k-done-confirmation.md`](runbooks/w3.2k-done-confirmation.md) and predecessors for evidence maps.

Current mainline checkpoints:

- `99a9629` — chore: migrate test_seed.py to TEST_DATABASE_URL + clean up testseed leftover (PR #73)
- `71193eb` — W3.2g: ADA parser emits aggregate `parser_failure` on silent row drops (PR #72)
- `b7578b0` — W3.2f: `--dry-run` preview mode with zero DB writes (PR #71)
- `1ba1e0f` — W3.2e: AAP Annual Meeting parser + config + tests + runbook (PR #69)
- `8a3b639` — W3.2e sub-spec (PR #68)
- `b51042b` — W3.2e prep: AAP fixtures + robots + byte-stability review (PR #67)
- `0dc007a` — test-harness mypy cleanup — 27 pre-existing errors → 0 (PR #66)
- `94c4b05` — W3.2d: Fly scheduled machine artifacts (repo-side only) (PR #65)
- `fe20cf4` — W3.2d↔W3.2e sequence swap (PR #64)
- `c05929a` — W3.2c: drift observability + None-rule + raw_title (PR #63)
- `956813d` — W3.2c sub-spec (PR #62)
- `67ae86f` — W3.2b: run --all + due-selection (PR #61)
- `77b1367` — W3.2a: source-run bookkeeping + --force plumbing (PR #58)
- `c63920b` — W3.1 Phase 4: wire gnydm into config/sources.yaml (PR #53)
- `c4c1c60` — W3.1 Phase 3: pipeline integration tests — dedupe + precedence + idempotence (PR #52)
- `e2491f2` — W3.1 Phase 2: GnydmListingParser — listing + detail + canary (PR #51)
- `45788cc` — W3.1 Phase 1: normalize weekday-prefix widening (PR #50)
- `9192163` — W3.1 implementation plan — 5 phases, 16 tasks (PR #48)
- `ed86dc9` — W3.1 sub-spec for second-source onboarding (GNYDM) (PR #46)
- `a4cedb4` — W3.1 prep: GNYDM canary fixtures + robots/byte-stability review (PR #45)
- `061a7de` — chore: bump ruff pre-commit hook to match CI
- `7a6cce5` — fix: ADA content_hash ignores rotating Sitecore tracking attrs (discovered in live smoke)
- `503d68a` — W2 Phase 7: CLI wiring + seed_urls array
- `0d29d20` — W2 Phase 6: pipeline.run_source orchestration
- `280d59a` — W2 Phase 5: AdaListingParser
- `4e70e1b` — W2 Phase 4: fetch.fetch_url with content_hash
- `5588179` — W2 Phase 3: 4 repositories
- `aab5bd2` — W2 Phase 2: normalize helpers
- `d6550ec` — W2 Phase 1: bs4/lxml deps + Parser.parse() widened
- `8ea639f` — W2 docs (spec + prep plan) tracked
- `83870d6` — W2 prep artifacts (fixtures, naming, seed URL fix)
- `docs/state-after-w1` — W0+W1 close: branch protection on `main`, final docs sync (this PR)
- `781dc44` — Phase 10 Task 40: W1 done-confirmation doc against the spec's 15 criteria
- `3952968` — Phase 10 Task 39: top-level README + local-dev runbook
- `1a53a20` — smoke follow-up: three runtime bugs fixed after manual operator happy-path testing
- `1d060d4` — Phase 9 Batch 2: review queue, events list/detail/edit, full operator surface
- `5a7cd08` — CSRF hardening on admin mutation routes
- `398b20a` — Phase 9 Batch 1: login flow, dashboard, sources pages/actions
- `ed0f7e4` — Phase 8 hardening: env validation, `@node-rs/argon2`, secure-cookie override, auth cleanup

Verification state:

- GitHub Actions green on `main`: `TypeScript (lint + typecheck + unit tests)`, `Python (ruff + mypy + pytest)`, `Drizzle schema drift check`
- Those three checks are now required on `main` (branch protection, `strict=true`, `enforce_admins=false`, 0 required reviewers — matches the solo-dev flow)
- W1 done-criteria confirmed against spec §10: [`docs/runbooks/w1-done-confirmation.md`](runbooks/w1-done-confirmation.md)
- Manual browser smoke of the operator happy path completed successfully against the local Homebrew Postgres setup; the three bugs it surfaced are fixed in PR `#28`
- Playwright option D is wired: `apps/web/tests/e2e/admin-login.spec.ts` now runs in `CI` on every `pull_request`/`push`, while `apps/web/tests/e2e/happy-path-smoke.spec.ts` runs via `.github/workflows/nightly-smoke.yml` on nightly schedule plus manual dispatch using deterministic ADA/review/event fixtures from `apps/web/scripts/seed-happy-path-smoke.mjs`.
- Live ADA smoke completed on 2026-04-21: first run created 6 events (Scientific Session + 5 CE rows); subsequent runs report skipped_unchanged=2 via the content_hash gate.
- GNYDM byte-stability verified 2026-04-21 (3× back-to-back fetches, identical sha-256 per page). Plain raw-body hashing works for this source — no Sitecore-style normalization needed.
- Live GNYDM smoke completed on 2026-04-22: first run `fetched=2 created=3 updated=1 review_items=0`; re-run `fetched=2 skipped_unchanged=2 created=0 updated=0`; the 2026 edition has exactly one events row with two event_sources rows (listing + detail) confirming intra-source dedupe + detail-over-listing precedence on real data.
- Live FDI smoke completed on 2026-04-24: first run `source=fdi_wdc fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; re-run `fetched=2 skipped_unchanged=2 created=0 updated=0`; dev DB holds one `FDI World Dental Congress 2026` row with two `event_sources` rows and populated source bookkeeping.
- Live EAO smoke completed on 2026-04-24: first run `source=eao_congress fetched=2 skipped_unchanged=0 created=3 updated=1 review_items=0`; after widening hub normalization for the LiteSpeed footer comment, the final rerun reported `fetched=2 skipped_unchanged=2 created=0 updated=0`; dev DB now holds `EAO Congress 2026`, `EAO Congress 2027`, and `EAO Congress 2028` with four `event_sources` rows total. Full ingest suite now at `155 passed`.
- Live CDS smoke completed on 2026-04-24: first run `source=cds_midwinter fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; re-run `fetched=2 skipped_unchanged=2 created=0 updated=0`; dev DB holds one `Chicago Dental Society Midwinter Meeting 2026` row with two `event_sources` rows, `venue_name = McCormick Place West`, `timezone = America/Chicago`, and populated source bookkeeping. Full ingest suite now at `163 passed`.
- Live Dentex smoke completed on 2026-04-24: first run `source=dentex_algeria fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; an immediate second rerun briefly reported `created=0 updated=2`, but two consecutive final reruns reported `fetched=2 skipped_unchanged=2 created=0 updated=0`; dev DB holds one `DENTEX Algeria 2026` row with two `event_sources` rows, canonical homepage `source_url`, and populated source bookkeeping. Full ingest suite now at `171 passed`.

## Open PRs awaiting review

_None recorded here._ The remaining required project-level action is the W3.2d operator deploy.

## Open decisions awaiting user input

_None._ On 2026-04-23 we chose **option D** and wired it in-repo:

- `apps/web/tests/e2e/admin-login.spec.ts` runs in `.github/workflows/ci.yml` on every `pull_request`/`push`.
- `apps/web/tests/e2e/happy-path-smoke.spec.ts` runs in `.github/workflows/nightly-smoke.yml` on a nightly schedule plus `workflow_dispatch`.
- `apps/web/scripts/seed-happy-path-smoke.mjs` seeds the deterministic fixtures the happy-path workflow expects.

Primary MVP spec:

- [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md)

Active foundation plan:

- [`docs/superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md`](superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md)

Active wave sub-spec:

_None. W3.2k shipped; the next optional wave is to be chosen in `docs/TODO.md`._

Historical wave sub-specs:

- W3.2k: [`docs/superpowers/specs/2026-04-24-medevents-w3-2k-dentex-algeria.md`](superpowers/specs/2026-04-24-medevents-w3-2k-dentex-algeria.md) — shipped (see [`docs/runbooks/w3.2k-done-confirmation.md`](runbooks/w3.2k-done-confirmation.md))
- W3.2j: [`docs/superpowers/specs/2026-04-24-medevents-w3-2j-cds-midwinter.md`](superpowers/specs/2026-04-24-medevents-w3-2j-cds-midwinter.md) — shipped (see [`docs/runbooks/w3.2j-done-confirmation.md`](runbooks/w3.2j-done-confirmation.md))
- W3.2i: [`docs/superpowers/specs/2026-04-24-medevents-w3-2i-eao-congress.md`](superpowers/specs/2026-04-24-medevents-w3-2i-eao-congress.md) — shipped (see [`docs/runbooks/w3.2i-done-confirmation.md`](runbooks/w3.2i-done-confirmation.md))
- W3.2h: [`docs/superpowers/specs/2026-04-24-medevents-w3-2h-fdi-world-dental-congress.md`](superpowers/specs/2026-04-24-medevents-w3-2h-fdi-world-dental-congress.md) — shipped (see [`docs/runbooks/w3.2h-done-confirmation.md`](runbooks/w3.2h-done-confirmation.md))
- W3.1: [`docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md`](superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md) — shipped (see [`docs/runbooks/w3.1-done-confirmation.md`](runbooks/w3.1-done-confirmation.md))
- W2: [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md) — shipped
- W1: [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) — shipped

Source runbooks:

- [`docs/runbooks/ada-fixtures.md`](runbooks/ada-fixtures.md) — ADA fixtures + source-code naming convention
- [`docs/runbooks/gnydm-fixtures.md`](runbooks/gnydm-fixtures.md) — GNYDM fixtures + robots + byte-stability protocol
- [`docs/runbooks/fdi-fixtures.md`](runbooks/fdi-fixtures.md) — FDI fixtures + robots + byte-stability protocol
- [`docs/runbooks/eao-fixtures.md`](runbooks/eao-fixtures.md) — EAO hub/detail fixtures + hash-normalization root cause
- [`docs/runbooks/cds-fixtures.md`](runbooks/cds-fixtures.md) — CDS event-page/JSON fixtures + byte-stability protocol
- [`docs/runbooks/dentex-fixtures.md`](runbooks/dentex-fixtures.md) — Dentex homepage/visit fixtures + visitor CTA contract

Project TODO:

- [`docs/TODO.md`](TODO.md)

Reference-only target-state spec:

- [`docs/superpowers/specs/2026-04-20-medevents-platform-design.md`](superpowers/specs/2026-04-20-medevents-platform-design.md)

## What Is Shipped

- Monorepo baseline: pnpm workspace, uv/Python workspace, CI, pre-commit, Alembic scaffold
- Postgres schema: all `8` migrations plus MVP indexes
- TS schema introspection: `drizzle-kit pull` committed to `packages/shared/db/schema.ts`
- Seed/config layer: `config/sources.yaml`, `config/specialties.yaml`, `seed-sources` CLI
- Ingest skeleton: repositories, parser `Protocol` + registry, `run --source` CLI shape
- Web infra: DB client, password hashing helper, sessions, middleware, CSRF helpers, audit writer
- Operator app: login, dashboard, sources list/detail/actions, review queue/detail/resolve, events list/detail/save/unpublish
- Mutation safety pattern: every admin POST route now has `isAuthenticated()` and CSRF verification; all mutating routes except logout write `audit_log`
- Manual operator smoke has been run end-to-end on localhost, and the smoke-driven fixes are already merged on `main`

## Locked decisions

### Product direction

- Start as an **automated directory MVP**, not a full intelligence platform.
- The system should gather and update events from multiple known sources automatically.
- Human work should be **exception-driven**, not part of the routine publish flow.
- Premium UX still matters, but architecture must stay proportionate to the MVP.

### Architecture stance

- **Monorepo** stays.
- **One Next.js app** owns the public site and MVP operator/review surface.
- **Python ingestion worker(s)** handle scheduled crawling and parsing for known sources.
- **Postgres** is the source of truth and primary search/filter backend for MVP.
- No separate read API, separate admin app, Meilisearch, Redis queue, or deep provenance model in the first build unless immediate pain proves they are necessary.

### Automation stance

- Start with curated known sources, not open-ended source discovery.
- Use source-specific parsers first, generic fallback second.
- Basic dedupe is enough for MVP: title + date + location + source URL heuristics.
- Track event lifecycle status early: active, postponed, cancelled, completed.
- Source transparency is required on every event detail page.
- W2 starts with `ada` only; generic fallback parsing stays deferred to W3.
- LinkedIn and Facebook discovery guidance is global by default; the Maghreb/North Africa pack is just one regional expansion lane.

### Long-term path

- The large platform design spec remains useful as a **future evolution path**.
- Introduce heavier platform layers only when the automated directory MVP shows concrete need:
  - search scale pain
  - parser maintenance pain
  - dedupe ambiguity volume
  - operator workflow pain
  - API/partner needs

## Restart Notes

- This machine is using local Homebrew Postgres 16 for development because `qemu`/Colima failed on macOS 12 Intel. Do not assume Docker is the working local DB path. See [`docs/runbooks/local-postgres-macos12.md`](runbooks/local-postgres-macos12.md).
- W3.1 through W3.2c shipped on 2026-04-22/23; W3.2e (third source AAP), W3.2f (`--dry-run`), W3.2g (ADA silent-drop review items), DB-test hygiene, Playwright option D, W3.2h (`fdi_wdc`), W3.2i (`eao_congress`), W3.2j (`cds_midwinter`), and W3.2k (`dentex_algeria`) all shipped by 2026-04-24. W3.2d (Fly scheduled machines) has repo artifacts on `main`, and live deploy attempts on 2026-04-23 and 2026-04-24 confirmed the remaining blocker is Fly billing/payment setup: `fly auth login` works, but `fly apps create medevents-ingest` stops at Fly's payment gate. Seven curated sources now run locally via `run --all` with operator-safe `--dry-run` preview. There is no remaining user-gated queue item.
- Local dev DB now holds: 6 ADA events (W2 smoke) + 3 GNYDM editions (W3.1 smoke) + 1 FDI row + 3 EAO congress rows + 1 CDS Midwinter row + 1 Dentex Algeria row. The 2026 GNYDM, FDI 2026, EAO 2026, CDS Midwinter 2026, and Dentex Algeria 2026 rows each have 2 `event_sources` rows. That state is safe to keep.
- A disposable `medevents_test` Postgres database exists alongside the dev DB with the same migrations applied. It is used exclusively by the DB-gated ingest suites (all gated on `TEST_DATABASE_URL`); those tests TRUNCATE all ingest tables before running. Do NOT point `DATABASE_URL` at `medevents_test` or vice versa.
- `docs/phase8-sync-pending` exists locally at `66c6ff3` from an older W0+W1 docs-sync attempt. Stale; reference only.

## Next focus

| Step                                                                                             | State                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated directory MVP spec                                                                     | ✅ Active                                                                                                                                                                                                                                                                                                                                                                          |
| Target-state platform spec                                                                       | ✅ Reference only                                                                                                                                                                                                                                                                                                                                                                  |
| W0+W1 foundation                                                                                 | ✅ Complete (Phases 0-10 shipped, `main` protected)                                                                                                                                                                                                                                                                                                                                |
| W0+W1 implementation plan                                                                        | ✅ Executed                                                                                                                                                                                                                                                                                                                                                                        |
| Manual operator smoke                                                                            | ✅ Completed                                                                                                                                                                                                                                                                                                                                                                       |
| W2 — one-source end-to-end automation (ADA)                                                      | ✅ Complete (live ADA ingestion on main; 6 events on first run; dedupe verified)                                                                                                                                                                                                                                                                                                   |
| W3.1 — second-source onboarding (GNYDM)                                                          | ✅ Complete (live GNYDM ingestion on main; 3 editions + dedupe + precedence verified; see w3.1-done-confirmation.md)                                                                                                                                                                                                                                                               |
| W3.2a — source-run bookkeeping (`last_crawled_at`, `--force` wiring)                             | ✅ Complete — 4 new tests (3 DB-gated + signature smoke), pipeline writes all four `sources` bookkeeping columns on success + error; see w3.2a-done-confirmation.md                                                                                                                                                                                                                |
| W3.2b — `run --all` + due-selection (W1 spec §304 entry-point)                                   | ✅ Complete — 8 new tests (4 DB-gated + 4 is_due unit cases with parametrize expanding to 11); SQL-side due filter via CASE expression; continues-on-failure proven live; see w3.2b-done-confirmation.md                                                                                                                                                                           |
| W3.2c — detail-page drift observability + `_diff_event_fields` `None`-rule                       | ✅ Complete — detail-zero emits `parser_failure` with `page_kind` in details_json; candidate None no longer clobbers; GNYDM `raw_title` is true source excerpt; 4 new tests; see w3.2c-done-confirmation.md                                                                                                                                                                        |
| W3.2d — external scheduler (Fly.io scheduled machines per w1-foundation §324)                    | 🟡 Partial — repo artifacts shipped (Dockerfile + fly.toml + deploy runbook + done-confirmation skeleton). `flyctl` auth is verified locally; `fly apps create medevents-ingest` is blocked until Fly billing/payment info is enabled. Marks ✅ after the first autonomous run is captured.                                                                                        |
| W3.2e — third curated source (`aap_annual_meeting`)                                              | ✅ Complete — parser + 8 tests (6 unit + 2 DB-gated), config seeded, live smoke verified on real site (1 events row + 2 event_sources for the 2026 edition; re-run = skipped_unchanged=2 via cfemail normalization). See w3.2e-done-confirmation.md.                                                                                                                               |
| W3.2f — `--dry-run` preview mode (zero DB writes)                                                | ✅ Complete — flag threaded through `run_source` / `run_all` / `_run_source_inner` / `_persist_event` with belt-and-braces CLI `session.rollback()`; added `get_last_content_hash_by_url` for read-only hash gate. 21 new tests (10 unit + 4 DB-gated + 4 CLI + 3 repo); 138 passed repo-wide. See w3.2f-done-confirmation.md.                                                     |
| W3.2g — ADA silent-drop aggregate review_items (W2 §7 drift observability)                       | ✅ Complete — new `ParserReviewRequest` dataclass; ADA emits one `parser_failure` with per-reason drop counts on silent drops; surfaced a pre-existing `continuing-education.html` 7-row date_parse_fail drop. 1 focused test; 139 passed repo-wide. PR #72.                                                                                                                       |
| W3.2h — fourth curated source (`fdi_wdc`)                                                        | ✅ Complete — parser + 8 tests (6 unit + 2 DB-gated), config seeded, live smoke verified on the official FDI site (1 events row + 2 event_sources for the 2026 edition; re-run = skipped_unchanged=2 with raw-body hashing). Full ingest suite at 147 passed. See w3.2h-done-confirmation.md.                                                                                      |
| W3.2i — fifth curated source (`eao_congress`)                                                    | ✅ Complete — parser + 8 tests (6 unit + 2 DB-gated), config seeded, live smoke verified on the official EAO hub + Lisbon 2026 microsite (3 event rows total; 2026 has 2 event_sources rows; final unchanged re-run = skipped_unchanged=2 after hub hash normalization for Simple Banner + LiteSpeed timestamps). Full ingest suite at 155 passed. See w3.2i-done-confirmation.md. |
| W3.2j — sixth curated source (`cds_midwinter`)                                                   | ✅ Complete — parser + 8 tests (6 unit + 2 DB-gated), config seeded, live smoke verified on the official CDS event page + public JSON endpoint (1 event row total; canonical row keeps the public event page as `source_url`; final unchanged re-run = skipped_unchanged=2 with raw-body hashing). Full ingest suite at 163 passed. See w3.2j-done-confirmation.md.                |
| W3.2k — seventh curated source (`dentex_algeria`)                                                | ✅ Complete — parser + 8 tests (6 unit + 2 DB-gated), config seeded, live smoke verified on the official Dentex homepage + visit page (1 event row total; canonical row keeps the homepage as `source_url`; final unchanged reruns = skipped_unchanged=2 with raw-body hashing). Full ingest suite at 171 passed. See w3.2k-done-confirmation.md.                                  |
| DB-gated ingest test hygiene (`test_seed.py` + pipeline/repository suites → `TEST_DATABASE_URL`) | ✅ Complete — all DB-gated ingest suites now alias `TEST_DATABASE_URL` back into `DATABASE_URL` with cache reset, so TRUNCATE-heavy tests stay on the disposable `medevents_test` database instead of the dev DB. Verified locally with `DATABASE_URL=.../medevents TEST_DATABASE_URL=.../medevents_test uv run pytest -q` → 139 passed.                                           |
| Playwright CI wiring — option D                                                                  | ✅ Complete — `admin-login.spec.ts` runs in the main CI workflow on every PR/push; `happy-path-smoke.spec.ts` moved to nightly/manual dispatch with deterministic fixtures from `apps/web/scripts/seed-happy-path-smoke.mjs`; the smoke now targets the ADA row explicitly rather than the first `Open` link.                                                                      |
| Intelligence-platform planning                                                                   | ❌ Deferred until justified                                                                                                                                                                                                                                                                                                                                                        |

## How to use this document

- **Resuming work?** Read this file first, then `docs/TODO.md`, then `docs/runbooks/w3.2k-done-confirmation.md` for the latest shipped wave.
- **Continuing execution?** W3.2d repo artifacts are on `main`; operator must enable Fly billing and then run `docs/runbooks/w3.2d-fly-scheduler-deploy.md` to complete live deployment (not autonomously runnable). The autonomous queue through 2026-04-24 is complete again: W3.2f `--dry-run`, W3.2g ADA silent-drop, DB-test hygiene, Playwright option D, W3.2h `fdi_wdc`, W3.2i `eao_congress`, W3.2j `cds_midwinter`, and W3.2k `dentex_algeria` are all wired. With seven curated sources on `main`, the next optional lane is the generic fallback parser or another curated-source expansion.
- **Planning future work?** Follow the automated directory MVP spec unless a new decision explicitly changes direction.
- **Using the target-state spec?** Treat it as a later-phase reference, not an instruction to build all layers now.
