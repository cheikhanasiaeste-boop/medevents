# MedEvents

Automated directory for medical and dental fairs, seminars, congresses, workshops, and trainings.

See [`docs/mission.md`](docs/mission.md), [`docs/guidelines.md`](docs/guidelines.md), and the active MVP spec at [`docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md`](docs/superpowers/specs/2026-04-20-medevents-automated-directory-mvp.md).

Current state, verified checkpoints, and what's shipped vs. pending live in [`docs/state.md`](docs/state.md).

## Local dev

Prerequisites: Node 22, pnpm 9, Python 3.12, uv 0.5+, Docker (or a local Postgres 16 — see the macOS 12 Intel runbook below).

```bash
make install        # pnpm + uv sync
make up             # start Postgres via docker-compose
make migrate        # apply all Alembic migrations
cp .env.example .env
# Fill ADMIN_PASSWORD_HASH (pnpm --filter @medevents/web exec node scripts/hash-password.mjs)
# Fill IRON_SESSION_PASSWORD and CSRF_SECRET (openssl rand -hex 32)
make ingest CMD="seed-sources --path ../../config/sources.yaml"
make dev            # Next.js at http://localhost:3000
```

The `make ingest` target `cd`s into `services/ingest` before running the CLI, so paths passed via `CMD=` are resolved relative to `services/ingest` — hence `../../config/sources.yaml`.

On **macOS 12 Intel** Docker is not viable (qemu build loop); follow [`docs/runbooks/local-postgres-macos12.md`](docs/runbooks/local-postgres-macos12.md) to use Homebrew Postgres 16 instead. Same `DATABASE_URL`, same schema, no app-side changes.

More detail, troubleshooting, and the migration/seed workflow: [`docs/runbooks/local-dev.md`](docs/runbooks/local-dev.md).

## Layout

- `apps/web` — Next.js 15 (public site + admin operator surface)
- `services/ingest` — Python ingest CLI + parsers
- `packages/shared/db` — Drizzle-introspected TS types from Postgres
- `db/migrations` — Alembic (forward-only)
- `config/sources.yaml`, `config/specialties.yaml` — seed files

## Testing

```bash
make test       # pnpm test + uv pytest
make lint       # pnpm lint + ruff
make typecheck  # tsc + mypy
```

Opt-in Playwright happy-path smoke (not part of CI):

```bash
cd apps/web && RUN_FULL_SMOKE=1 pnpm test:e2e
```

## License

Private (not yet licensed).
