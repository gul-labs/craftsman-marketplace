# Backend & Data Testing

Server and data-layer code earns trust only when it's tested against the *real* boundary: a real
Postgres, the real migrations, the real handler driven by a real request. **Mocking the database is
the default that ships green tests and broken prod** — the query was wrong, a constraint fired, the
migration drifted, and the mock knew none of it. The discipline: test the data layer against an
ephemeral real database, drive routes through the actual handler, assert the *persisted* effect, and
mock only what you don't own (third-party HTTP).

> **Scope split.** This file owns *testing server + data-layer code against the real boundary*: the
> testcontainers/ephemeral-DB setup, per-test isolation (transactional rollback vs truncate vs
> per-worker DBs), DB-insertion mechanics for seeds/factories, integration-testing routes and
> handlers (status + body + persisted effect), the regression test that *proves* an authZ/IDOR fix,
> contract testing at service edges, testing observable side-effect behavior with external HTTP
> mocked, and running real migrations in tests. It does **not** own: schema/index/query *design*
> correctness (**`craft-db`**), the API/error-contract *design* (**`craft-backend`**), or the
> security *vulnerability catalog* (**`craft-security`** defines the vuln; this file writes the test
> that proves the fix holds).
>
> **See also:** `flake.md` — a shared mutable DB across tests is the #1 source of order-dependent
> flake. `test-design.md` — factory *philosophy* (own your rows, no shared mutable fixtures); here
> it's the DB-*insertion* mechanics. `strategy.md` — whether a contract test is Tier-2 worth it.
> `craft-backend` → `side-effects.md` — the outbox/idempotency *design* you write a behavior test
> for here.

---

## Contents

- [Don't mock the database](#dont-mock-the-database)
- [Test isolation — the one that matters](#test-isolation--the-one-that-matters)
- [Seeding & deterministic data](#seeding--deterministic-data)
- [Integration-testing routes and handlers](#integration-testing-routes-and-handlers)
- [Proving an authorization fix (IDOR regression)](#proving-an-authorization-fix-idor-regression)
- [Contract testing at service boundaries](#contract-testing-at-service-boundaries)
- [External services & side effects](#external-services--side-effects)
- [Migrations in tests](#migrations-in-tests)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Don't mock the database

A mocked ORM returns whatever you told it to. So a test on `getInvoice()` with a mocked `db` proves
the *mock* returns a row — not that the query compiles, that the `WHERE` matches the schema, that the
`NOT NULL` constraint holds, or that the migration that added the column actually ran. Every real DB
failure mode is exactly the thing the mock erases. This is why "mock the database in unit tests" is
the wrong default: the data layer's whole job is to talk to the database, so mocking it tests
nothing.

Test the data layer against a **real, ephemeral Postgres**. [Testcontainers](https://testcontainers.com)
spins one up in Docker, scoped to the test run, and tears it down after. Starting a container is slow
(seconds), so start as few as possible: Vitest/Jest `globalSetup` runs **once for the whole run** (in
the main process, not per worker), so it gives you **one shared container** for every test file.
Keep this setup in the loopback integration suite (`quality:full`), not unit tests in `quality:ci`.
Isolate parallel workers with a per-worker schema or database *inside* that one container (strategy 3
below) — never a container per worker or per test.

Discover the repo's real migration runner before wiring the setup. For projects adopting the
Craftsman Postgres profile, the same
registered chain that production uses must run on the loopback test database, including any
non-transactional steps. The example assumes a `db:migrate` script that reads
`DATABASE_URL_DIRECT` and sets session timeouts before `BEGIN`.

```ts
// test/db.setup.ts — Vitest globalSetup: ONE shared container for the whole run
import { PostgreSqlContainer, type StartedPostgreSqlContainer } from '@testcontainers/postgresql'
import { execFileSync } from 'node:child_process'
import { assertLoopbackTestUrl } from './assert-loopback'

let container: StartedPostgreSqlContainer

export async function setup() {
  const major = Number(process.env.POSTGRES_MAJOR) // set to the production major version
  if (!Number.isInteger(major) || major < 12) throw new Error('POSTGRES_MAJOR is required')
  container = await new PostgreSqlContainer(`postgres:${major}-alpine`).start()
  try {
    const url = assertLoopbackTestUrl(container.getConnectionUri())
    execFileSync('pnpm', ['db:migrate'], {
      env: { ...process.env, DATABASE_URL: url, DATABASE_URL_DIRECT: url },
      stdio: 'inherit',
    })
    process.env.TEST_DATABASE_URL = url
  } catch (err) {
    await container.stop()
    throw err
  }
}

export async function teardown() {
  await container?.stop()
}
```

No Docker available (some CI tiers, local sandboxes)? Start a throwaway local Postgres cluster at
the production major version with `initdb`/`pg_ctl`, bound to a free loopback port under a temp
directory; the test script starts and stops it. An in-memory Postgres like
[pglite](https://github.com/electric-sql/pglite) can cover pure relational semantics, but not
pool, driver, timeout, lock, or migration-runner behavior. Never use a remote host, even a "test"
database on a shared cluster. **SQLite is not a
substitute** — its type coercion, lack of real `jsonb`, and different constraint semantics hide the
bugs you're testing for. The DB under test must be the same engine as production.

What a test may connect to (loopback only, never a shared or production host) and the standard
database suites T1–T8 (pool config, URL guards, transaction helper, migrations, connection-loss
resilience) are owned by **`craft-db`** → `seeding-and-testing.md`. PGlite is single-connection:
use it for relational semantics, never to prove pool, driver, timeout or lock behaviour.

---

## Test isolation — the one that matters

The trap: tests share one database and mutate it. Test A inserts a user; test B counts users and
asserts `=== 1`; run them in a different order, or in parallel, and B flakes. A shared mutable DB
makes the suite **order-dependent** — the canonical flake source (`flake.md`). Every test must start
from a known state and leave no trace for the next. Three strategies, fastest-but-narrowest first:

**1. Transactional rollback per test.** Begin a transaction in `beforeEach`, hand the test that
transaction as its `db`, roll back in `afterEach`. Nothing ever commits, so cleanup is instant and
tests can't see each other's writes.

Discover the ORM in the repo first, then use the matching pattern:

```ts
// Drizzle (drizzle-orm) — raw client transaction with explicit ROLLBACK in afterEach
import { afterEach, beforeEach, it } from 'vitest'
import { drizzle } from 'drizzle-orm/node-postgres'
import { Client } from 'pg'

let client: Client
let db: ReturnType<typeof drizzle>

beforeEach(async () => {
  client = new Client({ connectionString: process.env.TEST_DATABASE_URL })
  await client.connect()
  db = drizzle(client)
  // each test begins a transaction; afterEach rolls it back unconditionally
  await client.query('BEGIN')
})

afterEach(async () => {
  await client.query('ROLLBACK')
  await client.end()
})

it('inserts a user and the row is visible within the transaction', async () => {
  const [u] = await db.insert(users).values({
    id: crypto.randomUUID(),
    email: 'ada@example.com',
    tenantId: crypto.randomUUID(),
  }).returning()

  // read-back within the same transaction — visible here, gone after ROLLBACK
  const rows = await db.select().from(users).where(eq(users.id, u.id))
  expect(rows).toHaveLength(1)
  // afterEach rolls back — nothing persists to the next test
})
```

For Prisma on a non-Postgres project, prefer the truncate or isolated-database
strategy below unless a transaction fixture has been proven against the installed
Prisma version. Do not `await prisma.$transaction(callback)` in `beforeEach`
while its callback waits for `afterEach`: the test body can never start.
Projects adopting the Craftsman Postgres profile use pg + Drizzle.

Rollback is fast, but has two real limits: (a) the **code under test must accept the transaction
handle** — if a handler opens its *own* connection from the pool, it won't see `tx`'s uncommitted
rows, and the test is meaningless. (b) you **cannot test code that itself commits or uses nested
transactions** the same way — use savepoints, or fall to the truncate strategy below.

**2. Truncate between tests.** Let writes commit; in `afterEach`, `TRUNCATE` every table. Slower than
rollback but works for *any* code path including ones that commit or spawn their own connections.

```ts
afterEach(async () => {
  await pool.query(
    `TRUNCATE TABLE ${tables.join(', ')} RESTART IDENTITY CASCADE`,
  )
})
```

`RESTART IDENTITY` resets serial sequences so ids are deterministic; `CASCADE` handles FK order.

**3. Per-worker database (or schema) for parallelism.** Vitest/Jest run files in parallel workers; if
they share one DB they collide. Inside the single shared container, give each worker its own database
(`CREATE DATABASE test_${VITEST_WORKER_ID}`) or its own Postgres schema (`SET search_path`) — one
container, N isolated namespaces, not N containers. Validate the worker ID before using it in an
identifier, then apply the exact registered migration chain to **each** worker database/schema
before its tests start. Migrating only the container's default database leaves worker namespaces
empty. Combine with rollback/truncate *within* a worker.
This is what makes a real-DB suite both parallel and isolated.

**Pick:** rollback for the bulk of data-layer tests (speed), truncate for handlers that manage their
own transactions, per-worker DBs to unlock parallelism. Never the fourth option — a long-lived shared
DB with hand-written cleanup — which is where order-dependence and flake breed.

---

## Seeding & deterministic data

`test-design.md` owns the *philosophy* (each test owns its rows; no shared mutable fixtures). Here's
the DB-side mechanic: a **factory that inserts the minimum rows the test needs** and returns them,
honoring FK order and constraints, with deterministic values.

```ts
// test/factories.ts — insert real rows, return real ids, no globals
import { faker } from '@faker-js/faker'
// NOTE: seed in beforeEach, not at module scope.
// Module-scope seeding is shared mutable RNG state: when Vitest runs files in parallel
// or in a different order, tests that execute between seed() and the next reset see
// unpredictable sequences, making test data order-dependent and eventually flaky.

// Reset seed before each test (call faker.seed(42) in a beforeEach in your test file,
// or in vitest.config.ts globalSetup). Example placement in a test file:
//   beforeEach(() => faker.seed(42))

export async function makeUser(db: Db, over: Partial<NewUser> = {}) {
  const [u] = await db.insert(users).values({
    id: crypto.randomUUID(),
    email: over.email ?? faker.internet.email(),
    tenantId: over.tenantId ?? crypto.randomUUID(),
    ...over,
  }).returning()
  return u
}

export async function makeInvoice(db: Db, over: Partial<NewInvoice> = {}) {
  // create the parent the FK requires if the caller didn't supply one
  const tenantId = over.tenantId ?? (await makeUser(db)).tenantId
  const [inv] = await db.insert(invoices).values({
    id: crypto.randomUUID(), tenantId, amount: over.amount ?? 100, ...over,
  }).returning()
  return inv
}
```

Rules that keep seeded data from becoming a shared-fixture trap:
- **The test, not a global `seed.sql`, creates its rows** inside its isolation boundary, so rollback/
  truncate cleans them and no two tests depend on the same row.
- **Insert the minimum.** A test about invoice totals needs one tenant and two invoices, not the
  whole demo dataset. Big shared seeds make tests fragile and slow.
- **Deterministic values** (seeded faker, fixed clock) so a failure reproduces. Random emails are
  fine; a random *amount* the assertion depends on is a flake.
- **Let constraints fire.** If a factory has to disable a FK or unique constraint to insert, the test
  data is wrong — that's a signal, not an obstacle.

---

## Integration-testing routes and handlers

A handler test that asserts only the HTTP status is half a test. The other half — the one that
catches real bugs — is asserting the **persisted side effect**: the row was written, the job was
enqueued, the status flipped. Drive the *real* handler with a *real* request, then read the database
back.

```ts
// Express/Fastify/Hono: hit the running app with supertest (or fetch against a test server)
import request from 'supertest'
import { app } from '../src/app'

test('POST /invoices creates and persists the invoice', async () => {
  const user = await makeUser(db)

  const res = await request(app)
    .post('/invoices')
    .set('authorization', signSession(user))   // real auth path, not a mocked req.user
    .send({ amount: 250 })

  expect(res.status).toBe(201)
  expect(res.body).toMatchObject({ amount: 250, status: 'draft' })

  // the assertion that actually matters: it landed in the DB, scoped to the right tenant
  const rows = await db.select().from(invoices).where(eq(invoices.tenantId, user.tenantId))
  expect(rows).toHaveLength(1)
  expect(rows[0].amount).toBe(250)
})
```

For **Next.js route handlers**, you don't need a server — import and invoke the exported handler with
a real `Request`:

```ts
import { POST } from '@/app/api/invoices/route'

const res = await POST(new Request('http://t/api/invoices', {
  method: 'POST',
  headers: { authorization: signSession(user), 'content-type': 'application/json' },
  body: JSON.stringify({ amount: 250 }),
}))
expect(res.status).toBe(201)
// then read the DB back exactly as above
```

Exercise the **real auth/authorization path** — sign a genuine session/token and let the middleware
run. A test that injects a fake `req.user` skips the exact code that decides who's allowed in, which
is usually the code most worth testing.

---

## Proving an authorization fix (IDOR regression)

This is where craft-testing pairs with **`craft-security`**: security defines the vulnerability (an
IDOR — caller A can read caller B's row by guessing an id); you write the test that *proves the fix
holds* and never silently regresses. Cede the vuln catalog; own the proof.

The shape: set up two tenants with real data, authenticate as A, request B's resource, assert A is
denied — and assert it at the *persisted* boundary, not just the status code.

```ts
test('caller cannot read another tenant\'s invoice (IDOR regression)', async () => {
  const alice = await makeUser(db)
  const bob   = await makeUser(db)
  const bobInvoice = await makeInvoice(db, { tenantId: bob.tenantId, amount: 999 })

  // Alice authenticates and tries to read Bob's invoice by its real id
  const res = await request(app)
    .get(`/invoices/${bobInvoice.id}`)
    .set('authorization', signSession(alice))

  // Must be 404 (not 403 — don't confirm the row exists to a stranger), and NO body leak
  expect(res.status).toBe(404)
  expect(res.body).not.toMatchObject({ amount: 999 })
})
```

Verify it's a *real* test by the rule in `SKILL.md`: comment out the tenant-scope check in the
handler and confirm this test goes **red**. A regression test you haven't watched fail is not yet a
test. Add one of these for every authZ fix; that's how the suite gets sharp instead of bloated.

---

## Contract testing at service boundaries

When you have **separate services** (a provider API and one or more consumers, or a frontend that
calls your API across a deploy boundary), a unit test on each side can't catch a *breaking change* —
the provider renames a field, both suites stay green, prod breaks at the seam. A contract test pins
the shape they agree on.

Two pragmatic levels:
- **Schema-validated fixtures (cheap).** Define the boundary payload as a Zod schema shared (or
  duplicated and diffed) between sides; the provider test asserts its real response
  `schema.parse()`s, the consumer test builds its fixtures from the same schema. A field rename now
  fails a parse on one side.
- **Consumer-driven contracts (Pact, heavier).** The consumer publishes the subset it actually uses;
  the provider verifies it still satisfies that contract in CI. Catches "we removed a field no
  consumer was supposed to use, but one was."

**Worth it (Tier 2) when:** services deploy independently, owned by different teams or repos, where a
mismatch ships silently. **Overkill when:** it's one codebase deployed atomically — a type at the
boundary and an integration test through it already catch the break; a full Pact broker is ceremony
you'll resent. Default to the schema-fixture level; reach for Pact only at a real org/deploy seam.

---

## External services & side effects

You don't test Stripe; you test *your code's behavior* when Stripe responds. Hitting the real Stripe/
SendGrid/S3 in tests is slow, flaky, costs money, and pollutes their systems. Mock the **third-party
HTTP at the network boundary** — [MSW](https://mswjs.io) or nock intercept the outbound call so your
HTTP client, retry logic, and response parsing all still run for real (only the wire is faked). Don't
mock your *own* billing module; that erases the code under test.

```ts
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const msw = setupServer()
beforeAll(() => msw.listen({ onUnhandledRequest: 'error' })) // any un-mocked egress fails loud
afterEach(() => msw.resetHandlers())
afterAll(() => msw.close())

test('a charge that times out once is retried and the order ends up paid', async () => {
  let calls = 0
  msw.use(http.post('https://api.stripe.com/v1/charges', () => {
    calls++
    if (calls === 1) return HttpResponse.error()           // first attempt: network failure
    return HttpResponse.json({ id: 'ch_123', status: 'succeeded' })
  }))
  const order = await makeOrder(db, { status: 'pending' })

  await chargeOrder(db, order.id)

  // assert the OBSERVABLE result of the side-effect design, not the internals:
  expect(calls).toBe(2)                                     // retry happened
  const [row] = await db.select().from(orders).where(eq(orders.id, order.id))
  expect(row.status).toBe('paid')
  expect(row.chargeId).toBe('ch_123')                       // external id captured
})
```

The side-effect *design* (outbox, idempotency keys, enqueue-after-commit) lives in **`craft-backend`**
→ `side-effects.md`. Here you test its **observable behavior**: a retried call ends in one paid order
not two; a replayed webhook with the same idempotency key writes the row once; a failed external call
leaves no falsely-"complete" row. Drive the second delivery and assert the DB has exactly one effect.

---

## Migrations in tests

Build the test schema by running the **real migration files**, the same ones prod runs — never a
hand-maintained `schema.sql` or `db.push` of the current model. A hand-built test schema is a second
source of truth that silently drifts: someone adds a migration that backfills a column or adds a
`CHECK` constraint, forgets the test schema, and the suite passes against a schema production no
longer has. Running migrations in setup means **schema drift is caught** — a broken or out-of-order
migration fails the test run, not the deploy.

The setup above invokes the repo's `db:migrate` script on `DATABASE_URL_DIRECT` after asserting the
URL is loopback. Use that exact runner and registered migration chain in T6, including steps such
as `CREATE INDEX CONCURRENTLY` that run outside a transaction. Do not call the ORM migrator directly
from the test harness if the production runner does more work.

This also turns the migration itself into something tested: if a migration won't apply to a clean DB,
or a `NOT NULL` added without a default breaks on existing-shaped data, you find out in CI. For
migrations that transform data, add a dedicated test — seed the *old* shape, run the migration, assert
the *new* shape — so a destructive backfill is caught before it runs on real rows. (Schema/constraint
*design* correctness is **`craft-db`**; here you only assert the migration applies and transforms as
intended.)

---

---

## Python / pytest backend testing

The same discipline — real boundary, real DB, isolated per test — applies to Python backends.
The tool names change; the pattern does not.

**SQLAlchemy session rollback fixture.** A `yield` fixture with function scope begins a transaction,
hands the session to the test, then rolls back in cleanup. The session is passed into the code
under test so every write goes through the same transaction.

```python
# conftest.py
import os
import ipaddress
from urllib.parse import urlsplit
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@pytest.fixture(scope="session")
def engine():
    # The fixture owns this disposable loopback DB; never migrate a shared URL.
    url = os.environ["TEST_DATABASE_URL"]
    parsed = urlsplit(url)
    try:
        loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if (not loopback or parsed.query or parsed.fragment or
            os.environ.get("TEST_DATABASE_DISPOSABLE") != "1"):
        raise RuntimeError("tests require an owned disposable loopback database")
    eng = create_engine(url)
    # Run the REAL migration files — not hand-built DDL (see "Migrations in tests" above)
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")
    yield eng
    eng.dispose()  # the container/disposable cluster owns final database teardown

@pytest.fixture
def session(engine):
    """Function-scoped: each test gets its own transaction, rolled back on teardown."""
    connection = engine.connect()
    transaction = connection.begin()
    s = Session(bind=connection)
    yield s
    s.close()
    transaction.rollback()
    connection.close()
```

```python
# test_invoices.py
def test_create_invoice_persists(session):
    user = make_user(session)
    invoice = create_invoice(session, user_id=user.id, amount=250)

    rows = session.query(Invoice).filter_by(id=invoice.id).all()
    assert len(rows) == 1
    assert rows[0].amount == 250
    # session rolls back in fixture teardown — nothing leaks to the next test
```

**httpx `AsyncClient` for FastAPI / Starlette.** Drive the real ASGI app with `httpx.AsyncClient`
— no separate server process, full middleware and dependency injection stack runs for real.

```python
import pytest, httpx
from app.main import app

@pytest.fixture
async def client(session):
    # Override the db dependency so the route uses the test-scoped session
    app.dependency_overrides[get_db] = lambda: session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_post_invoice_creates_row(client, session):
    user = make_user(session)
    res = await client.post("/invoices", json={"amount": 250},
                            headers={"authorization": sign_session(user)})
    assert res.status_code == 201

    row = session.query(Invoice).filter_by(id=res.json()["id"]).first()
    assert row is not None
    assert row.amount == 250
```

**freezegun for time-based tests.** Any code that calls `datetime.now()` or `datetime.utcnow()`
internally is non-deterministic without a freeze. freezegun patches the standard library so the
code under test reads the pinned instant.

```python
from freezegun import freeze_time
from app.tokens import issue_token, is_expired
from datetime import datetime, timedelta

@freeze_time("2026-01-15 12:00:00")
def test_token_expires_after_one_hour():
    token = issue_token()

    with freeze_time("2026-01-15 13:00:01"):   # advance past the TTL
        assert is_expired(token)
```

**conftest.py structure summary.**

```
conftest.py (root)
├── engine fixture  (scope="session") — one DB for the whole run
├── session fixture (scope="function") — per-test transaction rollback
└── client fixture  (scope="function") — ASGI client wired to the test session
```

Scope the `engine` to the session (fast — create once) and the `session` to the function
(isolated — rollback per test). Never share a function-scoped session across tests.

---

## Testing Server Actions and tRPC

Server Actions and tRPC procedures live entirely in the same Node process as your tests — you can
call them as ordinary async functions. No HTTP server, no fetch, no port. This is faster and more
isolated than driving a running server.

**Next.js Server Actions.** Import the action function directly and call it. The test controls the
database through the same `db` handle (or transaction) the action uses — assert the persisted effect
exactly as you would in a handler test.

```ts
import { createInvoice } from '@/app/actions/invoices'
import { db } from '@/lib/db'                           // the real db, under your test isolation

test('createInvoice persists a draft invoice scoped to the caller', async () => {
  const user = await makeUser(db)

  // Call the Server Action as a plain async function — no HTTP needed
  const result = await createInvoice({ amount: 250 }, { userId: user.id })

  expect(result.status).toBe('draft')
  const rows = await db.select().from(invoices).where(eq(invoices.id, result.id))
  expect(rows).toHaveLength(1)
  expect(rows[0].tenantId).toBe(user.tenantId)           // scoped to the right tenant
})
```

Important: if the action reads `auth()` / `getServerSession()` from Next.js internals, mock that
boundary at the module level so the test controls the calling identity without needing an HTTP
session cookie. Mock only the auth resolution, not the action logic or the database.

**tRPC — `createCallerFactory`.** Instantiate the router directly in the test and call procedures
as async functions. The caller carries the context you provide — supply a real `db` handle and a
test user for the session, and the procedure runs exactly as in production without going through
HTTP transport.

```ts
import { appRouter } from '@/server/routers'
import { createCallerFactory } from '@trpc/server'

const createCaller = createCallerFactory(appRouter)

test('rejects with UNAUTHORIZED when the caller is not authenticated', async () => {
  // Unauthenticated context: session is null
  const caller = createCaller({ db, session: null })
  await expect(caller.invoices.create({ amount: 250 })).rejects.toThrow('UNAUTHORIZED')
})

test('invoices.create persists the invoice for the authenticated user', async () => {
  const user = await makeUser(db)
  const caller = createCaller({ db, session: { userId: user.id, tenantId: user.tenantId } })

  const invoice = await caller.invoices.create({ amount: 250 })

  expect(invoice.status).toBe('draft')
  const rows = await db.select().from(invoices).where(eq(invoices.id, invoice.id))
  expect(rows).toHaveLength(1)
})
```

The same transactional rollback or truncate isolation applies here — the `db` you pass in the
context is your test-scoped handle, so cleanup works identically to any other integration test.

---

## Quick-reject checklist

Flag with `file:line` and the fix:

| Smell | Fix |
| --- | --- |
| Data-layer test with the DB / ORM mocked | Test against a real ephemeral Postgres (testcontainers); the mock erases every real failure mode |
| SQLite (or `better-sqlite`) standing in for Postgres | Use the same engine as prod; SQLite hides `jsonb`/type-coercion/constraint bugs |
| Tests share one long-lived DB with manual cleanup | Add per-test isolation (rollback/truncate) + per-worker DBs; this is the #1 order-dependent flake (`flake.md`) |
| Rollback isolation but the handler opens its own pool connection | Thread the test transaction into the code, or switch that test to truncate isolation |
| Global `seed.sql` every test depends on | Each test inserts its own minimal rows via factories, inside its isolation boundary |
| Random factory value the assertion depends on | Seed faker / fix the clock; only assertion-irrelevant fields may be random |
| Handler test asserting status code only | Also read the DB back — assert the row written / job enqueued / status flipped |
| Test injects a fake `req.user` / mocked session | Sign a real session and run the actual auth middleware — that's the code worth testing |
| AuthZ fix shipped without a cross-tenant regression test | Add an IDOR test (caller A denied B's row); confirm it goes red with the fix removed (`craft-security` pairing) |
| Independently-deployed services with no contract test | Add a schema-validated boundary fixture (or Pact at a real org seam); unit tests can't catch a cross-service break |
| Test hits real Stripe / SendGrid / S3 | Mock the third-party HTTP at the boundary (MSW/nock); keep your client + retry logic real |
| Own billing/email module mocked instead of the network | Mock only what you don't own; mocking your module erases the code under test |
| Retry/idempotency/outbox logic with no behavior test | Drive a duplicate/failed delivery; assert exactly one persisted effect |
| Test schema hand-built, `db.push`'d, or migrated by a test-only path | Run the exact registered chain through the real runner on loopback Postgres |
| Data-transforming migration with no test | Seed the old shape, run the migration, assert the new shape before it touches real rows |
