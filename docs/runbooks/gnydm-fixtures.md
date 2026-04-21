# GNYDM fixtures and W3.1 source intake notes

Captured 2026-04-21 as W3.1 prep for onboarding `gnydm` (Greater New York Dental Meeting) as the second real source after ADA.

## Captured GNYDM HTML fixtures

Three fixtures under [`services/ingest/tests/fixtures/gnydm/`](../../services/ingest/tests/fixtures/gnydm/). Fetched with `curl` and a descriptive `User-Agent`.

| File                   | Source URL                                     | Purpose                                                                                                                                                     |
| ---------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `homepage.html`        | `https://www.gnydm.com/`                       | Flagship 2026 edition page; venue + dates + theme; likely one canonical event per current-edition landing.                                                  |
| `future-meetings.html` | `https://www.gnydm.com/about/future-meetings/` | Multi-edition listing page — 2026, 2027, 2028 editions each with Meeting Dates and Exhibit Dates, same Javits venue. Primary listing-parse target for W3.1. |
| `about-gnydm.html`     | `https://www.gnydm.com/about/about-gnydm/`     | Organizational copy; kept as a "non-event" canary to verify the parser yields zero events against it.                                                       |

### Byte-stability check (W2 lesson applied)

Three consecutive fetches of each page produced **identical sha-256 hashes and identical byte counts**. Unlike ADA (whose Sitecore platform rotates featured-story tracking attributes per request), GNYDM serves byte-stable HTML — a plain sha-256 of the raw body will work as the `content_hash` skip-gate input. No parser-scoped body normalization is required.

```
homepage          run1==run2==run3  (43026 bytes, hash 1bcd637d…)
future-meetings   run1==run2==run3  (25666 bytes, hash 49b78017…)
about-gnydm       run1==run2==run3  (27714 bytes, hash 958f7b15…)
```

### Content shape highlights (for parser design)

- **Flagship dates on homepage** live in inline spans alongside "JACOB K. JAVITS CONVENTION CENTER".
- **Future-meetings listing** uses a `<p><strong>{year}</strong></p>` header followed by a sibling `<p>Meeting Dates: {Weekday}, {Month} {day}th - {Weekday}, {Month} {day}st<br>Exhibit Dates: ...</p>` block. Three editions in the current page: 2026, 2027, 2028.
- **Ordinals** (`27th`, `1st`) and **day-of-week prefixes** (`Friday,`, `Tuesday,`) appear inline with the dates — the existing `normalize.parse_date_range` handles ordinals but **does not strip day-of-week prefixes**, so the gnydm parser will need local pre-processing OR a small shared-helper extension. This is the first real pressure on the shared `normalize.py` layer — decided intentionally in the W3.1 spec.

### How to refresh

Re-capture with the same `User-Agent` when GNYDM visibly changes page layout and a fixture test starts failing with a template-drift signature. Commit the refreshed fixture alongside any parser update that depends on it.

## robots.txt and terms review

### robots.txt (fetched 2026-04-21 from https://www.gnydm.com/robots.txt)

```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /utilities/
Disallow: /database/
Disallow: /speaker-site-preview/
Disallow: /test.php
Disallow: /uploads/speaker-site/
Disallow: /uploads/speaker-site-public/
Disallow: /uploads/posters/
Disallow: /uploads/handouts/

Sitemap: http://www.gnydm.com/sitemap/
```

**Summary:** permissive at event surfaces.

- **Clearly allowed** — everything under `/` (homepage, `/about/*`, `/attendees/*`, `/educationce/*`, and the sitemap). The pages W3.1 will seed (`/`, `/about/future-meetings/`, `/about/about-gnydm/`) are all in-scope.
- **Clearly disallowed** — admin/utilities/database/test infrastructure and four `/uploads/*` paths used for speaker/poster/handout asset hosting. None intersect with the event-listing pages W3.1 needs.
- **Ambiguous / rate-limit** — no crawl-delay or per-agent rules. W3.1 will apply the same conservative cadence as ADA: single-process, no parallel fetches per source, no aggressive crawl loop.

### Terms-of-use

GNYDM does not expose a machine-readable ToU at a canonical URL; their site has a standard copyright footer and privacy/cookie notices. No explicit prohibition against reading or indexing public event pages, which aligns with the robots.txt posture. Maintainer judgement accepts this as normal for a public event/trade-fair site; W3.1 will continue to identify itself via a descriptive `User-Agent` with a contact email.

## Stability-check protocol for future sources

The above byte-stability check (three back-to-back fetches, compare sha-256) is now the default prep step for every new source. A stable hash across fetches permits raw-body hashing; an unstable hash requires a parser-scoped body normalizer (as implemented for ADA in `parsers/ada.py::_normalize_body_for_hashing`). Record the finding in the source's fixture runbook alongside the raw `robots.txt` excerpt.
