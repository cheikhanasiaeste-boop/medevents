# MedEvents — W2 Prep and Source Curation Plan

|                |                                                                                                                                                                                                                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**     | Prepared                                                                                                                                                                                                                                                                               |
| **Date**       | 2026-04-20                                                                                                                                                                                                                                                                             |
| **Scope**      | Source shortlist, onboarding order, and pre-W2 prep decisions while W0+W1 are executing                                                                                                                                                                                                |
| **Reads with** | [`../specs/2026-04-20-medevents-w2-first-source-ingestion.md`](../specs/2026-04-20-medevents-w2-first-source-ingestion.md), [`../specs/2026-04-20-medevents-automated-directory-mvp.md`](../specs/2026-04-20-medevents-automated-directory-mvp.md), [`../../state.md`](../../state.md) |

---

## 0 — Goal

Keep the next wave honest.

This plan does two things:

1. turns W2 into a bounded first-source ingestion wave instead of an open-ended parser spree
2. curates the initial source queue so onboarding order follows operational value, not prestige alone

---

## 1 — Method

Candidate sources were reviewed from **official source pages** on 2026-04-20.

Selection criteria:

- official event owner or official society/federation page
- obvious event yield for fairs / congresses / seminars / workshops
- good fit with the automated directory MVP
- parser shape that teaches something useful without exploding complexity too early
- international reach over time, not just one local calendar

---

## 2 — Recommended source queue

### Primary lane — dental-first, because W1 already seeds `ada`

| Priority | Source                                        | Type                               | Official URL                                               | Recommended wave | Why it fits                                                                                  | Parser shape                                  | Main risk                                      |
| -------- | --------------------------------------------- | ---------------------------------- | ---------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------- | ---------------------------------------------- |
| 1        | ADA Continuing Education + Scientific Session | society                            | `https://www.ada.org/education/continuing-education`       | W2               | Already aligned with seed config; mixes webinars, workshops, travel CE, and flagship meeting | one hub page plus one flagship detail page    | mixed content; external registration links     |
| 2        | Greater New York Dental Meeting               | organizer / society-backed meeting | `https://www.gnydm.com/`                                   | W2 smoke or W3   | flagship fair + CE with clear date/venue and strong global visibility                        | homepage plus about/future-meetings pages     | homepage-heavy information architecture        |
| 3        | AAP Annual Meeting                            | specialty society                  | `https://am2026.perio.org/`                                | W3               | clean event microsite, clear date/location, good specialty coverage                          | single annual-meeting microsite               | lower event yield outside annual meeting cycle |
| 4        | FDI World Dental Congress                     | federation                         | `https://www.fdiworlddental.org/fdi-world-dental-congress` | W3               | strong global reach; official annual congress page                                           | federation hub linking to event microsite     | off-domain congress microsite                  |
| 5        | EAO Congress                                  | specialty society                  | `https://eao.org/congress/`                                | W3/W4            | clean flagship congress page, international implant focus                                    | detail-first congress page                    | modest source breadth per year                 |
| 6        | Chicago Dental Society Midwinter Meeting      | society                            | `https://www.cds.org/event/2026-midwinter-meeting/`        | W4               | major annual meeting with fair/exhibitor value                                               | WordPress event page plus external event site | split architecture and external event platform |

### Reserve lane — valuable, but intentionally later

| Priority | Source                  | Type                              | Official URL                                                                   | Recommended wave                           | Why it matters                               | Parser shape                  | Main risk                                   |
| -------- | ----------------------- | --------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------ | -------------------------------------------- | ----------------------------- | ------------------------------------------- |
| 7        | EuroPerio               | federation congress               | `https://www.efp.org/news-events/europerio/`                                   | W4 reserve                                 | globally respected dental congress           | event overview page           | triennial cadence, low annual yield         |
| 8        | AEEDC Dubai             | conference + exhibition organizer | `https://aeedc.com/`                                                           | W4/W5 reserve                              | major dental fair with conference components | site + PDF-heavy support docs | PDFs and file-heavy content                 |
| 9        | ESC Congresses          | medical society                   | `https://www.escardio.org/events/congresses/`                                  | medical pilot after dental lane stabilizes | best bridge into broader medical events      | multi-event official listing  | broader taxonomy and denser event family    |
| 10       | Arab Health / WHX Dubai | exhibition organizer              | `https://prod65.arabhealthonline.com/en/visit/frequently-asked-questions.html` | medical fair pilot later                   | major global healthcare fair                 | marketing-heavy event pages   | brand transition, noisy commercial surfaces |

---

## 3 — Onboarding order

### Recommended order after ADA

1. `ada`
2. `gnydm`
3. `aap_annual_meeting`
4. `fdi_wdc`
5. `eao_congress`
6. `cds_midwinter`

### Why this order

- `gnydm` is the best next shape test after ADA: one big flagship meeting, clear venue/date, less mixed content than CDS
- `aap_annual_meeting` is cleaner than many multi-program sites and likely low-maintenance
- `fdi_wdc` proves international rotation and off-domain event microsites
- `eao_congress` strengthens the European specialty lane
- `cds_midwinter` is valuable but structurally messier, so it should not be the second parser lesson

---

## 4 — North Africa / Maghreb resource pack

These are not all immediate onboarding candidates, but they are strong regional discovery resources worth keeping in memory because they expand beyond the US/EU dental lane.

### Dental-focused regional resources

| Resource            | Country | Type                                       | Official URL                         | Why it matters                                                          | Main risk                                                               |
| ------------------- | ------- | ------------------------------------------ | ------------------------------------ | ----------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Dental Expo 2026    | Morocco | dental fair + scientific forum             | `https://www.mdentalexpo.ma/lang/en` | strong Maghreb dental anchor; large oral-health event in Casablanca     | event-platform style site, likely mixed marketing content               |
| DENTEX Algeria 2026 | Algeria | dental exhibition + conferences            | `https://www.dentex.dz/en/`          | strong Algeria dental trade-show source with clear dates, venue, themes | exhibition-heavy pages may change around annual editions                |
| AMIED               | Morocco | implantology / esthetic dentistry congress | `https://amied.ma/`                  | useful specialty congress source in Marrakech                           | narrower specialty scope, likely low event yield outside congress cycle |

### Medical / healthcare regional resources

| Resource                  | Country | Type                                              | Official URL                       | Why it matters                                                                | Main risk                                                                         |
| ------------------------- | ------- | ------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Morocco Medical Expo 2026 | Morocco | medical exhibition + forum                        | `https://www.mmedicalexpo.ma/`     | broad healthcare fair with strong North Africa reach                          | commercial fair site, broad category noise                                        |
| AMTS 2026                 | Algeria | medical tourism / hospital / wellness salon       | `https://www.amts-expo.com/`       | useful Algeria healthcare-business source, more medical than dental           | broader than core MVP, may not fit early taxonomy cleanly                         |
| SOMEDEX                   | Algeria | medical & hospital equipment salon                | `https://www.somedex-dz.com/`      | regional hospital-equipment and healthcare event source                       | more exhibitor/equipment heavy than attendee-event oriented                       |
| Forum de l'Officine 2026  | Tunisia | pharmacy / health forum                           | `https://www.forumdelofficine.tn/` | good Tunisia healthcare-professional event signal, clean dedicated event site | pharmacy-adjacent rather than dentist-first                                       |
| TUSAMED                   | Tunisia | health / innovation / Sino-African medicine forum | `https://www.tusamed.com/`         | useful Tunisia cross-border medical event lead                                | currently shows 2025 event cycle, so freshness must be verified before onboarding |

### Suggested regional sequencing

If and only if the core dental lane is stable, the recommended Maghreb expansion order is:

1. `morocco_dental_expo`
2. `dentex_algeria`
3. `morocco_medical_expo`
4. `amied`
5. `forum_officine_tn`

This keeps the regional expansion close to the current dental-first MVP before widening into broader medical fairs.

---

## 5 — LinkedIn discovery pack

Use these as **manual discovery searches** on LinkedIn when expanding source coverage in any region.

The Maghreb / North Africa examples below are a regional pack, not the limit of where LinkedIn should be used.

### How to use them

- Search in **Posts** first for fresh event announcements
- Then search in **Companies** for organizer pages
- Then search in **People** for organizers, marketing leads, and association accounts
- Prefer the last 30 days when looking for current event cycles
- Start with global templates, then swap in the country, city, specialty, and year you care about
- Run the queries in English first, then in the dominant local language for the region you are exploring

### Global search templates

Paste these into LinkedIn search and replace placeholders as needed:

- `"medical conference" <country> <year>`
- `"dental congress" <country> <year>`
- `"healthcare expo" <city> <year>`
- `"medical seminar" <city> <year>`
- `"continuing education" healthcare <country>`
- `"webinar" healthcare <specialty> <country>`
- `"association annual meeting" <specialty> <country>`

### Regional examples — Maghreb / North Africa

### Post searches

Paste these into LinkedIn search:

- `"dental congress" AND (Morocco OR Maroc OR Algeria OR Algérie OR Tunisia OR Tunisie)`
- `"medical expo" AND (Morocco OR Maroc OR Algeria OR Algérie OR Tunisia OR Tunisie)`
- `"healthcare forum" AND (North Africa OR Maghreb OR Afrique du Nord)`
- `"congrès dentaire" AND (Maroc OR Algérie OR Tunisie)`
- `"salon médical" AND (Maroc OR Algérie OR Tunisie)`
- `"forum santé" AND (Maroc OR Algérie OR Tunisie)`

### Company searches

- `"Dental Expo" Morocco`
- `"DENTEX" Algeria`
- `"Morocco Medical Expo"`
- `"AMTS" Algeria medical`
- `"SOMEDEX" Algeria`
- `"Forum de l'Officine" Tunisie`
- `"congrès dentaire" Maroc`
- `"salon médical" Algérie`

### People searches

- `"event manager" healthcare Morocco`
- `"responsable communication" congrès dentaire Maroc`
- `"marketing manager" medical expo Algeria`
- `"organisateur" salon médical Algérie`
- `"directeur" événement santé Tunisie`
- `"project manager" congress healthcare North Africa`

### What LinkedIn is good for

- spotting newly announced editions before search engines catch up
- finding organizer names and company pages
- finding alternate spellings across English and local languages
- confirming whether a source is active this year before adding parser effort

LinkedIn should guide discovery, not replace official-site verification. Do not seed a source until an official event page exists.

---

## 6 — Facebook Events discovery pack

Facebook is a useful discovery surface in any region, especially where organizers post event dates, venue updates, or registration announcements there earlier or more visibly than on their official websites.

### How to use it

- Search **Events** first, then **Pages**
- Prefer the current year plus the city name when available
- Start with global templates, then swap in the country, city, specialty, and year you care about
- Check both English and the dominant local language for the region you are exploring
- Treat Facebook as a discovery and freshness signal only
- Do not seed a source from Facebook alone; always verify against an official page or organizer site

### Global event search templates

Use these in Facebook search and replace placeholders as needed:

- `<medical specialty> conference <country> <year>`
- `<medical specialty> congress <city> <year>`
- `medical expo <country> <year>`
- `healthcare forum <city> <year>`
- `medical seminar <city> <year>`
- `dental fair <country> <year>`
- `CME <specialty> <country> <year>`

### Global page search templates

- `<medical specialty> association <country>`
- `medical expo <country>`
- `healthcare congress <city>`
- `medical seminar organizer <country>`
- `dental fair <city>`

### Regional examples — Maghreb / North Africa

### Event searches

Use these in Facebook search:

- `Dental Expo Morocco 2026`
- `DENTEX Algeria 2026`
- `Morocco Medical Expo 2026`
- `AMIED Marrakech 2026`
- `Forum de l'Officine Tunisie 2026`
- `congrès dentaire Maroc 2026`
- `salon dentaire Maroc 2026`
- `salon dentaire Algérie 2026`
- `salon médical Maroc 2026`
- `forum santé Tunisie 2026`
- `événement santé Maghreb 2026`

### Page searches

- `Dental Expo Casablanca`
- `DENTEX Algérie`
- `Morocco Medical Expo`
- `AMIED Marrakech`
- `Forum de l'Officine Tunisie`
- `salon médical Algérie`
- `congrès dentaire Maroc`

### What Facebook is good for

- spotting newly announced editions before search engines index them
- finding organizer pages and alternate event titles
- verifying whether an edition is active this year
- finding city-specific event posters and registration-opening posts across local-language communities

### Watch-outs

- Facebook event pages are often duplicated or reposted by attendees or exhibitors
- titles may differ from the official organizer wording
- dates may be stale if an old edition is being reshared

Use Facebook to find leads, then confirm them on an official organizer or event site before parser work starts.

---

## 7 — Pre-W2 prep tasks

These are the only prep tasks worth doing before W2 implementation planning:

1. confirm the final W0+W1 code exposes the fields and parser hooks assumed by the W2 spec
2. store ADA canary HTML fixtures
3. manually review robots.txt / terms for ADA, GNYDM, AAP, FDI, and EAO
4. decide the source code naming convention for future seeds (`gnydm`, `aap_annual_meeting`, `fdi_wdc`, etc.)
5. keep `sources.yaml` limited until ADA runs cleanly from schedule

---

## 8 — What to defer on purpose

Do **not** do these during W2 prep:

- seed all shortlisted sources into the live config immediately
- build generic parser logic to satisfy future sources
- onboard aggregator directories before official-source coverage exists
- widen into broad medical sources before the dental lane proves the maintenance posture

---

## 9 — Decision gates

After ADA is working, ask these before onboarding the next source:

1. Did ADA require frequent manual parser fixes?
2. Did the source-local update path avoid duplicate churn?
3. Were `review_items` useful, or just noise?
4. Do we understand which shape hurt us most: listing extraction, date inference, or external registration links?

If the answer is "no" to any of the above, fix the pattern before adding more sources.

---

## 10 — Recommended next planning move

Once W0+W1 code is in place:

- write the W2 implementation plan from the W2 sub-spec
- keep it strictly source-bounded to `ada`
- treat `gnydm` only as a smoke candidate, not as guaranteed scope
