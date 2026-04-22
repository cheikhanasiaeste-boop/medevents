# MedEvents TODO

_Last updated: 2026-04-23 — W3.2c shipped; parser/pipeline boundary hardened. W3.2d (third source — `aap_annual_meeting`) is next._

## Now

**W3.2d — Third curated source: `aap_annual_meeting`.** Proves the two-source pattern generalizes to three without code rework. With W3.2a/b/c shipped, the third source inherits: real bookkeeping, due-selection, drift observability, clean None semantics, and true `raw_title` provenance — so onboarding is pure parser work + fixtures + config wiring.

**Candidate source:** AAP (American Academy of Periodontology) Annual Meeting. Per the W3.1 prep-plan §3 ordering, `aap_annual_meeting` is the next-best candidate after GNYDM; `fdi_wdc` (FDI World Dental Congress) follows.

**Scope (to lock in the sub-spec):**

- Source-code naming + canary protocol (same discipline as W3.1 prep).
- Fixtures + robots + byte-stability review.
- Parser module `parsers/aap.py` following the W3.1 parser shape (discover + fetch + parse + classifier).
- `config/sources.yaml` entry + seed.
- Live smoke + done-confirmation.

**Prep work that may justify a sub-wave W3.2d-prep:** fetching AAP fixtures, reviewing robots.txt, byte-stability check across three consecutive fetches (mirror the GNYDM prep in PR #45). Decide in the sub-spec whether prep is a separate PR or bundled.

**Next concrete action:** author the W3.2d sub-spec via `superpowers:brainstorming` + `superpowers:writing-plans`.

### Remaining W3.2 sequence (after W3.2d)

- **W3.2e — External scheduler wiring.** **Fly.io scheduled machines** per [`w1-foundation.md:324`](superpowers/specs/2026-04-20-medevents-w1-foundation.md). `run --all` is on `main` (W3.2b) so the Fly machine has something concrete to call. The scheduler wires in UNCHANGED regardless of how many curated sources ship — running after the third source proves the primitive at a realistic source count.

## Next

- [ ] Decide whether to wire the existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement `--dry-run` (currently exits 4 per `cli.py:53-55`). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the ADA schedule rows that returned `None` from `_row_to_event` — any should have landed in `review_items` per W2 spec §7? Currently silent-dropped. Not blocking W3.2.
- [ ] Pre-existing mypy errors in `tests/test_ada_parser.py` + related test-harness files (11 errors surfaced by `uv run mypy .`). CI does not check these (CI mypy scope is `medevents_ingest` only). Either add type hints or `# type: ignore` suppressions.
- [ ] Partial-page precedence drift risk: `pipeline._diff_event_fields` treats `None` in the incoming candidate as a deliberate clear — revisit in W3.2c spec.

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until a third curated source either lands or proves infeasible.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

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
