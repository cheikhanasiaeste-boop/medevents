# MedEvents — Current State

_Last updated: 2026-04-21 at Phase 10 closeout; W0+W1 foundation wave is complete on `main`._

## Status

**W0+W1 foundation wave is complete.** Phases 0-10 are shipped on `main`; W2 (first-source ingestion with ADA) is the next active wave.

Current mainline checkpoints:

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

Primary MVP spec:

- [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md)

Active foundation plan:

- [`docs/superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md`](superpowers/plans/2026-04-20-medevents-w0-w1-foundation.md)

Active wave sub-spec:

- [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) — schema, parser interface, operator bones, search approach, audit log

Prepared next-wave docs present locally:

- [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md)
- [`docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md`](superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md)

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
- `docs/phase8-sync-pending` exists locally at `66c6ff3`. It contains an older docs-sync attempt and is stale after Phase 9. Treat it as reference only; roll anything useful into the final docs sync instead of reviving it as-is.
- The working tree contains two user-owned, untracked W2 docs:
  - `docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`
  - `docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md`
    Leave them untouched unless explicitly asked to commit them.

## Next focus

| Step                                        | State                                               |
| ------------------------------------------- | --------------------------------------------------- |
| Automated directory MVP spec                | ✅ Active                                           |
| Target-state platform spec                  | ✅ Reference only                                   |
| W0+W1 foundation                            | ✅ Complete (Phases 0-10 shipped, `main` protected) |
| W0+W1 implementation plan                   | ✅ Executed                                         |
| Manual operator smoke                       | ✅ Completed                                        |
| W2 — one-source end-to-end automation (ADA) | ⏳ Next                                             |
| Intelligence-platform planning              | ❌ Deferred until justified                         |

## How to use this document

- **Resuming work?** Read this file first, then the active W2 spec/plan listed above.
- **Continuing execution?** W0+W1 is closed; pick up W2 ADA ingestion from [`docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md`](superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md).
- **Planning future work?** Follow the automated directory MVP spec unless a new decision explicitly changes direction.
- **Using the target-state spec?** Treat it as a later-phase reference, not an instruction to build all layers now.
