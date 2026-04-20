# W1 Done Confirmation

Date: 2026-04-20
`main` at: `3952968` (includes Phases 0-10, README + local-dev runbook)

Against [`docs/superpowers/specs/2026-04-20-medevents-w1-foundation.md`](../superpowers/specs/2026-04-20-medevents-w1-foundation.md) §10:

1. ✅ All 6 tables exist via Alembic forward migrations (`sources`, `source_pages`, `events`, `event_sources`, `review_queue`, `audit_log`; plus the auxiliary `alembic_version`). Migrations 0001–0008 apply cleanly in CI and locally.
2. ✅ Extensions enabled: `pgcrypto`, `pg_trgm`, `unaccent`, `citext`. Enforced by migrations and re-verified by CI's `python` job at the start of each run.
3. ✅ All MVP indexes created — 16 indexes introspected by `drizzle-kit pull`, matching the spec's index list.
4. ✅ `drizzle-kit pull` output committed to [`packages/shared/db/schema.ts`](../../packages/shared/db/schema.ts) and [`packages/shared/db/relations.ts`](../../packages/shared/db/relations.ts); CI `schema-drift` job green on every merge to main. (Local re-pulls can produce cosmetic column/import-ordering differences on some dev environments; CI is the authoritative gate and has remained green.)
5. ✅ [`config/sources.yaml`](../../config/sources.yaml) seeds ADA with `parser_name: ada_listing`.
6. ✅ [`config/specialties.yaml`](../../config/specialties.yaml) defines the dental specialty codes.
7. ✅ `medevents-ingest seed-sources --path <yaml>` upserts `sources` (exercised in CI via `test_seed.py` and manually during the operator smoke).
8. ✅ `Parser` Protocol, `@register_parser` decorator, and `parser_for(source)` resolver are in place in [`services/ingest/medevents_ingest/parsers/`](../../services/ingest/medevents_ingest/parsers/); registry starts empty in W1.
9. ✅ `medevents-ingest run --source ada` resolves the source and exits with the expected W1 behavior (no registered parser → exit code 3, details captured in `audit_log.details_json.stderrTail` when invoked from the operator UI). Parser body is intentionally W2.
10. ✅ Operator routes scaffolded: login, dashboard, sources list/detail, review list/detail, events list/detail/edit. Pages render against the real DB.
11. ✅ Login flow end-to-end: Argon2id password check → iron-session cookie → middleware-protected `/admin/*`. Password hashing via `@node-rs/argon2`.
12. ✅ "Run now" button on `/admin/sources/[id]` invokes the CLI via a subprocess call; `audit_log.source.run` is written with exit code, stdout/stderr tails, and duration.
13. ✅ `/admin/events` returns paginated rows with the W1 filter SQL; `pg_trgm` fuzzy title filter verified during the manual operator smoke.
14. ✅ Every mutating admin action (source create/run, review resolve, event save/unpublish) writes an `audit_log` row; enforced by CSRF verification + `isAuthenticated()` on each POST handler.
15. ✅ CI gates green on `main`:
    - `ts` (ESLint + `tsc` + Vitest): pass
    - `python` (ruff + mypy + Alembic forward-migrate + pytest): pass
    - `schema-drift` (pnpm db:pull vs. committed schema): pass

## Local verification performed for this confirmation

Against `main` at `3952968`:

| Gate                      | Command                                                                                                                                                | Result                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| TypeScript lint           | `make lint` → `pnpm lint` + `uv run ruff check .`                                                                                                      | ✅ no warnings / all checks passed                                            |
| Type check                | `make typecheck` → `tsc --noEmit` + `uv run mypy medevents_ingest`                                                                                     | ✅ success, no issues                                                         |
| Tests                     | `make test` → Vitest (22 passed, 1 skipped) + pytest (6 passed, 8 skipped — skipped tests require live DB session not configured in this one-shot run) | ✅                                                                            |
| Operator happy-path smoke | Manual browser walk-through of login → dashboard → sources → run-now → review → events list/detail/save/unpublish                                      | ✅ completed earlier; surfaced 3 runtime bugs all fixed in PR #28 (`1a53a20`) |

## Known intentional gaps for W2+

- Parser body for ADA is W2 (registry is wired, resolver is wired, body is not).
- Generic fallback parser is W3.
- Dedupe heuristics / stale-event sweep / source-health visibility beyond `last_*` are W3+.

W1 is complete. Next: W2 — ADA parser body. See [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](../superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md) (currently untracked local draft) and [`docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md`](../superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md).
