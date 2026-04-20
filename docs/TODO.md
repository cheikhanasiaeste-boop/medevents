# MedEvents TODO

_Last updated: 2026-04-21 at Phase 10 closeout. W0+W1 foundation wave is complete on `main`._

## Now

- [ ] Start W2 — ADA parser body — from [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](./superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md).
- [ ] Promote the W2 spec and plan from local-only to committed (still untracked in the working tree).

## Next

- [ ] Choose the second-source smoke only after ADA is stable: `gnydm` or `aap_annual_meeting`.
- [ ] Decide whether to wire an existing Playwright happy-path spec into CI, or keep it opt-in local-only.

## Later

- [ ] Keep generic fallback parsing deferred until W3.
- [ ] Add broader regional sources only after the core dental lane is stable.
- [ ] Revisit intelligence-platform layers only if the MVP surfaces concrete pain (search scale, parser maintenance, dedupe ambiguity, operator workflow, partner API).

## Shipped on Main

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
