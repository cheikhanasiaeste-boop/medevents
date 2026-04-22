# MedEvents TODO

_Last updated: 2026-04-22 — W3.1 shipped end-to-end (Phases 1–5); W3.2 sequenced below after architectural review corrected my "just wire a scheduler" first-pass recommendation._

## Now

**W3.2 is a four-wave sequence, not a single scheduler wave.** Review of the shipped code against the W1 spec surfaces three gaps that must close before any external scheduler is useful:

- **W3.2a — Source-run bookkeeping.** Required before any due-selection scheduler can exist.
  - `pipeline.run_source()` does not write `sources.last_crawled_at / last_success_at / last_error_at / last_error_message` on completion. The admin UI already reads those fields ([`sources/page.tsx:15`](../apps/web/app/%28admin%29/admin/sources/page.tsx), [`sources/[id]/page.tsx:36`](../apps/web/app/%28admin%29/admin/sources/%5Bid%5D/page.tsx)) and is effectively lying to the operator today.
  - `cli.py:47` declares `--force` ("Ignore last_crawled_at.") but the flag is never threaded into `run_source()` — currently a no-op.
  - Scope: write the four timestamps on the success and error paths in `pipeline.run_source()`; thread `--force` through to the (future) due-selection check; integration tests cover success, error, and force-override paths.

- **W3.2b — `run --all` + due-selection.** The W1 spec at [`w1-foundation.md:304`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) promised this entrypoint; it does not exist today.
  - CLI gains `medevents-ingest run --all` — iterates `sources` where `is_active = true` AND the schedule is due per `crawl_frequency` + `last_crawled_at`.
  - `--force` bypasses the due check and runs every active source.
  - Depends on W3.2a landing first — without `last_crawled_at` being written, due-selection has nothing to look at.

- **W3.2c — Detail-page drift observability (gate before any third source).**
  - Today, if the GNYDM homepage classifier silently starts yielding zero events (markup drift, logo rename, `<sup>` structure change), the listing keeps the 2026 row alive and the run reports healthy — but detail-over-listing enrichment quietly disappears. `pipeline.py:146` only emits `parser_failure` when a _listing_ page yields zero; detail pages are silent.
  - Scope: when a _seeded_ page classified as detail (NOT a canary) yields zero events, emit a `review_items` row or at minimum a structured warning. Canaries (URL + markup-known-negative like `about-gnydm`) must not trigger.
  - Also decide the `_diff_event_fields` `None`-as-clear semantic: should `None` from a later-processed page be allowed to clear fields won by an earlier page? Decision belongs in the W3.2c spec.
  - Low-priority carry: `raw_title` for GNYDM currently stores the year (listing) or synthesized title (homepage), not a raw source excerpt — spec §4 promised source-originating provenance. Weakens future audit/debug tooling but does not corrupt data. Fix during W3.2c since we're already touching the parser.

- **W3.2d — Third source onboarding.** Only after W3.2a + W3.2b + W3.2c land. Candidate: `aap_annual_meeting` (per prep plan §3, then `fdi_wdc`). Generic fallback stays deferred until a third curated source either proves or breaks the pattern.

- **W3.2e — External scheduler wiring.** Target is **Fly.io scheduled machines** per the architecture decision in [`w1-foundation.md:324`](superpowers/specs/2026-04-20-medevents-w1-foundation.md) — NOT GitHub Actions cron, NOT host cron. The W3.2e spec should explicitly close that options discussion. Only ship after W3.2a + W3.2b are on `main` so the Fly machine has `medevents-ingest run --all` to call.

**Next concrete action:** author the W3.2a sub-spec (source-run bookkeeping) via the `superpowers:brainstorming` + `writing-plans` skills. Do not open implementation branches until the spec + plan pair is reviewed.

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

- [x] W3.1 GNYDM second-source onboarding shipped end-to-end — 5 phases, 5 PRs (#50, #51, #52, #53, plus this runbook PR). Two sources now live; intra-source dedupe + detail-over-listing precedence proven on real data. See `docs/runbooks/w3.1-done-confirmation.md`.
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
