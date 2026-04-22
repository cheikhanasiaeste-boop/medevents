# W3.2d — Fly.io scheduled machines wiring

Date: 2026-04-23
Parent wave: W3.2 (per [`docs/TODO.md`](../../TODO.md) "Now" sequence).
Predecessor sub-specs:

- [W1 foundation](2026-04-20-medevents-w1-foundation.md) §324 — locked architecture: "A small Fly machine wakes hourly, runs `medevents-ingest run --all`, exits. No long-running scheduler process."
- [W3.2b](2026-04-23-medevents-w3-2b-run-all-due-selection.md) — landed the `run --all` primitive that this wave calls.
- [W3.2c](2026-04-23-medevents-w3-2c-drift-observability.md) — landed drift observability so autonomous runs surface drift to the review queue.

## 1 — Objective

Wire `medevents-ingest run --all` into Fly.io scheduled machines so the ingest pipeline runs hourly without operator intervention. This is the wave that turns the project from "a CLI tool you can run manually" into "an automated directory MVP running in production."

**Two-stage delivery:** the autonomous half ships in this PR (repo artifacts + runbook); the operator-action half is documented in the runbook and requires the user's Fly.io account to complete.

## 2 — Context

- Until this wave, the ingest CLI exists but is manually invoked. `last_crawled_at` in the dev DB only advances when a human types `medevents-ingest run`.
- `run --all` (W3.2b) is the intended scheduler target. It handles due-selection internally, continues on per-source failure, and exits non-zero only when every selected source failed — matching the robustness a scheduled machine needs.
- All internal primitives are on `main`: bookkeeping (W3.2a), scheduler CLI (W3.2b), drift observability (W3.2c). Nothing else blocks external-scheduler wiring.
- Fly.io's "scheduled machines" feature runs a container on a cron expression, auto-starting and stopping the machine between runs (no long-running process, no idle cost). Matches W1 §324's "wakes hourly, runs, exits" architecture.

## 3 — Scope

### 3.1 In scope (ships autonomously in this PR)

- **`services/ingest/Dockerfile`** — multi-stage build: (1) `python:3.12-slim` base + `uv` installer + dep install via `uv sync --frozen`; (2) runtime image copying only the virtualenv + source. Entrypoint runs `medevents-ingest run --all` as the default command so the scheduled machine doesn't need to specify args.
- **`fly.toml`** at the **repo root** (not `services/ingest/`) — Fly app config with `app = 'medevents-ingest'` (or a user-chosen name), `primary_region`, `build.dockerfile = 'services/ingest/Dockerfile'`, and a `[[machines]]` section marking the machine as scheduled with an hourly cron expression. No HTTP service (ingest doesn't expose a port). Root placement is deliberate so Fly's default build context reaches the workspace-root `pyproject.toml` + `uv.lock`.
- **`docs/runbooks/w3.2d-fly-scheduler-deploy.md`** — step-by-step operator runbook covering:
  - Prerequisites (Fly account, credit card on file, `flyctl` installed).
  - `fly apps create medevents-ingest`.
  - Database access: two options — (a) a Fly Postgres cluster created via `fly postgres create` + attached via `fly postgres attach`; (b) an existing cloud Postgres reachable from Fly (e.g. Supabase, Neon) with SSL. Neither auto-configured; operator chooses.
  - `fly secrets set DATABASE_URL=...`.
  - `fly deploy` to build + push the image.
  - `fly machines list` / `fly logs` to verify the first scheduled run.
  - Rollback procedure (`fly deploy --strategy rolling`, `fly releases list`, `fly releases rollback`).
  - Cost expectations (one machine, wakes hourly, ~1 min per run ≈ $1/month).
- **Repo-level smoke**: build the Docker image locally and run `medevents-ingest --help` inside the container to verify the build is valid before shipping.
- **`docs/state.md` + `docs/TODO.md` updates**: W3.2d marked as "Repo artifacts shipped, operator deployment required before ✅ Complete." Third source (W3.2e) promoted to "Next" for when operator finishes Fly deployment.

### 3.2 Out of scope

- Automated deployment. `fly deploy` requires the user's Fly credentials + an initialized app — both operator actions. The runbook lists the commands; the assistant does not run them.
- Fly Postgres provisioning. The operator chooses DB strategy (Fly PG vs external cloud PG). Runbook covers both paths; spec doesn't prescribe one.
- Alerting / paging from Fly. Fly logs are enough for MVP; Datadog / Sentry wiring is a follow-up if operators want proactive alerts.
- CI/CD GitHub Actions → Fly. Initial deploy is manual (`fly deploy` from operator's machine). Automated image push on merge to `main` is W3.3+ polish.
- A web-service Fly app for the admin UI. The Next.js app deploys elsewhere (Vercel-style host or a second Fly app); W3.2d is purely about the ingest scheduler.

## 4 — Design decisions

### D1. Base image: `python:3.12-slim` not `python:3.12-alpine`

**Decision: slim, not alpine.** `psycopg[binary]` wheels don't exist for musl on all architectures, and `lxml` has the same story. Slim avoids the "debug a failed alpine build" spiral; the ~40 MB image size cost is acceptable for a machine that runs hourly, not at scale. If size becomes a pain point later, revisit with static-linked psycopg builds.

### D2. Dependency install: `uv sync --frozen` inside the image

**Decision: use `uv` inside the container, not `pip`.** The project uses `uv` throughout local dev + CI; using the same tool inside the container avoids "works locally, breaks in Fly" drift from pip resolving dependencies differently. `uv.lock` (if present) pins exact versions; `--frozen` fails the build on lockfile mismatch instead of silently resolving anew.

If `uv.lock` doesn't exist yet, the spec mandates generating one as part of W3.2d (via `uv lock` locally, then commit). Fly deploy must reproduce the same environment bit-for-bit.

### D3. Entrypoint: `medevents-ingest run --all` as default `CMD`

**Decision: bake the scheduled-run command as the image's default.** Fly's scheduled machine runs whatever the image's `CMD` is. Baking `run --all` means the fly.toml scheduled-machine definition doesn't need an `args = [...]` line — a minor but real simplification that also makes `docker run <image>` equivalent to "what the scheduled machine does," useful for local debug.

Overrides are possible (`fly machine run <image> --command 'medevents-ingest run --source ada'` for manual one-off), but the default is "run everything that's due."

### D4. Fly scheduled-machine syntax

**Decision:** use `[[machines]]` with `schedule = 'hourly'` in fly.toml (or the equivalent `fly machine run --schedule hourly` command-line form). Fly accepts `hourly`, `daily`, `weekly`, `monthly`, or a cron expression. `hourly` matches W1 §324's language.

Exact fly.toml fragment:

```toml
[[machines]]
  name = "ingest-scheduled"
  schedule = "hourly"
  # schedule = "0 * * * *"  # alternative cron form, same behavior
```

### D5. Secrets: only `DATABASE_URL`

**Decision: only `DATABASE_URL` needs to be a Fly secret.** Everything else (source URLs, user-agent string) is baked into the image via code or `config/sources.yaml`. No API keys, no per-request auth. If future sources need tokens, add as Fly secrets in the wave that onboards that source.

### D6. Exit-code behavior on Fly

**Decision: Fly re-starts the machine on next schedule regardless of exit code, because scheduled machines don't retry on failure within the same tick.** Our CLI's exit-code logic (W3.2b §4 D4: 0 if any succeeded, non-zero if every selected source failed) is the right contract: non-zero indicates the batch needs operator attention in the admin UI, but Fly doesn't thrash trying to retry within the hour. Next hour's wake tries again.

### D7. Log format: Python `structlog` stdout → Fly logs

**Decision: the existing `structlog` output is already Fly-compatible (stdout lines, JSON-ish format). No additional log config.** Fly captures container stdout/stderr automatically; operators read via `fly logs`. If structured log search becomes important later, add a Fly log-shipping integration in a follow-up wave.

## 5 — Exit criteria

1. `services/ingest/Dockerfile` builds locally → image tagged `medevents-ingest:dev`.
2. `docker run --rm medevents-ingest:dev --help` prints the Typer help text without error.
3. `services/ingest/fly.toml` exists with the scheduled-machine config + Dockerfile reference.
4. `docs/runbooks/w3.2d-fly-scheduler-deploy.md` contains verbatim `fly` commands the operator runs to complete deployment, covering both DB strategies (Fly PG, external cloud PG) and rollback.
5. `docs/state.md` + `docs/TODO.md` updated: W3.2d marked "repo artifacts shipped, operator deployment pending"; W3.2e (third source) promoted to "Next" for after operator finishes deployment.
6. The PR body calls out clearly: "this PR ships repo artifacts; the operator must run the commands in the runbook to complete deployment."

There is no §6 "autonomous verification" of a live Fly deploy — that's operator-gated. The done-confirmation runbook ships as a skeleton (`w3.2d-done-confirmation.md`) with placeholders the operator fills in after deploy.

## 6 — Forward refs

- W3.2e onboards `aap_annual_meeting`. Runs autonomously via the Fly machine once deployed.
- W3.3+ candidates: (1) Fly log shipping to an external log store; (2) CI-driven auto-deploy on merge to main; (3) alerting on batch-complete-with-failures.

## 7 — Open questions for the operator (not the plan)

- **App name**: `medevents-ingest` is the spec's default. Operator can choose anything; the runbook should accept the name as a variable.
- **Region**: operator picks. If Postgres is on Fly, pick the same region. If Postgres is cloud (Supabase, Neon), pick the region nearest the Postgres host.
- **Cron schedule**: `hourly` is the recommended default. Operator can change to `daily` or a cron expression if two sources × weekly frequency doesn't need an hourly wake. Runbook notes the tradeoff.
