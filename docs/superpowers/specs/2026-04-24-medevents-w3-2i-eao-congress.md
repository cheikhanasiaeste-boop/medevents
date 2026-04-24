# W3.2i — Fifth Curated Source: EAO Congress

Date: 2026-04-24
Status: implemented in this wave

## 1 — Why this wave

W3.2d live deployment is still blocked on Fly billing/payment setup. The best autonomous next move is to add the next named curated source from the source-curation plan: `eao_congress`.

This wave stays narrow:

- source-specific parser, not generic fallback
- one association hub page plus one edition-specific detail page
- current-value bias: ship the 2026 Lisbon congress with two-source enrichment while also capturing the 2027 and 2028 future congress cards already exposed on the hub

## 2 — Source contract

- Source code: `eao_congress`
- Parser name: `eao_congress`
- Hub URL: `https://eao.org/congress/`
- Detail URL: `https://congress.eao.org/en/`
- Registration URL: `https://congress.eao.org/en/congress/registration`
- Organizer: `European Association for Osseointegration`

Expected event rows from the current live hub:

- `EAO Congress 2026` — Lisbon, Portugal — `2026-09-24` → `2026-09-26`
- `EAO Congress 2027` — Madrid, Spain — `2027-09-23` → `2027-09-25`
- `EAO Congress 2028` — Amsterdam, Netherlands — `2028-10-19` → `2028-10-21`

## 3 — Required behavior

### 3.1 discover()

- Yield the hub URL first as `page_kind='listing'`.
- Yield the 2026 microsite homepage second as `page_kind='detail'`.

### 3.2 fetch()

- Use the standard `fetch_url()` path with the normal MedEvents user-agent.
- Compute a parser-scoped normalized `content_hash` for the hub URL only.
- Hub normalization strips:
  - the rotating `current_date` / `start_date` / `end_date` values injected by WordPress Simple Banner
  - the rotating LiteSpeed cache footer comment
- The microsite homepage can use raw-body hashing unchanged.

### 3.3 parse() — hub page

The hub page may yield up to three `ParsedEvent`s:

- current congress card: `EAO Congress: Lisbon 26`
- future congress card: `EAO Congress 2027 in Madrid`
- future congress card: `EAO Congress 2028 in Amsterdam`

Required classifier for the page itself:

- `content.url` matches the hub URL
- page `<title>` matches the live congress-hub title exactly

Required extraction behavior:

- The Lisbon card yields `EAO Congress 2026`.
- If the registration URL is present on the hub, attach it to the 2026 row.
- The Madrid and Amsterdam cards yield separate future rows when their title/date signals are present.
- Missing future cards do not invalidate the rest of the page.

### 3.4 parse() — 2026 detail page

The detail page yields exactly one `ParsedEvent` only when all of the following hold:

- `content.url` matches the 2026 microsite homepage
- page `<title>` is `Homepage | Eaocongress 2026`
- body text contains the Lisbon welcome signal
- body text contains the sentence announcing the 33rd annual congress in Lisbon from 24 to 26 September 2026
- a link resolves to `https://congress.eao.org/en/congress/registration`

The yielded event must carry:

- title `EAO Congress 2026`
- city `Lisbon`
- country_iso `PT`
- registration_url `https://congress.eao.org/en/congress/registration`

### 3.5 canaries

- The microsite `programme/detail` page must yield zero events even if served at the microsite homepage URL.
- The hub hash normalizer must collapse both rotating banner timestamps and the LiteSpeed footer timestamp.

## 4 — Pipeline expectations

First run against the seeded source:

- `fetched=2`
- `skipped_unchanged=0`
- `created=3`
- `updated=1`
- `review_items=0`

Post-run DB shape:

- three `events` rows (`2026`, `2027`, `2028`)
- four `event_sources` rows total
- the 2026 row has two `event_sources` rows (hub + detail)

Final unchanged run after the normalization fix is stored:

- `fetched=2`
- `skipped_unchanged=2`
- `created=0`
- `updated=0`
- `review_items=0`

## 5 — Test plan

- 6 parser unit tests:
  - discover order
  - reversed seed order still yields hub first
  - hub page yields three events
  - detail page yields the 2026 event with registration URL
  - programme canary yields zero
  - hub normalization collapses both timestamp sources
- 2 DB-gated pipeline tests:
  - first run creates three events + four event_sources
  - second unchanged run skips both pages

## 6 — Done criteria

This wave is complete when:

1. `config/sources.yaml` contains `eao_congress`
2. parser is registered and import-stable
3. parser + pipeline tests pass locally
4. repo-wide ingest suite passes on the final code
5. live smoke against the official EAO hub + 2026 microsite succeeds on first run and unchanged re-run
6. `docs/TODO.md` and `docs/state.md` reflect five curated sources while keeping W3.2d as the only required blocker
