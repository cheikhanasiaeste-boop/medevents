# MedEvents — Guidelines

Principles that govern every feature, architectural change, and product decision on MedEvents. When in doubt, ask whether the change helps us ship and operate an automated directory MVP with low-touch upkeep, or whether it is premature platform work.

## Architectural principles

### 1. Start as an automated directory, not a full intelligence platform

The MVP goal is automatic ingestion and updating from multiple known sources with minimal manual upkeep.

Do not build target-state platform complexity before the MVP proves demand or operational pain.

### 2. Automate known-source ingestion; accept exception-driven review

Routine work should be automatic:

- scheduled crawling
- extraction
- normalization of core fields
- update detection
- publish/update of ordinary events

Manual intervention is acceptable for exceptions:

- new source onboarding
- parser breakages
- ambiguous duplicates
- suspicious or low-confidence records

Zero-touch is not required. Low-touch is.

### 3. Keep the architecture simple until real pain appears

Prefer fewer deployables, fewer datastores, and fewer moving parts.

Logical separation in code is good. Operational separation into extra apps and services should be earned.

### 4. Trust starts with visible source transparency and freshness

For MVP, source links, last checked timestamps, and clear event status matter more than deep provenance machinery.

Field-level provenance, confidence math, and forensic history are later-stage upgrades.

### 5. Structured enough to automate, not exhaustive enough to stall

Model the fields users actually filter and compare on:

- title
- date range
- location
- format
- event type
- source link
- registration link
- organizer
- specialty/topic
- lifecycle status

Do not attempt to model every edge case before launch.

## Product principles

- **Premium, not template.** The experience should feel intentional and trustworthy.
- **Decision-density, not browsing theater.** Every page should help users decide where to go.
- **Fast feedback.** Filters and search should feel immediate.
- **Mobile-first.** Touch-friendly and usable on the go.
- **Source transparency everywhere.** The user should always be able to see where an event came from.

## Engineering stances

- **Quality over cleverness.** Reliable automation beats ambitious architecture.
- **Operator workflow matters.** MVP can use lightweight review tooling instead of a full admin platform.
- **Use AI selectively.** Apply it where it clearly reduces manual ops or improves UX; do not force it into every surface.
- **Prefer reversible decisions.** Delay service splits, search engines, and deep data models until they are justified.
- **Measure pain before solving for scale.** Build the next layer only after the current one shows strain.

## How to apply

When proposing a feature or architectural change, validate it against these principles. Push back if the change:

- adds new services before the current flow is proven
- models long-tail complexity that users will not feel in MVP
- requires humans in the normal ingestion/update path
- weakens source transparency or freshness
- delays launch without materially de-risking automation
