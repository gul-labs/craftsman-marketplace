# Postgres standard

This is the **canonical Postgres policy** for a project that explicitly adopts the Craftsman
Postgres profile. `craft-db/SKILL.md` is its router and audit checklist; the other `craft-db`
references explain implementation and tests. A dated audit, a repo's runbook, or an agent pointer
records evidence and local settings but does not redefine these rules. If this standard is wrong,
correct it from upstream documentation and a reproduction, then update the affected projects.

The profile was chosen for Node.js services using Drizzle, often behind Supabase's transaction
pooler. It is a **team architecture choice**, not a claim that every other Postgres driver or
deployment model is non-compliant with PostgreSQL. For a project that has not adopted this profile,
audit its actual provider, runtime, and failure modes before recommending a migration. Do not
silently treat an exception or an unrun test as a pass.

## 1. Driver and pooler compatibility

- **1.1 Adopted Node profile:** use `pg` with `drizzle-orm/node-postgres` in runtime code,
  workers, scripts, and migrations. Pin and test the installed minor versions. The profile does
  not add postgres.js, Prisma, Neon HTTP/WebSocket drivers, or `@vercel/postgres` to those paths.
  An edge-only runtime that cannot use `pg` routes database work through a Node service or
  records a reviewed project exception with equivalent tests. `driver-migration.md` covers a
  staged move from postgres.js and its result-shape risks.
- **1.2 Transaction-pooler safety:** keep node-postgres `pipeline` unset/false and use unnamed
  statements (no named `.prepare()` or query `{ name }`). Supabase transaction mode does not
  support pipelining or prepared statements. The observed postgres.js 3.4.x transaction and
  connection-loss defects justify the adopted driver choice; they do not prove every version of
  postgres.js or every pooler has the same failure. Verify the actual path with T7.
- **1.3 Supabase data access:** the adopted profile uses the database driver for server-side
  table access. `supabase-js` may handle Auth, Storage, and Realtime; a different table-access
  architecture requires an explicit project decision.

See `connection-pooling.md` for failure mechanisms and pooler differences. Drizzle itself
supports multiple drivers; [its PostgreSQL guide](https://orm.drizzle.team/docs/get-started-postgresql)
does not impose this team's choice. [Supabase's connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)
documents transaction-mode limitations.

## 2. Connection targets and TLS

- **2.1** `DATABASE_URL` is the approved runtime endpoint. For transient/serverless Supabase
  traffic, use the transaction pooler (`:6543`); a persistent backend may use direct or session
  mode when the project records why and budgets those server connections. Never infer an endpoint
  by rewriting a port. A narrower runtime role uses `<ROLE>_DATABASE_URL` with the same endpoint
  choice. `DATABASE_URL_DIRECT` is a direct or session endpoint for migrations, DDL, operator
  scripts, and allowed singleton session work.
- **2.2** URL guards fail closed against the project's recorded hosts and modes. A Supabase
  direct/migration factory refuses `:6543`, including an effective port supplied through
  `PGPORT`. Tests and test runners refuse non-loopback URLs without an override switch.
- **2.3** Strip conflicting `ssl*` connection-string parameters before passing an explicit TLS
  configuration. Verify certificates (`rejectUnauthorized: true`); use the system trust store
  when appropriate or the provider CA when needed. Loopback may use `ssl: false`. A project
  records its endpoint and trust choice, never a credential in source or logs.

[node-postgres SSL guidance](https://node-postgres.com/features/ssl) explains why URL SSL
parameters can replace an explicit `ssl` object. `connection-pooling.md` supplies guard and
pool-config patterns.

## 3. Pool and fleet budget

- **3.1** Build pool configuration in a pure function. Create a lazy, process-cached singleton;
  attach handlers for idle-pool and checked-out-client errors. End worker pools after drain and
  script pools in `finally`. On Vercel, use its supported pool suspension helper.
- **3.2** Start Vercel/Supabase functions at `max: 1`; raise only with recorded queue/wait
  evidence, normally no higher than 5 under this profile. A worker's `DB_POOL_MAX` caps its DB
  concurrency, not its total activity count. Record every runtime's `max`, instance ceiling,
  provider client limit, and sum of `max × ceiling`. The team's initial safety budget keeps that
  sum at or below 50% of the pooler's client limit; change it only with measured capacity and
  an explicit project decision. These numbers are operating defaults, not PostgreSQL limits.
- **3.3** Do not create a pool per request or use named prepared statements on a transaction
  pooler. Reserve manual `pool.connect()` for the transaction and singleton session helpers.

See `connection-pooling.md` for lifecycle mechanics and
[node-postgres pool sizing](https://node-postgres.com/guides/pool-sizing) for workload tradeoffs.

## 4. Timeouts and roles

- **4.1** Use distinct runtime and migration/owner roles, with a separate worker role when
  needed. Set server defaults using `ALTER ROLE … IN DATABASE`. Choose the runtime
  `statement_timeout` below its shortest relevant request deadline with a margin; 10 seconds
  for a 15-second route and 60 seconds for a worker are initial examples, not universal values.
  Verify the effective setting through the actual pooler.
- **4.2** The direct migration runner sets its own session `statement_timeout` and
  `lock_timeout` before `BEGIN`; this is mandatory when it shares a role with runtime.
- **4.3** `pg`'s client `query_timeout` is only a backstop above the server limit, usually by
  about five seconds. A client timeout does not prove a sent statement was canceled.
- **4.4** On a transaction-pooled runtime connection, do not depend on startup-parameter
  timeouts or use session `SET` / `set_config(…, false)`. Put per-transaction settings inside
  the transaction with `SET LOCAL` or `set_config(…, true)`.

[PostgreSQL ALTER ROLE](https://www.postgresql.org/docs/current/sql-alterrole.html) and
[SET](https://www.postgresql.org/docs/current/sql-set.html) define server semantics;
`connection-pooling.md` explains pooler behavior.

## 5. Transactions and session state

- **5.1** Route application transactions through one helper that accepts a deadline and passes
  `(tx, AbortSignal)` to its callback. The deadline includes pool acquisition. The helper checks
  time before allowing COMMIT, destroys a failed or timed-out checked-out client, and preserves
  the callback's original error when rollback also fails. A client-side timeout before a
  *confirmed* COMMIT cannot by itself prove immediate server rollback; check persisted state in
  tests and never report success while cleanup is unknown.
- **5.2** Once COMMIT may have been sent, a client timeout, connection loss, or rollback attempt
  does not prove whether the write committed. Return an unknown-outcome error unless the server
  supplied an authoritative transaction-abort response. Error classification unwraps Drizzle's
  `cause` chain. Reconcile unknown writes by idempotency key before retry.
- **5.3** Transaction-scoped tenant context uses `set_config(…, true)`; request/worker advisory
  locks use `pg_advisory_xact_lock`. Savepoints nest through the helper's `tx`.
- **5.4** Session locks, LISTEN, and session cursors belong only in a singleton worker/operator
  module on a separately budgeted direct/session `max: 1` pool. Connection loss aborts the
  protected operation; durable fencing protects against stale holders.
- **5.5** Await DB work sequentially inside one transaction. Do not await HTTP, LLM, email, or
  storage operations while holding a checked-out client. Commit an intent, perform external
  work idempotently, then commit completion; never delete external bytes inside a transaction
  that can roll back.

`connection-pooling.md` explains the helper and session work. Its code is an implementation
sketch, not proof of these guarantees; T5/T7 on loopback Postgres are the gate.

## 6. Migrations

- **6.1** Generate and review migration SQL and its journal; register hand SQL and
  nontransactional steps in the real runner with an applied log.
- **6.2** Apply with the project's `db:migrate` on `DATABASE_URL_DIRECT` using the migration
  role, staging first. A human or manually dispatched job runs it. Never run it in a platform
  build, app/worker boot, or ordinary quality CI.
- **6.3** This profile allows schema `push` only on guarded loopback databases. That is a
  review and data-safety policy, not a claim that Drizzle cannot use `push` elsewhere.
- **6.4** Test the exact registered chain from zero, including `CREATE INDEX CONCURRENTLY` and
  other steps outside a transaction. Quality CI checks generated-schema drift and journal
  completeness without connecting to a database.

See `migrations.md` for the release sequence and
[Drizzle's documented migration modes](https://orm.drizzle.team/docs/migrations).

## 7. Test safety and evidence

- **7.1** Test suites cannot reach a non-loopback database. Unit tests do not instantiate a real
  pool. PGlite can prove relational semantics; pool, timeout, connection-loss, and migration
  behavior needs a throwaway loopback Postgres at the production major version.
- **7.2** Projects adopting this profile use the T1–T8 suite IDs and assertions in
  `seeding-and-testing.md`. T1–T4 and T8, plus drift/journal checks, run in `quality:ci`;
  T5–T7 run in `quality:full`. Only truly inapplicable subcases may be marked n/a with a reason.
- **7.3** T5 must cover acquisition timeout, an expired callback before COMMIT, a timeout
  around the callback/COMMIT boundary, a sent COMMIT with a lost or locally timed-out reply,
  cause-wrapped connection errors, rollback failure, and a known server rejection. T7 proves
  recovery and no client reuse. Do not call an illustrative helper validated merely because
  the written test plan mentions these cases.

## 8. Health, observability, and retries

- **8.1** `/health/live` does no DB work. Protected `/health/ready` probes the shared pool with
  `SELECT 1` and a short client-side budget (2–5 seconds is this profile's starting point).
  `HEALTH_MONITOR_SECRET` is the profile's monitor credential, not a Postgres requirement.
- **8.2** Instrument the actual driver query path, including both pool convenience queries and
  queries on checked-out transaction clients, exactly once. Record slow queries, classified
  errors, and total/idle/waiting pool counts in a durable destination. Do not expose DB state
  publicly or count an unscripted in-memory metric as production observability.
- **8.3** Retry complete transactions on `40001` or `40P01` with bounded jittered backoff;
  this profile's ceiling is three attempts. Retry connection failures only for explicitly
  idempotent work. Never blindly retry `57014` or an unknown COMMIT outcome. Temporal activity
  retries are a separate outer policy.

[PostgreSQL's serialization guidance](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html)
requires a complete transaction retry, including decisions based on prior reads.

## 9. Local configuration and changes to this standard

Each project records only its facts: provider endpoints, role names, certificate trust,
timeouts, instance ceilings and fleet budget, test evidence, and approved deviations. An
exception states the workload constraint, alternative, risk, owner, and verification result.
Project records and dated audits never silently override this document. Change a generally
wrong rule here once, then update affected checklists and examples in the same work.
