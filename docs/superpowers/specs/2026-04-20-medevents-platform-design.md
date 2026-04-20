# MedEvents — Platform Architecture Design Spec

| | |
|---|---|
| **Status** | Reference only for now (target-state architecture, not current MVP build spec) |
| **Date** | 2026-04-20 |
| **Scope** | Top-level platform architecture for the MedEvents global medical/dental events aggregation platform. Sub-spec implementation detail follows in `docs/superpowers/specs/` per wave. |
| **Reads with** | [`docs/mission.md`](../../mission.md), [`docs/guidelines.md`](../../guidelines.md), [`docs/state.md`](../../state.md) |
| **Supersedes** | — (greenfield) |

> **Implementation note:** the active implementation-driving MVP spec is [`2026-04-20-medevents-automated-directory-mvp.md`](./2026-04-20-medevents-automated-directory-mvp.md). This document remains the long-term target-state reference for a later evolution toward a fuller intelligence platform.

---

## 0 — Context & scope

### What this spec is

The top-level platform architecture for MedEvents — a production-grade global platform that aggregates, normalizes, deduplicates, and continuously updates medical and dental congresses, fairs, and training events. MVP is dental-first; architecture scales to medical post-MVP without migration.

This spec covers: monorepo topology, canonical schema, source registry & taxonomy, pipeline data flow, storage & search, product API contract, frontend architecture (bones), observability/evals/quality discipline, and the end-to-end build sequence.

### What this spec is NOT

- Not a UI Design sub-spec (that's a separate document, written before Wave 5b).
- Not a per-subsystem implementation plan — those follow in their own brainstorm → spec → plan cycle, just-in-time.
- Not a product strategy doc (see [`mission.md`](../../mission.md)).

### Strategic stance

> **Build for A on the inside, look like B on the outside.**

- **Inside (A):** relentless data quality, freshness, coverage depth, pipeline robustness.
- **Outside (B):** premium, modern, dynamic, high-trust UX from day one.
- **Seam:** data platform and product layer are cleanly separated via a stable, typed API contract, generated from shared JSON Schema. Both halves evolve in parallel.

### MVP scope

| Dimension | Commitment |
|---|---|
| Specialty | Dental only at launch |
| Coverage | Seed-then-expand — ~150 curated events at launch, architecture scales to ~1000 |
| Effort | Solo, 16 weeks best-case / 18–24 weeks realistic |
| Infra stance | Mostly self-hosted with selective managed (Neon Postgres, Cloudflare R2, Anthropic API) |
| Primary UX | Filtered browsing (premium directory) |

---

## 1 — Monorepo topology

### Decision

Single git repo, **split workspace**: TypeScript (`pnpm` + Turborepo) for the product side, Python (`uv`) for the data platform, with a **shared schema package that's the source of truth for both halves**.

### Tree

```
medevents/
├── apps/
│   ├── web/                    # Next.js 15 App Router product
│   ├── api/                    # Hono on Node (Bun optional) — read-side API
│   └── admin/                  # reserved Next.js app for ops surface
├── services/                   # Python data platform
│   ├── crawler/                # Playwright + source adapters
│   ├── extractor/              # LLM + rules extraction
│   ├── normalizer/             # canonical transforms
│   ├── deduper/                # fuzzy + semantic dedupe
│   ├── publisher/              # canonical → Postgres + Meilisearch
│   └── common/                 # HTTP, R2, logging, tracing, shared utils
├── packages/
│   ├── schema/
│   │   ├── source/             # JSON Schema source (hand-edited)
│   │   ├── generated/ts/       # Zod + TS types (codegen)
│   │   └── generated/py/       # Pydantic v2 models (codegen)
│   ├── ui/                     # Radix-wrapped React primitives
│   ├── design-system/          # Tailwind preset, tokens, fonts
│   └── config/                 # shared lint / tsconfig / ruff / mypy
├── db/migrations/              # Alembic migrations (top-level)
├── infra/docker/               # docker-compose for local dev
├── evals/                      # extraction / dedupe / specialty eval harness
├── docs/
│   ├── mission.md
│   ├── guidelines.md
│   ├── state.md
│   ├── superpowers/specs/      # this file + sub-specs
│   ├── runbooks/               # ops runbooks
│   └── postmortems/            # incident write-ups
├── pyproject.toml              # uv workspace root
├── package.json                # pnpm workspace root
└── turbo.json
```

### Locked decisions

- **Monorepo, not polyrepo.** Solo dev + shared schema = atomic PRs beat coordinated releases.
- **Contract source-of-truth, layered:**
  - `packages/schema/source/*.json` (JSON Schema 2020-12) owns **payload models** — Event, Source, Observation, Taxonomy, etc. Hand-edited.
  - Codegen emits Zod + TS types (`packages/schema/generated/ts/`) and Pydantic v2 models (`packages/schema/generated/py/`). Never hand-edited.
  - Hono routes in `apps/api/` own **route contracts** (paths, methods, status codes, query params) and **import** the generated Zod schemas for request/response payloads.
  - **OpenAPI 3.1 is assembled**, not authored: `@hono/zod-openapi` walks Hono routes (which already import the generated Zod) and emits `packages/schema/generated/openapi.yaml`. CI gate fails on drift.
  - Authority flows: JSON Schema → Zod/Pydantic → Hono routes → OpenAPI. Single direction; no round-tripping.
- **Read-side API is a separate app** (`apps/api/`, Hono on Node), not Next.js route handlers. Keeps the Next.js surface pure UI/RSC, allows independent caching and scaling, future-proofs partner/API access.
- **Python tooling**: `uv` + `ruff` + `mypy --strict`. One workspace = one lockfile.
- **TS tooling**: `pnpm` + `Turborepo` + `ESLint + Prettier`. Biome revisited post-MVP.
- **Local dev**: `docker-compose` for Postgres + Meilisearch + Redis-cache + Redis-queue; apps run native.
- **`apps/admin/` reserved now**, even before Wave 7 implementation.
- **DB migrations live at `db/migrations/`** (top-level, not under generic `infra/`). Database schema is part of the application contract.
- **Raw artifacts**: blobs in R2, pointers (`source_pages.raw_artifact_uri`) in Postgres. R2 path scheme defined in §4.
- **Hono on Node by default**, Bun optional. Optimize for boring reliability.

### Deployment targets (MVP)

| Component | Choice |
|---|---|
| Postgres | **Neon** (managed) — migrate to self-hosted Hetzner post-MVP if justified |
| Search index | **Meilisearch**, self-hosted on Fly.io |
| Object storage | **Cloudflare R2** |
| App + worker hosting | **Fly.io** (Next.js + Hono API + Python workers) |
| LLM | **Anthropic API** |
| Observability | **Grafana Cloud** free tier (OTel exporters) |
| Error tracking | **Sentry** free tier |
| Analytics | **Self-hosted Plausible** on Fly.io |

### Tradeoffs accepted

- Two language ecosystems — accepted, they share a schema, not logic.
- One extra service (Hono read API) — accepted, pays for itself on first cache/rate-limit/partner need.
- Neon at MVP, migration later — accepted, branching speeds early schema iteration.

---

## 2 — Canonical event schema

### Mental model — three layers, strictly separated

1. **Raw artifacts** — HTML / PDF / screenshots in R2, content-hashed, immutable. Pipeline-only access.
2. **Observations** — Per-source, per-extraction-run, immutable append-only. Includes per-field confidence, normalized payload, parse-status metadata, and a pointer to the raw artifact.
3. **Canonical records** — Merged, published, product-facing. Per-field provenance + materialized flat columns + sidecar tables + enrichment.

The product reads **only** canonical records. Never observations. Never raw.

### Locked decisions

- **D1 — Identity**: `events_canonical.id` is UUID v7 (sortable, timestamped). Stable across event lifetime. Never changes. Merges write `merged_into_id`; merged records redirect at the product layer.
- **D2 — Per-field provenance is first-class.** `event_canonical_fields(event_id, field_name, value_jsonb, source_observation_id, confidence_0_1, last_verified_at)`. Flat columns on `events_canonical` are **materialized projections** of highest-confidence values, refreshed by the publisher. The fields table is truth; flat columns are a fast-read cache. **Per-field provenance required for contract-critical fields in MVP**: dates, deadlines, prices, geo, format, `event_kind`, `lifecycle_status`, registration URL, specialties, accreditations.
- **D3 — Confidence + freshness + source transparency are contract fields.** Every canonical record exposes to the product:
  - `data_confidence` (0–100, derived: source-tier weight × field confidence × recency decay)
  - `last_verified_at` (most recent observation matching current canonical value)
  - `last_changed_at` (most recent material change to a contract field)
  - `sources[]` (`{source_name, source_url, observed_at, fields_contributed[]}`)
  These render in the UI. They are why the product is trustworthy.
- **D4 — Dates**: `starts_on DATE NOT NULL` + `starts_at TIMESTAMPTZ NULL`. Most sources publish "April 12–14, 2027" without specific times. Commit to the date. Time is optional. Timezone IANA mandatory once `starts_at` is set. **Never** coerce a date to "midnight UTC."
- **D5 — Sidecar tables**, not JSON blobs: `event_deadlines`, `event_prices`, `event_accreditations`, `event_specialties`, `event_organizers`, `event_field_history`. Indexable, queryable, type-safe.
- **D6 — Geo**: PostGIS `geography(Point, 4326)` venue, ISO 3166-1 alpha-2 country, free-text city, optional geonameId.
- **D7 — Money**: integer minor units + ISO 4217 currency, **always in the source's original currency**. No floats. **No FX conversion at MVP** — display "€1,200", "$800", "¥45,000" exactly as the source published. No `price_usd_estimate`, no `price_band` in any index, no implicit conversion. Filter UX shows currency-tagged ranges per event; cross-currency price filtering is **post-MVP** (depends on the FX rates table and dated `as_of` provenance below).
- **D8 — `field_history` for high-signal fields only in MVP**: `starts_on`, `ends_on`, `registration_url`, `format`, `venue_name`, **`lifecycle_status`** (changes here are user-critical — postponed/cancelled events must surface a visible change banner), deadline rows (whole-row history), price rows. **Plus**: `events_canonical_snapshots` archives the full published record on every republish — forensic trail without the full-field-audit cost.
- **D9 — Slug separate from title.** `slug TEXT UNIQUE NOT NULL` derived at publish time; stable URLs are a product contract.
- **D10 — Publish gate (trust-tiered)**:
  1. **Authoritative** source + confidence ≥ threshold → publish, OR
  2. ≥2 **verified** corroborating sources → publish, OR
  3. **Manual reviewer approval** → publish.
  4. **Unverified** alone never auto-publishes.
  Rules live in `config/publish_policy.yaml`, not hardwired into schema.
- **`event_kind`** is a canonical field separate from `format` and from specialty. Enum: `congress | fair | workshop | symposium | hands_on_course | conference | seminar | webinar | training | exhibition | masterclass`, with `event_kind_raw` fallback.
- **`lifecycle_status`** — distinct from publication `status` (`draft | hold | published | archived | merged_into`). Captures the **real-world event lifecycle** that users care about most:

| Value | Meaning |
|---|---|
| `tentative` | Announced but not fully confirmed (no firm date, no firm venue, or explicitly marked TBC by source) |
| `scheduled` | Confirmed and upcoming (default for published events with firm date + venue) |
| `postponed` | Date/venue change in progress; previous date no longer valid |
| `cancelled` | Explicitly cancelled |
| `completed` | Past event (auto-derived nightly: `ends_on < CURRENT_DATE`) |

  - Stored as `events_canonical.lifecycle_status` (`text NOT NULL DEFAULT 'scheduled'`), with provenance via `event_canonical_fields` (D2) and history via `event_field_history` (D8).
  - Extractor surfaces this from explicit source signals ("Cancelled", "POSTPONED", "Date TBC"); LLM tier prompts include the enum.
  - Publisher derives `completed` automatically from a nightly job; never extracted.
  - Search index includes it as a filterable + sortable facet (D39). Default search excludes `cancelled` and `completed` unless explicitly filtered in.
  - Trust panel surfaces a high-priority banner when `lifecycle_status ∈ {postponed, cancelled}` — this is exactly the change users notice and trust most.

### Enrichment layers (sessions / speakers / sponsors) — MVP scope, lightweight

Event-scoped, observation-backed, confidence-scored, **non-blocking**. Publish gate ignores these.

```
event_sessions(id, event_id, title, starts_at?, ends_at?, track?, raw_speakers_text?,
               kind?, kind_raw?, display_order?, source_observation_id, confidence)

event_speakers(id, event_id, name, role?, role_raw?, affiliation?, bio_short?,
               is_keynote, display_order?, external_url?, source_observation_id, confidence)

event_sponsors(id, event_id, name, tier?, kind?, kind_raw?, logo_url?,
               display_order?, external_url?, source_observation_id, confidence)
```

**Controlled enums** (with `*_raw` fallback for messy sources):
- Sessions `kind`: `lecture | workshop | panel | masterclass | live_demo | keynote | course`
- Speakers `role`: `speaker | chair | moderator | faculty`
- Sponsors `kind`: `sponsor | partner | exhibitor`

**Publisher rule for enrichment**:
- **Single-source adoption** — pick the highest-trust observation with non-empty enrichment. No cross-source merging.
- **Replace-on-republish** for canonical enrichment rows (no history kept at canonical layer).
- **Observation-level enrichment evidence remains append-only** (truth ledger preserved).

### What's NOT in MVP schema (deliberate YAGNI)

- Full conference schedule graphs (rooms, tracks-as-entities, session dependencies)
- Cross-event speaker identity / speaker search / speaker following
- Sponsor analytics / intelligence views
- Session-level filtering UX / timetable visualizations
- Reviews / ratings / attendance numbers / UGC
- Translations (post-MVP)
- FX conversion at read time — **deferred entirely; no hardcoded conversion at MVP**. Post-MVP introduces `currency_rates(currency_iso, as_of_date, usd_rate, source)` with explicit dated provenance, plus `price_usd_estimate` as a separate display field with `as_of` and `rate_source` tags.

### MVP vs post-MVP

| Item | MVP | Post-MVP |
|---|---|---|
| Identity, dates, geo, format, event_kind | ✅ | — |
| Sidecar tables (deadlines/prices/accreditations/specialties/organizers) | ✅ | — |
| Per-field provenance for contract-critical fields | ✅ | All fields |
| Confidence/freshness/sources contract fields | ✅ | — |
| `field_history` for high-signal + full snapshots | ✅ | Full field audit |
| Enrichment (sessions/speakers/sponsors, lightweight) | ✅ | Full schedule, speaker identity, sponsor analytics |
| Multilingual content (human-translated) | ❌ | ✅ |
| Prices stored in source's original currency | ✅ (only mode at MVP) | Add `price_usd_estimate` w/ dated provenance |
| FX daily rates table + cross-currency filter | ❌ | ✅ (`currency_rates` table, dated, sourced) |

---

## 2.5 — Source registry & taxonomy strategy

The control plane behind the pipeline. Drives onboarding, crawl frequency, trust scoring, specialty assignment, and expansion path.

### Part A — Source registry

#### Locked decisions

- **D11 — A source is a distinct entity, not implicit from URL.** Explicit `sources` table, stable UUID, `code` slug. Never identify by URL alone.
- **D12 — Named trust tiers** (publish authority lives in `config/publish_policy.yaml`, not in schema):

| Tier | Examples | Default publish authority |
|---|---|---|
| `authoritative` | ADA, FDI, EAO, EuroPerio, IADR, national societies, major publishers | Single-source publish above threshold |
| `verified` | Known industry aggregators, well-maintained sponsor portals | 2+ corroborating verified, OR 1 verified + 1 authoritative |
| `unverified` | Newly discovered, not yet vetted | Cannot publish alone; needs corroboration or admin override |
| `archived` | Retired / unreliable / dead | Observations stored; never feeds publish gate |

- **D13 — Source type orthogonal to trust tier.** Types: `society | sponsor | aggregator | venue | government | media | academic | other`.
- **D14 — `sources` table**:

```
sources
  id uuid PK
  name text not null
  code text unique not null            -- 'ada', 'fdi', 'dentaltown'
  homepage_url text not null
  source_type text not null            -- enum
  trust_tier text not null             -- enum, default 'unverified'
  primary_language text not null       -- ISO 639-1
  country_iso char(2) null
  specialty_roots text[] not null      -- e.g. ['dental']
  specialty_priors jsonb               -- {dental.orthodontics: 0.7, ...}
  crawl_strategy text not null         -- 'rss' | 'sitemap' | 'listing' | 'api' | 'manual'
  crawl_frequency text not null        -- 'daily' | 'weekly' | 'biweekly' | 'monthly'
  crawl_config jsonb not null          -- selectors, pagination, etc.
  -- Capability flags (first-class):
  requires_js boolean
  has_pdf_content boolean
  has_event_listings boolean
  supports_rss boolean
  supports_sitemap boolean
  access_mode text                     -- 'public_html' | 'api' | 'manual_review'
  robots_reviewed_at timestamptz null
  rate_limit_profile text              -- 'polite_10rpm' | 'standard_30rpm' | ...
  is_active boolean default true
  created_at timestamptz
  onboarded_by text                    -- 'seed' | admin user
  notes text
```

Plus history: `source_tier_history(source_id, old_tier, new_tier, changed_at, reason)` and weekly rollup `source_crawl_stats(source_id, week_starting, crawls_attempted, crawls_succeeded, observations_produced, observations_published, extraction_errors)`.

- **D15 — MVP source onboarding = `sources.yaml` seed file + `source_candidates` intake queue.**

```
source_candidates
  id uuid PK
  discovered_url text not null
  discovered_name text null
  inferred_source_type text null
  inferred_language text null
  first_seen_at timestamptz
  discovered_by_job text
  status text                           -- 'pending' | 'approved' | 'rejected'
  notes text
```

Crawler-discovered candidates land here; admin promotes to `sources` via approval flow. **Target for MVP launch: 10–15 curated dental sources.**

- **D16 — Crawl frequency strategy**: `authoritative` (society/gov) weekly; `authoritative` (aggregator) daily; `verified` biweekly; `unverified` monthly; `archived` never. Per-source overridable via `crawl_frequency`. 3 consecutive errors → halve frequency; 10 errors → admin alert.
- **D17 — Source health monitoring**: `source_crawl_stats` weekly rollup. Admin dashboard surfaces liveness, extraction success rate, publishable ratio, tier-fitness warnings.

### Part B — Taxonomy

- **D18 — Hierarchical, versioned, controlled vocabulary** in `taxonomy_specialties`:

```
taxonomy_specialties
  id uuid PK
  code text unique not null            -- 'dental.orthodontics'
  specialty_root text not null         -- 'dental'
  parent_id uuid null
  label text not null
  description text null
  aliases text[]                       -- 'Ortho', 'Orthodontia'
  sort_order int
  version_added int not null
  deprecated_at timestamptz null
  is_active boolean default true
```

- **D19 — MVP dental taxonomy seed** (~20 tags):
  - **ADA-recognized specialties**: `dental.dental_public_health`, `dental.endodontics`, `dental.oral_maxillofacial_pathology`, `dental.oral_maxillofacial_radiology`, `dental.oral_maxillofacial_surgery`, `dental.orthodontics`, `dental.pediatric_dentistry`, `dental.periodontics`, `dental.prosthodontics`, `dental.oral_medicine`, `dental.dental_anesthesiology`
  - **High-value practice areas**: `dental.general_dentistry`, `dental.implantology`, `dental.cosmetic_dentistry`, `dental.digital_dentistry`, `dental.dental_materials`, `dental.prevention_hygiene`, `dental.restorative_dentistry`, `dental.dental_sleep_medicine`, `dental.practice_management`
- **D20 — Specialties are tags, M:N**: `event_specialties(event_id, specialty_id, relevance_0_1, source_observation_id)`.
- **D21 — Topics separate from specialties.** Topics are free-text keywords, indexed in Meilisearch for full-text relevance. **Click-to-search behavior on chips** (not formal facet) preserves discovery without taxonomy explosion.
- **D22 — Hybrid specialty assignment, three-step**:
  1. **Source priors** — per-source specialty weighting (`sources.specialty_priors`).
  2. **Deterministic keyword/alias matching** against `taxonomy_specialties.aliases`.
  3. **Constrained LLM** only when steps 1+2 disagree or yield low confidence.
  LLM cannot invent codes — schema-enforced.
- **D23 — Taxonomy versioning (lightweight)**: `version_added` + `deprecated_at` only. Full rebind/migration tooling post-MVP.
- **D24 — Expansion to medical** = add `medical` specialty_root + new YAML seed; existing dental events stay under `dental.*` (zero migration).

### MVP vs post-MVP

| Item | MVP | Post-MVP |
|---|---|---|
| `sources` + YAML seed + `source_candidates` queue | ✅ | Admin UI for source CRUD |
| Named trust tiers + policy-based publish gate | ✅ | Automated tier adjustment from track record |
| Source capability flags first-class | ✅ | — |
| `source_crawl_stats` weekly rollup | ✅ | Real-time dashboards, alerting |
| YAML taxonomy seed (dental) | ✅ | Admin UI for taxonomy |
| Hybrid specialty assignment | ✅ | Active learning from reviewer corrections |
| Topics as click-to-search chips | ✅ | Topics as controlled hashtags (filter facet) |
| Full taxonomy versioning + rebind | ❌ (deprecated_at only) | ✅ |
| Multi-jurisdiction specialty mapping (US vs EU) | ❌ | ✅ |

---

## 3 — Pipeline data flow

### Stage map

```
sources.yaml + source_candidates
         │
         ▼
   1A page discovery     (RSS/sitemap/listing/API/manual — known sources)
   1B source discovery   (outlinks → source_candidates)
         │
         ▼
   2 fetch               (httpx or Playwright; → R2 raw artifact + content_hash dedup)
         │
         ▼
   2.5 page classify     (event_detail | event_listing | general_info | pdf_brochure | dead | duplicate)
         │
         ▼
   3 extract             (adapter → generic → LLM fallback; observation with per-field confidence)
         │
         ▼
   4 normalize           (dates / currency / geo / language / text; emits parse-status per field)
         │
         ▼
   5 dedupe              (blocker + scorer + hard-negative veto → linked_event_id)
         │
         ▼
   6A canonical merge    (per-field selection + provenance + materialized projection + snapshot)
   6B publish gate       (policy engine → publish | hold)
         │
         ▼
   7 index               (publisher → Meilisearch via canonical_updated channel)
         │
         ▼
   8 history + notify    (field_history writes; user notifications post-MVP)
```

Every stage is **idempotent**, observation-scoped, and isolated. One failure never cascades.

### Stage details (locked)

#### Stage 1 — Discovery (split)

- **1A page discovery**: from approved sources via `crawl_strategy`. Emits `source_pages` for new URLs, upserts last-seen for known URLs.
- **1B source discovery**: outlinks from `source_pages` matching allowed-domain heuristics → `source_candidates` rows for admin review.

#### Stage 2 — Fetch

- **`httpx`** for static HTML (when `requires_js = false`); **`playwright-chromium`** when `requires_js = true`.
- **R2 key scheme**: `sources/{source_code}/pages/{yyyy-mm-dd}/{url_sha256}.{ext}.gz`.
- **Content-hash dedup**: skip downstream stages if hash matches `last_content_hash`.
- **Rate limiting** per `rate_limit_profile`. Exponential backoff on 5xx/timeout; immediate fail on 4xx (except 429).
- PDFs handled via `pypdf` in extraction, not in fetch.

#### Stage 2.5 — Page classification (NEW per refinement)

Heuristic-driven labels: `event_detail | event_listing | general_info | pdf_brochure | dead | duplicate`. Different downstream handling per label. Prevents wasted LLM calls on listing or general pages.

#### Stage 3 — Extract (three-tier)

In order:
1. **Source-specific adapter** — `services/crawler/adapters/{source_code}.py`. Cheapest, most precise.
2. **Generic HTML adapter** — `trafilatura` + `readability-lxml` + heuristic field detection.
3. **LLM structured-output fallback** — Anthropic with JSON Schema constraint matching observation `raw_payload`.

All extractors emit the same observation shape (defined in `packages/schema/source/observation.schema.json`). **Confidence per field is graded, never 1.0** (per refinement):
- Exact source-specific selector: 0.90–0.98
- Brittle selector: 0.70–0.85
- Generic heuristic: 0.55–0.75
- LLM: self-reported confidence

`extractor_version` always recorded. Re-extraction on bump uses archived R2 artifacts.

#### Stage 4 — Normalize

Operations in order: text (NFC, whitespace, entity decode), language detection (`lingua-py`), dates (`dateparser` multilingual + range parsing), currency, geo (country ISO, optional Nominatim geocode for venue), deadlines mapping, enrichment minimal cleanup.

**Per-field parse status emitted alongside values** (per refinement):
- `parsed`
- `normalized_with_assumption`
- `copied_raw_unparsed`
- `failed`

Publisher reads parse status alongside values: a date parsed from "Spring 2027" is *not* the same confidence as "April 12, 2027".

#### Stage 5 — Dedupe (blocker + scorer + hard-negative veto)

**Blocker** (cheap prefilter): same domain or URL canonicalization match; date window ±14 days; title trigram > 0.6.

**Scorer** (config-driven via `config/dedupe_scoring.yaml` — weights are tuning constants, not architecture):
- URL canonicalization match: +0.50
- Title rapidfuzz ≥ 0.85: +0.25
- Date overlap (any day in common): +0.15
- Venue geo distance ≤ 2km: +0.15
- Semantic embedding cosine ≥ 0.88 (pgvector): +0.25

**Hard-negative vetoes** (any one fires → no merge regardless of score):
- Non-overlapping dates >60 days for same-year event
- Different countries with high confidence on both
- Conflicting official registration URLs (both present, different)
- Strongly-conflicting `event_kind` (e.g., webinar vs in-person congress)
- Explicitly different series names (when detected)

**Decision thresholds** (bias toward over-splitting):
- ≥ 0.90: auto-link
- 0.70–0.89: link + admin review (low-priority queue)
- 0.50–0.69: create new event + admin review
- < 0.50: create new event silently

#### Stage 6 — Merge + Publish gate (split)

**6A — Canonical resolution**:
- For each contract-critical field, select value by `weight = trust_tier_weight × field_confidence × recency_decay`.
- Write `event_canonical_fields` provenance + materialize flat columns.
- **Hybrid specialty assignment** (D22): priors → rules → constrained LLM only on ambiguity.
- **Enrichment merge**: single-source adoption; replace prior canonical enrichment for `(event_id)`; insert new.
- **Snapshot**: serialize full canonical record to `events_canonical_snapshots` on every publish.

**6B — Publish policy evaluation**:
- Calls policy engine loaded from `config/publish_policy.yaml`.
- Context: `(event_id, contributing_sources[], field_confidences, admin_overrides)`.
- Decision logged to `publish_decisions` table.

#### Stage 7 — Index

- Subscribes to `canonical_updated` Redis pub/sub (emitted by Stage 6 publisher).
- Builds denormalized Meilisearch document (see §4).
- Batches 50 docs / 5-second windows.
- Delete propagation on `archived` / `merged_into`.

#### Stage 8 — Change detection & notify

- Diffs new vs prior snapshot.
- Writes `event_field_history` for high-signal fields.
- MVP: stores history, rendered as "updated X days ago" in UI.
- Post-MVP: push notifications to subscribed users.

### Orchestration

- **D25 — RQ (Redis Queue) for MVP.** Not Celery, not Temporal, not Prefect. Dependency between stages enforced by handlers (each enqueues next). Per-source concurrency via named worker queues.
- **Migration triggers (documented now)** — promote to Prefect/Dagster when:
  - workflow retries spanning days needed
  - backfill orchestration UI required
  - >3 worker types with dependency complexity
  - frequent manual replay / DAG introspection
  - team size > 2 on pipeline
- **D26 — Adapter protocol** (widened):
```python
class SourceAdapter(Protocol):
    source_code: str
    def discover(self) -> Iterator[CandidateUrl]: ...
    def fetch_config(self) -> FetchConfig: ...                # capability hints
    def classify_page(self, artifact) -> PageClass: ...        # optional
    def fetch(self, url: str) -> RawArtifact: ...
    def extract(self, artifact: RawArtifact) -> Observation: ...
    def normalize_hints(self) -> NormalizeHints: ...           # optional
```
Default `GenericHtmlAdapter` works for most sources; subclasses override where needed.

- **D27 — Re-extraction on extractor version bump** via CLI: `medevents reextract --source ada --since 2025-01-01`. Uses archived R2 HTML.
- **D28 — Idempotency** via natural keys: `(source_page_id, extractor_version)`, `(event_id, observation_id)`.
- **D29 — Error isolation**: per-observation, never per-batch. `pipeline_errors` row written; downstream stages skip cleanly.

### Manual review insertion points (explicit operating model)

Automation with review choke points — not fully automatic:
- Source candidate approval (Stage 1B → `source_candidates.status`)
- Ambiguous dedupe queue (Stage 5, 0.50–0.89 score band)
- Low-confidence specialty tags (Stage 6A, < 0.5 held from publish)
- Publish hold override (Stage 6B, admin override path)
- Source tier review (when publishable ratio drops on `verified`+)

### Tradeoffs accepted

- RQ over Celery/Prefect — less polish, zero learning curve.
- Playwright slow + memory-hungry — pays for sites unreachable via HTTP.
- pgvector over Qdrant — slower at 1M+ vectors, but no extra service.
- Bias toward over-splitting in dedupe — more admin review, safer than false merges.
- Snapshot every publish — storage grows linearly with republishes; forensic trail is worth it.
- LLM extractor per-page — expensive, mitigated by tier ordering.

---

## 4 — Storage + search + caching

### Layer map

```
PIPELINE WRITE                                          PRODUCT READ
     │                                                       │
     ▼                                                       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
│  POSTGRES    │───►│ MEILISEARCH  │    │  REDIS-CACHE         │
│ source-of-   │    │ filter+search│    │  bounded, allkeys-lru│
│ truth +      │    │ + geo + facets│    └──────────────────────┘
│ PostGIS +    │    └──────────────┘    ┌──────────────────────┐
│ pgvector     │                        │  REDIS-QUEUE         │
└──────────────┘                        │  RQ; AOF on; no evict│
     │                                   └──────────────────────┘
     ▼
┌──────────────┐
│   R2         │  raw HTML/PDF; pipeline-only access
│  immutable   │  product NEVER reads R2 directly
└──────────────┘
                                                       ▲
                                              CDN edge ─┘ (Cloudflare front)
```

### Locked decisions

#### Postgres

- **D33 — Single `public` schema**, naming-based separation (`source_*`, `event_*`, `taxonomy_*`, `pipeline_*`, `publish_*`).
- **D34 — Required extensions**: `postgis`, `pgvector`, `pg_trgm`, `unaccent`, `pgcrypto`.
- **D35 — Index inventory (MVP minimum)**: see Appendix B.
- **D36 — Connection pooling**: PgBouncer (Neon-provided) for API in transaction mode, max 25 server-side. Pipeline workers each own a 4–8 connection pool.
- **D37 — Alembic forward-only migrations**, Python-owned, in `db/migrations/`. **Breaking read-model changes follow expand → backfill → switch → contract** (no single-shot destructive migrations — the product API is a contract). Data migrations as numbered scripts.
- **D38 — Retention policy**:

| Table | Retention |
|---|---|
| `event_observations` | Indefinite |
| `events_canonical_snapshots` | Indefinite (compress after N years post-MVP) |
| `event_field_history` | Indefinite |
| `pipeline_errors` | 90 days, daily prune |
| `source_crawl_stats` | Indefinite (weekly rollup, small) |
| `publish_decisions` | **3 years minimum**, snapshot to R2 before delete |
| `source_candidates` (rejected) | 90 days |
| Raw R2 artifacts | Indefinite |
| `admin_audit_log` | 5 years |

#### Meilisearch

- **D39 — Single `events` index**, denormalized document. Document shape:

```json
{
  "event_id": "...",
  "slug": "ids-2027-cologne",
  "title": "...", "summary": "...",
  "starts_on": 20270312, "ends_on": 20270316,
  "country_iso": "DE", "city": "Cologne",
  "format": "in_person", "event_kind": "fair",
  "lifecycle_status": "scheduled",
  "specialty_codes": ["dental.general_dentistry", "dental.digital_dentistry"],
  "specialty_roots": ["dental"],
  "topics": ["CAD/CAM", "digital workflows"],
  "has_cme": true,
  "accreditation_bodies": ["ADA_CERP"],
  "price_min_minor": 50000,            // in price_currency, no FX
  "price_max_minor": 150000,
  "price_currency": "EUR",
  "has_free_tier": false,
  "organizer_names": ["..."],
  "featured_speakers": ["..."],
  "sponsor_names": ["..."],
  "data_confidence": 94,
  "last_verified_at": 1742000000,
  "_geo": { "lat": 50.94, "lng": 6.95 }
}
```

`_geo` is filterable/sortable. `_geoPoint(lat,lng):asc` is a **query-time sort expression**, not a stored attribute.

**Filterable**: `country_iso, city, format, event_kind, lifecycle_status, specialty_codes, specialty_roots, has_cme, accreditation_bodies, price_currency, has_free_tier, starts_on, ends_on, data_confidence`. (No cross-currency price filter at MVP — filter is by `price_currency` first, then by `price_min_minor`/`price_max_minor` within that currency.)
**Sortable**: `starts_on, data_confidence, _geo`.
**Searchable** (ranked): `title > organizer_names > featured_speakers > city > summary > topics > sponsor_names`.

- **D40 — Hand-curated synonyms** in `config/meilisearch_synonyms.json`. Updated from query-log learning.
- **D41 — Update strategy**: incremental via `canonical_updated` channel; full rebuild via `medevents reindex --full` with blue/green alias swap.
- **D42 — Meilisearch is product primary**. **Postgres `tsvector` is admin-only.** Dual path = graceful degradation (Meili down → admin still works).

#### Object storage (R2)

- **D43 — Key scheme**: `sources/{source_code}/pages/{yyyy-mm-dd}/{url_sha256}.{ext}.gz`. Versioning enabled. No lifecycle at MVP.
- **D44 — Access**: pipeline writes + reads only. Product never touches R2 directly. Logos/hero images are re-hosted to a separate `medevents-assets` bucket with CDN access.

#### Caching

- **D45 — Two Redis instances** (per refinement, not one):
  - **`redis-queue`**: RQ only, AOF on, no eviction policy
  - **`redis-cache`**: bounded memory, `allkeys-lru` eviction, no AOF

- App-level cache keys (in `redis-cache`):

| Key | TTL | Invalidation |
|---|---|---|
| `taxonomy:dental:tree` | 5 min | Push on taxonomy update |
| `sources:public:list` | 15 min | Push on source tier change |
| `event:{id}:detail` | 10 min | Push on canonical update |
| `search:facet_counts:{filter_hash}` | 2 min | Natural expiry |
| `rate_limit:{ip}` | 1 min rolling | Natural expiry |

- **D46 — Edge + CDN caching**: Cloudflare in front of Fly. `Cache-Control: public, s-maxage=60, stale-while-revalidate=300` for public GETs. Cloudflare purge API on publish (post-MVP integrates push purge; MVP relies on s-maxage).
- **D47 — Rendering strategy per route** (see also §6):

| Route | Strategy |
|---|---|
| `/` | RSC + ISR (60s) |
| `/events` | RSC initial render via API; client-side filter changes update URL (nuqs) → React Query refetches `/v1/events` + `/v1/facets` from the API. **Browser never talks to Meili directly.** |
| `/events/{slug}` | **ISR + on-demand revalidation in MVP** (publisher webhook → `revalidatePath`) |
| `/specialties/{code}` | ISR (300s) |
| `/map` | Client-side via geosearch |
| `/admin/**` | SSR, no cache |

- **D48 — Client-side**: React Query, 30s default stale time, 5min for taxonomy.

### Backup & DR

| Target | Mechanism | RPO | RTO |
|---|---|---|---|
| Postgres | Neon PITR (7-day) | ~30s | <10min |
| R2 | Versioning on; cross-region post-MVP | N/A | instant |
| Meilisearch | Fully rebuildable from canonical | N/A | minutes at MVP scale |
| Redis-cache | No durable state | N/A | warm up next requests |
| Redis-queue | Job idempotency covers replay | in-flight jobs | worker restart |

### Tradeoffs accepted

- pgvector over Qdrant — migrate at 1M+ vectors.
- Meilisearch self-hosted over Meilisearch Cloud — ops burden vs cost + control.
- Two Redis instances over one — small ops cost; protects queue durability.
- ISR with on-demand revalidation — hybrid; fresh on publish + s-maxage backstop.
- No dedicated read replica at MVP — neither contention path matters at 150–1000 events.

---

## 5 — Product API contract

The **only** surface the product talks to. The **only** surface the data platform exposes.

### Contract philosophy

**In** (product reads): published canonical events + sidecars + enrichment + trust envelope (`data_confidence`, `last_verified_at`, `last_changed_at`, `sources[]`) + `field_history` for high-signal fields + public taxonomy + source directory.

**Out** (product never sees): observations, raw artifacts, extractor versions, source candidates, pending review queues, dedup scores, merge logs, per-field raw confidences, pipeline errors, worker health, any `draft | hold | archived | merged_into` records.

### Locked decisions

- **D49 — REST, not GraphQL.** Hono + typed routes + OpenAPI generation.
- **D50 — Endpoint inventory**:

| Method | Path | Purpose |
|---|---|---|
| **Public** | | |
| GET | `/v1/events` | Paginated list with filters + lightweight preview enrichment |
| GET | `/v1/events/{slug}` | Full detail (canonical + sidecars + enrichment + trust + history) |
| GET | `/v1/events/{slug}/similar` | Simple similarity (specialty + geo + date proximity + event_kind) |
| GET | `/v1/events/map` | Viewport-bounded events with server-side clusters |
| GET | `/v1/facets` | Filter facet counts |
| GET | `/v1/taxonomy/specialties` | Full specialty tree under root |
| GET | `/v1/sources` | Public source directory (with `trust_badge`) |
| GET | `/v1/sources/{code}` | Source detail with `trust_badge` |
| **Admin** (auth required) | | |
| GET | `/v1/admin/events` | Includes draft/hold/low-confidence |
| POST | `/v1/admin/events/{id}/{publish,hold}` | Override (requires `reason`) |
| POST | `/v1/admin/events/{id}/merge` | Force merge into target |
| GET/POST | `/v1/admin/dedupe_queue/...` | Resolve ambiguous |
| GET/POST | `/v1/admin/source_candidates/...` | Approve/reject |
| PATCH | `/v1/admin/sources/{id}/tier` | With reason → `source_tier_history` |
| POST | `/v1/admin/sources` | Add source |
| POST | `/v1/admin/taxonomy/specialties` | Add/deprecate |
| POST | `/v1/admin/revalidate` | Manual cache/CDN purge |

- **D51 — Response envelope** (consistent):

```json
{ "data": {...}, "meta": { "request_id": "...", "generated_at": "..." } }
{ "data": [...], "meta": { ..., "pagination": {...} }, "links": { "next": "...", "prev": null } }
{ "error": { "code": "INVALID_FILTER", "message": "...", "details": {...}, "request_id": "..." } }
```

Error codes (controlled enum): `INVALID_FILTER | VALIDATION_ERROR | NOT_FOUND | GONE | UNAUTHORIZED | FORBIDDEN | RATE_LIMITED | UPSTREAM_ERROR | INTERNAL_ERROR`. `GONE` includes `redirect_to_slug` for merged events.

- **D52 — List item shape** includes lightweight enrichment preview: `featured_speakers_preview` (max 2), `sessions_preview_count`, `sponsors_preview_count`, `has_keynote: bool`, **`lifecycle_status`** (always present so the list UI can render postponed/cancelled badges without a detail fetch), prices in source currency (`price_min_minor`, `price_max_minor`, `price_currency`, `has_free_tier`). Full enrichment detail-only.
- **D53 — Detail shape** includes full enrichment, deadlines, prices (every tier in its source currency, no FX-converted alternative at MVP), accreditations, organizers, speakers (max 8 featured), sessions (max 10 curated), sponsors, `lifecycle_status` plus its `field_history` entries (so the trust panel can render "Postponed 4 days ago" with the prior date). Plus `description_text` AND `description_html`. **HTML is sanitized at publish time** (publisher), allowlist: `p, ul, ol, li, strong, em, br, a` (with `rel="noopener"`); strip styles/classes/scripts/iframes/embeds/event handlers. API serves already-clean HTML.
- **D54 — Map endpoint**: server-side clusters via PostGIS `ST_ClusterKMeans` or Meilisearch geo postprocessing. Client never clusters. 250ms debounce client-side.
- **D55 — Facets endpoint**: powered by Meilisearch `facetDistribution`. Called alongside `/v1/events` on filter changes.
- **D56 — Auth (concrete flow, MVP)**:
  - **Two paths into admin endpoints, never the same credential.**
  - **Path A — service/CLI bearer token.** Long-lived secret, generated once, stored in Fly secrets only. Used by: the `medevents review …` CLI, internal scripts, contract regression tests. Sent as `Authorization: Bearer <token>`. **Browsers never carry this token.** Rotated quarterly; rotation runbook in `docs/runbooks/secret-rotation.md`.
  - **Path B — admin web app session.** Single admin user at MVP. Login flow:
    1. Operator visits `admin.medevents.io/login`, submits email + password.
    2. Server compares password against `ADMIN_PASSWORD_HASH` (Argon2id, stored in Fly secrets).
    3. On success, server creates a session record in `redis-cache` (key `session:{uuid}`, value `{actor: "owner", created_at, expires_at}`, 24h TTL).
    4. Server sets `medevents_admin_session={uuid}` cookie — `HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=86400`.
    5. Subsequent admin requests carry only the cookie. Middleware validates the session, populates `request.actor`, then enforces admin authorization.
  - **CSRF**: SameSite=Strict provides baseline; admin POST/PATCH endpoints additionally require an `X-CSRF-Token` double-submit value rotated per session.
  - **Audit**: every admin action writes `admin_audit_log(actor, action, target, reason, session_id_or_token_id, request_id, occurred_at)`. CLI calls log `token_id`; web calls log `session_id`. Both resolvable to a human via the session/token registry.
  - **Public endpoints** unauthenticated. Rate limit: 60 req/min per IP via `redis-cache` token bucket.
  - **Post-MVP**: Clerk/Supabase user accounts (multi-admin, password reset, MFA via WebAuthn); partner API keys with per-key rate-limit tier and scoped permissions.
- **D57 — Versioning**: URL prefix `/v1/`. Breaking → `/v2/`. N-2 support. Deprecation telemetry via `Deprecation:` header.
- **D58 — OpenAPI assembled (not authored)** per §1's contract source-of-truth model: `@hono/zod-openapi` walks Hono routes (which import payload schemas from `packages/schema/generated/ts/`) and emits `packages/schema/generated/openapi.yaml`. Routes own paths/methods/status codes; payload Zod owns request/response shapes; OpenAPI is the assembled output. Frontend uses `openapi-fetch` against the generated YAML. CI gate fails on drift between regenerated and committed.
- **D59 — Cache headers** per endpoint (covered in §4 D47).
- **D60 — Content negotiation**: JSON only at MVP. Post-MVP: CSV (admin export), RSS, ICS.
- **D61 — `trust_badge`** is a client-friendly label on source detail and event-level source rows: `authoritative | verified | unverified | archived`. Frontend renders directly without remapping.
- **D62 — `/similar` simple in MVP**: (≥1 shared specialty) AND (same country OR within 500km) AND (start date within ±90d) AND (same/compatible event_kind). Limit 6, sorted by overlap score.
- **Contract stability rules for `/v1`**: additive only, no silent removals, no semantic changes to existing fields, nullable additions allowed, enum expansion documented in `docs/api/changelog.md`.

### Tradeoffs accepted

- REST over GraphQL — less client flexibility; better caching, tooling, rate-limit ergonomics.
- List omits full enrichment — second request needed for cards wanting more than 2 speaker previews.
- No public accounts at MVP — saved filters in localStorage; migrate to accounts post-MVP.
- Single bearer token for admin — single operator; rotated quarterly; full audit log.
- No WebSocket/SSE — simpler server; users see updates on next navigation.
- `sources[]` on every detail (~1–2KB) — trust transparency literally is the feature.

---

## 6 — Frontend architecture (bones)

This section covers bones — routes, state model, component organization, design-system foundations, performance posture. **The full visual design language (colors, typography scale, page mockups) is a deliberate separate sub-spec written before Wave 5b**, with the visual companion.

### Locked decisions

- **D63 — RSC by default, client islands by exception.** `"use client"` only when state/refs/browser APIs/event handlers/hooks are needed. Streaming SSR with `<Suspense>` everywhere data is slow.
- **D64 — App router structure** per Section 6 D63 (full tree in conversation; key routes: `/`, `/events`, `/events/[slug]`, `/events/map`, `/specialties`, `/specialties/[code]`, `/sources`, `/sources/[code]`, `/search`, `/api/revalidate`, `/api/og`).
- **D65 — State management three-axis split**:

| Axis | Tool |
|---|---|
| URL state (truth) | `nuqs` |
| Server state | React Query |
| Ephemeral UI state | Zustand |

URL is the source of truth for any state a user might share or bookmark. No global Redux. No event bus.

- **Query-key factory** in `apps/web/lib/query-keys.ts`: `qk.events.list(filters)`, `qk.events.detail(slug)`, `qk.events.facets(filters)`, `qk.events.similar(slug)`, `qk.events.map(bbox, filters)`, `qk.taxonomy.specialties(root)`, `qk.sources.list()`, `qk.sources.detail(code)`. Lint rule blocks raw key arrays.
- **D66 — Three-layer component organization**:
  - `packages/design-system/` — tokens, theme, fonts, Tailwind preset (app-agnostic)
  - `packages/ui/` — Radix-wrapped primitives (app-agnostic)
  - `apps/web/components/` — feature components composing primitives + accessing app data
- **Data-fetching rule**: route-level orchestration is primary. Feature components fetch their own data only when (a) interactive or (b) independently refreshable.
- **D67 — Design system foundations** (values deferred to UI Design sub-spec):
  - Tailwind CSS 4 with custom preset
  - oklch color tokens (light/dark via `data-theme`)
  - Token roles: surface (`bg`, `bg-elevated`, `bg-muted`, `bg-overlay`), foreground (`fg`, `fg-muted`, `fg-subtle`), accent (`accent`, `accent-fg`, `accent-muted`), border (`border`, `border-strong`), status (`success`, `warning`, `danger`, `info` each with `-bg` and `-fg`)
  - Variable sans (Inter / Geist Sans), variable mono for data
  - 4px spacing base, fluid type scale via `clamp()`
  - Lucide icons exclusively
  - Framer Motion for animations; honors `prefers-reduced-motion`
  - **No shadcn/ui copy-paste** — own Radix-wrapped primitives (justifies the work for non-generic premium look)
- **D68 — Filter UX**: `nuqs` URL state; cascading facets; zero-count options grey out (don't disappear); chip strip; mobile bottom-sheet drawer; saved filters in localStorage at MVP.
- **D69 — Map architecture**: MapLibre GL JS with MapTiler/Stadia tiles. **Map provider abstracted** via `MapProvider` interface (init/addSource/addLayer/on/fitBounds) — swappable to Mapbox without app-state changes. Server-side clustering. **`replaceState` during pan/zoom churn; `pushState` only on settled changes** (500ms idle).
- **D70 — Performance posture**:
  - First Load JS budgets enforced in CI (Home ≤100KB, Events list ≤150KB, Detail ≤120KB, Map ≤220KB)
  - Lighthouse ≥ 90 across Performance, Accessibility, Best Practices, SEO on key pages
  - Core Web Vitals targets: LCP < 2.0s, INP < 200ms, CLS < 0.05 at p75
  - `next/image` with AVIF + WebP, sized sources
  - `next/font` with `display: swap`
  - `<Suspense>` wraps slow data; shaped skeletons not generic spinners
  - **Reduced-data posture**: defer map (dynamic import + `navigator.connection.effectiveType` gating); trim animations on slow connections; lower-priority hero images
- **D71 — Accessibility baseline**: WCAG 2.2 AA. Radix primitives provide keyboard/focus/ARIA. Visible focus rings. Color contrast verified in tokens. Map has accessible list alternative. `axe` CI on key pages.
- **D72 — Internationalization**: MVP English-only UI via `next-intl` (single locale active). Route shape `/[locale]/...` reserved. **Multilingual data display-safe from day one**: `lang` attribute on rendered text, source language preserved, "Original language: French" badge when summary differs from UI language.
- **D73 — Testing**: Vitest (units), Playwright (e2e on critical flows), Storybook (`packages/ui/` + `packages/design-system/`), `axe` (a11y).
- **D74 — Telemetry**: Self-hosted Plausible (cookie-free, no consent banner) + Sentry. **Controlled analytics taxonomy** (lint rule blocks events not in registry): `filter_applied | facet_opened | facet_value_selected | event_card_clicked | event_detail_viewed | registration_clicked | source_transparency_opened | source_badge_clicked | map_marker_clicked | map_cluster_clicked | search_performed | similar_event_clicked`.
- **D75 — Admin UI shell**: separate Next.js app (`apps/admin/`), separate domain. Same `packages/ui` + `packages/design-system`. **Auth model per §5 D56 Path B** — login form → Argon2id password check → server-side session in `redis-cache` → `HttpOnly; Secure; SameSite=Strict` cookie carrying only the session UUID (never a service credential). CSRF via double-submit token. Browser never sees the long-lived bearer token (that lives in Fly secrets, used by CLI/scripts only).
  - **Scope progression:**
    - W4 (thin surface): dedupe queue resolver, source-candidate review, publish hold/override.
    - W7 (full surface): + source tier change, raw observation inspector, AI-assisted surfaces (D75b).
  - Inspector components stay in `apps/admin/components/inspectors/` — never absorbed into `packages/ui`.

- **D75b — AI surfaces in MVP** (honors `feedback_ai_everywhere` from `docs/guidelines.md` — no manual-only inputs ship without an AI assist):

| Surface | Where | What |
|---|---|---|
| **AI event summary** | Detail page, when source `description_text` < 200 chars or missing | Claude generates a 3-sentence factual intro from `(title, dates, venue, format, specialties, organizers)`. Cached on `events_canonical`; regenerated on republish. UI labels it "AI summary". |
| **Empty-state intelligence** | Events list when results = 0 | Claude proposes 2–3 filter relaxations from the active filter set ("Try removing the country filter, or extending dates to Q1 2028"). Each suggestion is a one-click apply button. |
| **AI source candidate triage** | Admin source-candidate review (W7) | Claude pre-fills inferred `source_type`, `primary_language`, `specialty_roots`, suggested `trust_tier` with rationale. Admin reviews + accepts/edits. |
| **AI dedupe explanation** | Admin dedupe queue (W4 thin surface, expanded W7) | When admin opens a 0.50–0.89 candidate pair, Claude generates a one-paragraph "same / different / why" explanation grounded in the two observations. Admin still decides. |
| **AI publish-hold briefing** | Admin publish-hold queue (W7) | For each held event, Claude summarizes "reasons to publish" + "reasons to hold" from contributing observations + policy decision log. |

  All AI surfaces have a non-AI fallback (raw text, blank state, manual-only input) so they degrade gracefully if Claude is down or rate-limited. AI output is always labeled. Token spend tracked per surface in §7 dashboards.

### Empty states (first-class architecture)

Designed and built for: no results / no map results in viewport / no sessions-speakers-sponsors / sparse source transparency / filters too narrow. Each gets a shaped state with copy + suggested next action (e.g., "Try removing the country filter" with one-click apply). The "no results" state is also where the **AI empty-state intelligence** surface (D75b) renders.

### Tradeoffs accepted

- MapLibre over Mapbox — less polish, free, no vendor lock.
- No shadcn/ui — higher upfront design effort, non-generic look.
- URL-as-truth filters — long URLs at extreme filter counts; shareability + back-button correctness wins.
- English-only at MVP — addressable market constrained, shipping faster.
- Self-hosted analytics — ops cost, privacy-first.
- Admin as separate app — more deployment, full surface separation.

---

## 7 — Observability, evals, quality discipline

Three pillars that keep the platform world-class over time.

### Pillar 1 — Observability

- **D76 — OpenTelemetry from day one** for traces + metrics + structured logs. Backend: **Grafana Cloud free tier** at MVP (10k metrics, 50GB logs, 50GB traces). Vendor-portable via OTel.
- **D77 — Distributed tracing**: trace ID at discovery, propagated through all stages. Spans carry `source_code, source_page_id, event_id, extractor_version, observation_id, decision`. Single click from "wrong dates on this event" → exact trace that produced it.
- **D78 — Structured JSON logs**: `structlog` (Python), `pino` (Node). Correlation via `request_id` / `trace_id`.
- **D79 — Two distinct dashboard families** (different audiences, different decisions):
  - **Platform correctness**: extraction accuracy, dedupe quality, publish lag, source health, API latency.
  - **Product usefulness**: search success rate, no-result rate, filter abandonment, detail-view-to-registration-click rate, source transparency click rate.
- **D80 — Alerts (small ruthless set)**:

| Alert | Trigger |
|---|---|
| API down | Health check fails 3× in 60s |
| Pipeline stalled | Zero published events in 24h despite enqueued work |
| Indexer lag | `canonical_updated → Meili` lag > 10min for 30min |
| Source down | 7+ consecutive failed crawls on `authoritative` source |
| LLM spend spike | Daily spend > 2× rolling 7d average |
| LLM fallback share spike | 7-day rolling LLM-tier fallback for any source jumps > 20pp from baseline |
| Postgres saturation | Active connections > 80% of limit for 5 min |
| Review queue backlog | Median age of unresolved review items > 14 days |

**Production synthetic failures page; staging synthetic failures log only.**

- **D81 — Synthetic monitoring**: hourly Playwright run from a separate Fly machine.
- **LLM fallback rate quality budget**: per-source-type targets (`society` ≤25%, `aggregator` ≤15%, `sponsor` ≤30%). Sudden shifts → alert (likely site redesign or adapter breakage).
- **Human-review queue health metrics**: dedupe queue size, source-candidate queue size, average age of unresolved items, publish-hold items > 7 days.

### Pillar 2 — Evals

- **D82 — Eval harness** in `evals/` (Python). CLI: `medevents eval --suite extraction --extractor v3`. Reports per-field metrics with regression flagging.
- **D83 — Eval suites and gating**:

| Suite | What | Gate (MVP) |
|---|---|---|
| Extraction | per-field precision/recall vs golden labels | Warn-only; CI gate post-MVP at stable thresholds |
| Dedupe | correct link / split / flag vs golden pairs | Warn-only |
| Specialty | tag precision vs hand-labeled events | Warn-only |
| Publish gate policy | correct publish/hold vs synthetic source mixes | Run before policy YAML edits |
| End-to-end smoke | crawl known source → verify event published | Nightly on staging |
| **Source canary pages** | 1–2 fixed pages per major source, expected-output snapshots | **Run on every extractor/adapter PR** |

- **D84 — Golden dataset growth**: ~50 hand-labeled at MVP; grows to 150 by W8. Every admin-resolved dedupe ambiguity, every corrected specialty tag, every publish-hold override → automatically appended.
- **D85 — Per-field metrics** (not aggregate). Regressions surface with file-level traces.
- **D86 — LLM eval discipline**: snapshot LLM outputs in evals (deterministic, free re-runs). Re-bake on prompt/model upgrades with diff review. `prompt_version` tracked.

### Pillar 3 — Quality discipline

- **D87 — CI pipeline (per PR)** — see Appendix C.
- **D88 — Pre-commit hooks**: `pre-commit` framework with ruff/prettier/eslint/tsc/conventional-commits/detect-secrets/no-direct-main-commit.
- **D89 — Branch protection**: `main` requires PR + green CI. Solo-friendly (self-merge with PR template checklist).
- **D90 — Coverage targets** (sober): `services/{normalizer,deduper,publisher}/` 70%; `apps/api/` route handlers 80%; `apps/web/` no threshold (Playwright covers critical flows); `packages/schema/` 100%.
- **D91 — Performance budgets enforced in CI** (per §6 D70 + bundle thresholds).
- **D92 — Security baseline**:
  - HTTPS-only + HSTS preload-eligible
  - CSP headers — strict (`default-src 'self'`, explicit allowlists). **Report-only first 2 weeks post-launch**, then enforce.
  - Subresource Integrity for any CDN-loaded JS (none MVP)
  - Admin domain isolation, SameSite=Strict, IP allowlist when feasible
  - Secrets in Fly secrets only
  - Scoped tokens (Anthropic with usage cap, R2 bucket-scoped, Neon role-scoped)
  - `admin_audit_log` 5-year retention
- **D93 — Runbooks in `docs/runbooks/`** (8 baseline at MVP):
  - `dr.md` (disaster recovery)
  - `source-onboarding.md`
  - `source-tier-change.md`
  - `index-rebuild.md`
  - `migration-rollout.md` (expand → backfill → switch → contract)
  - `incident-response.md`
  - `extractor-version-bump.md`
  - `secret-rotation.md`
- **D94 — Definition of Done** (per PR):
  - All CI green
  - Tests added (or rationale)
  - E2E added if user-facing
  - Eval impact assessed if pipeline-touching (PR description includes eval delta)
  - Documentation updated (per `feedback_documentation` discipline)
  - Migrations applied to staging clean
  - Lighthouse + bundle budgets if web-touching
  - Reviewer (or self) walked diff against the spec section it implements
- **D95 — Critical-incident triggers** — each forces a post-mortem in `docs/postmortems/YYYY-MM-DD-{slug}.md`:
  - Wrong published date (off ≥1 day after publish)
  - Broken registration URL on a published event
  - Indexing lag silently exceeded threshold > 1 hour
  - Admin override misuse (no/vague reason)
  - Source tier wrongly elevated causing bad publish decisions
  - Pipeline outage > 4 hours
  - Product outage > 15 minutes
  - Data leak / security event of any size
- **D96 — API contract regression suite** in `apps/api/test/contract/` — snapshot/schema-level assertions on `/v1/events`, `/v1/events/{slug}`, `/v1/facets`, `/v1/sources/{code}`. Catches semantic shape drift even when generated types still type-check.
- **Spec / plan / docs as living artifacts**: every architectural change updates `docs/state.md` and the relevant section of this spec.

### Tradeoffs accepted

- Grafana Cloud free tier may not last — migration is endpoint swap + dashboard re-import (~1 day).
- Evals warn-only at MVP — risk of regression slip; mitigated by PR comment surfacing eval delta.
- No on-call rotation at MVP — solo, single point of presence; synthetic + email/push alerts.
- CSP report-only first 2 weeks — risk of missed XSS surface; aggressive staging testing.
- No UI coverage threshold — Playwright critical flows + axe + Lighthouse + Storybook matter more.
- Solo post-mortems — discipline argument; keeps you honest 3 months later.

---

## 8 — Build sequence

### Guiding principles

- **D97 — Vertical slices, not horizontal layers.** Each wave produces a working end-to-end demoable thing.
- **D98 — Risk-first ordering**: extraction quality → dedup correctness → premium UI → coverage breadth.
- **D99 — Two streams, architecturally parallel + operationally interleaved**: Stream A (data platform: W1→W2→W3→W6) and Stream B (product: W4→W5→W7) re-converge at W4 (API contract) and W8 (pre-launch). Solo founder switches in focused blocks at clean boundaries — never daily bouncing.
- **D100 — Sub-specs just-in-time**, not all upfront. Schedule in Appendix D.
- **Wave exit criteria**: a wave is done only if demo works AND docs updated AND runbook impact handled AND tests added AND rollback/recovery path understood.

### Waves

| # | Weeks | Goal | Stream |
|---|---|---|---|
| **W0** | 0 | Foundation: git+CI+monorepo+local dev+Grafana Cloud bootstrap | Both |
| **W1** | 1–2 | Schema + storage; Alembic migrations; YAML seeds | A |
| **W2** | 3–5 | End-to-end pipeline for ADA only (discover → fetch → classify → extract → normalize → observation). + **second-source smoke test** in last days. + **minimal observability** (Sentry + structured logs + basic OTel). | A |
| **W2 gate** | end of W2 | **Kill/redesign checkpoint**: extraction quality good enough? LLM fallback cost acceptable? Manual cleanup tolerable? Source model viable? If any "no" → pause and redesign. | — |
| **W2.5** | end of W2 | **Abstraction review**: what's source-specific, what's generic, what's premature, what broke when second source was tried. | — |
| **W3** | 6–7 | Dedup + canonical merge + publish (5+ published ADA events with full provenance). **Hardened review CLI** ships here: `medevents review {dedupe,source-candidates,publish-holds,specialty-tags}` with structured input/audit-log writes. | A |
| **W4** | 8–9 | Read API + Meilisearch indexer; OpenAPI emitted; contract regression tests. **+ Thin admin web surface** (`apps/admin/` minimal pages): dedupe queue resolver, source-candidate review, publish hold/override. Same auth + audit-log path that W7 will extend. Honors the admin-priority guideline without delaying the public product. | B |
| **W5a** | 8–9 (parallel start) | UI Design sub-spec — visual companion | B |
| **W5b** | 9–11 | Next.js scaffold; Tailwind tokens from sub-spec; primitives; routes; filters; map; trust panel; Lighthouse green | B |
| **W5c** | 11 | On-demand revalidation wired (publisher → `/api/revalidate`) | B |
| **W6** | 12 | Comprehensive observability: dashboards (two families), alerts wired, eval suites, source canaries, LLM fallback dashboard, review-queue health | A |
| **W7** | 13–14 | Admin app **expanded** beyond W4 thin surface: source tier change, raw-observation inspector, AI-assisted source candidate auto-classification, dedupe LLM-explanation, publish-hold AI briefing (see §6 D75b). | B |
| **W8** | 15–16 | Pre-launch: 9 more sources, 150 events, hand-review first 50, performance + security passes, DR rehearsal, all 8 runbooks. **Last 5–7 days = launch freeze** (bug fixes / data quality / runbooks / security / DR / polish only). | Both |

**Review tooling progression** (honors `feedback_admin_priority` from `docs/guidelines.md`):
- **W2** — ad-hoc SQL views + Jupyter notebooks for inspection only.
- **W3** — hardened review CLI (`medevents review …`) with structured commands, dry-run mode, and audit-log writes. Operationally complete enough that admin can resolve dedupe / source-candidate / publish-hold work without the web UI.
- **W4** — thin admin web surface (same `apps/admin/` codebase) covering the W3 CLI commands clickable + visible. Same auth, same audit log.
- **W7** — full admin app: source tier changes, observation inspector, AI surfaces (D75b).

The admin priority is satisfied by the W3 CLI being production-quality, not by deferring the web UI. The web UI lands in W4 — clickable from the moment there are events to admin.

### "MVP done" criteria (D101 — explicit)

| # | Criterion |
|---|---|
| 1 | ≥150 published dental events |
| 2 | From ≥10 distinct sources |
| 3 | Sources span **≥3 source types** (society + aggregator + sponsor at minimum) |
| 4 | Publishable ratio ≥70% on `verified`+ tier sources (not just count, also trust) |
| 5 | First 50 events hand-reviewed; ≥95% canonical fields correct |
| 6 | Filtered browsing works on desktop + mobile (Playwright passes both viewports) |
| 7 | Map renders with clusters; viewport-driven filtering works |
| 8 | Source transparency renders on every event |
| 9 | Trust badges + confidence visible |
| 10 | Lighthouse ≥90 on home/list/detail/map |
| 11 | Eval extraction precision ≥90% on golden set |
| 12 | Admin can resolve dedupe ambiguities + approve sources |
| 13 | All 8 baseline runbooks exist |
| 14 | DR rehearsal completed once |
| 15 | OTel traces visible in Grafana for every pipeline run |
| 16 | Synthetic monitoring runs hourly + alerts on failure |
| 17 | Public site deployed at production domain over HTTPS with HSTS |
| 18 | `lifecycle_status` extraction validated on golden set; postponed/cancelled events render with visible status banner + prior-value history |
| 19 | All prices displayed in source's original currency; no implicit FX shown anywhere |

Anything less = not MVP. No "soft launch" with broken pieces.

### Timeline

- **Best case**: 16 weeks
- **Realistic planning range**: **18–24 weeks**

Source weirdness, extraction surprises, frontend polish drag, deployment friction, and review/labeling time all expand the timeline. The sequence is correct; the uncertainty is in dwell time per wave.

### Post-MVP roadmap (first 6 months after launch)

| Month | Focus |
|---|---|
| 1 | Monitor + bug fix; observe user behavior; tune dedupe weights, fallback thresholds, source tier policies on real data. No new features. |
| 2 | Expand to 500 events / 25 sources; 4+ new source adapters; promote evals from warn-only to CI-blocking. |
| 3 | User accounts (Clerk/Supabase); saved filters server-side; deadline / new-event alerts via email. |
| 4 | Multi-locale (FR, DE, ES) — UI + machine-translated summaries. |
| 5 | Begin medical specialty expansion (cardiology pilot — proves namespace strategy). |
| 6 | Partner API (scoped tokens + rate-limit tier); RSS/ICS exports; sponsor/intelligence post-MVP exploration. |

### Tradeoffs accepted

- One source through W2 before scaling — feels slow; pays off when every other source onboards faster.
- UI Design sub-spec starts ~W5a (end of W3) — design against real data shape, not speculation. Visual companion earns its keep here.
- Evals warn-only through W6 — promote to CI gate post-launch with stable thresholds.
- Admin web surface arrives in W4 (thin), expanded in W7 (full + AI surfaces). Hardened review CLI ships in W3. Admin priority is satisfied throughout — never a "no admin until W7" gap.
- Observability comprehensive in W6, after W5 — minimal observability ships from W0.
- Public launch with 10 sources / 150 events — every event hand-reviewed; trust earned per piece.

---

## 9 — Open questions / known unknowns

These are not blocking the architecture — flagged for resolution in the relevant sub-spec or post-launch decision:

1. **R2 vs S3 vs Backblaze B2** — picked R2 for egress cost; verify rate-limit tolerance with real Playwright traffic in W2.
2. **Meilisearch scale ceiling** — comfortable to ~5M events. If post-MVP coverage growth blows past, Typesense is the swap target.
3. **Specialty alias coverage in non-English sources** — extractor `aliases[]` are English-first; international sources may need locale-specific alias lists. Resolve in Sub-spec: Pipeline (W2) or post-MVP i18n wave.
4. **Source onboarding velocity post-MVP** — at YAML-PR-per-source pace, scaling to 500 sources is ~25 PRs. Tolerable or do we need the admin UI sooner? Decide post-Wave 8.
5. **LLM model selection** — Anthropic chosen; revisit if Claude pricing shifts or if Gemini/OpenAI demonstrably better on extraction evals.
6. **Time-to-publish target** — what's an acceptable lag from new event existing on a source to appearing on MedEvents? MVP target: <7 days. Post-MVP target: <24 hours. Verify in W6 instrumentation.
7. **Revalidation webhook on Vercel/Fly multi-instance** — Next.js cache is per-instance by default; if we run >1 instance, need a shared cache handler or accept brief inconsistency.

---

## Appendices

### Appendix A — Glossary

- **Canonical record**: the merged, published, product-facing event in `events_canonical`. Source of truth for the product API.
- **Observation**: an extracted record from one source page at one extraction run, in `event_observations`. Append-only; immutable.
- **Provenance**: per-field record of which observation contributed which value, in `event_canonical_fields`.
- **Snapshot**: full canonical record at a point in time, in `events_canonical_snapshots`. Forensic trail for republishes.
- **Trust tier**: named tier on `sources.trust_tier` — `authoritative | verified | unverified | archived`.
- **Trust badge**: client-friendly label exposed to product, mirrors `trust_tier`.
- **Publish gate**: policy engine evaluating whether a canonical record may transition `draft → published`.
- **Source canary**: 1–2 fixed pages per major source with expected-output snapshots; checked on every extractor PR.
- **Enrichment**: lightweight event-scoped data (sessions, speakers, sponsors). Non-blocking; single-source adoption.
- **Vertical slice**: a build wave that produces a working end-to-end demoable thing, not a horizontal layer.

### Appendix B — Postgres index inventory (MVP minimum)

```sql
-- Core lookup
CREATE UNIQUE INDEX ix_events_canonical_slug ON events_canonical(slug);
CREATE INDEX ix_events_canonical_status_starts_on ON events_canonical(status, starts_on);
CREATE INDEX ix_events_canonical_country_starts ON events_canonical(country_iso, starts_on);

-- Geo
CREATE INDEX ix_events_canonical_venue_geo ON events_canonical USING GIST(venue_geo);

-- Admin full-text (Postgres FTS — admin only per §4 D42)
CREATE INDEX ix_events_canonical_search_vector ON events_canonical USING GIN(search_vector);

-- Specialties
CREATE INDEX ix_event_specialties_specialty_event ON event_specialties(specialty_id, event_id);
CREATE INDEX ix_event_specialties_event ON event_specialties(event_id);

-- Pipeline
CREATE UNIQUE INDEX ix_event_observations_page_extractor
  ON event_observations(source_page_id, extractor_version);
CREATE INDEX ix_event_observations_linked_event ON event_observations(linked_event_id);
CREATE INDEX ix_source_pages_content_hash ON source_pages(content_hash);

-- Provenance
CREATE UNIQUE INDEX ix_event_canonical_fields_event_field
  ON event_canonical_fields(event_id, field_name);
```

Add per-table `created_at` indexes where admin sorts by recency. Add more as profiling reveals hot spots — don't prematurely index.

### Appendix C — CI pipeline (per PR)

| Job | Tools | Blocks merge? |
|---|---|---|
| Python lint + type | ruff format-check, ruff check, mypy --strict | ✅ |
| TS lint + type | eslint, prettier check, tsc --noEmit | ✅ |
| Python unit tests | pytest | ✅ |
| TS unit tests | vitest | ✅ |
| Schema codegen drift | regenerate, diff vs committed | ✅ |
| OpenAPI drift | regenerate, diff vs committed | ✅ |
| Migration smoke | alembic upgrade head against ephemeral PG | ✅ |
| API contract regression | snapshot assertions on key endpoints | ✅ |
| E2E (PR preview) | Playwright critical flows | ✅ |
| Lighthouse CI | thresholds ≥90 | ✅ |
| Bundle size budget | next-bundle-analyzer thresholds | ✅ |
| Eval suite | extraction + dedupe + specialty + canaries | ❌ MVP (warn-only); ✅ post-MVP |
| `axe` accessibility | on built pages | ✅ no new violations |
| Dependency audit | pnpm audit, pip-audit | ⚠ warn-only; manual review for criticals |
| License audit | license-checker, pip-licenses | ✅ no GPL leakage |

Path-scoped: PRs touching only `services/*` skip TS jobs; vice versa.

### Appendix D — Sub-spec writing schedule

| Sub-spec | Written before | Brainstorm depth |
|---|---|---|
| Schema sub-spec | W1 | Medium |
| Pipeline sub-spec | W2 | Deep |
| Dedup + Publisher sub-spec | W3 | Deep |
| API + Indexer sub-spec | W4 | Medium |
| **UI Design sub-spec** | W5a (parallel from end-W3) | **Deep — visual companion** |
| Frontend implementation sub-spec | mid-W5 | Medium |
| Observability sub-spec | W6 | Light |
| Admin app sub-spec | W7 | Medium |
| Pre-launch sub-spec | W8 | Light (checklist) |

### Appendix E — Configuration file inventory

Configs live in `config/` (YAML, version-controlled, PR-reviewable):

- `config/sources.yaml` — source registry seed
- `config/taxonomy_specialties.yaml` — dental taxonomy seed
- `config/publish_policy.yaml` — publish gate rules (trust-tier authority, exceptions, manual override paths)
- `config/dedupe_scoring.yaml` — blocker, scorer weights, hard-negative vetoes (eval-driven tuning constants)
- `config/meilisearch_synonyms.json` — synonyms (curated from query logs)
- `config/rate_limit_profiles.yaml` — per-tier rate limit definitions

### Appendix F — Decision register summary

100+ locked decisions, organized by section. Each `D{N}` decision in the spec body is canonical. Sub-specs reference these by number.

---

## Status & next steps

| Step | State |
|---|---|
| Automated directory MVP spec | ✅ Active build spec |
| Target-state platform spec | ✅ Reference only |
| User direction update | ✅ Captured |
| Wave 0 — Setup decision | ⏳ Next |
| Wave 1 implementation planning | ⏳ Next, based on the automated directory MVP spec |
| Intelligence-platform planning | ❌ Deferred until justified |

This spec is the **target-state architecture overview**. The active build direction is the lean automated directory MVP, with future platform complexity added only when real MVP pain justifies it.
