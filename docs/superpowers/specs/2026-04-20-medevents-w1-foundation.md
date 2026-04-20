# MedEvents — W1 Foundation Sub-Spec (Schema, Parser Interface, Operator Bones)

|                 |                                                                                                                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**      | Active                                                                                                                                                                                                                          |
| **Date**        | 2026-04-20                                                                                                                                                                                                                      |
| **Wave**        | W1 (foundation under W0 setup)                                                                                                                                                                                                  |
| **Scope**       | Implementation-driving spec for the foundation wave: database schema, migration tooling, parser interface, MVP operator pages, search approach                                                                                  |
| **Reads with**  | [`docs/mission.md`](../../mission.md), [`docs/guidelines.md`](../../guidelines.md), [`docs/state.md`](../../state.md), [`./2026-04-20-medevents-automated-directory-mvp.md`](./2026-04-20-medevents-automated-directory-mvp.md) |
| **Plan target** | One combined W0+W1 implementation plan follows this spec                                                                                                                                                                        |

---

## 0 — Scope discipline

This sub-spec covers **only the foundation choices that shape the W0 setup**. Anything not listed here is out of scope and lives in a later wave's sub-spec (W2 ingestion logic, W3 dedupe + multi-source, W4 public polish, W5 hardening).

**In scope:**

- Database schema (6 tables) and indexes
- Migration tooling and ownership
- Type generation between Postgres and TS
- Parser interface (Python protocol + registry + generic fallback timing)
- Per-source run flow (CLI shape + scheduling)
- MVP operator pages and actions (inside `apps/web/admin/`)
- Operator authentication
- Postgres search approach (filters, fuzzy title, no FTS yet)
- Audit log table

**Out of scope:**

- Actual ingestion pipeline implementation (W2)
- Generic fallback parser implementation (W3)
- Multi-source dedupe heuristics (W3)
- Public site visual design (W4)
- Source-health dashboards (W5)
- Anything in the target-state platform spec that isn't echoed here

---

## 1 — Locked decisions (W1 brainstorm outcomes)

| #   | Topic                      | Decision                                                                                                                                           |
| --- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | DB type generation         | `drizzle-kit pull` for **DB-derived TS types only**. Hand-write Zod schemas at form/request boundaries where runtime validation matters.           |
| 2   | Specialty storage          | `events.specialty_codes text[]` (denormalized, GIN-indexed). Join table is a post-MVP migration when relevance scores or M:N analytics are needed. |
| 3   | Source error visibility    | `sources.last_error_message text NULL` for operator UI.                                                                                            |
| 4   | Generic fallback parser    | Defer to W3. No second-source pressure in W2.                                                                                                      |
| 5   | Scheduling                 | Fly.io scheduled machines invoking the CLI. No in-process scheduler.                                                                               |
| 6   | Audit log                  | `audit_log` is the 6th MVP table. Worthwhile, not overengineering.                                                                                 |
| 7   | "Run now" action           | **Sync** for single-source runs only. If flaky in real deployment, fall back to CLI-only rather than build job infra.                              |
| 8   | Edit form                  | Full canonical-field override allowed (operator override is part of the exception path).                                                           |
| 9   | Default browse             | Exclude `cancelled` and `completed` from default lists; opt-in via filter (`?include=cancelled,completed`).                                        |
| 10  | Pagination                 | Offset (`LIMIT/OFFSET`) for MVP. Cursor is a post-pain optimization.                                                                               |
| 11  | Schema enums               | `text` columns with `CHECK` constraints (no Postgres ENUM types — reversible without migration friction).                                          |
| 12  | Postgres extensions        | `pgcrypto` (`gen_random_uuid`), `pg_trgm`, `unaccent`, `citext`. No PostGIS, no pgvector at MVP.                                                   |
| 13  | Local dev                  | docker-compose with one Postgres service.                                                                                                          |
| 14  | Prod DB                    | Neon (managed). Branching is genuinely useful even at MVP.                                                                                         |
| 15  | Migration ownership        | Alembic, hand-written migrations (no SQLAlchemy autogenerate). Lives in `db/migrations/`.                                                          |
| 16  | Audit-log-driven mutations | Every operator mutation writes one `audit_log` row before returning success.                                                                       |

---

## 2 — Database schema

All timestamps `timestamptz`. UUIDs via `gen_random_uuid()`. Enums as `text` + `CHECK`. `code`-style identifiers as `citext` for case-insensitive uniqueness.

### `sources`

```sql
CREATE TABLE sources (
  id                 uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  name               text          NOT NULL,
  code               citext        UNIQUE NOT NULL,                 -- e.g. 'ada'
  homepage_url       text          NOT NULL,
  source_type        text          NOT NULL CHECK (source_type IN
                                       ('society','sponsor','aggregator','venue','government','other')),
  country_iso        char(2)       NULL,
  is_active          boolean       NOT NULL DEFAULT true,
  parser_name        text          NULL,                            -- registered parser code; NULL → generic fallback (W3+)
  crawl_frequency    text          NOT NULL CHECK (crawl_frequency IN
                                       ('daily','weekly','biweekly','monthly')),
  crawl_config       jsonb         NOT NULL DEFAULT '{}'::jsonb,
  last_crawled_at    timestamptz   NULL,
  last_success_at    timestamptz   NULL,
  last_error_at      timestamptz   NULL,
  last_error_message text          NULL,
  notes              text          NULL,
  created_at         timestamptz   NOT NULL DEFAULT now(),
  updated_at         timestamptz   NOT NULL DEFAULT now()
);
```

### `source_pages`

```sql
CREATE TABLE source_pages (
  id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       uuid          NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  url             text          NOT NULL,                           -- canonicalized URL
  page_kind       text          NOT NULL CHECK (page_kind IN
                                    ('listing','detail','pdf','unknown')),
  content_hash    text          NULL,                               -- sha256 hex of last fetched body
  last_seen_at    timestamptz   NULL,                               -- last time URL was discovered in a listing
  last_fetched_at timestamptz   NULL,
  fetch_status    text          NULL,                               -- 'success' | 'http_4xx' | 'http_5xx' | 'timeout' | 'blocked' | 'parse_error'
  parser_name     text          NULL,                               -- which parser handled this last
  created_at      timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (source_id, url)
);
```

### `events`

```sql
CREATE TABLE events (
  id                uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  slug              text          UNIQUE NOT NULL,
  title             text          NOT NULL,
  summary           text          NULL,
  starts_on         date          NOT NULL,
  ends_on           date          NULL,
  timezone          text          NULL,                             -- IANA, optional
  city              text          NULL,
  country_iso       char(2)       NULL,
  venue_name        text          NULL,
  format            text          NOT NULL DEFAULT 'unknown' CHECK (format IN
                                      ('in_person','virtual','hybrid','unknown')),
  event_kind        text          NOT NULL DEFAULT 'other' CHECK (event_kind IN
                                      ('fair','seminar','congress','workshop','webinar','conference','training','other')),
  lifecycle_status  text          NOT NULL DEFAULT 'active' CHECK (lifecycle_status IN
                                      ('active','postponed','cancelled','completed','tentative')),
  specialty_codes   text[]        NOT NULL DEFAULT '{}',            -- denormalized array of specialty codes
  organizer_name    text          NULL,
  source_url        text          NOT NULL,                         -- primary source URL
  registration_url  text          NULL,
  source_count      int           NOT NULL DEFAULT 1,
  last_checked_at   timestamptz   NOT NULL DEFAULT now(),
  last_changed_at   timestamptz   NOT NULL DEFAULT now(),
  is_published      boolean       NOT NULL DEFAULT true,
  created_at        timestamptz   NOT NULL DEFAULT now(),
  updated_at        timestamptz   NOT NULL DEFAULT now()
);
```

### `event_sources`

```sql
CREATE TABLE event_sources (
  id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id        uuid          NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  source_id       uuid          NOT NULL REFERENCES sources(id),
  source_page_id  uuid          NULL REFERENCES source_pages(id),   -- NULL allowed when source pre-dates a specific page row
  source_url      text          NOT NULL,                           -- the actual page URL for this contribution
  first_seen_at   timestamptz   NOT NULL DEFAULT now(),
  last_seen_at   timestamptz   NOT NULL DEFAULT now(),
  is_primary      boolean       NOT NULL DEFAULT false,
  raw_title       text          NULL,
  raw_date_text   text          NULL,
  created_at      timestamptz   NOT NULL DEFAULT now()
);

-- One source may contribute multiple pages to one event (listing, detail, PDF, update).
-- Uniqueness is on (event, page) when page is known; not on (event, source).
CREATE UNIQUE INDEX event_sources_event_page_uniq
  ON event_sources(event_id, source_page_id)
  WHERE source_page_id IS NOT NULL;

-- For the rare case where source_page_id is NULL, we still don't want exact-duplicate URL pairs.
CREATE UNIQUE INDEX event_sources_event_url_uniq
  ON event_sources(event_id, source_url)
  WHERE source_page_id IS NULL;
```

### `review_items`

```sql
CREATE TABLE review_items (
  id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  kind            text          NOT NULL CHECK (kind IN
                                    ('duplicate_candidate','parser_failure','suspicious_data','source_blocked')),
  source_id       uuid          NULL REFERENCES sources(id),
  source_page_id  uuid          NULL REFERENCES source_pages(id),
  event_id        uuid          NULL REFERENCES events(id),
  status          text          NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','ignored')),
  details_json    jsonb         NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz   NOT NULL DEFAULT now(),
  resolved_at     timestamptz   NULL,
  resolved_by     text          NULL,                               -- free-text actor for MVP single-admin
  resolution_note text          NULL
);
```

### `audit_log`

```sql
CREATE TABLE audit_log (
  id           uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  actor        text          NOT NULL,                              -- admin identity (MVP: 'owner')
  action       text          NOT NULL,                              -- 'source.run' | 'source.toggle' | 'review.resolve' | 'review.merge' | 'event.edit' | 'event.unpublish' | ...
  target_kind  text          NULL,                                  -- 'source' | 'event' | 'review_item' | NULL
  target_id    uuid          NULL,
  details_json jsonb         NOT NULL DEFAULT '{}'::jsonb,
  occurred_at  timestamptz   NOT NULL DEFAULT now()
);
```

---

## 3 — Indexes (minimum MVP set)

```sql
-- events
CREATE INDEX events_published_starts_on ON events(is_published, starts_on);
CREATE INDEX events_country_starts_on   ON events(country_iso, starts_on);
CREATE INDEX events_lifecycle           ON events(lifecycle_status);
CREATE INDEX events_specialty_codes_gin ON events USING GIN(specialty_codes);
CREATE INDEX events_title_trgm          ON events USING GIN(title gin_trgm_ops);

-- source_pages
CREATE INDEX source_pages_source_kind   ON source_pages(source_id, page_kind);
CREATE INDEX source_pages_content_hash  ON source_pages(content_hash);

-- event_sources (regular indexes; uniques defined inline above)
CREATE INDEX event_sources_event        ON event_sources(event_id);
CREATE INDEX event_sources_source       ON event_sources(source_id);
CREATE INDEX event_sources_page         ON event_sources(source_page_id);

-- review_items
CREATE INDEX review_items_status_kind   ON review_items(status, kind, created_at);

-- sources (scheduler pickup)
CREATE INDEX sources_active_crawled     ON sources(is_active, last_crawled_at);

-- audit_log
CREATE INDEX audit_log_target           ON audit_log(target_kind, target_id, occurred_at);
CREATE INDEX audit_log_actor_time       ON audit_log(actor, occurred_at);
```

Add indexes only when profiling shows hot paths. Don't pre-index speculatively.

---

## 4 — Migration tooling & ownership

- **Tool**: Alembic, owned by the Python ingest service.
- **Location**: `db/migrations/` at repo root (workspace-visible).
- **Style**: hand-written `op.execute(...)` SQL or `op.create_table(...)` calls. **No SQLAlchemy ORM autogenerate.** Every migration is reviewable as plain SQL intent.
- **Direction**: forward-only. No downgrade scripts. Rollback = restore Neon PITR or apply a forward correction migration.
- **CI gate**: `alembic upgrade head` runs against an ephemeral Postgres in CI; PR fails on error.
- **Initial migration enables extensions**: `CREATE EXTENSION IF NOT EXISTS pgcrypto; pg_trgm; unaccent; citext;`
- **Data migrations** (not just DDL) live as numbered Alembic scripts; `audit_log` records that they ran.

---

## 5 — TS type generation

- **`drizzle-kit pull`** introspects the Postgres schema and emits TS types (and Drizzle table definitions, used for query building) into `packages/shared/db/`.
- **CI gate**: `drizzle-kit pull` on every PR; commit must match generated output. Schema changes propagate to TS in one step.
- **Zod schemas are NOT auto-generated.** Hand-write Zod at:
  - Form input validation (operator edit forms)
  - Route handler request bodies (POST endpoints)
  - External-input boundaries (parsed event payloads from the ingest service)
- This split keeps DB-shape sync mechanical, and runtime-validation explicit.

---

## 6 — Parser interface

Python protocol in `services/ingest/parsers/base.py`:

```python
from typing import Protocol, Iterator

class Parser(Protocol):
    name: str                                                # registered code, e.g. "ada_listing"

    def discover(self, source: Source) -> Iterator[DiscoveredPage]:
        """Yield candidate URLs for this source.
           Implementations: read RSS, parse sitemap, paginate listing pages, or read manual."""

    def fetch(self, page: SourcePage) -> FetchedContent:
        """Fetch URL → bytes/text + content_type + status. Default impl uses httpx.
           Override for Playwright when a source requires JS rendering."""

    def parse(self, content: FetchedContent) -> ParsedEvent | None:
        """Return None if not a recognizable event detail page."""
```

**Registry**: `@register_parser("ada_listing")` decorator collects parsers into a dict keyed by the same string stored in `sources.parser_name`.

**Resolution**: `parser_for(source)` returns `registry[source.parser_name]` if set, else raises `UnknownParserError`. The **generic fallback parser is W3 work** — at W2 the ADA-only run resolves a registered parser by name; missing parsers are a hard error.

**Per-source parser file location**: `services/ingest/parsers/{source_code}.py`. Each file registers one or more parsers (a source may have separate listing-page and detail-page parsers if useful).

---

## 7 — Run flow & scheduling

### CLI

The Python ingest service exposes one entrypoint:

```
medevents-ingest run --source ada
medevents-ingest run --all                      # iterates active sources whose schedule is due
medevents-ingest run --source ada --force       # ignore last_crawled_at
medevents-ingest run --source ada --dry-run     # parse but don't write
medevents-ingest run --source ada --page <url>  # re-process a single page
```

### Per-source run procedure

1. Resolve parser via `sources.parser_name`.
2. `parser.discover(source)` → upsert `source_pages` (insert new URLs, bump `last_seen_at`).
3. For each new or stale `source_pages` row whose `(content_hash, last_fetched_at)` indicates re-fetch:
   - `parser.fetch(page)` → if hash matches `content_hash`, skip downstream and update `last_fetched_at` only.
   - Else `parser.parse(content)` → `ParsedEvent | None`.
   - On `ParsedEvent`: dedupe (W3 logic; for W2/ADA-only, treat as new) → `INSERT INTO events` and `INSERT INTO event_sources` (with `is_primary = true` on first contribution).
   - On parse failure or suspicious extraction: insert `review_items` row.
4. Update `source_pages.{last_fetched_at, content_hash, parser_name, fetch_status}`.
5. On completion, update `sources.{last_crawled_at, last_success_at}`. On error, also `last_error_at` + `last_error_message`.

### Scheduling

- **Fly.io scheduled machines.** A small Fly machine wakes hourly, runs `medevents-ingest run --all`, exits. No long-running scheduler process.
- For W1, only the CLI exists — actual scheduling is **W5 hardening**. Manual `make ingest-ada` is enough for W2.

---

## 8 — Operator surface (`apps/web/admin/`)

### Routes

All under the `(admin)` route group, gated by middleware checking the session cookie.

| Path                  | Purpose                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------- |
| `/admin/login`        | Password form                                                                            |
| `/admin`              | Dashboard: counts (sources, events, open reviews); recent runs feed                      |
| `/admin/sources`      | Source list with `last_crawled_at`, `last_error_at`, "Run now", "Toggle active" buttons  |
| `/admin/sources/[id]` | Source detail: recent runs, recent pages, `last_error_message`, edit notes               |
| `/admin/review`       | Open review queue, filterable by `kind`                                                  |
| `/admin/review/[id]`  | Single review item: per-`kind` UI (merge candidate, dismiss, mark resolved)              |
| `/admin/events`       | Event search by title (`pg_trgm` `%`), filters: source / lifecycle_status / is_published |
| `/admin/events/[id]`  | Event detail with full edit form, attached `event_sources`, "Unpublish", "Merge into…"   |

### Mutating actions (POST route handlers in Next.js)

| Endpoint                                 | Body                     | Result                                                                                                                                                                                                                                                                            |
| ---------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /admin/sources/[id]/run`           | none                     | Sync invocation of the ingest CLI for a single source. Blocks until complete or 60s timeout (whichever first). Writes `audit_log('source.run', target_id=source_id)`. **If flaky in real use, this button gets removed and the operator runs CLI directly** — no job-queue infra. |
| `POST /admin/sources/[id]/toggle-active` | none                     | Flips `is_active`. `audit_log('source.toggle')`.                                                                                                                                                                                                                                  |
| `POST /admin/review/[id]/resolve`        | `{ resolution_note }`    | Sets `status='resolved'`, `resolved_at`, `resolved_by`, `resolution_note`. `audit_log('review.resolve')`.                                                                                                                                                                         |
| `POST /admin/review/[id]/merge`          | `{ target_event_id }`    | Only for `kind='duplicate_candidate'`. Re-points `event_sources` to target, deletes the duplicate, creates `audit_log('review.merge')`.                                                                                                                                           |
| `POST /admin/events/[id]`                | `{ ...editable fields }` | Updates any canonical field. `audit_log('event.edit', details_json={changed_fields})`.                                                                                                                                                                                            |
| `POST /admin/events/[id]/unpublish`      | none                     | Sets `is_published=false`. `audit_log('event.unpublish')`.                                                                                                                                                                                                                        |

**Editable fields on `/admin/events/[id]`** (full canonical-field override): `title, summary, starts_on, ends_on, timezone, city, country_iso, venue_name, format, event_kind, lifecycle_status, specialty_codes, organizer_name, source_url, registration_url, slug, is_published`.

### Authentication

- Single admin user. Password stored as `ADMIN_PASSWORD_HASH` (Argon2id, generated once via a CLI helper).
- `/admin/login` form posts `{ password }` → server compares against `ADMIN_PASSWORD_HASH`.
- On success, server creates an `iron-session` signed cookie:
  - Name: `medevents_admin_session`
  - Attributes: `HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=86400`
  - Payload: `{ actor: 'owner', issued_at, expires_at }` — signed with `IRON_SESSION_PASSWORD` env (32+ chars).
- Middleware on `/admin/*` (except `/admin/login`) redirects unauthenticated requests to login.
- **No DB sessions table.** `iron-session` is sufficient for single user.
- **CSRF**: SameSite=Strict + every mutating route requires an `X-CSRF-Token` header carrying a value embedded in the page render and rotated per session.
- All mutating actions write `audit_log` before returning success.

---

## 9 — Postgres search approach

### Filter query (single SQL, parameterized)

```sql
SELECT id, slug, title, summary, starts_on, ends_on, timezone, city, country_iso,
       venue_name, format, event_kind, lifecycle_status, specialty_codes,
       organizer_name, registration_url, source_count, last_checked_at,
       last_changed_at
FROM events
WHERE is_published = true
  AND ($country_iso::char(2)[]      IS NULL OR country_iso = ANY($country_iso))
  AND ($specialties::text[]         IS NULL OR specialty_codes && $specialties)
  AND ($from::date                  IS NULL OR starts_on >= $from)
  AND ($to::date                    IS NULL OR starts_on <= $to)
  AND ($formats::text[]             IS NULL OR format = ANY($formats))
  AND ($kinds::text[]               IS NULL OR event_kind = ANY($kinds))
  AND ($include_inactive            OR lifecycle_status NOT IN ('cancelled','completed'))
  AND ($q::text                     IS NULL OR title % $q)
ORDER BY starts_on ASC, id ASC
LIMIT $limit OFFSET $offset;
```

### Conventions

- **Default browse excludes** `cancelled` and `completed`. Opt-in via `?include=cancelled,completed` query param.
- **Fuzzy title search** uses `pg_trgm` `%` operator. Threshold starts at the default `0.3`; tuneable via `SET pg_trgm.similarity_threshold = ...` per session if needed.
- **Facet counts** for the filter UI: separate `SELECT … GROUP BY` per facet (country, format, event_kind, specialty unnest). In-memory cached on the Next.js server for a few seconds; no Redis at MVP.
- **No tsvector / FTS in MVP.** When fuzzy title isn't enough — typically when users want to search summary or organizer text — add a `tsvector` column with a trigger. Slated as a triggered upgrade in W3+ pending real query patterns.
- **Pagination**: `LIMIT/OFFSET` for MVP. Switch to cursor (`(starts_on, id) > (last_starts_on, last_id)`) only when offset performance hurts.

---

## 10 — Done criteria for W1

The wave is complete when:

| #   | Criterion                                                                                                                                                                                                   |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | All 6 tables exist in Postgres via Alembic migration (forward-only).                                                                                                                                        |
| 2   | All extensions enabled: `pgcrypto`, `pg_trgm`, `unaccent`, `citext`.                                                                                                                                        |
| 3   | All MVP indexes created and verified via `\d+`.                                                                                                                                                             |
| 4   | `drizzle-kit pull` emits clean TS types into `packages/shared/db/`; CI passes the drift gate.                                                                                                               |
| 5   | `config/sources.yaml` seed file defines at least 1 source (ADA) with `parser_name = 'ada_listing'`.                                                                                                         |
| 6   | `config/specialties.yaml` defines the dental specialty codes used in seed events.                                                                                                                           |
| 7   | Importer command `medevents-ingest seed-sources` upserts the YAML into `sources`.                                                                                                                           |
| 8   | Parser interface (`Parser` Protocol + `@register_parser` decorator + `parser_for(source)` resolver) is in place; `services/ingest/parsers/__init__.py` registers an empty registry.                         |
| 9   | CLI shape exists: `medevents-ingest run --source <code>` is callable but only resolves the parser and exits cleanly (full ingest logic is W2).                                                              |
| 10  | Operator routes scaffolded under `apps/web/app/(admin)/`: login, dashboard, sources list/detail, review list/detail, events list/detail. Pages render against real DB; mutating handlers write `audit_log`. |
| 11  | Login flow works end-to-end: password hash check → iron-session cookie → middleware-protected admin pages.                                                                                                  |
| 12  | "Run now" button on `/admin/sources/[id]` invokes the CLI sync (in W1 this just resolves and exits cleanly; W2 makes it actually crawl).                                                                    |
| 13  | `/admin/events` returns paginated rows with the W1 filter SQL working; `pg_trgm` fuzzy title proven by manual smoke.                                                                                        |
| 14  | All mutating actions write `audit_log` rows; verified by inspecting the table after operator clicks.                                                                                                        |
| 15  | CI gates green: lint + types + Alembic forward + drizzle-kit pull drift + Vitest smoke + Playwright login flow.                                                                                             |

---

## 11 — Out of scope (explicit deferrals)

- Actual crawling/parsing logic (W2 — implements the registered ADA parser body).
- Generic fallback parser (W3).
- Dedupe heuristics (W3).
- Stale-event handling job (W3).
- Source-health visibility beyond `last_*` columns (W5).
- Public events list/detail UI polish (W4 — W1 only scaffolds the operator side).
- Sitemap/RSS for SEO (W4).
- FTS, cursor pagination, facet caching beyond in-memory (post-MVP triggers).
- Sessions/speakers/sponsors sub-models (deferred per MVP spec §3).
- Per-field provenance / confidence / snapshots (deferred per MVP spec §3).

---

## 12 — Open questions / forward refs

- **Slug generation strategy**: derive at insert time from `(title, starts_on, country_iso)`? Or assign UUID-ish slug and let operator override? **Decision deferred to W2** when first parsed event arrives — needs real titles to design against.
- **Argon2id parameters**: use library defaults (memory ~19 MiB, parallelism 1, iterations 2). Revisit if login latency feels off on Fly.
- **`iron-session` vs Next.js's built-in `cookies()` + signed JWT**: choosing iron-session for its mature TS API; revisit if Next ships a primitive that obsoletes it.
- **Multiple parsers per source code**: schema doesn't forbid registering multiple parsers under one source code; the W1 `parser_for(source)` resolver returns one. Defer the "discover vs detail" parser split design to W3 if needed.

---

## 13 — Status

| Step                                             | State                                                               |
| ------------------------------------------------ | ------------------------------------------------------------------- |
| W1 brainstorm                                    | ✅ Complete (defaults locked + 3 schema fixes + sync-run guardrail) |
| W1 sub-spec                                      | ✅ This document                                                    |
| W0+W1 implementation plan                        | ⏳ Next via `writing-plans` skill                                   |
| W0 setup (git init local first → gh repo create) | ⏳ Step 1 of the plan                                               |
| W2 sub-spec brainstorm                           | ⏳ Follows W1 implementation completion + gate                      |
