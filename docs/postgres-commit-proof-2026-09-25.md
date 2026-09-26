# Postgres COMMIT outcome proof — 2026-09-25

This is dated evidence for Craftsman [Postgres standard](../plugins/craftsman/skills/craft-db/references/postgres-standard.md)
§5. It is not a second policy source. The permanent harness is
[`scripts/repro-pg-commit-outcome.cjs`](../scripts/repro-pg-commit-outcome.cjs).

## Question and environment

Can a client-side timeout during COMMIT produce an error even though the write
persisted? Does a transaction deadline include waiting for `pool.connect()`?

Tested locally on a throwaway PostgreSQL **17** cluster listening only on
`127.0.0.1:55487`. The harness printed Node, `pg`, Drizzle, and server
versions at run time. This run used `pg 8.23.0` and Drizzle `0.45.2`.
The cluster used trust auth and contained no application data. No shared or
production database was contacted.

## Reproduce

Use a throwaway loopback cluster with a role permitted to create a schema.
Install `pg` and `drizzle-orm` in a Node package, then set
`CRAFT_DB_MODULE_ROOT` to that package's absolute directory:

```sh
CRAFT_DB_PROOF=1 \
CRAFT_DB_MODULE_ROOT=/absolute/path/to/package \
DATABASE_URL=postgres://local-user@127.0.0.1:55487/postgres \
node scripts/repro-pg-commit-outcome.cjs
```

The harness refuses a non-loopback URL, URL query parameters (including a
`?host=` override), and a driver-resolved non-loopback target. It creates a
uniquely named proof schema and drops it after the run. `CRAFT_DB_PROOF=1` is an explicit guard because it
creates and removes database objects. Run only against a disposable cluster.

It checks two cases:

1. Hold the sole pool client; a second transaction with an 80 ms deadline must
   reject while waiting to acquire a client. The late acquisition is destroyed.
2. Create a deferred trigger that sleeps 300 ms at COMMIT. With `pg`
   `query_timeout: 100`, the Drizzle transaction rejects on the local timeout
   or subsequent rollback error. A separate admin connection then confirms
   that the inserted row **persisted**. The correct client result is
   `UnknownCommit`, pending reconciliation by idempotency key.

Observed on 2026-09-25 from the checked-in harness:

```text
{"versions":{"node":"v24.16.0","pg":"8.23.0","drizzle":"0.45.2"},"postgres":"17.9 (Homebrew)"}
acquisition deadline: 81ms; late client destroyed
local COMMIT timeout: Failed query: rollback
params: ; persisted=1; outcome classified unknown
```

The checked-in harness printed those lines and passed its assertions. The
local run used the installed dependencies in onecast's `packages/data`
package. Future runs may use any package with the stated dependencies.
After a reviewer found that `pg` can treat `?host=` as an override, the guard
was tightened to reject URL query parameters and verify the driver's effective
host. A negative run with
`postgres://atifgul@127.0.0.1:55487/postgres?host=example.com` failed at
the guard before connecting; the positive loopback run above passed again.
`scripts/test-repro-pg-guard.cjs` keeps the host-override and non-loopback
rejections in CI without requiring a database.

## What this proves and does not prove

The local timeout is **not** a server-side rollback guarantee. In this case
Drizzle surfaced a rollback failure while the COMMIT had succeeded. The proof
supports conservative classification of a lost or timed-out COMMIT response and
a deadline that starts before pool checkout. It does not validate every path of
the illustrative transaction helper, a Supavisor connection, or a production
deployment. T5/T7 in each adopting project must cover its own driver version,
pooler, and failure paths.

## Current primary documentation

- [Supabase connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres):
  transaction mode for transient/serverless clients, direct or session mode for
  persistent services; transaction mode does not support prepared statements or
  query pipelining.
- [Drizzle PostgreSQL drivers](https://orm.drizzle.team/docs/get-started-postgresql):
  both node-postgres and postgres.js are supported, so the chosen driver is
  Craftsman policy rather than a Drizzle requirement.
- [node-postgres Client API](https://node-postgres.com/apis/client):
  `query_timeout` is a client-side query-call timeout; `pipeline` is opt-in.
- [node-postgres Pool API](https://node-postgres.com/apis/pool):
  `pool.connect()` waits for a free client and `release(true)` destroys it.
- [PostgreSQL transaction timeout settings](https://www.postgresql.org/docs/17/runtime-config-client.html):
  server-side `statement_timeout` and `transaction_timeout` are distinct
  from a client's local timer.
