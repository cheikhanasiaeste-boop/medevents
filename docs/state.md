# MedEvents — Current State

_Last updated: 2026-04-23 — W3.2c shipped; parser/pipeline boundary hardened (detail-drift signal, None-no-clobber rule, raw_title provenance). Third source onboarding (W3.2d) is next._

## Status

**W0+W1 foundation + W2 ADA ingestion + W3.1 GNYDM + W3.2a bookkeeping + W3.2b scheduler-primitive CLI + W3.2c drift observability + provenance are complete.** Ingest now exposes a single entry-point — `medevents-ingest run --all` — that iterates every active, schedule-due source, continues on per-source failure, and returns a parseable batch summary. A Fly.io scheduled machine can call this hourly (W3.2e) and rely on the CLI to handle due-selection internally; no wake-time logic on the Fly side. Admin UI shows real timestamps from W3.2a. See [`docs/runbooks/w3.2b-done-confirmation.md`](runbooks/w3.2b-done-confirmation.md) and predecessors for evidence maps.

Current mainline checkpoints:

- W3.2c squash commit — pending (this PR's merge commit, will appear as the most recent `feat(w3.2c):` entry)
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
- An opt-in Playwright happy-path smoke spec exists at `apps/web/tests/e2e/happy-path-smoke.spec.ts`; not part of CI
- Live ADA smoke completed on 2026-04-21: first run created 6 events (Scientific Session + 5 CE rows); subsequent runs report skipped_unchanged=2 via the content_hash gate.
- GNYDM byte-stability verified 2026-04-21 (3× back-to-back fetches, identical sha-256 per page). Plain raw-body hashing works for this source — no Sitecore-style normalization needed.
- Live GNYDM smoke completed on 2026-04-22: first run `fetched=2 created=3 updated=1 review_items=0`; re-run `fetched=2 skipped_unchanged=2 created=0 updated=0`; the 2026 edition has exactly one events row with two event_sources rows (listing + detail) confirming intra-source dedupe + detail-over-listing precedence on real data.

## Open PRs awaiting review

_None. W3.1 Phase 5 (this state update + done-confirmation runbook) is pending squash-merge; once landed, `main` is caught up._

Primary MVP spec:

- [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md)

Active foundation plan:

- [`docs/superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md`](superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md)

Active wave sub-spec:

_None. Next wave to be chosen in `docs/TODO.md`._

Historical wave sub-specs:

- W3.1: [`docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md`](superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md) — shipped (see [`docs/runbooks/w3.1-done-confirmation.md`](runbooks/w3.1-done-confirmation.md))
- W2: [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md) — shipped
- W1: [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) — shipped

Source runbooks:

- [`docs/runbooks/ada-fixtures.md`](runbooks/ada-fixtures.md) — ADA fixtures + source-code naming convention
- [`docs/runbooks/gnydm-fixtures.md`](runbooks/gnydm-fixtures.md) — GNYDM fixtures + robots + byte-stability protocol

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
- W3.1 + W3.2a + W3.2b + W3.2c are complete. W3.2 continues as sequenced sub-waves (third source → Fly scheduler) per [`docs/TODO.md`](TODO.md) "Now" section. Next wave is W3.2d.
- Local dev DB now holds: 6 ADA events (W2 smoke) + 3 GNYDM editions (W3.1 smoke); the 2026 GNYDM edition has 2 event_sources rows. That state is safe to keep.
- A disposable `medevents_test` Postgres database exists alongside the dev DB with the same migrations applied. It is used exclusively by `tests/test_gnydm_pipeline.py` (gated on `TEST_DATABASE_URL`); every test TRUNCATEs all ingest tables before running. Do NOT point `DATABASE_URL` at `medevents_test` or vice versa.
- `docs/phase8-sync-pending` exists locally at `66c6ff3` from an older W0+W1 docs-sync attempt. Stale; reference only.

## Next focus

| Step                                                                          | State                                                                                                                                                                                                       |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated directory MVP spec                                                  | ✅ Active                                                                                                                                                                                                   |
| Target-state platform spec                                                    | ✅ Reference only                                                                                                                                                                                           |
| W0+W1 foundation                                                              | ✅ Complete (Phases 0-10 shipped, `main` protected)                                                                                                                                                         |
| W0+W1 implementation plan                                                     | ✅ Executed                                                                                                                                                                                                 |
| Manual operator smoke                                                         | ✅ Completed                                                                                                                                                                                                |
| W2 — one-source end-to-end automation (ADA)                                   | ✅ Complete (live ADA ingestion on main; 6 events on first run; dedupe verified)                                                                                                                            |
| W3.1 — second-source onboarding (GNYDM)                                       | ✅ Complete (live GNYDM ingestion on main; 3 editions + dedupe + precedence verified; see w3.1-done-confirmation.md)                                                                                        |
| W3.2a — source-run bookkeeping (`last_crawled_at`, `--force` wiring)          | ✅ Complete — 4 new tests (3 DB-gated + signature smoke), pipeline writes all four `sources` bookkeeping columns on success + error; see w3.2a-done-confirmation.md                                         |
| W3.2b — `run --all` + due-selection (W1 spec §304 entry-point)                | ✅ Complete — 8 new tests (4 DB-gated + 4 is_due unit cases with parametrize expanding to 11); SQL-side due filter via CASE expression; continues-on-failure proven live; see w3.2b-done-confirmation.md    |
| W3.2c — detail-page drift observability + `_diff_event_fields` `None`-rule    | ✅ Complete — detail-zero emits `parser_failure` with `page_kind` in details_json; candidate None no longer clobbers; GNYDM `raw_title` is true source excerpt; 4 new tests; see w3.2c-done-confirmation.md |
| W3.2d — third curated source (`aap_annual_meeting`)                           | 🟡 Next — proves the two-source pattern generalizes to a third source; generic fallback stays deferred until three curated sources ship                                                                     |
| W3.2e — external scheduler (Fly.io scheduled machines per w1-foundation §324) | ⏳ After 3.2a/b — architecture already locked to Fly, NOT GitHub Actions or host cron                                                                                                                       |
| Intelligence-platform planning                                                | ❌ Deferred until justified                                                                                                                                                                                 |

## How to use this document

- **Resuming work?** Read this file first, then `docs/TODO.md`, then `docs/runbooks/w3.1-done-confirmation.md` for the latest shipped wave.
- **Continuing execution?** W0+W1, W2, W3.1, W3.2a, W3.2b, and W3.2c are closed. Next concrete action is authoring the W3.2d sub-spec (third source onboarding — `aap_annual_meeting`). External scheduler wiring (W3.2e, Fly.io scheduled machines) comes after W3.2d.
- **Planning future work?** Follow the automated directory MVP spec unless a new decision explicitly changes direction.
- **Using the target-state spec?** Treat it as a later-phase reference, not an instruction to build all layers now.
