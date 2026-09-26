# Seeding and Testing

Seed scripts and test database patterns follow distinct but related disciplines. Seeds must be idempotent, FK-aware, and free of production-like sensitive data. Test database patterns must be fast, isolated, and deterministic. Both share the principle: **no test or seed should leave the database in a state that affects other tests or seed runs.**

> **Scope split.** This file owns seed script patterns (idempotency, insertion ordering), per-test database isolation patterns (transaction rollback with Drizzle + vitest), test-database safety (what a test may connect to), and the standard database test suites T1–T8 that gate pool, driver, transaction and migration behaviour. The actual schema design (column types, constraints) lives in `schema.md`; migration workflow lives in `migrations.md`; query helpers for testing live in `access-patterns.md`. The application-side test infrastructure (test server setup, auth mocking) is `craft-testing` → `backend-data-testing.md`.

> **Dialect note:** These docs assume PostgreSQL with the Drizzle ORM and vitest. Adjust driver-specific calls for MySQL or SQLite.

---

## Contents

- [Idempotent seed scripts](#idempotent-seed-scripts)
- [FK-aware insertion ordering](#fk-aware-insertion-ordering)
- [What NOT to put in seeds](#what-not-to-put-in-seeds)
- [Per-test transaction rollback with Drizzle + vitest](#per-test-transaction-rollback-with-drizzle--vitest)
- [Test database safety](#test-database-safety)
- [Database test suites T1–T8](#database-test-suites-t1t8)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Idempotent seed scripts

A seed script must be safe to run multiple times. Running it twice should produce the same final state — not duplicate rows, not errors, not a half-seeded database.

**Pattern: `INSERT ... ON CONFLICT DO NOTHING`**

```ts
// db/seeds/workspaces.ts
import { getDb } from '../client'
import { workspaces } from '../schema'

export async function seedWorkspaces() {
  await getDb()
    .insert(workspaces)
    .values([
      {
        id: 'ws_seed_acme',
        name: 'Acme Corp',
        slug: 'acme',
        createdAt: new Date('2024-01-01T00:00:00Z'),
      },
      {
        id: 'ws_seed_globex',
        name: 'Globex',
        slug: 'globex',
        createdAt: new Date('2024-01-01T00:00:00Z'),
      },
    ])
    .onConflictDoNothing()
    // OR, to update specific fields on re-seed while preserving others:
    // .onConflictDoUpdate({
    //   target: workspaces.id,
    //   set: { name: sql`excluded.name` },
    // })
}
```

Use stable, human-readable seed IDs (e.g. `ws_seed_acme`, not `crypto.randomUUID()`). Random UUIDs change on every seed run, making `ON CONFLICT` useless — you'd insert a new row each time because the ID never matches.

**Seed entry point — run all seeds in FK order:**

```ts
// db/seeds/index.ts
import { seedWorkspaces } from './workspaces'
import { seedUsers } from './users'
import { seedInvoices } from './invoices'

async function seed() {
  console.log('Seeding database...')
  await seedWorkspaces()   // no FKs; runs first
  await seedUsers()        // FK → workspaces
  await seedInvoices()     // FK → workspaces, users
  console.log('Done.')
  process.exit(0)
}

seed().catch((err) => {
  console.error(err)
  process.exit(1)
})
```

---

## FK-aware insertion ordering

Foreign key constraints will reject an insert if the referenced row doesn't exist yet. Always seed parent tables before child tables.

**Dependency order (most to least foundational):**

1. Tables with no FK dependencies (e.g. `workspaces`, `plans`, lookup/reference tables)
2. Tables that FK to #1 (e.g. `users` → `workspaces`)
3. Tables that FK to #2 (e.g. `invoices` → `workspaces` + `users`)
4. Join/pivot tables last (e.g. `workspace_members` → `workspaces` + `users`)

If you have circular FK references (rare, but possible in self-referential tables), disable the FK constraint check for the seed transaction or use `NOT VALID` + deferred validation. This is the exception, not the rule — circular FK references are usually a schema design smell.

```sql
-- Emergency workaround for circular FK during seed only
BEGIN;
SET CONSTRAINTS ALL DEFERRED;
-- ... inserts ...
COMMIT;
```

In Drizzle, you can also use `db.transaction()` with deferred constraints if your FKs are declared `DEFERRABLE INITIALLY DEFERRED`.

---

## What NOT to put in seeds

Seeds are committed to the repository and run in CI. They must never contain:

| Category | Why not | Alternative |
| --- | --- | --- |
| Production-like PII (real emails, names, phone numbers) | Seeds appear in git history and CI logs; GDPR/CCPA exposure | Use obviously fake data: `alice@example.com`, `test-workspace-1` |
| Real UUIDs copied from production | They conflict with production data if a DB is accidentally pointed at prod | Use `ws_seed_*` prefixed string IDs or `00000000-0000-0000-0000-000000000001` format UUIDs |
| `crypto.randomUUID()` or `Math.random()` in IDs | Changes on every run; `ON CONFLICT DO NOTHING` never fires; seeds duplicate | Use hardcoded stable IDs |
| Production API keys or secrets | Seeds are committed | Use placeholder values: `sk_test_seed_placeholder` |
| Passwords in plaintext | Plaintext passwords in git | Use a hardcoded bcrypt hash of a well-known test password (e.g. `password123`) |

**Test password pattern:**

```ts
// Generate once, hardcode the hash — never call bcrypt in the seed loop
// bcrypt.hash('password123', 10) → run once and paste the result
const TEST_PASSWORD_HASH = '$2b$10$K7L1OJ45/4Y2nIvhRVpCe.FSmhDdWoXehVzJptJ/op0/AHqtyLMf2'

await db.insert(users).values({
  id: 'user_seed_alice',
  email: 'alice@example.com',
  passwordHash: TEST_PASSWORD_HASH,
  workspaceId: 'ws_seed_acme',
}).onConflictDoNothing()
```

---

## Per-test transaction rollback with Drizzle + vitest

The most reliable way to isolate DB state between tests is to wrap each test in a transaction and roll it back after the test completes. This avoids the need for `DELETE FROM` cleanup, works against a real (not mocked) database, and is fast because no data is actually committed to disk.

**Why use a real DB instead of mocks?** Mocking the DB layer means your tests don't catch constraint violations, query planner issues, or ORM-generated SQL bugs. A transaction-per-test pattern against a real test DB gives you correctness with isolation.

**Pattern: Drizzle + vitest transaction rollback**

```ts
// tests/helpers/db.ts
import pg from 'pg'
import { drizzle, type NodePgDatabase } from 'drizzle-orm/node-postgres'
import * as schema from '../../db/schema'
import { assertLoopbackTestUrl } from './assert-loopback'

// Loopback only (testcontainers / docker compose) — see "Test database safety"
const url = assertLoopbackTestUrl(process.env.TEST_DATABASE_URL)
export const testPool = new pg.Pool({ connectionString: url, max: 1 })
export const testDb: NodePgDatabase<typeof schema> = drizzle(testPool, { schema })
```

```ts
// tests/helpers/withTestTransaction.ts
import { testDb } from './db'
type TestTx = Parameters<Parameters<typeof testDb.transaction>[0]>[0]
type TestFn = (tx: TestTx) => Promise<void>
const expectedRollback = Symbol('test transaction rollback')

/**
 * Wraps a test body in a transaction that is always rolled back.
 * The test receives the transaction client — all DB calls inside
 * the test must use `tx`, not the module-level `db` instance.
 */
export async function withTestTransaction(fn: TestFn): Promise<void> {
  try {
    await testDb.transaction(async (tx) => {
      await fn(tx)
      // Only this private sentinel is expected; callback and rollback errors must fail the test.
      throw expectedRollback
    })
  } catch (err) {
    if (err !== expectedRollback) throw err
  }
}
```

```ts
// tests/invoices.test.ts
import { describe, it, expect } from 'vitest'
import { withTestTransaction } from './helpers/withTestTransaction'
import { createInvoice } from '../src/services/invoices'
import { invoices } from '../db/schema'
import { eq } from 'drizzle-orm'

describe('createInvoice', () => {
  it('inserts an invoice with the correct tenant', async () => {
    await withTestTransaction(async (tx) => {
      const result = await createInvoice(tx, {
        tenantId: 'ws_seed_acme',
        amount: 10000, // cents
        status: 'pending',
      })

      // Assert within the same transaction — row is visible here but not outside
      const [row] = await tx
        .select({ id: invoices.id, status: invoices.status })
        .from(invoices)
        .where(eq(invoices.id, result.id))

      expect(row.status).toBe('pending')
      // Transaction rolls back here — no cleanup needed
    })
  })

  it('does not see rows from a different test', async () => {
    await withTestTransaction(async (tx) => {
      // This test starts clean — prior test's data was rolled back
      const rows = await tx.select().from(invoices)
      expect(rows.length).toBe(0) // only seed data, if any
    })
  })
})
```

**Key constraints of this pattern:**

- All DB calls inside the test must use `tx` (the transaction client), not the module-level `db`. A query using `db` opens a separate connection outside the transaction and will not be rolled back.
- Your service functions must accept a `db` parameter (dependency injection) rather than importing the module-level client directly. This is also better design — it makes services composable within transactions.
- `TEST_DATABASE_URL` must be **loopback** (an ephemeral container or throwaway local cluster). The rollback pattern prevents permanent writes, but tests pointed at a shared dev or prod database still run migrations, take locks and leak seed data. See "Test database safety".
- Run the repo's real `db:migrate` runner against the loopback test DB before the suite. It must use `DATABASE_URL_DIRECT`, apply registered non-transactional steps, and set session timeouts before `BEGIN`.

**vitest globalSetup for the loopback integration suite (`quality:full` only):**

```ts
// tests/globalSetup.ts
import { execFileSync } from 'node:child_process'
import { assertLoopbackTestUrl } from './helpers/assert-loopback'

export async function setup() {
  const url = assertLoopbackTestUrl(process.env.TEST_DATABASE_URL)
  // The real runner reads DATABASE_URL_DIRECT. Force every DB URL in this process to loopback.
  execFileSync('pnpm', ['db:migrate'], {
    env: { ...process.env, DATABASE_URL: url, DATABASE_URL_DIRECT: url },
    stdio: 'inherit',
  })
}
```

---

## Test database safety

Many small teams run one managed database for dev *and* production, or share
a cluster across environments. A test that can reach it will eventually write
to it: an E2E run, a forgotten `.env`, a "just this once" integration test.

- **Tests never connect to a non-loopback host.** The app's URL resolver
  throws under a test runner (vitest/jest/node:test env markers) unless the
  target is loopback or an in-process database. No env var overrides this: an
  opt-in flag is only as safe as whoever sets it.
- **Unit tests cannot instantiate a real pool.** Keep the singleton lazy and
  pure config separate. T3 uses a TypeScript runtime-import graph to reject
  paths from unit tests to driver-importing modules, except registered lazy
  singletons with a justified allowlist. Every unit-test setup also installs
  a runtime guard that fails if a registered singleton creates a real pool.
  Type-only imports do not count.
- **Pick the engine by what the test proves:**
  - **PGlite** (in-process, single connection) for relational semantics:
    queries, constraints, tenant filters, idempotent seeds.
  - **Loopback Postgres at the production major version** (a Docker container,
    or a throwaway local `initdb`/`pg_ctl` cluster on a free port under a temp
    directory when Docker is unavailable) for anything about connections: pools, driver
    behaviour, timeouts, advisory-lock contention, connection loss, and the
    real migration runner. PGlite cannot show these.
- **E2E suites** get their own ephemeral database too. A "test schema" inside
  the production database is still the production database: one wrong
  `search_path` and the run writes to live tables.

## Database test suites T1–T8

Use the same suite IDs in every project adopting `postgres-standard.md`, so an audit can check for them
by name and a reviewer knows what "T5 passed" means. T1–T8 are required;
even a project with no application transactions yet tests the transaction
helper. Only a genuinely inapplicable subcase (for example, T7(d) when there
is no session-lock module) may be marked *n/a* with a one-line reason.

| ID | Suite | What it asserts | Runs on | Gate |
| --- | --- | --- | --- | --- |
| T1 | `db-pool-config` | `buildPoolConfig(env)` equals the standard: `max`, timeouts, `application_name`, the SSL object, and pipelining off. With `pg` mocked, the factory attaches both error handlers and calls the platform suspension helper when on serverless | unit | `quality:ci` |
| T2 | `db-url-guards` | The runtime factory refuses any remote host/mode outside the project's approved target (which may be direct/session for a recorded persistent runtime); the direct factory refuses the transaction pooler (including Supabase `:6543` supplied by `PGPORT`); the test runner refuses non-loopback after effective driver URL parsing, including a loopback URL with a remote `?host=` override; SSL params are stripped from URLs | unit | `quality:ci` |
| T3 | `no-db-in-unit-tests` | A TypeScript runtime-import graph rejects unit-test paths to modules importing `pg`, `postgres`, `drizzle-orm/node-postgres`, or `drizzle-orm/postgres-js`, except registered lazy singletons on a justified allowlist. A guard in every unit-test setup fails if a registered singleton instantiates a real pool. The singleton creates its pool only on first use | unit | `quality:ci` |
| T4 | `db-forbidden-patterns` | Lint rules (typed where needed). No `postgres`/`drizzle-orm/postgres-js` import; no `pipeline: true`; no `db.transaction`/`pool.connect` outside the helper modules; no named `.prepare(`; no SQL `SET <guc>` other than `SET LOCAL`/`SET CONSTRAINTS`/`SET TRANSACTION`; no `set_config(…, false)`; no `pg_advisory_lock` or `pg_try_advisory_lock` outside the session-lock module. Scope: runtime source; migrations and scripts listed as exclusions | lint | `quality:ci` |
| T5 | `db-transaction-helper` | Pool acquisition is inside the deadline, including a late-checkout cleanup test; per-transaction settings apply; callback throw preserves the original error and the mutation is absent after confirmed cleanup; a failed rollback keeps `rollbackError`; a pre-COMMIT timeout prevents commit and destroys the client on PG ≥ 17 and older versions; a fault in the callback-to-COMMIT gap is conservatively unknown; a sent COMMIT with a lost or locally timed-out reply is unknown even through Drizzle's `cause` chain; server-reported `40001`/`40P01` or deferred constraint rejection is a known abort; nested `tx.transaction()` rolls back to its savepoint without affecting the outer transaction | loopback PG plus fault injection | `quality:full` |
| T6 | `db-migrations` | The exact registered chain applies from zero with the real runner, including non-transactional steps, with no SQL rewritten for the test. The runner sets its session timeouts before `BEGIN` | loopback PG | `quality:full` |
| T7 | `db-resilience` | Run with pool `max: 1`, so "the next query" can only succeed on a replacement client. (a) `pg_terminate_backend` mid-transaction returns `true`; the transaction rejects; its mutation is absent; the old backend PID is gone from `pg_stat_activity`; no uncaught exception after an event-loop turn; the next query succeeds on a new PID. (b) A deadline-expired client is never reused (a new PID, and the old one gone). (c) A 20-query `Promise.all` burst on the pool, concurrent with transactions, completes with ≤ 1 query in flight per socket. (d) If a session-lock module exists, connection loss aborts the protected operation | loopback PG | `quality:full` |
| T8 | `db-budget` | Each runtime's pool `max` × instance ceiling fits the recorded pooler client limit and adopted safety budget (50% initial target, or a measured explicit project decision) | unit | `quality:ci` |

The migration drift check (`drizzle-kit generate` produces no diff) and a
journal test also run on every commit; they need no database.

**T7(a), sketch** (pool created with `max: 1`; `probe` is a separate `pg.Client` for assertions):

```ts
it('connection loss mid-transaction rejects, persists nothing, and the pool recovers', async () => {
  const uncaught: unknown[] = []
  const onUncaught = (e: unknown) => uncaught.push(e)
  process.on('uncaughtException', onUncaught)
  let victimPid: number | undefined
  try {
    await expect(withTransaction(async (tx) => {
      await tx.insert(markers).values({ id: 'terminated-tx' })
      const { rows } = await tx.execute(sql`select pg_backend_pid() as pid`)
      victimPid = Number(rows[0].pid)
      const killed = await probe.query('select pg_terminate_backend($1) as ok', [victimPid])
      expect(killed.rows[0].ok).toBe(true)              // the kill itself must succeed
      await tx.execute(sql`select 1`)                     // this is what must fail
    })).rejects.toThrow()

    await new Promise((r) => setImmediate(r))             // let late socket errors surface
    expect(uncaught).toEqual([])

    const gone = await probe.query('select 1 from pg_stat_activity where pid = $1', [victimPid])
    expect(gone.rowCount).toBe(0)                         // old backend is gone
    const persisted = await probe.query(`select 1 from markers where id = 'terminated-tx'`)
    expect(persisted.rowCount).toBe(0)                    // nothing committed

    const { rows } = await db.execute(sql`select pg_backend_pid() as pid`)
    expect(Number(rows[0].pid)).not.toBe(victimPid)       // max: 1 → proves a replacement client
  } finally {
    process.off('uncaughtException', onUncaught)
  }
})
```

**T7(c), counting queries in flight.** Put a tiny TCP proxy between the pool
and Postgres. It counts frontend `Parse`/`Query` messages against backend
`ReadyForQuery` per socket and records the maximum. Anything above 1 means the
driver pipelined. The same counter, pointed at an in-process fake wire server,
makes a fast unit-level variant that needs no database.

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| Seed uses `crypto.randomUUID()` for IDs | Use stable hardcoded IDs (e.g. `ws_seed_acme`); idempotency requires stable keys |
| Seed inserts without `ON CONFLICT DO NOTHING` | Add `.onConflictDoNothing()` or the SQL equivalent; running twice must be safe |
| Seed inserts child table before parent table | Reorder to respect FK dependency chain; parent first, child after |
| Seed contains real email addresses or names | Replace with `@example.com` addresses and obviously fictional names |
| Test calls module-level `db` instead of the transaction `tx` | Pass `tx` as a parameter; queries on `db` escape the transaction and are not rolled back |
| Tests use `DELETE FROM` for cleanup instead of transaction rollback | Switch to `withTestTransaction`; rollback is faster and more reliable than manual cleanup |
| Test DB URL points at dev or production, or at any non-loopback host | Loopback ephemeral database only; the URL resolver throws under a test runner, with no override flag |
| E2E / integration suite runs against a "test schema" inside a shared or production database | Its own ephemeral database (a container in CI and locally) |
| Pool/driver/timeout/lock behaviour "tested" on PGlite or with mocks only | Run it on loopback Postgres at the production major version (T5–T7) |
| Migration test that rewrites SQL (e.g. strips `CONCURRENTLY`) before applying | Run the exact chain with the real runner (T6) |
| Missing T1–T8 suite, or a whole suite marked n/a | Add the suite; only genuinely inapplicable subcases may be n/a with a reason |
| Service functions import `db` directly (not injectable) | Refactor to accept a `db` parameter; enables transaction rollback in tests and composability in application code |
