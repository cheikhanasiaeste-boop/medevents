# MedEvents — Automated Directory MVP Spec

| | |
|---|---|
| **Status** | Active |
| **Date** | 2026-04-20 |
| **Scope** | Implementation-driving MVP architecture for the first build of MedEvents |
| **Reads with** | [`docs/mission.md`](../../mission.md), [`docs/guidelines.md`](../../guidelines.md), [`docs/state.md`](../../state.md) |
| **Relation** | Narrows the target-state platform spec to a lean automated directory MVP |

---

## 0 — Direction

### What this spec is

The build spec for a lean MVP that:

- gathers medical and dental events from multiple known sources automatically
- updates them on a schedule
- deduplicates the obvious overlaps
- displays them in a premium directory with filtering and source transparency

### What this spec is not

- Not the full intelligence-platform target state
- Not a zero-touch promise
- Not a multi-service architecture exercise

### Strategic stance

> **Automate the routine path. Handle exceptions deliberately.**

If a capability does not help us automatically gather, update, or present events in the MVP, it is probably later.

---

## 1 — Product goal

### User promise

"Find relevant medical events in one place, with useful filters, visible sources, and listings that stay reasonably up to date."

### MVP capabilities

| Capability | MVP stance |
|---|---|
| Multi-source ingestion | ✅ Automatic from curated known sources |
| Scheduled updates | ✅ Required |
| Filtered browsing | ✅ Required |
| Event detail pages | ✅ Required |
| Source transparency | ✅ Required |
| Basic dedupe | ✅ Required |
| Manual event entry as routine ops | ❌ Avoid |
| Open-ended source discovery | ❌ Later |
| Deep provenance/confidence engine | ❌ Later |
| Partner/public API | ❌ Later |
| Full intelligence workflows | ❌ Later |

### Non-goals

- No attempt to model every possible event field in v1
- No attempt to automate every edge case
- No promise that every source works without maintenance forever
- No target-state data platform layers before real need

---

## 2 — Architecture

### Decision

Use one repository with one product app, one ingestion codebase, and one database.

### Topology

```text
medevents/
├── apps/
│   └── web/                 # Next.js app: public site + MVP operator/review surface + route handlers
├── services/
│   └── ingest/              # Python scheduled ingestion jobs and source parsers
├── packages/
│   └── shared/              # shared types, constants, simple helpers if needed
├── db/
│   └── migrations/          # schema migrations
├── config/
│   ├── sources.yaml         # curated source registry seed
│   └── specialties.yaml     # lightweight specialty/topic seed
└── docs/
```

### Locked decisions

- **One Next.js app for MVP.** Do not split public web, admin, and API into separate deployables yet.
- **Python handles ingestion.** Keep crawling/parsing in one place instead of multiple pipeline services.
- **Postgres is the only required datastore for MVP.**
- **Search starts in Postgres.** Add a dedicated search engine only if query performance or facet quality becomes a real bottleneck.
- **No queue system in the first cut.** Use scheduled jobs and per-source runs. Introduce Redis/RQ only if job orchestration becomes painful.
- **No object-storage dependency in the first cut.** Store the metadata needed for re-fetching and debugging; add raw artifact archival later if parser debugging demands it.

### Why this is enough

The hard MVP problem is source automation, not service topology.

Keep the system small until we know:

- how many sources we can reliably automate
- how often parsers break
- how ambiguous dedupe really is
- how much operator tooling is actually needed

---

## 3 — Data model

### Design principle

Model the fields users need to browse, filter, compare, and trust.

### Core tables

#### `sources`

Tracks curated sources we intentionally support.

Minimum fields:

- `id`
- `name`
- `code`
- `homepage_url`
- `source_type`
- `country_iso`
- `is_active`
- `crawl_frequency`
- `crawl_config`
- `last_crawled_at`
- `last_success_at`
- `last_error_at`
- `notes`

#### `source_pages`

Tracks discovered pages for known sources.

Minimum fields:

- `id`
- `source_id`
- `url`
- `page_kind` (`listing | detail | pdf | unknown`)
- `content_hash`
- `last_seen_at`
- `last_fetched_at`
- `fetch_status`
- `parser_name`

#### `events`

The product-facing directory record.

Minimum fields:

- `id`
- `slug`
- `title`
- `summary`
- `starts_on`
- `ends_on`
- `timezone`
- `city`
- `country_iso`
- `venue_name`
- `format` (`in_person | virtual | hybrid | unknown`)
- `event_kind` (`fair | seminar | congress | workshop | webinar | conference | training | other`)
- `lifecycle_status` (`active | postponed | cancelled | completed | tentative`)
- `specialty`
- `organizer_name`
- `source_url`
- `registration_url`
- `source_count`
- `last_checked_at`
- `last_changed_at`
- `is_published`
- `created_at`
- `updated_at`

#### `event_sources`

Connects an event to one or more supporting source pages.

Minimum fields:

- `id`
- `event_id`
- `source_id`
- `source_page_id`
- `source_url`
- `first_seen_at`
- `last_seen_at`
- `is_primary`
- `raw_title`
- `raw_date_text`

#### `review_items`

Explicit exception queue for cases automation cannot resolve confidently.

Minimum fields:

- `id`
- `kind` (`duplicate_candidate | parser_failure | suspicious_data | source_blocked`)
- `source_id`
- `source_page_id`
- `event_id`
- `status` (`open | resolved | ignored`)
- `details_json`
- `created_at`
- `resolved_at`

### Deliberate omissions

- No raw/observation/canonical three-layer model yet
- No per-field provenance table yet
- No confidence scoring engine yet
- No deep history/snapshots yet
- No session/speaker/sponsor sub-models yet

---

## 4 — Automation flow

### Routine path

```text
known sources
   -> discover pages
   -> fetch pages
   -> parse core event fields
   -> normalize dates/locations/format
   -> dedupe against existing events
   -> insert or update event
   -> mark stale/expired items
```

### Rules

- **Known sources only.** No open web crawling in MVP.
- **Scheduled runs per source.** Daily or weekly depending on source quality and update frequency.
- **Parser order:** source-specific parser first, generic fallback second.
- **Update detection:** use `content_hash` or equivalent fingerprint to skip unnecessary work.
- **Expiry handling:** expired events can be hidden from default browse views automatically.
- **Lifecycle handling:** postponed/cancelled/completed must be represented explicitly in `events.lifecycle_status`.

### Basic dedupe

Good enough for MVP:

- exact or near title match
- overlapping dates
- same city/country when available
- matching registration URL or source URL when available

If duplicate confidence is unclear, create a `review_items` row instead of trying to be clever.

---

## 5 — Operator model

### Low-touch, not zero-touch

The system should run without daily manual curation, but human review is still expected for exceptions.

### Expected manual interventions

- onboarding a new source
- fixing a parser after a source redesign
- resolving ambiguous duplicates
- checking suspicious extracted data
- unblocking a source that starts rate-limiting or blocking requests

### What should not require manual work

- adding ordinary events from already-supported sources
- updating event dates or URLs when the parser still works
- hiding past events from browse views
- refreshing normal listings on schedule

### MVP review surface

Use lightweight review tooling inside the main app:

- open review queue
- source health view
- simple event search/edit/publish screen

Do not build a separate admin application yet.

---

## 6 — Product surface

### Required pages

- home
- events list
- event detail
- sources list
- minimal operator/review pages

### Required UX

- fast filtering by date, region, format, and specialty/topic
- event cards with the core decision fields
- visible source link on every detail page
- visible last checked or last updated signal
- clear lifecycle labels for postponed/cancelled/completed events
- mobile-friendly filtering

### Data access

For MVP, server-rendered pages and route handlers inside the Next.js app are enough.

Do not create a separate read API unless external consumers or internal complexity force the split.

---

## 7 — Quality bar

### MVP quality requirements

- scheduled jobs run reliably
- source failures are visible
- duplicate rate is tolerable
- event detail pages do not show obviously broken key fields
- source transparency is always present
- filters are fast enough on mobile and desktop

### Keep it lean

Required from day one:

- CI
- linting
- migration discipline
- basic ingestion logging
- basic error reporting

Deferred until pain proves need:

- full observability platform
- eval harness suites across every subsystem
- advanced contract testing
- multi-dashboard analytics stack

---

## 8 — Build sequence

| Wave | Goal |
|---|---|
| **W0** | Repo setup, Next.js scaffold, Python ingest scaffold, Postgres, CI, local dev |
| **W1** | Core schema, migrations, `sources.yaml`, minimal operator pages |
| **W2** | One-source end-to-end automation: discover, fetch, parse, normalize, insert/update |
| **W3** | Add 4-9 more curated sources, basic dedupe, review queue, stale-event handling |
| **W4** | Public directory polish: filters, event pages, source pages, mobile UX, search tuning |
| **W5** | Hardening: source-health visibility, parser maintenance flow, deployment, launch prep |

### Gate after W2

Stop and reassess if:

- parser maintenance already feels too brittle
- automatic updates do not materially reduce manual work
- dedupe errors are too frequent
- data quality is too weak for public trust

Only after that gate should we decide whether heavier platform layers are justified.

---

## 9 — Evolution path to intelligence platform

Introduce heavier architecture only when a concrete trigger appears.

| Trigger | Then add |
|---|---|
| Postgres search/facets become limiting | Dedicated search engine |
| Source debugging becomes painful | Raw artifact archival and richer fetch history |
| Duplicate ambiguity becomes frequent | Stronger provenance and dedupe review workflow |
| One app becomes too coupled | Separate API and/or admin app |
| Scheduled jobs become hard to coordinate | Queue/workflow system |
| Users need stronger trust signals | Per-field provenance, confidence, publish policy |
| External consumers appear | Stable public API |

The target-state platform spec remains useful, but only as a menu of future upgrades.

---

## 10 — MVP success criteria

| Criterion | Target |
|---|---|
| Published events | 100-300 quality listings |
| Sources | 5-15 curated known sources |
| Update model | Automatic scheduled refreshes |
| Manual work | Exception-driven, not routine data entry |
| Dedupe | Obvious duplicates merged or flagged |
| UX | Fast filtered browsing on desktop and mobile |
| Transparency | Source shown on every event |
| Freshness | `last_checked_at` visible and meaningful |
| Lifecycle | Cancelled/postponed/completed events clearly labeled |

If the MVP delivers these well, it has earned the right to grow into a deeper intelligence platform later.
