# Local Postgres on macOS 12 Intel (Homebrew fallback)

## Why this exists

The project's standard local-dev pattern is **docker-compose** (see `docker-compose.yml`, `make up`). That requires a working Docker daemon.

On **macOS 12.7 Intel**, the common Mac Docker path (colima) needs `qemu` for virtualization because Apple's built-in `vz` framework requires macOS 13+. On this specific machine, `brew install qemu` failed repeatedly while building dependencies from source (openssl@3 build loop). Rather than burn hours fighting qemu, local dev on macOS 12 Intel uses Homebrew-installed Postgres directly.

**This is a machine-specific workaround, not a product-direction change.** CI still uses a Postgres service container (unchanged). Prod still uses Neon (unchanged). Other dev machines on macOS 13+, Linux, or Windows follow the standard `docker-compose` path.

## One-time setup

```bash
brew install postgresql@16
/usr/local/opt/postgresql@16/bin/initdb -D /usr/local/var/postgresql@16 --encoding=UTF8 --locale=en_US.UTF-8 -U "$(whoami)"
brew services start postgresql@16
```

Create the `medevents` role + database + extensions:

```bash
/usr/local/opt/postgresql@16/bin/psql -h localhost -d postgres <<'SQL'
CREATE ROLE medevents WITH LOGIN PASSWORD 'medevents' SUPERUSER;
CREATE DATABASE medevents OWNER medevents;
\c medevents
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;
SQL
```

## Running migrations

```bash
export DATABASE_URL=postgresql://medevents:medevents@localhost:5432/medevents  # pragma: allowlist secret
uv --directory services/ingest run alembic -c ../../db/migrations/alembic.ini upgrade head
```

Or equivalently, set `DATABASE_URL` in `.env` and use `make migrate`. The Makefile `migrate` target is compatible — it just calls alembic with the configured DB URL.

## Everyday commands

| Docker path (`make up`, etc.) | Homebrew Postgres equivalent                                                                                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `make up`                     | `brew services start postgresql@16`                                                                                                                                            |
| `make down`                   | `brew services stop postgresql@16`                                                                                                                                             |
| `make logs`                   | `tail -f /usr/local/var/log/postgresql@16.log`                                                                                                                                 |
| `make psql`                   | `PGPASSWORD=medevents /usr/local/opt/postgresql@16/bin/psql -h localhost -U medevents -d medevents`                                                                            |
| `make fresh`                  | `PGPASSWORD=medevents /usr/local/opt/postgresql@16/bin/psql -h localhost -U medevents -d medevents -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"` then `make migrate` |

## Reverting to Docker later

When qemu install succeeds (or if you upgrade to macOS 13+ where Apple's `vz` framework is available):

```bash
brew services stop postgresql@16
colima start  # or Docker Desktop
make up       # boots medevents-postgres container
```

Both layouts use port 5432 and the same DB/user/password, so there is **no schema change and no `DATABASE_URL` change** required to switch. Raw data does not migrate automatically — but since all state is reproducible from migrations + seeds, that's not a real issue.

## What's still deferred in Task 4

The plan's original Task 4 includes a verification step that boots `medevents-postgres` via Docker and checks extensions are loaded:

```bash
make up
docker compose ps                # expect "healthy"
docker exec -it medevents-postgres psql -U medevents -d medevents -c "SELECT extname FROM pg_extension ORDER BY extname;"
```

**That step is deferred on this machine** until Docker is available. The equivalent Postgres-side check has already been run against the Homebrew instance and passes (see extensions list above). The docker-compose.yml is still committed because (a) it is the canonical local-dev path for every other machine, and (b) it documents the exact postgres config the project expects (including the init.sql extensions).
