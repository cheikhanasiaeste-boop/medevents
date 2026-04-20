# ADA fixtures and W2 source-code naming convention

## Captured ADA HTML fixtures

The four fixtures under [`services/ingest/tests/fixtures/ada/`](../../services/ingest/tests/fixtures/ada/) are canary snapshots of the ADA pages the W2 spec (`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`) and its implementation plan will parse. Captured with `curl` on 2026-04-21 with a descriptive `User-Agent`; `robots.txt` explicitly permits full site access (`User-agent: * / Disallow:` empty).

| File                              | Source URL                                                                 | Purpose                                                                                                                                                                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `continuing-education.html`       | `https://www.ada.org/education/continuing-education`                       | W2 spec §2 first seed URL — top-level CE hub, linking to workshops/webinars/travel-CE sub-sections. Kept as a canary for hub drift detection; does not itself contain schedule rows.                                                         |
| `ada-ce-live-workshops.html`      | `https://www.ada.org/education/continuing-education/ada-ce-live-workshops` | The actual "Upcoming Schedule" page the spec describes — a `<table>` of `<td class="cel22airwaves-left">{date}</td><td class="cel22airwaves-right"><a>{title}</a>, <strong>{location?}</strong></td>` rows. Primary W2 listing-parse target. |
| `scientific-session.html`         | `https://www.ada.org/education/scientific-session/continuing-education`    | W2 spec §2 second seed URL — the CE-offerings sub-page of Scientific Session. Marketing copy describing CE content, not the canonical event page. Kept as canary.                                                                            |
| `scientific-session-landing.html` | `https://www.ada.org/education/scientific-session`                         | The main Scientific Session 2026 landing page — meta description carries `The ADA 2026 Scientific Session...Oct. 8-10, 2026 in Indianapolis`. Primary W2 detail-parse target.                                                                |

### Note on the spec's §2 seed URLs

The spec's two literal URLs (`/education/continuing-education` and `/education/scientific-session/continuing-education`) are correct as the **documented entry points**, but the schedule rows and the canonical Scientific Session event live one link below them (the workshops schedule page and the main scientific-session landing respectively). The W2 implementation plan resolves this by seeding the leaf pages directly in `config/sources.yaml` for MVP simplicity, while treating the hub URLs as "discoverable from" references rather than primary seeds. No spec change is needed — the difference is implementation-level.

### How to refresh

Re-capture with the same `User-Agent` string when ADA visibly changes page structure and a fixture test fails with a template-drift signature. Commit the refreshed fixture alongside any parser update that depends on it.

## Source-code naming convention

Adopting the `docs/superpowers/plans/2026-04-20-medevents-w2-prep-and-source-curation.md` §3 list verbatim as the project convention:

- **Short shared-calendar parsers** — organization abbreviation only, lowercase: `ada`, `gnydm`.
- **Single-flagship meeting parsers** — organization abbreviation + short event slug, snake_case: `aap_annual_meeting`, `fdi_wdc`, `eao_congress`, `cds_midwinter`.

Each code is the unique `sources.code` value and maps one-to-one to a parser module at `services/ingest/medevents_ingest/parsers/{code}.py`. A single parser is free to register under its code and optionally under a more descriptive `parser_name` (for example, `ada` seeds register `parser_name: ada_listing` while the source `code` stays `ada`).

New sources follow the same rule: short-and-broad or abbreviation+flagship. Avoid per-year or per-edition suffixes in the code; edition-specific data belongs in `events`, not `sources`.
