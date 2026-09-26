# Recommended Stack — the opinion layer (read the rules before the picks)

> **Last reviewed: 2026-06-19.** This is the **most perishable file in the plugin.** Tool pricing,
> capabilities, and the field itself change in months. Treat every pick below as a *default to fill a
> gap*, not a law — and re-review the date before quoting it. If the date is stale, verify the pick
> still makes sense before recommending it.

The other craft skills are **principle-based and stack-agnostic** — they teach what good auth, data,
and observability *are*, and stay true for years. This file is different: it's an **opinionated,
dated, swappable layer** that names concrete tools, *only* to help the paralyzed beginner who has a
genuine gap and can't evaluate ten options. The two must never be mixed: principles live in the
domain skills; the opinion lives here, in one place, so it can be updated or thrown away without
touching the durable guidance.

> **Pairs with:** `discovery.md` (detects what's already chosen), `prioritization.md` (the two-tier
> model these picks map onto). The domain skills hold the *how to use it well* for whatever's chosen.

---

## Contents

- [The three rules that govern every recommendation](#the-three-rules-that-govern-every-recommendation)
- [Tier 1 — MVP-hardening defaults](#tier-1--mvp-hardening-defaults)
- [Tier 2 — scaling-to-enterprise defaults](#tier-2--scaling-to-enterprise-defaults)
- [Quick-reject checklist](#quick-reject-checklist)

---

## The three rules that govern every recommendation

1. **Defer to what already works — never demand a rewrite.** If discovery found a working stack
   (Auth.js, Postgres on Railway, custom JWT that's actually verified), audit *that* against the
   domain principles. Recommend a tool **only where the surface is genuinely missing** ("you have no
   auth at all"), and say so. Telling someone to swap their working Auth.js for Clerk is the
   obnoxious-AI failure mode — it destroys trust and wastes their week.

2. **Match the tier to where they are.** Recommend Tier-1 defaults to harden an MVP; only raise
   Tier-2 once Tier 1 is cleared. Don't put Grafana + Prometheus in front of someone who still has no
   error tracking and no auth.

3. **Recommend, then point to the principle.** A pick is a starting point; the *quality* comes from
   the domain skill. "Add Sentry" → then craft-observability → `references/sentry.md` for how to wire it so the
   DSN comes from validated env, errors aren't gated by sampling, etc. The tool without the principle
   is just another dependency.

These rules outlive the picks. If you remember nothing else from this file, remember: **fill gaps,
don't replace working choices; tier to the project; hand off to the principle.**

---

## Tier 1 — MVP-hardening defaults

For someone going from "cool demo" to "safe to have real users." These are *sensible defaults to
fill a gap*, optimized for low setup cost and a managed/hosted path (the persona doesn't want to run
infrastructure):

| Gap | Default pick | Solid alternatives | Hand off to |
| --- | --- | --- | --- |
| **No real auth** | Clerk (managed, fast to wire) | Auth.js/NextAuth, Supabase Auth, Lucia, WorkOS | craft-security `authz.md`, craft-backend `auth.md` |
| **No real database** | Postgres via Supabase or Neon (managed), connected with node-postgres (`pg` + `drizzle-orm/node-postgres`, pipelining off) through the provider's pooled endpoint for app traffic, and a direct/session URL for migrations | PlanetScale, RDS, Railway PG | craft-db `schema.md`, `integrity.md`, `connection-pooling.md` |
| **Unsafe SQL or no migration discipline** (string-built queries, no reviewed migrations, no query boundary) | Drizzle ORM + drizzle-kit migrations for Postgres | For another database engine, retain a working ORM with parameterized queries and reviewed migrations | craft-db `access-patterns.md`, `migrations.md` |
| **No input validation** | Zod at every boundary | Valibot, ArkType | craft-backend `validation.md` |
| **No error tracking** | Sentry | — | craft-observability `sentry.md` |
| **Secrets in client / raw process.env** | A validated env module (`@t3-oss/env` or hand-rolled) | — | craft-infra `config.md`, craft-security `secrets.md` |
| **No error/empty/loading states** | (not a tool — a pattern) | — | craft-ux `layer-4-states.md` |
| **No way to see whether the core transaction finished, or that a job is stuck** | (not a tool — committed ops queries + one tested alert path) | — | craft-observability `operational-readiness.md` |

The last row matters: not every gap is a dependency. "Add an error boundary and a designed empty
state" is a Tier-1 fix with no package to install.

**Raw SQL is not itself a gap.** Disciplined, parameterized, migration-backed SQL behind a query
boundary is a legitimate, working access layer — audit it against craft-db and craft-security
principles, don't replace it. The gap is the *missing safeguard* (string-concatenated queries, no
reviewed migrations, no generated types or query boundary), and the fix is to close that safeguard —
adopting an ORM is one way, not a mandate. Recommending Drizzle to someone whose parameterized SQL is
clean is exactly the rewrite-nudge rule 1 forbids.

---

## Tier 2 — scaling-to-enterprise defaults

Only once Tier 1 is cleared and there's real traffic/a team to justify the operational weight:

| Gap | Default pick | Notes |
| --- | --- | --- |
| **No metrics pipeline** | Prometheus + Grafana (or a managed equivalent: Grafana Cloud, Datadog) | craft-observability `grafana.md` — self-hosting both is real ops work, managed first |
| **No SLOs / alerting** | Define SLOs, alert on burn rate | craft-observability `slo-alerts.md` — process before tooling |
| **No distributed tracing** | OpenTelemetry → your backend | craft-observability `serverless-vs-server.md` |
| **No structured logging** | A structured logger (pino) + log aggregation | craft-observability `logging.md` |
| **Coarse access control** | Fine-grained RBAC / policy layer | craft-security `authz.md` |
| **No audit trail** | Append-only audit log | craft-db `integrity.md` |

Tier 2 is the horizon you *name*, not the work you push first. A vibe-coded MVP with no auth does not
need Prometheus.

---

## Quick-reject checklist

| Smell | Fix |
| --- | --- |
| Recommending a tool that replaces a working one | Stop — audit the existing one instead |
| A concrete tool pick baked into a domain reference (`auth.md` says "use Clerk") | Keep picks here only; the domain skill stays stack-agnostic |
| Tier-2 tooling recommended before Tier 1 is done | Re-sequence |
| Quoting this file without checking the "Last reviewed" date | Re-verify the pick is still current |
| A pick with no hand-off to a principle | Add the domain-skill reference — the tool alone isn't the standard |
