# Driver Migration: postgres.js → node-postgres

When a repo adopts the Craftsman Postgres profile and still runs postgres.js (`postgres` package, `drizzle-orm/postgres-js`), migrate its driver rather than applying a config-only change. The reproduced 3.4.x transaction defect under `max_pipeline: 0` and connection-loss wedge can occur behind any pooler or none; pipelining also risks hangs behind Supavisor transaction mode (why: `connection-pooling.md` → "Choosing the Node driver behind a transaction-mode pooler"). Verify a different installed version and pooler before attributing those failures to it. This file is the playbook for moving without silently changing what the app reads back. The discipline: **inventory every raw result, pin its shape with a test, then swap, then prove the resilience properties on a real Postgres.**

> **Scope split.** This file owns the mechanics of moving an existing codebase from postgres.js to node-postgres under Drizzle: result shapes, type parsing, option mapping, raw-API rewrites and the verification gate. Why the move is needed, the target pool config, the transaction helper and timeouts are in `connection-pooling.md`. The test suites that gate the move are in `seeding-and-testing.md`.

---

## Contents

- [When to do it and when to stop](#when-to-do-it-and-when-to-stop)
- [Step 1 — Inventory](#step-1--inventory)
- [Step 2 — Pin result shapes and types with tests](#step-2--pin-result-shapes-and-types-with-tests)
- [Step 3 — Swap the adapter](#step-3--swap-the-adapter)
- [Step 4 — Rewrite raw driver calls](#step-4--rewrite-raw-driver-calls)
- [Step 5 — Verify on real Postgres](#step-5--verify-on-real-postgres)
- [Interim mitigations while the move is scheduled](#interim-mitigations-while-the-move-is-scheduled)
- [Quick-reject checklist](#quick-reject-checklist)

---

## When to do it and when to stop

For a project adopting `postgres-standard.md`, do it whenever postgres.js is used in runtime,
workers, operator scripts, or migrations; prioritize production traffic behind a transaction-mode
pooler. Elsewhere, first establish the installed version, pooler mode, and a concrete defect or
architecture decision. Inventory every path before changing the adapter. You can implement runtime
paths first, but the adopted driver move is incomplete until scripts and migrations use node-postgres
too. Keep any unfinished path as an open finding; do not declare the migration done or remove the
old driver while it is still needed.

Stop and report instead of guessing when:
- the app depends on postgres.js-only features with no drop-in equivalent: `sql.listen` streams, `sql.subscribe` (logical replication), `cursor()` iteration, `COPY` streams, or custom `types`/`transform` options (e.g. camelCase column transforms);
- raw results are consumed in more places than you can pin with tests in this change. Split by module instead.

---

## Step 1 — Inventory

Record counts with `file:line` examples. They go in the finding and the PR description.

| Search | What it tells you |
| --- | --- |
| Imports of `postgres` / `drizzle-orm/postgres-js` | every client construction site (runtime, scripts, tests) |
| `db.execute(` / `tx.execute(` whose result is **read** | raw results whose envelope *and* value types change (below) |
| postgres.js tagged templates on the raw client (`` sql`…` ``, where `sql` is the postgres.js client, not drizzle's `sql` helper) | raw queries to rewrite |
| `.begin(`, `.unsafe(`, `.reserve(`, `.listen(`, `.subscribe(`, `.cursor(`, `sql.array(`, `sql.json(`, `sql(obj)` / `sql(obj, 'col')` helpers | postgres.js APIs with no 1:1 equivalent |
| `.count` on raw results, `result[0]`, `as T[]` casts on `db.execute` | code relying on postgres.js's array-shaped result |
| Options: `max_pipeline`, `prepare`, `connection: {…}`, `types`, `transform`, `onnotice`, `fetch_types`, `max_lifetime` | options to map or drop |
| `patches/postgres@*.patch`, `patchedDependencies` | local driver patches to delete after the move |

---

## Step 2 — Pin result shapes and types with tests

**Schema-typed queries** (`db.select().from(table)`, relational `db.query.*`, `insert().returning()`) are mapped by Drizzle's column types on both drivers. Their values stay the same shape.

**Raw results change, and how much depends on whether the postgres.js client was handed to Drizzle.** `drizzle(postgresClient)` mutates that client's parsers so temporal types come back as strings, and that applies to *every* query on the client, including raw tagged templates. A postgres.js client never passed to Drizzle (typical in scripts) keeps postgres.js's own parsing.

| Aspect | postgres.js client passed to Drizzle | standalone postgres.js client | node-postgres under Drizzle |
| --- | --- | --- | --- |
| Envelope of a raw query | an array of rows (`.count`, `.columns`) | array of rows | `QueryResult`: rows in `.rows`, count in `.rowCount` |
| `timestamptz`, `timestamp`, `date`, `time` | string | **`Date`** (`time`: string) | string |
| `interval` | string | string | string |
| `date[]`, `timestamp[]`, `timestamptz[]`, `numeric[]` | raw array literal string (`'{…}'`) | **parsed JS array** | raw array literal string |
| `interval[]` | parsed array of strings | parsed array of strings | **raw array literal string** |
| other arrays (`int4[]`, `text[]`, `uuid[]`, `jsonb[]` …) | parsed JS array | parsed JS array | parsed JS array |
| `numeric`, `bigint` (int8) | string | string | string |
| `json` / `jsonb` | parsed | parsed | parsed |
| `int4`, `float8`, `bool`, `text`, `uuid`, `bytea` | native (`bytea` → `Buffer`) | native | native |

Verify these against the installed versions before relying on them: the driver's type parsers and Drizzle's pass-through list (`drizzle-orm/postgres-js/driver.js`, `drizzle-orm/node-postgres/session.js`) are the source of truth. Schema-typed selects are unaffected; Drizzle maps them by column type on both drivers.

Before swapping, for **every** raw read found in step 1:

1. Route it through a driver-agnostic helper, so the envelope difference is handled in one place:
   ```ts
   export function rowsOf<T>(result: unknown): T[] {
     if (Array.isArray(result)) return result as T[]                  // postgres.js
     const rows = (result as { rows?: unknown }).rows
     if (Array.isArray(rows)) return rows as T[]                      // node-postgres
     throw new TypeError('unexpected db.execute result shape')
   }
   ```
2. Make the value types explicit rather than driver-dependent. Either cast in SQL (`created_at::text`, `extract(epoch from created_at)::float8`, `to_jsonb(...)`), or map in code (`new Date(row.created_at)`).
3. Add a compatibility test per distinct shape. Cover `timestamptz`, `timestamp`, `date`, `interval`, `numeric`, `bigint`, `json`/`jsonb`, and arrays of each type you read. Assert the exact JS types the caller relies on. Run these tests on the **old** driver first. They must pass before and after the swap. The highest-risk sites are standalone postgres.js clients (scripts, one-off tools) whose callers expect `Date`s or parsed arrays.

---

## Step 3 — Swap the adapter

```ts
// before
import postgres from 'postgres'
import { drizzle } from 'drizzle-orm/postgres-js'
export const db = drizzle(postgres(url, { max, prepare: false }), { schema })

// after — use the lazy singleton with full config and error handlers in connection-pooling.md
import { getDb } from './db/client'
// Call getDb() when runtime code actually needs database access.
```

**Option mapping:**

| postgres.js | node-postgres | Note |
| --- | --- | --- |
| `max` | `max` | re-derive with the serverless/worker sizing rules |
| `idle_timeout` (s) | `idleTimeoutMillis` (ms) | |
| `max_lifetime` (s) | `maxLifetimeSeconds` (s) | |
| `connect_timeout` (s) | `connectionTimeoutMillis` (ms) | this is *pool acquisition* wait in pg-pool; longer for workers |
| `prepare: false` | *(drop)* | Drizzle node-postgres statements are unnamed unless you call `.prepare('name')` |
| `max_pipeline` | *(drop)* | keep pg's `pipeline` unset |
| `connection: { statement_timeout, application_name }` | `application_name` option; timeouts via role defaults | startup-parameter timeouts are often dropped by poolers (`connection-pooling.md` → timeouts) |
| `ssl: 'require'` | explicit verified `ssl` object (`rejectUnauthorized: true`, provider CA when required), URL `ssl*` params stripped | Verify certificate trust; do not silently disable it |
| `onnotice` | `client.on('notice', …)` via `pool.on('connect')` | |
| `types` / `transform` | custom `types.getTypeParser` or code mappers | treat as a stop-and-report item unless trivial |
| `sql.end({ timeout })` | `pool.end()` | workers: after drain; scripts: in `finally` |

After runtime, worker, script, and migration paths have moved, delete the local driver patch and its `patchedDependencies` entry, and remove `postgres` from `package.json`, so it can't creep back.

---

## Step 4 — Rewrite raw driver calls

| postgres.js | node-postgres / Drizzle |
| --- | --- |
| `` await sql`select … where id = ${id}` `` | `rowsOf(await db.execute(sql\`select … where id = ${id}\`))` using drizzle's `sql`; or `(await pool.query('select … where id = $1', [id])).rows` |
| `sql.begin(async (tx) => …)` | the repo's `withTransaction` helper (`connection-pooling.md`) |
| `tx.savepoint(async (sp) => …)` | a nested `tx.transaction(async (sp) => …)` called on the `tx` the helper passes into your callback. That `tx` is a Drizzle transaction, so nesting issues `SAVEPOINT`. Calling `.transaction()` on a plain `drizzle(client)` database instead sends a second `BEGIN` that Postgres ignores, and its `COMMIT` commits the whole outer transaction |
| `sql.unsafe(text, params)` | `pool.query(text, params)` (scripts), or `db.execute(sql.raw(text))` for trusted DDL only |
| `sql.reserve()` | the session-lock helper (singleton processes only), or `pool.connect()` inside the transaction helper |
| `sql.array(values)` | pass a JS array as a parameter; cast in SQL (`$1::int[]`) |
| `sql.json(value)` | pass the object as a parameter; cast (`$1::jsonb`) |
| `sql(obj)` / `sql(obj, 'a', 'b')` insert helpers | Drizzle `insert(table).values(obj)` |
| `result.count` | `result.rowCount` |

---

## Step 5 — Verify on real Postgres

The move is done only when runtime, workers, scripts, and migrations all use the new driver and the suites in `seeding-and-testing.md` pass on a loopback Postgres at the production major version:
- the step 2 compatibility tests;
- the transaction-helper suite (T5);
- the resilience suite (T7):
  - a connection killed mid-transaction rejects the transaction without an uncaught exception, and the pool serves the next query;
  - a deadline-expired client is never reused;
  - a concurrent burst completes with at most one query in flight per socket.

Also replace `Promise.all` *inside* transactions with sequential awaits while you're in there. node-postgres 8 queues concurrent queries on one client but deprecates it, and pg 9 removes it.

Run T7 on the old driver too, if you can. Watching it fail there is the evidence for the finding.

---

## Interim mitigations while the move is scheduled

None of these fix the underlying bugs. They reduce exposure until the move lands.

- Keep `prepare: false` behind a transaction-mode pooler.
- Don't set `max_pipeline: 0` unless the transaction path is also fixed (every `begin` breaks otherwise). If a repo already has it with a local driver patch, keep the patch pinned to the exact driver version with a test proving it applied, until the move.
- Reduce concurrent queries on one shared client in hot paths. Fewer overlapping queries means fewer pipelined writes.
- As a last-resort guard against a slot wedged by connection loss, recreate the client after N consecutive client-side timeouts.
- Put role-level timeouts in place now; they carry over unchanged.

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| Adapter swapped without inventorying raw `db.execute` reads | Inventory, route through `rowsOf`, pin types with tests, then swap |
| Raw results from a standalone postgres.js client (`Date`s, parsed temporal arrays) moved to node-postgres/Drizzle without mapping | Cast in SQL or map in code; compatibility test per shape |
| Two drivers left in the runtime path | One driver; remove `postgres` from `package.json` |
| Local postgres.js patch left behind after the move | Delete the patch and its `patchedDependencies` entry |
| `sql.listen` / `subscribe` / `cursor` / custom `transform` silently dropped | Stop and report; each needs an explicit replacement plan |
| Move declared done without the resilience suite on real Postgres | Run T5 and T7 on loopback Postgres at the production major version |
