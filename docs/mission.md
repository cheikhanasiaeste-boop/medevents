# MedEvents — Mission

## What it is

An automated global directory for medical and dental fairs, seminars, congresses, workshops, and trainings.

MVP focuses on automatically gathering and updating events from curated sources, then presenting them through a premium filtered-browsing product.

## Objective

Find events from multiple known sources, normalize the core details into a usable directory, keep listings reasonably fresh with scheduled re-crawls, and expose the result through a premium browsing experience.

MVP is not trying to be a perfect source-of-truth platform on day one. It is trying to be useful, automated, and low-touch.

## Target user (v1)

Medical and dental professionals planning which fairs, seminars, congresses, and trainings to attend.

**Primary job:** _filtered browsing_ — "show me relevant events by specialty, region, date range, and format."

Not a feed. Not a blog. Not a generic calendar website.

## Positioning

A premium event directory first; an intelligence platform later if the automated directory proves demand and operational pain.

The product should feel premium and decision-dense, but the system should earn complexity gradually.

## Strategic stance (load-bearing)

> **Automate the routine work first. Add intelligence layers only when the directory proves the need.**

- **Inside:** reliable source automation, simple normalization, low-touch updates, exception-driven review.
- **Outside:** premium, modern, high-trust UX from day one.
- **Seam:** keep ingestion and product concerns cleanly separated in code, but do not split them into extra deployables until scale or pain justifies it.

## MVP scope

| Dimension    | Commitment                                                                        |
| ------------ | --------------------------------------------------------------------------------- |
| Category     | Medical and dental events, with scope narrowing allowed if focus pressure appears |
| Coverage     | Curated known sources first; automation over breadth theater                      |
| Effort       | Solo, fast validation, complexity added only when proven                          |
| Infra stance | Simplest stack that keeps automation reliable                                     |
| Primary UX   | Filtered browsing (premium directory)                                             |

## Decision heuristics

- **Feature decision** — does it help a professional discover and compare relevant events faster?
- **Automation decision** — does it reduce routine manual upkeep without creating brittle complexity?
- **Architectural decision** — is it the simplest thing that supports automatic multi-source updates?
- **UI decision** — does it feel premium and decision-dense, not like a generic events site?
- **Escalation decision** — are we adding complexity because the MVP truly needs it, or because the long-term vision sounds exciting?
