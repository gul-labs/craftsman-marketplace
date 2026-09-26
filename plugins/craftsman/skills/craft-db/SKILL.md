---
name: craft-db
description: >-
  The Craftsman standard for database work — schema design, migrations, query writing, indexing, and
  multi-tenant data scoping. Use this WHENEVER the work touches the database in any form: designing
  or changing schema, writing migrations, modeling tables or relations, writing or optimizing queries,
  adding indexes, handling soft-deletes, scoping data to a tenant, or wiring up connection pooling.
  Trigger even when the user only says "add a column", "this query is slow", "design the data model",
  or "write a migration" without naming an ORM or dialect.
---

# DB Craft

This skill encodes one engineer's method for database work. Discover the target repo's dialect,
current adapter, migrations, and tenant-scope helpers before editing. Projects that explicitly
adopt the Craftsman Postgres profile follow `references/postgres-standard.md`: its Node adapter is
`pg` with `drizzle-orm/node-postgres`. Elsewhere, assess the actual provider, runtime, and failure
evidence before recommending a driver migration. Other dialects need their own choices.

## Operating principle — discover before you build

Different repos are at different points in their DB evolution. Before touching anything, spend a few
minutes mapping what already exists so you extend rather than duplicate or fight the grain:

- `package.json` / lockfile → is `drizzle-orm`, `prisma`, `knex`, `pg`, `mysql2`, or similar
  already present?
- Existing migration directory (e.g. `drizzle/`, `prisma/migrations/`, `db/migrations/`) → what
  conventions are already established (naming, timestamps, reversibility)?
- Schema files → column naming style (camelCase vs snake_case), timestamp columns (`createdAt` /
  `created_at`), soft-delete column name and type, how tenant id is stored and named.
- Query helpers → is there a shared conditions/helpers file that enforces tenant scoping and
  soft-delete filters? Read it before writing any query.
- Dialect → Postgres, MySQL, SQLite? Some patterns (advisory locks, `RETURNING`, expression indexes)
  are dialect-specific.

State what you found, then propose the smallest set of changes that achieves the goal.

## The data layers (work in this order)

1. **Schema design** — model the domain correctly before writing a line of migration code. Choose
   the right types, enforce NOT NULL where the domain demands it, express relationships as real
   foreign keys, and name columns consistently with the existing schema. See `references/schema.md`.

2. **Migrations** — translate the schema design into a forward-only migration, reviewed before it
   ever runs. Prefer reversible migrations where the cost is low (drop → add back); know when
   forward-only is the honest choice. See `references/migrations.md`.

3. **Access patterns** — every query that touches a tenant table must go through a shared helper
   that enforces the tenant id (always, when multi-tenant) **and** the soft-delete filter **when
   the project uses soft-delete**. Write queries against real access patterns, not "I might need
   this later". See `references/access-patterns.md`.

4. **Indexing** — add indexes for the query patterns you can see in the code, measured with
   EXPLAIN/EXPLAIN ANALYZE. An index you haven't verified helps is a write-amplification tax.
   See `references/indexing.md`.

5. **Integrity & safety** — prefer DB-level constraints and foreign keys over app-level validation;
   wrap multi-step writes in transactions; plan large backfills as separate steps, not inside a
   schema migration. See `references/integrity.md`.

## Standing opinions (the non-negotiables)

These judgments keep output consistent — apply them unless the user overrides:

- **Every tenant-scoped query goes through a shared helper.** That helper enforces the tenant id
  always (when multi-tenant), and the soft-delete filter **when soft-delete is used** (see
  `schema.md` "When soft-delete is used"). Querying a tenant table raw — even "just this once" —
  is the pattern that ships data leaks. Don't do it.
- **Migrations are generated and reviewed, never auto-pushed to production.** The migration tool's
  "push" shortcut skips the review step and, with some versions, produced non-convergent diffs (this
  was a confirmed drizzle-kit pre-0.20 behavior; verify the behavior of the version in use before
  relying on push even in dev). Generate a migration file, read it, then apply it.
- **DB constraints beat app-level checks.** A unique constraint enforced by the database holds even
  when a second process, a migration script, or a future developer bypasses the application layer.
  Write the constraint first, then add app-level validation for UX.
- **Index for measured patterns, not guesses.** Run EXPLAIN ANALYZE on the slow query, confirm the
  index would be used, then add it. Speculative indexes cost write performance on every insert and
  update.
- **For projects adopting the Postgres profile, one query per socket and every transaction bounded.** Use a
  driver configuration that never pipelines (node-postgres with `pipeline` off),
  attach error handlers to idle *and* checked-out clients, and route every transaction through one
  helper with a deadline covering pool acquisition and transaction work. Timeouts come from role
  defaults and `SET LOCAL`, not startup parameters. Runtime traffic and migrations use separate
  guarded URLs, and tests never reach a non-loopback database. The profile's numeric limits and
  exception process are in `references/postgres-standard.md`.
- **Destructive or large-table migrations are split into stages.** Add the column nullable → backfill
  in batches → add the constraint → drop the old column. Doing all four steps in one migration risks
  long locks and an unrecoverable failure mid-way.

## Workflow

1. **Discover** the repo's ORM, dialect, migration tool, schema conventions, and tenant-scope
   helpers. Report what you found and what's missing.
2. **Propose** the schema change or query approach, explaining why the types/constraints/indexes
   make sense for the domain.
3. **Implement** — generate the migration following the repo's tooling (e.g. `pnpm db:generate`),
   name and format it consistently with existing migrations, write queries through the repo's
   shared helpers.
4. **Verify** — run the migration up, spot-check the resulting schema, and run EXPLAIN on any
   query that will hit a large table or run in a hot path. Migrations you haven't seen applied
   aren't done.

## Dialect note

These docs assume PostgreSQL. If your project uses SQLite or MySQL, check driver-specific notes in each section — locking semantics, JSON column support, and some index/constraint behaviors differ.

## Reference index

Read the one matching the current task — they hold the concrete patterns, not this overview:

- `references/postgres-standard.md` — canonical requirements, scope, operational defaults, and exceptions for projects adopting the Craftsman Postgres profile
- `references/schema.md` — column types, naming conventions, timestamp and soft-delete patterns
- `references/migrations.md` — generation workflow, naming, reversibility, safe apply checklist
- `references/access-patterns.md` — tenant-scoped query helpers, soft-delete filtering, pagination
- `references/indexing.md` — EXPLAIN workflow, index types, GIN indexes, partial indexes, composite key order
- `references/integrity.md` — transactions, FK strategy, constraint naming, large-table backfill stages
- `references/connection-pooling.md` — pool sizing and fleet budget, driver choice behind poolers, runtime vs direct URLs, node-postgres pool config, timeouts and roles, the transaction helper, session locks, leak detection
- `references/driver-migration.md` — moving postgres.js → node-postgres: inventory, result-shape/type compatibility tests, option mapping, raw-API rewrites, verification gate
- `references/seeding-and-testing.md` — idempotent seeds, FK-aware ordering, per-test transaction rollback, test-database safety, standard DB test suites T1–T8

## Audit checklist (for craft-audit)

When `craft-audit` plans a db pass for a scope, it turns this checklist into the `plan.md`
todo list — the checklist is owned by this skill, not improvised by the orchestrator. Tailor to what
discovery found: skip a step that genuinely doesn't apply with a one-line reason; never silently drop
one. Emit findings using craft-audit `workspace.md` → "Canonical findings.md emission format"
(authority). Heading grammar (variables required — do not hardcode NNN/severity/status):

`## <scopeLabel>-DB-<NNN> · severity <🔴|🟡|🟢> · status <open|fixed|wontfix (reason)|regressed|fixed (merged into <ID>)>`

Example only: `## <scopeLabel>-DB-001 · severity 🔴 · status open`

Required fields under each heading, in order, with these exact labels:
`**What breaks (plain language):**` · `**Technical:**` · `**Fix:**` · `**Fingerprint:**` ·
`**Last-checked:**` (optional `**Confidence:**` — `verified | inferred | unverified-from-repo`, absent
means `verified` — then optional `**Fix-attempt:**` only from craft-fix).
Assign sequential NNN per (scope, domain); judge severity with craft-audit `prioritization.md`.
Forbidden: `###` headings; `## ID · 🔴 · open` shorthand; severity/status as body bullets.

- [ ] Map the repo's ORM, dialect, migration tool, schema conventions, and tenant-scope helpers
      before judging anything; flag assumptions made without this discovery → `SKILL.md` (Operating
      principle)
- [ ] Audit schema modeling: wrong/loose column types, missing NOT NULL on required fields,
      relationships not expressed as real foreign keys, float for money, inconsistent naming →
      `references/schema.md`
- [ ] Check every tenant-scoped query routes through the shared helper enforcing tenant id
      (multi-tenant required); soft-delete filter is mandatory on that helper **only when the
      project uses soft-delete** — do not invent a soft-delete requirement on hard-delete schemas;
      flag raw tenant-table reads, `SELECT *`, OFFSET pagination, and N+1 →
      `references/access-patterns.md` · `references/schema.md`
- [ ] Verify DB-level integrity: constraints/unique/FK at the database not just app-level checks,
      on-delete strategy chosen deliberately, multi-step writes wrapped in transactions →
      `references/integrity.md`
- [ ] Review migrations: generated-and-reviewed (never auto-pushed/`push` mode), named and
      timestamped consistently, reversible where cheap, breaking changes done expand-contract →
      `references/migrations.md`
- [ ] Confirm indexes back measured query patterns via EXPLAIN/EXPLAIN ANALYZE, with correct
      composite column order; flag speculative, redundant, or write-amplifying indexes →
      `references/indexing.md`
- [ ] Check destructive or large-table changes are staged (add nullable → batched backfill → add
      constraint → drop old), not done in one long-locking migration → `references/integrity.md`

The following driver, pool, timeout, migration-path and T1–T8 checks apply to projects adopting
`references/postgres-standard.md`. For other Postgres projects, use them as diagnostic questions;
do not impose an unrelated stack migration without evidence.

- [ ] Connection pool is sized appropriately (serverless starts at `max: 1`; record the fleet
      budget against the pooler's client limit, starting at 50% unless measured capacity and an
      explicit project decision justify another limit; serverless runtime constraints → craft-infra) →
      `references/connection-pooling.md`
- [ ] Flag profile driver/pooler incompatibility: postgres.js in runtime, workers, scripts or migrations;
      `max_pipeline: 0` as a supposed fix; node-postgres `pipeline: true`; named prepared statements on
      pooled connections; if a move is warranted, plan it with the migration playbook →
      `references/connection-pooling.md` · `references/driver-migration.md`
- [ ] Pool construction: one pool per process (cached across hot reload), error handlers on idle
      *and* checked-out clients, the platform suspension helper on serverless, pools ended on
      worker shutdown and in script `finally` → `references/connection-pooling.md`
- [ ] Connection targets: separately guarded, approved runtime and migration URLs (transaction
      pooler for transient/serverless Supabase traffic; a documented persistent runtime may use
      direct/session mode), with
      fail-closed guards (no silent port rewriting), SSL verified with an explicit object and no URL
      `ssl*` params → `references/connection-pooling.md`
- [ ] Timeouts and roles: no reliance on startup-parameter timeouts behind a pooler; role-level
      defaults below route deadlines; no plain `SET`/`set_config(…, false)` on pooled runtime
      connections; runtime and migration roles separated or the runner sets session timeouts
      before `BEGIN` → `references/connection-pooling.md` · `references/migrations.md`
- [ ] Transactions go through one helper: wall-clock deadline checked before COMMIT, a timeout
      during COMMIT reported as an unknown outcome (not blindly retried), client destroyed on any
      failure, original error rethrown with the rollback failure kept (`rollbackError`), savepoints only by
      nesting on the helper's `tx`, no network I/O inside, `xact` advisory locks only; session locks/LISTEN only in a singleton module on the direct URL, aborting work
      on connection loss → `references/connection-pooling.md`
- [ ] Migration apply path: direct/session URL, migration role, never in the platform build or at
      boot, staging first, drift check and journal test in CI → `references/migrations.md`
- [ ] Test-database safety and suites: tests cannot reach a non-loopback DB (resolver refuses under
      a test runner, no override), unit tests cannot instantiate a real pool, T1–T8 are present
      (only inapplicable subcases may be n/a with a reason), pool/driver/timeout behaviour tested
      on loopback Postgres rather than PGlite or mocks → `references/seeding-and-testing.md`
- [ ] DB health and retries: liveness has no DB call; protected readiness probes the shared pool
      within 2–5 s; pool counts and classified failures are observable; retries are limited to
      `40001`/`40P01` (at most three with jitter) or explicitly idempotent connection failures,
      never `57014` or an unknown COMMIT outcome → `references/connection-pooling.md`
- [ ] Check PII columns are identified/flagged (comment or naming convention) and kept out of
      primary keys, public URLs, and log output → `references/schema.md`
