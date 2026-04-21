# MedEvents TODO

_Last updated: 2026-04-21 — W2 closed, W3.1 prep shipped, W3.1 spec in PR #46 awaiting review._

## Now

- [ ] **Review PR #46** — [docs(w3.1): sub-spec for second-source onboarding (GNYDM)](https://github.com/cheikhanasiaeste-boop/medevents/pull/46). Branch `docs/w3-1-spec-second-source-gnydm`. Content at `docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md`. Approve, request changes, or close; nothing downstream can proceed until this resolves.
- [ ] **After PR #46 merges:** invoke the `superpowers:writing-plans` skill to author the W3.1 implementation plan against the merged spec. Do not start implementation until the plan is reviewed.

## Next

- [ ] Execute W3.1 implementation plan task-by-task behind branch protection (each task → branch → PR → CI green → squash-merge). Same discipline as W2.
- [ ] Ship `docs/runbooks/w3.1-done-confirmation.md` as the last W3.1 step, mapping each §9 exit criterion to live-run / rerun / test evidence.
- [ ] Periodic scheduler story: `medevents-ingest run` currently runs manually or via the operator "Run now" button. Decide whether W3.2 wires a GitHub Actions schedule, a cron on the host, or a background worker.
- [ ] Decide whether to wire an existing Playwright happy-path spec into CI, or keep it opt-in local-only.
- [ ] Implement W2 `--dry-run` (currently exits 4). Candidate for late-W3 if operators need preview runs for risky source config changes.
- [ ] Audit the ADA schedule rows that returned `None` from `_row_to_event` — any should have landed in review_items per W2 spec §7? Currently silent-dropped. Not blocking W3.1.

## Later

- [ ] Generic fallback parser (W3.2+) — deferred until the two-source pattern (ADA + GNYDM) is proven.
- [ ] Third-source onboarding (candidate order: `aap_annual_meeting` then `fdi_wdc`, per prep plan §3).
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

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
