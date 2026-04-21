# W2 Done Confirmation

Date: 2026-04-21
`main` at: `061a7de` (Phases 1-8 shipped + Sitecore content-hash fix + ruff hook bump)

Against [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](../superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md) §9:

1. ✅ `medevents-ingest run --source ada` completes cleanly from a fixed seed configuration. First live run output: `source=ada fetched=2 skipped_unchanged=0 created=6 updated=0 review_items=0`.
2. ✅ Unchanged ADA pages skipped via `content_hash`. The initial implementation hashed the raw HTML body, which failed for ADA because the site is served by Sitecore and embeds rotating per-request tracking attributes (`data-sc-page-name='...'`, `data-sc-item-uri='sitecore://web/{UUID}?lang=en&ver=N'`, JS `itemUri`) that change on every request. Fix landed in commit `7a6cce5`: the ADA parser strips these attrs before hashing, leaving the raw body for parsing unchanged. Verified by three consecutive live runs: first post-fix run re-hashed to the new stable value (`updated=6`), then `skipped_unchanged=2 created=0 updated=0` on every subsequent run.
3. ✅ At least one Scientific Session event and multiple live CE rows landed. The first live run created:
   - `ADA 2026 Scientific Session` — `2026-10-08` to `2026-10-10`, Indianapolis, US, conference, in_person
   - `Travel Destination CE: Pharmacology…` — `2026-09-08` to `2026-09-16`, Umbria, IT, training, in_person, engage.ada.org registration URL
   - `Travel Destination CE: Pharmacology…` — `2026-10-29` to `2026-11-06`, Barcelona, ES, training, in_person, engage.ada.org registration URL
   - `Botulinum Toxins, Dermal Fillers, TMJ Pain Therapy and Gum Regeneration` — three occurrences (`2026-06-12`/`13`, `2026-09-11`/`12`, `2026-11-06`/`07`), US, workshop, in_person
4. ✅ Second run updates existing events instead of duplicating them. Dedupe by (source_id, normalized_title, starts_on), fallback to (registration_url + starts_on) when an external URL is present. Zero duplicates created across repeated runs.
5. ✅ Non-event ADA pages ignored. `test_parse_non_event_hub_yields_nothing` covers the CE hub; the CE sub-page classifier correctly rejects `/education/scientific-session/continuing-education` (substring match excluded in `_is_scientific_session_landing`).
6. ✅ Broken / ambiguous rows become `review_items`:
   - Listing page that parses zero events → `parser_failure` (template-drift catcher).
   - Fetch error (non-2xx or network) → `source_blocked` with stderr string.
   - Individual rows with unparseable dates return `None` from `_row_to_event` and are silently dropped (a conservative choice — spec §7 allows this for rows-missing-data but note that an ambiguous-year row for a future W2.1 hardening could also land in `review_items`).
7. ✅ Fixture tests cover the known page shapes: 10 tests in [`services/ingest/tests/test_ada_parser.py`](../../services/ingest/tests/test_ada_parser.py) covering listing fan-out, date-range extraction, external registration + location extraction, scientific-session detail, non-event hub, discover() seed URLs, unknown-page zero, and the Sitecore-hash normalizer.

## Local verification performed for this confirmation

| Gate           | Command                                                                                     | Result                                                                                                                                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TypeScript     | `make lint && make typecheck && make test`                                                  | ✅ all green                                                                                                                                                                                                       |
| Python         | `cd services/ingest && uv run pytest tests/ -v`                                             | ✅ 27 normalize + 10 ada_parser + 3 fetch + 3 cli + 5 parser_registry + DB-gated tests skip-or-pass in CI; `uv run mypy medevents_ingest` clean; `uv run ruff check .` clean; `uv run ruff format --check .` clean |
| Live ADA smoke | `DATABASE_URL=... uv --directory services/ingest run medevents-ingest run --source ada` × 3 | ✅ first run `created=6`; subsequent runs `skipped_unchanged=2 created=0 updated=0`                                                                                                                                |

## Shipped CI state

Three required checks on `main` passing throughout every Phase PR:

- `TypeScript (lint + typecheck + unit tests)`
- `Python (ruff + mypy + pytest)`
- `Drizzle schema drift check`

## Known intentional deferrals for W3+

- **Dry-run mode** — `--dry-run` returns exit 4 ("not yet implemented, W3"). The flag is documented but the implementation is deferred.
- **Generic fallback parser** — still W3.
- **Cross-source dedupe** — W2 is source-local-only by design; cross-source merging is W3.
- **Stale-event sweep** — W3.
- **Source-health visibility beyond `last_*` columns** — W5.
- **Second-source onboarding (`gnydm` etc.)** — deferred behind ADA proving stable in real operation.

W2 is complete. Next: either a second-source smoke (gnydm) or the W3 generic fallback, per the W2 prep plan §10.
