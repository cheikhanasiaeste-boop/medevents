# MedEvents TODO

_Last updated: 2026-04-21 at W2 closeout. W0+W1 foundation + W2 ADA ingestion live on main._

## Now

- [ ] Decide W3 direction: second-source smoke (`gnydm`) first, or generic fallback parser first. See docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md §3 for recommended order.
- [ ] Periodic scheduler story: `medevents-ingest run --source ada` currently runs manually or via the operator "Run now" button. Decide whether W3 wires a GitHub Actions schedule, a cron on the host, or a background worker.

## Next

- [ ] Choose the second-source smoke only after ADA is stable: `gnydm` or `aap_annual_meeting`.
- [ ] Decide whether to wire an existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement W2 `--dry-run` (currently exits 4). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the remaining schedule rows in the ADA fixture that returned None from `_row_to_event` — any should have landed in review_items per spec §7? Currently silent-dropped. Not blocking for W2 close.

## Later

- [ ] Keep generic fallback parsing deferred until W3.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

- [x] W2 first-source ingestion (ADA) shipped: parser, pipeline, dedupe, review-item emission. Live smoke on main at 061a7de.
- [x] W2 spec + prep plan + W2 implementation plan all tracked on main.
- [x] W0+W1 foundation through Phase 10 is on `main`
- [x] All schema migrations, indexes, and Drizzle introspection landed
- [x] `seed-sources`, parser registry, and `run --source` CLI shape landed
- [x] Admin auth, CSRF, audit, sources, review, and events operator surfaces landed
- [x] Manual operator happy-path smoke completed on localhost
- [x] PR `#28` fixed the three runtime bugs surfaced by that smoke
- [x] Top-level `README.md` + `docs/runbooks/local-dev.md` (PR `#29`)
- [x] W1 done-confirmation against spec §10 (PR `#30`)
- [x] Branch protection on `main` with three required checks
- [x] CI is green on `main` for TypeScript, Python, and schema drift
