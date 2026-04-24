# MedEvents TODO

_Last updated: 2026-04-24 — W3.2o (`forum_officine_tn`) shipped end-to-end; mainline now has eleven curated sources, Playwright option D, clean DB-test hygiene, and Node 24 workflows. The only required next step is still W3.2d live Fly deploy, and the blocker remains Fly billing/payment setup._

## Now

**Primary open track:**

### Track A (operator-gated) — W3.2d live deployment

Repo artifacts on `main`:

- `services/ingest/Dockerfile` — multi-stage Python 3.12 + uv image; default CMD = `medevents-ingest run --all`.
- `fly.toml` at repo root — scheduled machine config, hourly wake, 256MB / shared CPU.
- `docs/runbooks/w3.2d-fly-scheduler-deploy.md` — step-by-step operator runbook.
- `docs/runbooks/w3.2d-done-confirmation.md` — skeleton the operator fills in after the first autonomous run.

**Operator action required** (not autonomously runnable — needs Fly.io account + billing + credentials):

Attempted on 2026-04-23 and re-checked on 2026-04-24: `fly auth login` + `fly auth whoami` succeed locally, but `fly apps create medevents-ingest` still stops at Fly's billing gate (`We need your payment information to continue!`).

1. `fly apps create medevents-ingest` (or operator-chosen name).
2. Provision / attach Postgres (Fly PG or external cloud PG).
3. `fly secrets set DATABASE_URL=...`.
4. `fly deploy` from repo root.
5. Verify first scheduled run via `fly logs`.
6. Fill in `w3.2d-done-confirmation.md` and commit.

### Track B (autonomous, optional) — follow-ups only

The autonomous queue is clear again. Optional waves that no longer block product value:

- Generic fallback parser — operator discretion.
- Additional curated-source expansion — operator discretion.

## Open decisions

_None._ On 2026-04-23 we chose **option D** and wired it into the repo:

- [`apps/web/tests/e2e/admin-login.spec.ts`](../apps/web/tests/e2e/admin-login.spec.ts) now runs in the main CI workflow on every `pull_request` and `push`.
- [`apps/web/tests/e2e/happy-path-smoke.spec.ts`](../apps/web/tests/e2e/happy-path-smoke.spec.ts) now runs via [`nightly-smoke.yml`](../.github/workflows/nightly-smoke.yml) on a nightly schedule plus `workflow_dispatch`.
- [`apps/web/scripts/seed-happy-path-smoke.mjs`](../apps/web/scripts/seed-happy-path-smoke.mjs) seeds the deterministic ADA/review/event fixtures used by the nightly smoke.

## Next

_No user-gated work remains. Further progress is either operator action (enable Fly billing, then complete W3.2d deploy) or optional follow-on parser/source work._

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until the curated-parser lane stops paying for itself or a target source clearly needs fallback extraction.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

- [x] W3.2o eleventh curated source: Forum de l'Officine (`forum_officine_tn`) — new source-specific parser in [`parsers/forum_officine.py`](../services/ingest/medevents_ingest/parsers/forum_officine.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`forum-officine-fixtures.md`](runbooks/forum-officine-fixtures.md), and live smoke against the official homepage + public practical-information page. First run: `source=forum_officine_tn fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; rerun: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 204 passed. See [`w3.2o-done-confirmation.md`](runbooks/w3.2o-done-confirmation.md).
- [x] W3.2n tenth curated source: AMIED Congress (`amied_congress`) — new source-specific parser in [`parsers/amied.py`](../services/ingest/medevents_ingest/parsers/amied.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`amied-fixtures.md`](runbooks/amied-fixtures.md), and live smoke against the official homepage + public inscriptions page. First run: `source=amied_congress fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; rerun: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 196 passed. See [`w3.2n-done-confirmation.md`](runbooks/w3.2n-done-confirmation.md).
- [x] W3.2m ninth curated source: EuroPerio (`europerio`) — new source-specific parser in [`parsers/europerio.py`](../services/ingest/medevents_ingest/parsers/europerio.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`europerio-fixtures.md`](runbooks/europerio-fixtures.md), and live smoke against the official EFP hub + `EuroPerio12` page. First run: `source=europerio fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; rerun: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 188 passed. See [`w3.2m-done-confirmation.md`](runbooks/w3.2m-done-confirmation.md).
- [x] W3.2l eighth curated source: Morocco Dental Expo (`morocco_dental_expo`) — new source-specific parser in [`parsers/morocco_dental_expo.py`](../services/ingest/medevents_ingest/parsers/morocco_dental_expo.py), config seed in [`sources.yaml`](../config/sources.yaml), 9 new tests (7 parser + 2 DB-gated pipeline), fixture/prep docs in [`morocco-dental-expo-fixtures.md`](runbooks/morocco-dental-expo-fixtures.md), and live smoke against the official English homepage + public exhibitor-list page. First run: `source=morocco_dental_expo fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; final reruns: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 180 passed. See [`w3.2l-done-confirmation.md`](runbooks/w3.2l-done-confirmation.md).
- [x] GitHub Actions Node 24 migration — live workflows now set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` and upgraded to current Node 24-capable action majors (`actions/checkout@v6`, `actions/setup-node@v6`, `actions/setup-python@v6`, `actions/upload-artifact@v7`, `pnpm/action-setup@v5`) in [`ci.yml`](../.github/workflows/ci.yml) and [`nightly-smoke.yml`](../.github/workflows/nightly-smoke.yml). This clears the previously noted Node 20 deprecation follow-up ahead of GitHub's June 2, 2026 default switch and September 16, 2026 removal.
- [x] W3.2k seventh curated source: Dentex Algeria (`dentex_algeria`) — new source-specific parser in [`parsers/dentex.py`](../services/ingest/medevents_ingest/parsers/dentex.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`dentex-fixtures.md`](runbooks/dentex-fixtures.md), and live smoke against the official Dentex homepage + visit page. First run: `source=dentex_algeria fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; final reruns: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 171 passed. See [`w3.2k-done-confirmation.md`](runbooks/w3.2k-done-confirmation.md).
- [x] W3.2j sixth curated source: Chicago Dental Society Midwinter Meeting (`cds_midwinter`) — new source-specific parser in [`parsers/cds.py`](../services/ingest/medevents_ingest/parsers/cds.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`cds-fixtures.md`](runbooks/cds-fixtures.md), and live smoke against the official CDS event page + public JSON endpoint. First run: `source=cds_midwinter fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; re-run: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 163 passed. See [`w3.2j-done-confirmation.md`](runbooks/w3.2j-done-confirmation.md).
- [x] W3.2i fifth curated source: EAO Congress (`eao_congress`) — new source-specific parser in [`parsers/eao.py`](../services/ingest/medevents_ingest/parsers/eao.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`eao-fixtures.md`](runbooks/eao-fixtures.md), and live smoke against the official EAO hub + 2026 microsite. First run: `source=eao_congress fetched=2 skipped_unchanged=0 created=3 updated=1 review_items=0`; final unchanged rerun after widening hub normalization: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 155 passed. See [`w3.2i-done-confirmation.md`](runbooks/w3.2i-done-confirmation.md).
- [x] W3.2h fourth curated source: FDI World Dental Congress (`fdi_wdc`) — new source-specific parser in [`parsers/fdi.py`](../services/ingest/medevents_ingest/parsers/fdi.py), config seed in [`sources.yaml`](../config/sources.yaml), 8 new tests (6 parser + 2 DB-gated pipeline), fixture/prep docs in [`fdi-fixtures.md`](runbooks/fdi-fixtures.md), and live smoke against the official site. First run: `source=fdi_wdc fetched=2 skipped_unchanged=0 created=1 updated=1 review_items=0`; re-run: `skipped_unchanged=2 created=0 updated=0`. Repo-wide ingest suite now at 147 passed. See [`w3.2h-done-confirmation.md`](runbooks/w3.2h-done-confirmation.md).
- [x] Playwright CI option D — admin-login spec now runs in CI on every PR/push via [`ci.yml`](../.github/workflows/ci.yml); full happy-path smoke moved to [`nightly-smoke.yml`](../.github/workflows/nightly-smoke.yml) (nightly + manual dispatch) with deterministic fixtures seeded by [`apps/web/scripts/seed-happy-path-smoke.mjs`](../apps/web/scripts/seed-happy-path-smoke.mjs). The happy-path spec now targets the ADA row explicitly instead of the first `Open` link.
- [x] Remaining DB-gated ingest test hygiene — the six older pipeline/repository suites now gate on `TEST_DATABASE_URL` and use the same `_alias_test_database_url` fixture pattern as the newer DB-gated modules, so no ingest test suite TRUNCATEs the dev DB anymore. Verified with `cd services/ingest && DATABASE_URL=postgresql://…@localhost:5432/medevents TEST_DATABASE_URL=postgresql://…@localhost:5432/medevents_test uv run pytest -q` → 139 passed.
- [x] Testseed cleanup (PR #73, `99a9629`) — migrated `test_seed.py` to `TEST_DATABASE_URL` + `_alias_test_database_url` fixture; deleted leftover `testseed` row from dev DB. Dev sources now lists only three live sources (`aap_annual_meeting`, `ada`, `gnydm`). The broader DB-gated suite migration was finished in the later hygiene wave above.
- [x] W3.2g ADA silent-drop aggregate `parser_failure` (PR #72, `71193eb`) — closes W2 §7 drift-observability gap: ADA parser now emits `ParserReviewRequest(kind='parser_failure', details={rows_seen, rows_yielded, drops_by_reason})` at end-of-stream whenever `_row_to_event` returns None for one or more rows. Pipeline routes to `insert_review_item` (real) or preview line (dry-run). New `ParserReviewRequest` dataclass in `parsers/base.py`; `Parser.parse()` return widened to `Iterator[ParsedEvent | ParserReviewRequest]` — gnydm/aap source unchanged (covariant). `_row_to_event`'s five None guards kept byte-for-byte identical. Surfaced a pre-existing silent-drop in `fixtures/ada/continuing-education.html` (7 rows all fail `parse_date_range`). 1 focused test; 139 passing.
- [x] W3.2f `--dry-run` implementation — `medevents-ingest run --dry-run` previews exactly what `run` would do (per-page status + per-candidate action + summary) with zero DB writes at any boundary. `dry_run=False` kwarg threaded through `run_source` / `run_all` / `_run_source_inner` / `_persist_event`; belt-and-braces `session.rollback()` in CLI for defense-in-depth. Added `get_last_content_hash_by_url(source_id, url)` so the dry-run content-hash gate stays read-only and still returns `would_skip_unchanged` on unchanged pages (spec §4 D5). 21 new tests (10 unit + 4 DB-gated + 4 CLI + 3 repo); full suite 138 passed, 0 xfails. Live-smoke on ADA + GNYDM + AAP confirmed zero writes, all preview lines emitted correctly. See `docs/runbooks/w3.2f-done-confirmation.md`.
- [x] W3.2e third curated source: AAP Annual Meeting 2026 — parser module (`parsers/aap.py`) with `_normalize_body_for_hashing` addressing Cloudflare email-obfuscation rotation + homepage base64 data-dbsrc noise; 8 new tests (6 unit + 2 DB-gated); `config/sources.yaml` entry; live smoke on `am2026.perio.org` confirmed 1 events row + 2 event_sources rows; re-run idempotence verified. See `docs/runbooks/w3.2e-done-confirmation.md`.
- [x] W3.2e prep — AAP fixtures + robots + byte-stability review (identified the cfemail rotation problem before implementation). See `docs/runbooks/aap-fixtures.md`.
- [x] test-harness mypy cleanup — 27 pre-existing mypy errors across `test_ada_parser.py`, `test_gnydm_parser.py`, `test_gnydm_pipeline.py`, `test_drift_observability.py`, `test_pipeline.py`, `test_repositories_event_sources.py` resolved by typing `_get_parser() -> Parser`, `_seed_*(session: Session)`, `_fresh_event(...) -> UUID`, and narrowing a `BeautifulSoup.select_one()` result. `uv run mypy .` (repo-wide) now clean; CI unaffected (CI scope is `medevents_ingest` only).
- [x] W3.2c `_diff_event_fields` None-as-clear fix addresses the partial-page precedence drift risk flagged in earlier TODO snapshots; item closed.
- [x] W3.2d repo artifacts — `services/ingest/Dockerfile` (multi-stage Python 3.12 + uv + non-root user, CMD = `medevents-ingest run --all`), `fly.toml` at repo root (scheduled-machine config, hourly wake, 256MB / shared CPU), `docs/runbooks/w3.2d-fly-scheduler-deploy.md` (operator deploy runbook with Fly PG + external PG strategies + rollback), `docs/runbooks/w3.2d-done-confirmation.md` (skeleton). Live deploy requires operator action; PR body + runbook explicit about the boundary.
- [x] W3.2c drift observability + None-rule + raw_title provenance — detail-page zero-yield now fires `parser_failure` (symmetric with listing, carries `page_kind` in details_json); `_diff_event_fields` treats candidate None as "no contribution" (preserves existing non-null fields); GNYDM `raw_title` is now a real source excerpt (listing = year + meeting-dates; homepage = `h1.swiper-title` text). 4 new tests. See `docs/runbooks/w3.2c-done-confirmation.md`.
- [x] W3.2b `run --all` + due-selection — CLI gains `medevents-ingest run --all`; iterates `is_active` + schedule-due sources via SQL-side CASE filter; continues on per-source failure; `--force` bypasses due check (but STILL respects `is_active=false`); `--source`/`--all` mutex validated; batch summary + per-source stdout + per-source stderr on failures. 8 new tests (4 DB-gated integration + 4 unit parametrized across all 4 `crawl_frequency` boundaries). See `docs/runbooks/w3.2b-done-confirmation.md`.
- [x] W3.2a source-run bookkeeping + `--force` plumbing — pipeline now writes `last_crawled_at` / `last_success_at` on success and `last_crawled_at` / `last_error_at` / `last_error_message` on error (via a fresh session so writes survive rollback). Admin UI sources pages display real timestamps for the first time. See `docs/runbooks/w3.2a-done-confirmation.md`.
- [x] W3.1 GNYDM second-source onboarding shipped end-to-end — 5 phases, 5 PRs (#50, #51, #52, #53, #54). Two sources now live; intra-source dedupe + detail-over-listing precedence proven on real data. See `docs/runbooks/w3.1-done-confirmation.md`.
- [x] W3.1 plan + sub-spec merged (PR #48 + PR #46).
- [x] W3.1 prep: GNYDM canary fixtures + robots/byte-stability review + source-code naming + stability-check protocol as default for future sources (PR #45, `a4cedb4`).
- [x] W3 direction decision: `gnydm` chosen as W3.1 second source before any scheduler or generic-fallback work.
- [x] W2 first-source ingestion (ADA) shipped: parser, pipeline, dedupe, review-item emission. Live smoke on main at `b0cd668`.
- [x] W2 spec + prep plan + W2 implementation plan all tracked on main.
- [x] W0+W1 foundation through Phase 10 is on `main`.
- [x] All schema migrations, indexes, and Drizzle introspection landed.
- [x] `seed-sources`, parser registry, and `run --source` CLI shape landed.
- [x] Admin auth, CSRF, audit, sources, review, and events operator surfaces landed.
- [x] Manual operator happy-path smoke completed on localhost.
- [x] PR `#28` fixed the three runtime bugs surfaced by that smoke.
- [x] Top-level `README.md` + `docs/runbooks/local-dev.md` (PR `#29`).
- [x] W1 done-confirmation against spec §10 (PR `#30`).
- [x] Branch protection on `main` with three required checks.
- [x] CI is green on `main` for TypeScript, Python, and schema drift.
