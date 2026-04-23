# Local dev runbook

## First-time setup

1. Install toolchains (Node 22 via nvm, pnpm 9, Python 3.12, uv, Docker). On macOS 12 Intel, skip Docker and follow [`local-postgres-macos12.md`](local-postgres-macos12.md) for Postgres.
2. `make install` — installs JS + Python deps.
3. `make up` — starts Postgres in Docker. (macOS 12 Intel: `brew services start postgresql@16`.)
4. `make migrate` — applies all Alembic migrations.
5. Copy `.env.example` → `.env` and fill in:
   - `ADMIN_PASSWORD_HASH` — generate with `pnpm --filter @medevents/web exec node scripts/hash-password.mjs`.
   - `IRON_SESSION_PASSWORD` — `openssl rand -hex 32`.
   - `CSRF_SECRET` — `openssl rand -hex 32`.
6. `make ingest CMD="seed-sources --path ../../config/sources.yaml"` — upsert seed sources. The `make ingest` target `cd`s into `services/ingest` first, so paths are resolved relative to that directory.
7. `make dev` — Next.js at http://localhost:3000. Visit `/admin` to reach the operator login.

## Reset the DB

```bash
make fresh
```

This drops the `public` schema and re-runs all migrations. Seeds must be re-applied (step 6 above). On macOS 12 Intel, see the `make fresh` equivalent in [`local-postgres-macos12.md`](local-postgres-macos12.md).

## Add a new migration

1. `cd services/ingest`
2. `uv run alembic -c ../../db/migrations/alembic.ini revision -m "<description>"`
3. Edit the generated `db/migrations/versions/<rev>.py` — write `op.execute("<SQL>")` lines.
4. `make migrate` locally, then `cd apps/web && pnpm db:pull` to regenerate TS types.
5. Commit both the migration and the regenerated `packages/shared/db/schema.ts`.

## Regenerate TS schema after migration

```bash
cd apps/web && pnpm db:pull
cd -
git add packages/shared/db/schema.ts
git commit -m "chore(db): regenerate drizzle schema types"
```

CI's `schema-drift` job re-runs `pnpm db:pull` against a fresh migration apply and fails if the committed schema disagrees.

## Re-hash admin password

```bash
cd apps/web && node scripts/hash-password.mjs
# Paste the emitted ADMIN_PASSWORD_HASH line into .env
```

## Run the operator smoke locally

```bash
cd apps/web && RUN_FULL_SMOKE=1 pnpm test:e2e
```

The Playwright happy-path spec lives at [`apps/web/tests/e2e/happy-path-smoke.spec.ts`](../../apps/web/tests/e2e/happy-path-smoke.spec.ts). It is opt-in and not part of CI.

## Preview a run without writing (`--dry-run`)

After editing `config/sources.yaml`, writing a new parser, or mid-debugging a
production issue, preview what `run` would do without mutating any DB row:

```bash
make ingest CMD="run --source ada --dry-run"
make ingest CMD="run --all --force --dry-run"
```

Output includes one line per discovered page
(`status=would_fetch_and_parse | would_skip_unchanged | would_file_review_item_source_blocked | would_file_review_item_parser_failure`)
and one line per candidate event (`action=would_create | would_update`). The
summary line is prefixed with `dry_run=1 ` to distinguish it from real-run
output. Zero writes hit the DB — safe to run against production.

See [`w3.2f-done-confirmation.md`](w3.2f-done-confirmation.md) for the write-path
bypass inventory and live-smoke examples.
