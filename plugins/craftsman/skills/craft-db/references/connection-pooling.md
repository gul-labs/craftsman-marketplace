# Connection Pooling

A database connection is not free. Each Postgres connection consumes roughly 5–10 MB of server memory, and the backend process overhead means you hit diminishing returns (and then wall-clock degradation) long before you run out of RAM. The discipline: **size the pool to the actual concurrency your workload produces, pick a driver that behaves correctly behind your pooler, and make every timeout and transaction bounded.** An unconfigured pool — or the wrong driver behind a transaction-mode pooler — is the most common cause of "the app hangs under load" and "database is slow" complaints in freshly deployed MVPs.

> **Scope split.** This file owns connection pool configuration and sizing: pool_size math, driver choice behind poolers, pool options, timeouts and roles, the transaction helper, session-state rules, leak detection, and transaction-mode gotchas. Moving an existing app from postgres.js to node-postgres is `driver-migration.md`. Query patterns and tenant scoping are in `access-patterns.md`. Migration apply paths are in `migrations.md`. Database test suites are in `seeding-and-testing.md`. Deploy-side environment variables (DATABASE_URL, connection string construction) belong to `craft-infra` → `build-release.md`. Runtime-model constraints (serverless vs long-lived, per-instance multiplication) → `craft-infra` → `runtime-health.md`; this file owns the sizing math and driver/pooler config.

> **Dialect note:** These docs assume PostgreSQL. SQLite (single-writer, no separate server, pooling handled by the driver) and MySQL (similar pool concepts, different default limits) have different constraints — verify your dialect.

> **Authority:** `postgres-standard.md` owns the adopted profile's requirements and their scope.
> This reference explains mechanisms and supplies implementation sketches. Its numbers are
> starting points to measure against a project's recorded workload.

---

## Contents

- [Pool sizing math](#pool-sizing-math)
- [Poolers and serverless drivers](#poolers-and-serverless-drivers)
- [Choosing the Node driver behind a transaction-mode pooler](#choosing-the-node-driver-behind-a-transaction-mode-pooler)
- [Connection targets: runtime vs direct](#connection-targets-runtime-vs-direct)
- [Drizzle + node-postgres pool config](#drizzle--node-postgres-pool-config)
- [Timeouts and roles](#timeouts-and-roles)
- [The transaction helper](#the-transaction-helper)
- [Session state, advisory locks, LISTEN](#session-state-advisory-locks-listen)
- [Connection leak detection](#connection-leak-detection)
- [Health, errors, and retries](#health-errors-and-retries)
- [Transaction-mode pooler gotchas](#transaction-mode-pooler-gotchas)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Pool sizing math

**The headline for an MVP: start small and measure.** Don't derive a number from a formula before you have real traffic. Tune from `pg_stat_activity` and from the pool's own wait counter once the app is live.

The model behind that number, for when you need to reason about scaling:

```
pool_size ≈ expected concurrent requests × fraction of request time spent holding a connection
```

Where the second factor is the share of a typical request's wall-clock time actually spent waiting on the DB (0.0–1.0) — not total request time, and not worker count on its own.

**Worked example:** an instance handling 20 concurrent requests, where each request holds a DB connection for about 25% of its total time:

```
pool_size ≈ 20 × 0.25 = 5
```

**Starting points by runtime:**

| Runtime | Starting `max` | Raise when |
| --- | --- | --- |
| Serverless functions (Vercel, Lambda, Cloud Run with high concurrency) | **1** for the adopted profile | The pool's wait counter (`waitingCount` in node-postgres) is persistently > 0 and the pooler has headroom. Record the evidence next to the number; this team's default ceiling is 5, subject to a reviewed capacity decision. |
| Long-lived server (container/VM) | 5–10 | Wait time shows up in traces |
| Background worker (queue/Temporal/cron) | The worker's DB concurrency cap | Callers wait longer than your acquisition timeout |

**Fleet budget.** Every instance opens its own pool, so the number that matters is:

```
Σ over runtimes of (pool max × instance ceiling)  ≤  50% of the pooler's client limit (team starting budget)
```

The instance ceiling is the *enforced* maximum: a platform concurrency limit, a replica count or an autoscaler max. If nothing enforces a maximum, assume a conservative one and write it down beside the calculation. Serverless platforms multiply instances silently. A default of `max: 10` across 30 warm instances is 300 pooler clients.

**Workers.** `DB_POOL_MAX` is the worker process's DB concurrency cap, and the pool queues callers beyond it. Worker activity/job concurrency may exceed `max` *only if* jobs hold a connection strictly for DB work (see [the transaction helper](#the-transaction-helper): no network I/O while holding a client). Give workers a longer acquisition timeout (e.g. 30 s) than request paths (e.g. 5 s).

**Server ceiling.** Postgres `max_connections` (often 100, sometimes 25 on small managed tiers) minus ~5 superuser slots is the hard limit behind any pooler that maps clients 1:1 (session mode). Transaction-mode poolers multiplex many clients onto fewer server connections; their own client limit is then the number to budget against.

---

## Poolers and serverless drivers

### Transaction-mode poolers (PgBouncer, Supavisor, RDS Proxy)

A pooler sits between your app and Postgres. In **transaction mode** a server connection is lent to a client for one transaction and then handed to someone else, which multiplexes many app connections onto a few Postgres backends. Managed "pooled" connection strings (Supabase's, Neon's) are usually transaction mode. **Session mode** gives one server connection per client session and supports every Postgres feature, at the cost of multiplexing.

Transaction mode is the right default for app traffic from many instances, but it changes what is safe. See [the gotchas](#transaction-mode-pooler-gotchas) and [driver choice](#choosing-the-node-driver-behind-a-transaction-mode-pooler).

### HTTP/WebSocket serverless drivers (e.g. `@neondatabase/serverless`)

These exist for runtimes without persistent TCP (edge workers). They do not satisfy the adopted
Node profile in `postgres-standard.md`; route edge database work to a Node runtime using
node-postgres, or record a reviewed project exception with equivalent safety tests. This is
an architecture choice, not a claim that HTTP/WebSocket transports are inherently invalid.
Some HTTP modes also lack interactive transactions.

---

## Choosing the Node driver behind a transaction-mode pooler

**Recommendation: `pg` (node-postgres) with `drizzle-orm/node-postgres`, pipelining off.** Pin `pg` to a tested minor range.

Why this matters more than it looks. Two kinds of problem get mixed up here: **driver defects that happen behind any pooler (or none)**, and **pooler-specific behaviour** that you must verify for the pooler actually in front of the app.

- **Pipelining (pooler-specific evidence).** `postgres` (postgres.js) pipelines queries by default: when every pooled socket is busy, it writes the next query onto a busy socket (up to `max_pipeline`, default 100). Behind Supavisor's transaction mode this has been observed to park the pipelined extended-protocol messages. The query never reaches Postgres (zero server backends), no server-side timeout can fire, and the request hangs until the platform kills it. It only happens under concurrency, which is why single requests work and bursts hang. For PgBouncer or RDS Proxy, treat it as a risk to verify with a burst test (T7(c) in `seeding-and-testing.md`), not as established fact.
- **`max_pipeline: 0` is not a fix on its own (driver defect).** In postgres.js 3.4.x, `sql.begin` learns its connection through an `onexecute` hook that only runs when the connection can accept another pipelined query. At `max_pipeline: 0` it never runs, so **every transaction fails** (`TypeError … 'onclose'` at `max: 1`, `UNSAFE_TRANSACTION` at `max > 1`). `max_pipeline: 1` restores transactions but still puts two queries on a socket.
- **Connection loss mid-transaction (driver defect; postgres.js 3.4.x, any `max_pipeline`, any or no pooler).** When the server or pooler drops a connection inside `sql.begin`, the driver writes the automatic `ROLLBACK` to the closed socket (an uncaught `TypeError: Cannot read properties of null (reading 'write')`). It then parks the dead connection as "full" forever. With `max: 1`, the pool never serves another query until the process restarts. In production this reads as "a pool slot got wedged after the pooler dropped a connection". Timeouts don't prevent it.
- **node-postgres** sends a query only after the previous one's `ReadyForQuery` on that client. With its opt-in `pipeline` option (pg ≥ 8.23) left unset or `false`, a socket never has two queries in flight. When a connection is killed mid-transaction, the transaction rejects and the pool keeps serving, *provided both error handlers are attached* (see config below).
- **Serverless suspension.** Platform helpers that close idle connections before an instance is frozen, such as Vercel's `attachDatabasePool` from `@vercel/functions`, recognise node-postgres pools but not postgres.js clients.

**If an adopting repo is on postgres.js 3.4.x,** the reproduced driver defects apply whatever sits in front of the database. Behind a transaction-mode pooler the pipelining risk comes on top. Flag it with the severity your evidence supports; verify other versions before extrapolating:

- 🔴 if there is observed hanging, wedged slots or result misrouting, or high concurrency on a shared client.
- 🟡 otherwise.

Plan the move with `driver-migration.md`. Don't set `max_pipeline: 0` without also fixing the transaction path. There is no config-only fix for the connection-loss wedge.

---

## Connection targets: runtime vs direct

Use separate runtime and privileged/session URLs, even when a persistent runtime's approved
endpoint is direct. The normative target rule is in `postgres-standard.md` §2:

| Env var | Points at | Used by |
| --- | --- | --- |
| `DATABASE_URL` | the approved runtime endpoint: transaction pooler for transient/serverless traffic (e.g. Supabase `:6543`); direct/session only for a recorded persistent-runtime choice; or loopback in dev | web requests, workers, crons |
| `DATABASE_URL_DIRECT` | **session-mode** pooler or the direct host | migrations, DDL, operator scripts, singleton session locks, LISTEN |
| `<ROLE>_DATABASE_URL` (for example `WORKER_DATABASE_URL`) | the approved runtime endpoint for that role, with a narrower login role | an additional runtime pool that needs different role defaults |

Map provider vault names to these app-facing names one-to-one; do not make application code know the vault's naming scheme.

**Guards fail closed; never silently rewrite a port.**
- The runtime pool factory refuses a URL unless it is loopback or the project's explicitly approved runtime host and mode.
- The direct factory refuses the transaction-pooler endpoint. For Supabase, reject `:6543` even when the effective port comes from `PGPORT` rather than the URL.
- Both guards are unit-tested (suite T2 in `seeding-and-testing.md`).

**SSL.** Strip every `ssl*` / `sslmode` query parameter from the URL and pass an explicit `ssl` object with `rejectUnauthorized: true`. Use the system trust store when it verifies the provider, or the provider's CA (pinned in the repo or supplied via env) when required. URL parameters override or downgrade the object depending on the driver version. `rejectUnauthorized: false` in production code is a finding. Loopback uses `ssl: false`.

---

## Drizzle + node-postgres pool config

Keep a **pure, side-effect-free `buildPoolConfig(env)`** separate from the module that instantiates the singleton. The config is then unit-testable without opening a connection.

```ts
// db/pool-config.ts — pure
export function buildPoolConfig(env: DbEnv): pg.PoolConfig {
  return {
    connectionString: stripSslParams(env.url),
    ssl: env.local ? false : { rejectUnauthorized: true, ...(env.caPem && { ca: env.caPem }) },
    max: env.max,                                   // see sizing
    idleTimeoutMillis: 10_000,
    maxLifetimeSeconds: 300,                        // recycle long-lived sockets
    connectionTimeoutMillis: env.runtime === 'worker' ? 30_000 : 5_000,
    query_timeout: env.roleStatementTimeoutMs + 5_000, // client backstop only
    keepAlive: true,
    keepAliveInitialDelayMillis: 5_000,             // below the pooler's idle cutoff
    allowExitOnIdle: true,
    application_name: `${env.project}-${env.runtime}`, // shows up in pg_stat_activity
    // pipeline: never set — keeps one query in flight per socket
  }
}
```

```ts
// db/client.ts — the singleton
import pg from 'pg'
import { drizzle } from 'drizzle-orm/node-postgres'

function createPool() {
  const pool = new pg.Pool(buildPoolConfig(readDbEnv()))
  pool.on('error', report)                          // errors on idle clients
  pool.on('connect', (c) => c.on('error', report))  // errors on checked-out clients
  if (process.env.VERCEL) attachDatabasePool(pool)  // or your platform's equivalent
  return pool
}

const g = globalThis as { __dbPool?: pg.Pool }
export function getPool() {
  return (g.__dbPool ??= createPool())                 // lazy, one pool per process, HMR-safe
}
export function getDb() {
  return drizzle(getPool(), { schema })
}
```

**Both error handlers are required.** `pool.on('error')` only covers idle clients. If the server or pooler drops a *checked-out* connection and that client has no `error` listener, Node raises an uncaught `Connection terminated unexpectedly`, which crashes a long-lived process.

**Shutdown.** Workers `await getPool().end()` after draining in-flight jobs on SIGTERM. Scripts call `end()` in `finally`, so a throw doesn't leak the connection. Serverless functions don't end the pool; the suspension helper handles idle sockets.

**No named prepared statements** on pools behind a transaction-mode pooler: no drizzle `.prepare('name')` and no `{ name }` query configs. Drizzle's default statements are unnamed, which is safe.

---

## Timeouts and roles

Behind a transaction-mode pooler, session-level settings don't behave the way they do on a direct connection, and each pooler fails differently:
- **Startup parameters** (`options=-c statement_timeout=…` in the URL, a driver `connection: { statement_timeout }` option) are dropped (Supavisor), rejected unless listed in `ignore_startup_parameters` (PgBouncer), or pin the session (RDS Proxy).
- **A plain `SET`** leaks to the next client that gets that backend (PgBouncer, Supavisor), or pins your client to one backend and quietly removes the multiplexing you're paying for (RDS Proxy).

Whatever the pooler, verify with `SHOW statement_timeout` through it before trusting a setting.

What works:

1. **Distinct login roles.** Have a *runtime* role (web), optionally a *worker* role, and a *migration/owner* role. Runtime pools never log in as the owner.
2. **Role-level defaults**, applied by the owner role in a committed migration:
   ```sql
   ALTER ROLE app_runtime IN DATABASE app SET statement_timeout = '10s';
   ALTER ROLE app_runtime IN DATABASE app SET idle_in_transaction_session_timeout = '30s';
   ALTER ROLE app_worker  IN DATABASE app SET statement_timeout = '60s';
   ```
   The runtime role's `statement_timeout` must be below the shortest function/route deadline (`maxDuration`) that uses it, minus a margin. The 10 s example leaves a 5 s margin for a 15 s route. Otherwise the platform kills the request first and the query keeps running.
3. **Per-transaction limits** via `SET LOCAL` inside the transaction helper (below).
4. **A client backstop** (`query_timeout`) set a few seconds above the role timeout, so the server cancels first. It only stops the client waiting; it does **not** cancel the server statement. For plain `pool.query` calls node-postgres destroys the client after a timeout, but a checked-out transaction client needs the helper's deadline handling.
5. **Migration and script sessions** connect through the direct/session URL and set their own limits (`SET statement_timeout = 0` or an explicit value, plus `lock_timeout`) *before* `BEGIN`. Session `SET` is safe there because the session is theirs.

---

## The transaction helper

Every transaction goes through one helper; raw `db.transaction(...)` elsewhere is a finding. The helper exists because a transaction needs a **whole-transaction deadline**, a guarantee that a broken client is never reused, and an honest answer when the outcome is unknown:

```ts
import { sql } from 'drizzle-orm'
import type { PoolClient } from 'pg'

type Isolation = 'read committed' | 'repeatable read' | 'serializable'
export class TransactionDeadlineError extends Error {}       // COMMIT prevented; server abort may still be pending
export class TransactionOutcomeUnknownError extends Error {} // COMMIT may have been sent

function sqlstateInCauseChain(error: unknown): string | undefined {
  const seen = new Set<unknown>()
  for (let current = error; current && typeof current === 'object' && !seen.has(current); ) {
    seen.add(current)
    const item = current as { code?: unknown; cause?: unknown }
    if (typeof item.code === 'string' && /^[0-9A-Z]{5}$/.test(item.code)) return item.code
    current = item.cause
  }
}
function isConfirmedServerAbort(error: unknown): boolean {
  const code = sqlstateInCauseChain(error)
  // Server-reported serialization/deadlock or deferred constraint rejection at COMMIT.
  return code === '40001' || code === '40P01' || !!code?.startsWith('23')
}

export async function withTransaction<T>(
  fn: (tx: Tx, signal: AbortSignal) => Promise<T>,
  { deadlineMs = 15_000, isolationLevel }: { deadlineMs?: number; isolationLevel?: Isolation } = {},
): Promise<T> {
  if (!Number.isFinite(deadlineMs) || deadlineMs <= 0) throw new RangeError('deadlineMs must be positive')
  const controller = new AbortController()
  const deadlineAt = Date.now() + deadlineMs          // includes time waiting for a pool client
  let phase: 'acquiring' | 'running' | 'commit-possible' = 'acquiring'
  let original: unknown                                  // the error fn threw, before any rollback failure
  let hasOriginal = false
  let failed = false
  let client: PoolClient | undefined
  let acquisition: Promise<PoolClient> | undefined
  let timer: ReturnType<typeof setTimeout> | undefined

  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort()
      reject(phase === 'commit-possible'
        ? new TransactionOutcomeUnknownError('deadline near COMMIT; reconcile before retry')
        : new TransactionDeadlineError(`exceeded ${deadlineMs}ms`))
    }, deadlineMs)
  })

  try {
    acquisition = getPool().connect()
    client = await Promise.race([acquisition, timeout])
    if (Date.now() >= deadlineAt) throw new TransactionDeadlineError('pool acquisition exhausted deadline')
    phase = 'running'
    // drizzle(client) uses this checked-out client for BEGIN/COMMIT and nested SAVEPOINTs.
    const work = drizzle(client, { schema }).transaction(async (tx) => {
      try {
        await tx.execute(sql`select set_config('statement_timeout', ${String(Math.min(deadlineMs, ROLE_STATEMENT_TIMEOUT_MS))}, true)`)
        if (SERVER_VERSION_NUM >= 170000) { // read once at startup: SHOW server_version_num
          await tx.execute(sql`select set_config('transaction_timeout', ${String(deadlineMs)}, true)`)
        }
        const result = await fn(tx, controller.signal)
        if (Date.now() >= deadlineAt) throw new TransactionDeadlineError(`exceeded ${deadlineMs}ms`) // roll back, don't commit late
        // Drizzle sends COMMIT after this callback returns. Treat this boundary
        // conservatively: a timeout here may be a false unknown, never a false rollback.
        phase = 'commit-possible'
        return result
      } catch (err) {
        original = err
        hasOriginal = true
        throw err
      }
    }, isolationLevel ? { isolationLevel } : undefined)

    return await Promise.race([work, timeout])
  } catch (err) {
    failed = true
    if (phase === 'commit-possible' && !(err instanceof TransactionOutcomeUnknownError)
        && !isConfirmedServerAbort(err)) {
      // A local query_timeout, wrapped socket error, or failed ROLLBACK after
      // COMMIT cannot establish whether the server committed the write.
      throw new TransactionOutcomeUnknownError('COMMIT result unconfirmed', { cause: err })
    }
    if (hasOriginal && err !== original && err instanceof TransactionDeadlineError) {
      // fn already failed; the timer won while ROLLBACK was still pending.
      // Destroy the client, but do not mislabel the timer error as a rollback failure.
      throw original
    }
    if (hasOriginal && err !== original) {
      // drizzle threw the ROLLBACK failure; surface the real error and keep the rollback failure as evidence.
      // ORM errors usually already carry the driver error in `cause`, so never overwrite it.
      if (original instanceof Error) {
        try {
          Object.assign(original, { rollbackError: err })
          if (original.cause === undefined) original.cause = err
        } catch { /* A frozen error cannot carry metadata; never mask the original. */ }
      }
      throw original
    }
    throw err
  } finally {
    clearTimeout(timer)
    if (client) client.release(failed ? true : undefined)
    else if (acquisition) {
      // pool.connect() cannot be aborted. If the deadline won, destroy the
      // client when the pending checkout eventually resolves; never leak it.
      void acquisition.then((lateClient) => lateClient.release(true), () => {})
    }
  }
}
```

What the helper guarantees, and what it doesn't:

- **One checked-out client, destroyed on any failure.** `release(err)` destroys the connection, so a client that hit the deadline, failed to roll back, or is still running a statement is never handed to the next request. Destroying on every failed transaction costs one reconnect; reusing a suspect client costs a wrong answer or a hang. (ORM transaction helpers that check out their own pool client typically call plain `release()` even after a failure.)
- **The original error is what callers see.** ORMs commonly throw the *rollback* failure ("Failed query: rollback") when the connection died, which hides the cause. The helper rethrows the original error unchanged. If the original is a mutable `Error` and Drizzle reports a rollback failure before the deadline, that failure is attached as `rollbackError`, and as `cause` when that slot is free. If the deadline wins while rollback is pending, the client is destroyed and the still-pending rollback cannot be reported synchronously.
- **A deadline is not always a confirmed rollback.** Before the callback permits COMMIT, `TransactionDeadlineError` prevents it and destroys the client; the server may need time to notice the disconnect and abort. Tests must confirm the mutation is absent before calling this a rollback. Once the callback permits COMMIT, this helper conservatively reports an unknown outcome on a timeout or non-authoritative error, including the small gap before Drizzle actually sends COMMIT. That can be a false unknown, but cannot falsely authorize a retry of a committed write. A server-reported `40001`, `40P01`, or deferred constraint rejection at COMMIT establishes an abort. Drizzle wraps driver errors in `cause`, so the classifier follows the cause chain. Reconcile unknown outcomes by idempotency key before any retry.
- **`Promise.race` doesn't stop JavaScript.** After the deadline, `fn` keeps running until its next await fails on the destroyed client. Pass the `AbortSignal` into anything long-running inside `fn` (and check it before side effects), so work stops cooperatively.
- **Whole-operation deadline, including pool wait, on every version.** `statement_timeout` bounds one statement; a transaction of many short statements can run far longer. The wall-clock race bounds client waiting and prevents a late COMMIT on every Postgres version. An acquisition that completes after timeout is released and destroyed. On PG ≥ 17, `transaction_timeout` also makes the server end the transaction. Destroying the client stops the *client* waiting; the server stops its work only when a server-side timeout fires or it notices the disconnect, which is why the role timeouts above must exist too.
- **Savepoints come from nesting.** Inside `fn`, `tx.transaction(async (sp) => …)` issues `SAVEPOINT` / `RELEASE` / `ROLLBACK TO` on the same client. Don't build nested transactions any other way.
- **Irreversible external side effects never happen inside a transaction.** Deleting stored objects, sending mail or charging a card inside a transaction that later rolls back (deadline, connection loss, constraint failure) leaves the database describing a world that no longer exists: rows pointing at deleted files, a "pending" order that was charged. Model them as durable, retryable phases: commit an intent row, do the external work outside any transaction (idempotently), then commit completion. A reconciler retries unfinished intents.
- **No network I/O inside the transaction.** HTTP, LLM, storage and email calls happen before or after, never while holding the client. A transaction that waits 20 s on an API holds a pool slot and row locks for 20 s.
- **Tenant/RLS context** uses `set_config('app.tenant_id', $1, true)` inside the transaction. It is transaction-scoped and parameterisable, unlike `SET LOCAL`.
- **`Promise.all` on the pool is fine**: each query checks out its own client, bounded by `max`. **Inside a transaction, await sequentially.** A transaction is one client, so concurrent queries on it gain nothing. node-postgres 8 still queues them but warns that concurrent `client.query()` is deprecated and removed in pg 9.

---

## Session state, advisory locks, LISTEN

| Need | Where it runs |
| --- | --- |
| Tenant/RLS context, per-transaction settings | `set_config(…, true)` / `SET LOCAL` inside the helper, on the runtime pool |
| Mutual exclusion in request/worker code | `pg_advisory_xact_lock(key)` inside a transaction (released at commit), or a claim row with a unique constraint |
| Session advisory locks (`pg_advisory_lock`), `LISTEN`, cursors, temp tables | **Only** in a singleton process (one worker/operator instance): a dedicated `max: 1`, `idleTimeoutMillis: 0` pool on the **direct/session** URL, in one named module |

- Never take session locks in horizontally scaled request runtimes. Each instance would hold a session-mode client, which exhausts the (usually much smaller) session-mode client limit.
- A dropped session silently releases its lock while the protected work carries on. The session-lock helper must listen for the client's `error`/`end` and abort the protected operation (e.g. through an `AbortSignal`).
- Budget the session-lock clients separately from the transaction-mode pool.
- The lock's scope must enclose the whole protected operation, including cleanup. A helper that acquires and releases around a `claim()` call, while the expensive work runs afterwards, protects nothing. Keep durable lease/epoch fencing in the data as well: the lock prevents concurrent runs, and the fence rejects a stale holder's writes.

---

## Connection leak detection

A leak is a connection acquired and never released: an exception path that skips `release()`, a script that never calls `end()`, or a transaction left open.

**Symptoms:**
- Acquisition timeouts (`timeout exceeded when trying to connect`), `too many connections`, pooler "max clients reached" errors (e.g. EMAXCONN)
- `pg_stat_activity` showing many `idle in transaction` rows with your `application_name`
- The pool at `max` with little actual DB load

**Levers (node-postgres):**

```ts
// expose on /metrics and in readiness output
const stats = { total: pool.totalCount, idle: pool.idleCount, waiting: pool.waitingCount }
```

- `idle_in_transaction_session_timeout` on the role kills sessions that opened a transaction and wandered off.
- Instrument the real driver path once per client (including checked-out transaction clients) to log slow queries (≥ 500 ms) and classified errors. Wrapping only `pool.query` misses Drizzle's transaction statements, which call `client.query` directly. Log the pool config once at startup (never credentials).
- A persistent `waitingCount > 0` means the pool is too small *or* something holds clients too long. Check for network I/O inside transactions before raising `max`.

---

## Health, errors, and retries

- Keep liveness free of DB calls. Readiness uses `SELECT 1` on the **shared** pool (`getPool()`), within a 2–5 s client-side budget; creating a separate client would hide pool exhaustion. Protect the detailed readiness response with a monitor secret. Probe routing and auth placement are in `craft-infra` → `runtime-health.md`.
- Log queries taking at least 500 ms as `db.slow_query`, classified failures as `db.query_error`, and the pool's `max`, `application_name`, and host once as `db.pool_configured`. Never log credentials. Expose `totalCount`, `idleCount`, and `waitingCount` on worker metrics and readiness output.
- Use one error classifier for SQLSTATE and connection failures: `serialization | deadlock | unique | timeout | connection | other`. Retry `40001` (serialization) and `40P01` (deadlock) at most three times with jittered backoff. Retry a connection error only when the call is explicitly marked idempotent; never auto-retry `57014` (query canceled). For an unknown COMMIT outcome, reconcile by idempotency key before any retry. Temporal activities rely on their activity retry policy; inside an activity, add only the bounded transaction retry, not another general retry layer.

---

## Transaction-mode pooler gotchas

Behaviour differs by pooler: *leak* (the state follows the backend to the next client), *pin* (the client is stuck to one backend, so no multiplexing), *reject* (an error), or *drop* (silently ignored). Check your pooler's docs; the right-hand column is safe everywhere.

| Feature | Works in transaction mode? | Workaround |
| --- | --- | --- |
| `LISTEN` / `NOTIFY` | No — `LISTEN` needs a persistent session | A singleton listener on the direct/session URL |
| Named prepared statements | Historically no. PgBouncer ≥ 1.21 can support them via `max_prepared_statements`; most managed poolers don't expose that | Unnamed statements only (drizzle default; `prepare: false` in postgres.js) |
| `SET` session variables (`search_path`, `statement_timeout`) | No — leaks (PgBouncer, Supavisor) or pins (RDS Proxy) | `SET LOCAL` / `set_config(…, true)` in a transaction, or role-level defaults |
| Startup parameters (`options=-c …`, driver `connection` options) | Dropped (Supavisor), rejected unless allow-listed (PgBouncer), or pinning (RDS Proxy) | Role defaults (`ALTER ROLE … IN DATABASE … SET`) |
| Session advisory locks (`pg_advisory_lock`) | No | `pg_advisory_xact_lock`, or a singleton session-lock pool on the direct URL |
| `TEMP TABLE` | No | Real tables with cleanup, or session mode for that process |
| Pipelined queries on one socket | Observed to hang behind Supavisor; unverified elsewhere, so test it | A driver configuration that never pipelines (node-postgres default) |

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| postgres.js (`postgres` package / `drizzle-orm/postgres-js`) in a project adopting the Node profile | Move runtime, workers, scripts, and migrations to node-postgres (`driver-migration.md`); don't "fix" with `max_pipeline: 0` alone |
| `max_pipeline: 0` without a driver fix for transactions | Every `sql.begin`/`db.transaction` fails; migrate the driver |
| node-postgres `pipeline: true` | Remove; one query in flight per socket |
| Only `pool.on('error')`, no per-client `error` listener | Add `pool.on('connect', c => c.on('error', …))` |
| Pool created per request / per call | One pool per process, cached on `globalThis` |
| Serverless `max` > 1 without recorded evidence; no fleet budget | Start at 1; write the budget against an enforced instance ceiling |
| No serverless suspension helper where the platform provides one | e.g. `attachDatabasePool(pool)` on Vercel |
| Runtime URL outside the project's approved mode, or migrations on the transaction pooler | Guard `DATABASE_URL` / `DATABASE_URL_DIRECT` separately; a recorded persistent runtime may use direct/session mode |
| Code silently rewriting the pooler port | Replace with a fail-closed guard |
| `sslmode=` in the URL plus an `ssl` object, or `rejectUnauthorized: false` | Strip URL SSL params; explicit verified `ssl` object |
| `statement_timeout` only as a startup parameter / URL option | Role default via `ALTER ROLE … IN DATABASE`; verify with `SHOW` through the pooler |
| Plain `SET …` or `set_config(…, false)` on a pooled runtime connection | `SET LOCAL` / `set_config(…, true)` inside the transaction helper |
| Runtime and migrations share one role with a short role timeout, and the runner doesn't set its own timeout | Separate roles; the runner sets session timeouts before `BEGIN` |
| Raw `db.transaction(...)` outside the helper; rollback failure rethrown instead of the original error | Route through the helper; rethrow the original error |
| HTTP/LLM/storage calls inside a transaction | Move them before or after the transaction (outbox for side effects) |
| `pg_advisory_lock` / `LISTEN` in request handlers or on the runtime pool | `pg_advisory_xact_lock`, or a singleton session-lock module on the direct URL |
| Named `.prepare('…')` behind a transaction pooler | Use unnamed statements |
| Worker pool never closed; script `end()` not in `finally` | `pool.end()` after drain; `finally { await client.end() }` |
| No slow-query log or pool stats | Instrument queries on each pool client, including checked-out transactions; expose total/idle/waiting counts |
| Readiness opens a separate connection or has no short budget | `SELECT 1` on the shared pool with a 2–5 s client-side budget; protect detailed output |
| Blind retry of a connection failure, `57014`, or an unknown COMMIT outcome | Classify the error; retry only permitted idempotent work, and reconcile unknown commits |
| Neon HTTP/WebSocket driver in a project adopting this Node Postgres profile | Route DB work through a Node runtime with node-postgres, or record a reviewed exception with equivalent tests |
