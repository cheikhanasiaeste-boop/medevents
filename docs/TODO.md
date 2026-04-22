# MedEvents TODO

_Last updated: 2026-04-23 — W3.2d repo artifacts shipped (Dockerfile + fly.toml + deploy runbook); operator runs the runbook to complete live deployment. Autonomous work continues with W3.2e (third source)._

## Now

**Two tracks in parallel:**

### Track A (operator-gated) — W3.2d live deployment

Repo artifacts on `main`:

- `services/ingest/Dockerfile` — multi-stage Python 3.12 + uv image; default CMD = `medevents-ingest run --all`.
- `fly.toml` at repo root — scheduled machine config, hourly wake, 256MB / shared CPU.
- `docs/runbooks/w3.2d-fly-scheduler-deploy.md` — step-by-step operator runbook.
- `docs/runbooks/w3.2d-done-confirmation.md` — skeleton the operator fills in after the first autonomous run.

**Operator action required** (not autonomously runnable — needs Fly.io account + billing + credentials):

1. `fly apps create medevents-ingest` (or operator-chosen name).
2. Provision / attach Postgres (Fly PG or external cloud PG).
3. `fly secrets set DATABASE_URL=...`.
4. `fly deploy` from repo root.
5. Verify first scheduled run via `fly logs`.
6. Fill in `w3.2d-done-confirmation.md` and commit.

### Track B (autonomous) — W3.2e third source

**W3.2e — Third curated source: `aap_annual_meeting`.** Lands on `main` independently of Track A timing. Once Track A completes, the third source runs autonomously via the Fly machine on the next wake. If Track A is still pending when Track B lands, the third source runs whenever an operator manually invokes `run --source aap_annual_meeting`.

Per W3.1 prep-plan §3: `aap_annual_meeting` (American Academy of Periodontology Annual Meeting) first, then `fdi_wdc` (FDI World Dental Congress). Scope mirrors W3.1: fixtures + robots + byte-stability prep, parser module `parsers/aap.py`, config entry, live smoke, done-confirmation. Generic fallback stays deferred until three curated sources prove or break the pattern.

**Next concrete action:** author the W3.2e sub-spec via `superpowers:brainstorming` + `superpowers:writing-plans`.

## Next

- [ ] Decide whether to wire the existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement `--dry-run` (currently exits 4 per `cli.py:53-55`). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the ADA schedule rows that returned `None` from `_row_to_event` — any should have landed in `review_items` per W2 spec §7? Currently silent-dropped. Not blocking W3.2.

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until a third curated source either lands or proves infeasible.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

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
