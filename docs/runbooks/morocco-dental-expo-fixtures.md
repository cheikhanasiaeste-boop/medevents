# Morocco Dental Expo — prep review (W3.2l)

Date: 2026-04-24
Source code: `morocco_dental_expo`
Candidate homepage URL: `https://www.mdentalexpo.ma/lang/en`
Chosen second URL: `https://www.mdentalexpo.ma/ExhibitorList`
Rejected English practical-info URL: `https://www.mdentalexpo.ma/Page/5601/practical-information`

## TL;DR — go signal

**Proceed with the eighth curated-source onboarding.** Morocco Dental Expo's
public English homepage and public exhibitor-list page together expose the 2026
event contract we need: title, date range, city, venue, and visitor
registration CTA. The English practical-information page is intentionally
excluded because it still advertises the stale range `From 30 April to 03 May
2026`.

The source is crawlable and parsable, but **raw-body hashing is not safe**:
both chosen pages rotate ASP.NET hidden-field values on every request. A small
hash-only normalization layer fixes that deterministically.

## 1 — robots.txt

Captured at
[`services/ingest/tests/fixtures/morocco_dental_expo/robots.txt`](../../services/ingest/tests/fixtures/morocco_dental_expo/robots.txt).

Relevant excerpt:

```text
User-agent:  *
Disallow: /Controls/
Disallow: /Countries/
Disallow: /CSS/
Disallow: /Documents/
Disallow: /Video/
Disallow: /editeur/
Disallow: /Images/Icons/
Disallow: /Images/ComboBox/
Disallow: /Images/Maps/
Disallow: /JavaScript/
Disallow: /js/
Disallow: /PayPal/
Disallow: /Scripts/
```

Summary:

- Public HTML pages are crawlable.
- Neither `/lang/en` nor `/ExhibitorList` is disallowed.
- The blocked paths are static assets and back-office/site-builder surfaces.

## 2 — Byte-stability evidence

Two consecutive fetches of the homepage produced identical byte counts but
different raw hashes because ASP.NET rotates hidden-field values:

| URL        | Raw run 1                                                          | Raw run 2                                                          | Size   |
| ---------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------ |
| `/lang/en` | `16176dd49d1290e6bc437af29261ac7118c773c3997bec560b14e4fab9060689` | `ee5c6148248fc363a0de750cc957726f5a3417882289a544b2090f33ea1501ff` | 30,857 |

After normalizing `__VIEWSTATE`, `__EVENTVALIDATION`, and homepage-only
`hfac`, both homepage bodies produce the same sha-256:

- normalized homepage hash: `0627f7308f48435642850f2cbf3f3875908e5abdeef551c5b9670e92bfcd9b6e`

The exhibitor-list page shows the same pattern:

| URL              | Raw run 1                                                          | Raw run 2                                                          | Size    |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------- |
| `/ExhibitorList` | `6ac3f78b50ebdd7c5b16b13c67b5e7253643824e469665e5d130d4f0dd9be71a` | `6fa50f6697e98d0efadaea2906fc21caeb33423ed0b91a1a482d421bd4b66b6e` | 139,119 |

After normalizing `__VIEWSTATE` and `__EVENTVALIDATION`, both exhibitor-list
bodies produce the same sha-256:

- normalized exhibitor-list hash: `8b389f74c08aade0f149d511175ae48c1c20213ad3a1949b5c8b59208664b62d`

Conclusion: **hash normalization is required** for this source, but the
instability is narrow and mechanical.

The committed fixtures keep the real page structure but replace the rotating
hidden-field values with literals:

- homepage `__VIEWSTATE` → `fixture-viewstate`
- homepage `__PREVIOUSPAGE` → `fixture-previous-page`
- homepage `__EVENTVALIDATION` → `fixture-eventvalidation`
- homepage `hfac` → `fixture-hfac`
- exhibitor-list `__VIEWSTATE` → `fixture-viewstate`
- exhibitor-list `__EVENTVALIDATION` → `fixture-eventvalidation`

## 3 — Captured fixtures

Committed under
[`services/ingest/tests/fixtures/morocco_dental_expo/`](../../services/ingest/tests/fixtures/morocco_dental_expo/).

| File                  | SHA-256                                                            | Size    | Role                                            |
| --------------------- | ------------------------------------------------------------------ | ------- | ----------------------------------------------- |
| `homepage.html`       | `fbfbcc30692e3c6a9d0f752b96b957531fc5bbfbfc415bb2167d20987d74a031` | 30,329  | English homepage with 2026 hero paragraph + CTA |
| `exhibitor-list.html` | `6457041bead130eac1e373a0cf72940c91f6b0d99b653d49710a469697f731f3` | 137,492 | Public exhibitor list with 2026 dates + venue   |
| `robots.txt`          | `2188bc4d80bd2155856a3aa253370dbf69be3b7f2af5bd011800becc6cd5a2b8` | 466     | Policy record                                   |

## 4 — Extracted signals

From `homepage.html`:

- `<title>`: `Dental Expo  - Home Page - DENTAL EXPO 2026`
- hero section title: `PROFESSIONAL EXHIBITION AND SCIENTIFIC FORUM`
- hero paragraph includes:
  - `Casablanca hosts the 7th edition ...`
  - `DENTAL EXPO 2026`
  - `07 to 10 May 2026`
  - `ATELIER VITA`
- public visitor-registration CTA:
  `https://www.mdentalexpo.ma/form/2749?cat=VISITOR`

From `exhibitor-list.html`:

- `<title>`: `Exposants MOROCCO DENTAL EXPO 2026`
- page `<h1>`: `Exposants MOROCCO DENTAL EXPO 2026`
- visible dates:
  - `07/05/2026`
  - `10/05/2026`
- hidden venue itemprop:
  - `ICEC AIN SEBAA`

Rejected `practical-information` page:

- `<title>` is 2026-branded, but the visible schedule still says
  `From 30 April to 03 May 2026`
- because that conflicts with the homepage and exhibitor-list 2026 contract,
  it is **not used** for onboarding

## 5 — Parser design chosen

- Parser module:
  `services/ingest/medevents_ingest/parsers/morocco_dental_expo.py`
- Registered name: `morocco_dental_expo`
- Seed URLs:
  - English homepage
  - public exhibitor list
- `discover()` order: homepage first, exhibitor list second
- One canonical event row:
  - title `Morocco Dental Expo 2026`
  - starts_on `2026-05-07`
  - ends_on `2026-05-10`
  - city `Casablanca`
  - country_iso `MA`
  - organizer `ATELIER VITA MAROC`
- Canonical row keeps the English homepage as `source_url`
- `registration_url` comes from the homepage visitor CTA
- `venue_name` comes from the exhibitor-list page (`ICEC AIN SEBAA`)
- `fetch()` normalizes the rotating ASP.NET hidden fields before sha-256

## 6 — Future-proofing note

This onboarding is **edition-specific for 2026**.

When Morocco Dental Expo rolls to a 2027 contract:

1. update the homepage and second seed URL in `config/sources.yaml`
2. bump the 2026 title/date gates in `parsers/morocco_dental_expo.py`
3. re-run `seed-sources`
4. re-run `run --source morocco_dental_expo`

If the old 2026 contract disappears first, the parser will emit zero events on
the stale branch rather than silently publishing the wrong edition.
