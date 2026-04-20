# MedEvents — Current State

_Last updated: 2026-04-20_

## Status

Greenfield. No code written yet.

Direction has been narrowed deliberately:

- **Build now:** automated directory MVP
- **Defer:** full intelligence-platform architecture until the MVP proves demand or real operational pain

Primary MVP spec:

- [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md)

Active wave sub-spec:

- [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) — W1 foundation (schema, parser interface, operator bones, search approach, audit log)

Reference-only target-state spec:

- [`docs/superpowers/specs/2026-04-20-medevents-platform-design.md`](superpowers/specs/2026-04-20-medevents-platform-design.md)

## Locked decisions

### Product direction

- Start as an **automated directory MVP**, not a full intelligence platform.
- The system should gather and update events from multiple known sources automatically.
- Human work should be **exception-driven**, not part of the routine publish flow.
- Premium UX still matters, but architecture must stay proportionate to the MVP.

### Architecture stance

- **Monorepo** stays.
- **One Next.js app** should own the public site and MVP operator/review surface.
- **Python ingestion worker(s)** handle scheduled crawling and parsing for known sources.
- **Postgres** is the source of truth and primary search/filter backend for MVP.
- No separate read API, separate admin app, Meilisearch, Redis queue, or deep provenance model in the first build unless immediate pain proves they are necessary.

### Automation stance

- Start with curated known sources, not open-ended source discovery.
- Use source-specific parsers first, generic fallback second.
- Basic dedupe is enough for MVP: title + date + location + source URL heuristics.
- Track event lifecycle status early: active, postponed, cancelled, completed.
- Source transparency is required on every event detail page.

### Long-term path

- The large platform design spec remains useful as a **future evolution path**.
- Introduce heavier platform layers only when the automated directory MVP shows concrete need:
  - search scale pain
  - parser maintenance pain
  - dedupe ambiguity volume
  - operator workflow pain
  - API/partner needs

## Next focus

| Step                                                                    | State                           |
| ----------------------------------------------------------------------- | ------------------------------- |
| Automated directory MVP spec                                            | ✅ Active                       |
| Target-state platform spec                                              | ✅ Reference only               |
| W1 sub-spec (schema + parser interface + operator bones + search)       | ✅ Locked                       |
| W0+W1 implementation plan                                               | ⏳ Next via writing-plans skill |
| W0 setup execution (git init local → gh repo create → scaffold commits) | ⏳ Step 1 of plan               |
| W1 implementation execution                                             | ⏳ Step 2 of plan               |
| Intelligence-platform planning                                          | ❌ Deferred until justified     |

## How to use this document

- **Resuming work?** Read this file first.
- **Planning work?** Follow the automated directory MVP spec unless a new decision explicitly changes direction.
- **Using the target-state spec?** Treat it as a later-phase reference, not an instruction to build all layers now.
