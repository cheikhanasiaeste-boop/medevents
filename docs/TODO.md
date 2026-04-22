# MedEvents TODO

_Last updated: 2026-04-22 — W3.1 shipped end-to-end (Phases 1–5); W3.2 direction TBD._

## Now

- [ ] **Pick W3.2 direction.** With two curated sources live (ADA + GNYDM), the next wave should be one of:
  - (a) **Periodic scheduler** — wire `medevents-ingest run` into a GitHub Actions cron or a host cron so the ingest runs without operator action. The two parsers have no value unless they run on a schedule.
  - (b) **Third source onboarding** — candidate order per prep plan: `aap_annual_meeting`, then `fdi_wdc`. Proves the two-source pattern generalizes to a third without code rework.
  - (c) **Generic fallback parser** — explicitly deferred by spec §10 until the curated-parser pattern is proven; a third curated source first is the better test.

  **Recommendation:** start with (a). Ingested-once-then-stale data is worse than no data, and both curated sources are already shipped. (b) and (c) are easier to justify after the scheduler is in place.

## Next

- [ ] Decide whether to wire the existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement `--dry-run` (currently exits 4 per `cli.py:53-55`). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the ADA schedule rows that returned `None` from `_row_to_event` — any should have landed in `review_items` per W2 spec §7? Currently silent-dropped. Not blocking W3.2.
- [ ] Pre-existing mypy errors in `tests/test_ada_parser.py` + related test-harness files (11 errors surfaced by `uv run mypy .`). CI does not check these (CI mypy scope is `medevents_ingest` only). Either add type hints or `# type: ignore` suppressions.
- [ ] Partial-page precedence drift risk: `pipeline._diff_event_fields` treats `None` in the incoming candidate as a deliberate clear. If one seed page's hash changes and the other's doesn't, a re-fetch of the changed page can clobber precedence-won fields from the unchanged page. Revisit if observed in the wild.

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
