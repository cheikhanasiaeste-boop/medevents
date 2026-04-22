# MedEvents — Current State

_Last updated: 2026-04-22 — W2 closed, W3.1 prep + sub-spec shipped, W3.1 implementation plan open in PR #48 with review changes requested._

## Status

**W0+W1 foundation + W2 ADA ingestion are complete.** **W3.1 (GNYDM second-source onboarding) is at the plan-revision gate:** the sub-spec merged to `main` as `ed86dc9` (PR #46); the implementation plan is drafted on branch `docs/w3-1-plan` (commit `327b2e6`, PR #48) with an explicit "Request changes" review — four findings (two high, two medium). Fixes were designed and discussed in the review thread but NOT yet pushed; session was paused for an IDE restart before revisions could land. The next step is to apply those fixes on `docs/w3-1-plan` and push to PR #48 for re-review.

Current mainline checkpoints:

- `ed86dc9` — W3.1 sub-spec merged (PR #46)
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

## Open PRs awaiting review

- **PR #48** — [docs(w3.1): implementation plan — 5 phases, 16 tasks](https://github.com/cheikhanasiaeste-boop/medevents/pull/48). Branch `docs/w3-1-plan`. Content at `docs/superpowers/plans/2026-04-21-medevents-w3-1-implementation.md`. User reviewed and requested changes — four findings tracked in `docs/TODO.md` under "Now". Re-review once fixes land on the same branch.

Primary MVP spec:

- [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md)

Active foundation plan:

- [`docs/superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md`](superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md)

Active wave sub-spec:

- W3.1 (merged): [`docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md`](superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md)

Active wave implementation plan:

- W3.1 (in review, revisions pending): [`docs/superpowers/plans/2026-04-21-medevents-w3-1-implementation.md`](superpowers/plans/2026-04-21-medevents-w3-1-implementation.md) on branch `docs/w3-1-plan` (PR #48). Review raised four findings; fix designs are captured in `MEMORY.md` under the W3.1 in-progress entry.

Historical wave sub-specs:

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
- W3.1 resume sequence: (1) read the `project_w3_1_in_progress.md` memory entry for the four PR #48 review findings and the proposed fixes; (2) apply the fixes on branch `docs/w3-1-plan` (separate test DB + content-derived year + seed-sources path + replace `--dry-run` smoke); (3) push to PR #48 and comment a change summary for re-review; (4) once the user re-approves and merges, dispatch execution subagent-driven, one worker per task, per the standing `feedback_plan_execution_mode.md` preference.
- Local DB currently holds the 6 ADA events from the W2 live smoke. That state is safe to keep; W3.1 will add GNYDM events alongside, not replace ADA. **Pipeline integration tests require a dedicated `medevents_test` database — do NOT run Phase 3 against the dev DB** (the TRUNCATE fixture would wipe the ADA smoke data). This is one of the four findings PR #48 is being revised to address.
- `docs/phase8-sync-pending` exists locally at `66c6ff3` from an older W0+W1 docs-sync attempt. Stale; reference only.

## Next focus

| Step                                                | State                                                                              |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Automated directory MVP spec                        | ✅ Active                                                                          |
| Target-state platform spec                          | ✅ Reference only                                                                  |
| W0+W1 foundation                                    | ✅ Complete (Phases 0-10 shipped, `main` protected)                                |
| W0+W1 implementation plan                           | ✅ Executed                                                                        |
| Manual operator smoke                               | ✅ Completed                                                                       |
| W2 — one-source end-to-end automation (ADA)         | ✅ Complete (live ADA ingestion on main; 6 events on first run; dedupe verified)   |
| W3.1 — second-source onboarding (GNYDM)             | 🟡 In review — spec merged (`ed86dc9`), plan open in PR #48 with changes requested |
| W3.2+ — generic fallback + scheduler + third source | ⏳ After W3.1 lands                                                                |
| Intelligence-platform planning                      | ❌ Deferred until justified                                                        |

## How to use this document

- **Resuming work?** Read this file first, then `docs/TODO.md`, then the W3.1 plan revisions outlined in the `project_w3_1_in_progress.md` memory entry.
- **Continuing execution?** W0+W1 and W2 are closed. W3.1 spec is merged. Next concrete action is applying the four fix designs on branch `docs/w3-1-plan` and pushing to PR #48 for re-review. Execution mode after PR #48 merges is subagent-driven (one worker per task) per standing preference.
- **Planning future work?** Follow the automated directory MVP spec unless a new decision explicitly changes direction.
- **Using the target-state spec?** Treat it as a later-phase reference, not an instruction to build all layers now.
