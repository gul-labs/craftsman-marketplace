# Access Patterns

Every tenant-scoped query that reaches the database raw is a data-leak waiting to ship. The
discipline: **every read or write against a tenant table goes through one shared helper that injects
the tenant id — no exceptions — and the soft-delete filter when the project uses soft-delete** (see
`schema.md` "When soft-delete is used"). That helper is the single enforcement point; bypass it once
and the pattern that ships IDOR bugs is established. Beyond tenant scoping, queries must be written
for real, observed access patterns: keyset pagination over OFFSET, explicit column selection over
`SELECT *`, and joined or batched loads over N+1.

> **Scope split.** This file owns *how queries are structured and scoped*: the tenant-scope helper
> contract, soft-delete filtering, pagination strategy, column selection, and N+1 avoidance. The
> indexes those patterns need live in `indexing.md`; the column types and soft-delete column
> definition are in `schema.md`; FK and transaction integrity rules are in `integrity.md`.
>
> **See also:** **`craft-security`** → `authz.md` — tenant scoping at the DB layer is the
> enforcement backstop for what authZ decided at the API layer; IDOR prevention requires both.
> **`craft-backend`** → `auth.md` — the request lifecycle where tenant id is resolved from the
> session and threaded into the query helper; this file assumes that id is already established and
> trusted.

---

## Contents

- [The tenant-scope helper](#the-tenant-scope-helper)
- [Soft-delete filtering](#soft-delete-filtering)
- [Column selection — no SELECT *](#column-selection--no-select-)
- [Pagination — keyset over OFFSET](#pagination--keyset-over-offset)
- [N+1 avoidance](#n1-avoidance)
- [Raw SQL template literals in Drizzle](#raw-sql-template-literals-in-drizzle)
- [Write patterns — updates and deletes](#write-patterns--updates-and-deletes)
- [Row-Level Security (RLS)](#row-level-security-rls)
- [Quick-reject checklist](#quick-reject-checklist)

---

## The tenant-scope helper

Every repo that supports multiple tenants (workspaces, organisations, accounts — whatever the
domain calls them) must have one shared function or query builder that enforces the tenant predicate.
Discover what it's called before writing any query: look for a `db/helpers.*`, `lib/db.*`,
`repositories/`, or a Drizzle/Prisma extension pattern that always appends a `tenantId` (or
`orgId`, `workspaceId`, `accountId` — check the schema) condition.

If no such helper exists, create it as a prerequisite — not as a nice-to-have.

**What the helper must do:**

1. Accept the trusted tenant id — sourced from the server-established session, never from the
   request body. (`craft-backend` → `auth.md` is where that id is resolved.)
2. Inject the tenant predicate into *every* query it builds, structurally — not as an optional
   parameter callers can forget to pass.
3. Enforce the soft-delete filter (see next section) by default, with an explicit opt-in for
   admin/recovery queries that genuinely need deleted rows.

A minimal Drizzle illustration (shape will vary — the principle is the same for any query builder):

```ts
// Helper wraps the raw table; callers never reach `invoices` directly.
// Explicit column selection — no SELECT *; enumerate only what callers need.
function findInvoiceById(db: DrizzleDB, tenantId: string, id: string) {
  return db
    .select({
      id: invoices.id,
      tenantId: invoices.tenantId,
      status: invoices.status,
      amountCents: invoices.amountCents,
      createdAt: invoices.createdAt,
    })
    .from(invoices)
    .where(and(eq(invoices.tenantId, tenantId), isNull(invoices.deletedAt), eq(invoices.id, id)))
    .limit(1)
}

// WRONG — raw table access; skips both tenant scope and soft-delete
const invoice = await db.select().from(invoices).where(eq(invoices.id, id)).limit(1)

// RIGHT — goes through the helper; a foreign tenantId simply returns nothing
const [invoice] = await findInvoiceById(db, session.tenantId, id)
```

What must not differ across ORMs and query builders is that the predicate is *always present*.

**Make bypass structurally hard.** Wrap the Drizzle table in a helper or repository function so callers cannot reach the raw table directly — a function that accepts a `tenantId` and returns a pre-scoped query base is the simplest form. The goal is structural: bypassing tenant scope should require an intentional, visible decision, not an accidental omission.

---

## Soft-delete filtering

Soft-delete means rows are never physically removed; instead a `deletedAt` (or `deleted_at`,
`is_deleted` — check the schema, name varies) column is set. Without a filter in every query,
soft-deleted rows appear in live results, breaking both correctness and compliance requirements.

**The helper must default to filtering them out.** This is why the soft-delete filter belongs in the
shared helper rather than at each call site:

```ts
// Every query through the helper sees: WHERE deleted_at IS NULL (or is_deleted = false)
// Admin/recovery queries opt in explicitly by querying without the soft-delete predicate:
const withDeleted = await db
  .select()
  .from(invoices)
  .where(and(eq(invoices.tenantId, session.tenantId), eq(invoices.id, id)))
  .limit(1)
// deletedAt intentionally omitted — recovery path only
```

Pitfalls:
- **Cascade soft-delete when the domain demands it.** Soft-deleting a workspace without soft-
  deleting its child resources means those children re-appear if a workspace is restored, and can
  leak in cross-table joins that filter only on the parent. Check whether the schema signals a
  cascade expectation (see `integrity.md`).
- **Unique constraints break on soft-delete without partial indexes.** A `UNIQUE(tenant_id, email)`
  on a users table prevents re-inviting someone after their account is soft-deleted. The fix is a
  partial unique index `WHERE deleted_at IS NULL`. Wire the index; see `indexing.md`.
- **Count queries must also filter.** `COUNT(*)` used for pagination totals or limit checks must
  apply the same `WHERE deleted_at IS NULL` predicate. An unfiltered count is its own class of
  correctness bug.

---

## Column selection — no SELECT *

`SELECT *` fetches every column the table has, including columns added later, large `text`/`jsonb`
blobs, internal audit columns, and potentially sensitive fields the current caller has no business
reading. Write the columns the call actually needs.

```ts
// WRONG — fetches all columns; expensive blobs and sensitive fields leak through
const rows = await db.select().from(users).where(tenantScope)

// RIGHT — fetch only what the caller reads
const rows = await db
  .select({ id: users.id, name: users.name, email: users.email, role: users.role })
  .from(users)
  .where(tenantScope)
```

This is not micro-optimisation. On a table with a `blob`, `text`, or `jsonb` content column,
`SELECT *` across thousands of rows can balloon query time and memory. More importantly, selecting
only needed columns makes it impossible to accidentally pass a full row — with its internal or
sensitive fields — to a downstream serializer or response.

**In raw SQL:** spell out the column list; never use `*` in application queries that return to
user-facing code. Wildcard selects are acceptable in migrations (e.g., `SELECT * FROM foo LIMIT 0`
to inspect structure) and REPL exploration, not in shipped query code.

---

## Pagination — keyset over OFFSET

`OFFSET n` tells the database to scan and discard `n` rows before returning results. On large tables
this scan grows linearly with depth: page 1 is fast; page 1 000 requires the DB to visit
1 000 × page_size rows before returning anything. This is why list queries get slower over time
with OFFSET — and why it should not be the default pagination strategy.

**Use keyset (cursor) pagination instead.** The cursor encodes the last-seen position (typically the
ordering column value plus the row id) and the query resumes from there:

```sql
-- WRONG — OFFSET degrades linearly with depth
SELECT id, created_at, title
FROM   posts
WHERE  tenant_id = $1 AND deleted_at IS NULL
ORDER  BY created_at DESC, id DESC
LIMIT  25 OFFSET 500;

-- RIGHT — keyset: resume after the last seen (created_at, id) pair
SELECT id, created_at, title
FROM   posts
WHERE  tenant_id = $1 AND deleted_at IS NULL
  AND  (created_at, id) < ($last_created_at, $last_id)  -- Postgres row-value comparison
ORDER  BY created_at DESC, id DESC
LIMIT  25;
```

The cursor is opaque to the client (base64-encode the `(created_at, id)` pair, or use a signed
token). The composite `(tenant_id, created_at DESC, id DESC)` index that backs this query is in
`indexing.md`.

**When OFFSET is acceptable:**
- Small, bounded tables (a few thousand rows and not growing) where depth never becomes an issue.
- Admin exports that run offline or in a background job with an explicit page budget.
- UI that requires random-access page jumps (jump to page 47). Even then, evaluate whether a keyset
  with a separate total-count query is sufficient before defaulting to OFFSET.

**Cursor encoding rules:** never expose raw database ids or timestamps directly if they reveal
internal structure. Sign or encrypt the cursor if the ordering fields are sensitive. Validate the
decoded cursor on the server before using its values in a query — treat it as untrusted input.

**Mixed-direction sort caveat:** row-value comparison cursors (`(created_at, id) < ($last_created_at, $last_id)`)
only work when all ORDER BY columns share the same direction (all ASC or all DESC). For
mixed-direction sorts (e.g., `ORDER BY name ASC, created_at DESC`), the row-value comparison must
be expanded into an explicit OR predicate: `(name > $last_name) OR (name = $last_name AND
created_at < $last_created_at)`. PostgreSQL cannot use a single B-tree index to satisfy a row-value
comparison when column sort directions differ.

---

## N+1 avoidance

An N+1 is a query that fires once to load N parent records, then fires once more per row to load a
related entity — N+1 round trips to the DB instead of 2. It is invisible in development with small
data sets and devastating in production with thousands of rows.

**Detect it:** look for a query inside a loop, an ORM relation access inside a `.map()`, or a
`for await` that calls the DB on each iteration.

**Fix it with a joined load or a batched second query:**

```ts
// WRONG — N+1: one query to load invoices, then one per invoice to load its client name
const rows = await getInvoices(tenantId)
const withClient = await Promise.all(
  rows.map(inv =>
    db.select().from(clients).where(eq(clients.id, inv.clientId)).limit(1)
  )
)

// RIGHT — join the relation in the first query (Drizzle)
const rows = await db
  .select({
    id: invoices.id,
    status: invoices.status,
    clientId: clients.id,
    clientName: clients.name,
  })
  .from(invoices)
  .leftJoin(clients, eq(invoices.clientId, clients.id))
  .where(and(eq(invoices.tenantId, tenantId), isNull(invoices.deletedAt)))

// ALSO RIGHT — batched second query (preferable when the join would inflate rows)
const clientIds = [...new Set(rows.map(inv => inv.clientId))]
const clientRows = await db
  .select({ id: clients.id, name: clients.name })
  .from(clients)
  .where(and(inArray(clients.id, clientIds), eq(clients.tenantId, tenantId), isNull(clients.deletedAt)))
const clientMap = new Map(clientRows.map(c => [c.id, c]))
```

**GraphQL / DataLoader pattern.** If the repo uses a GraphQL layer (Apollo, Pothos, GraphQL Yoga),
each field resolver fires independently, making N+1 the default behaviour. Use DataLoader (or the
ORM's equivalent batching) to coalesce per-request loads: DataLoader dedupes and batches all
resolver calls for the same key within a single event-loop tick. Wire it to a batched query — e.g. `db.select().from(table).where(inArray(table.id, keys))` — this is the canonical GraphQL N+1 fix.

**Joins can also over-fetch.** A join that multiplies rows (one-to-many) inflates the result set.
The risk is most severe when joining *multiple* one-to-many relations in a single query: an invoice
joined to both 100 line items and 50 payments returns 5,000 rows (100 × 50 Cartesian product)
instead of 151 rows across two separate batched queries. Even a single one-to-many join duplicates
the parent row's columns across every child row, inflating wire transfer size roughly proportionally
to the child count. The two-query batched approach is often cheaper for large one-to-many relations.
Confirm with `EXPLAIN ANALYZE` — see `indexing.md`.

---

## Raw SQL template literals in Drizzle

When Drizzle's `sql` tagged template is used for a raw expression (a CAS check, a lateral join, a custom function), **use the physical column name as it exists in the database — not the ORM camelCase alias.**

```ts
import { sql } from "drizzle-orm";

// WRONG — Drizzle does NOT translate camelCase aliases inside sql`` literals
db.update(dossiers)
  .set({ status: "processing" })
  .where(sql`dossierId = ${id} AND status = 'idle'`);
// → runtime error: column "dossierId" does not exist

// RIGHT — use the actual column name from the DB schema
db.update(dossiers)
  .set({ status: "processing" })
  .where(sql`dossier_id = ${id} AND status = 'idle'`);
```

This applies to every raw string interpolated through `sql`: column references, table aliases, ORDER BY expressions, window functions, and custom predicates. The ORM column mapping only applies to the structured query builder (`.select({ id: table.id })` etc.); inside `sql```, you are writing raw Postgres.

Also: in **multi-schema Postgres repos** (schemas defined via `pgSchema` or explicit `search_path`-less connections), raw SQL must use fully-qualified `<schema>.<table>` names. Without a `search_path` override, Postgres resolves bare table names against `public` only and will error or hit the wrong table silently.

```ts
// WRONG in a multi-schema repo with no search_path
sql`INSERT INTO regeneration_requests ...`

// RIGHT — schema-qualify every raw table reference
sql`INSERT INTO pipeline_v2.regeneration_requests ...`
```

Discover whether the repo uses `pgSchema` (Drizzle) or a schema prefix before writing any `sql` literal. State what you find.

---

## Write patterns — updates and deletes

**Always scope writes by tenant id.** A bare `UPDATE invoices SET ... WHERE id = $1` that omits the
tenant predicate will execute successfully against any row in the table — including rows belonging to
a different tenant — if the id is known or guessed. The same helper logic applies to writes:

```sql
-- WRONG — no tenant scope on the write
UPDATE invoices SET status = 'paid' WHERE id = $1;

-- RIGHT — tenant predicate prevents cross-tenant mutation
UPDATE invoices
SET    status = 'paid', updated_at = NOW()
WHERE  id = $1 AND tenant_id = $2 AND deleted_at IS NULL;
```

Use `RETURNING` (Postgres) or a follow-up `SELECT` to verify the row was actually updated —
assert `rowsAffected === 1`: a zero result is a 404 (row not found or wrong tenant); a result
greater than 1 is a server error — it signals a missing uniqueness constraint or an overly broad
WHERE clause and must never be treated as success.

**Soft-delete as an UPDATE, not a DELETE:**

```sql
UPDATE invoices
SET    deleted_at = NOW()
WHERE  id = $1 AND tenant_id = $2 AND deleted_at IS NULL;
```

Include `deleted_at IS NULL` in the predicate so a double-delete is a no-op rather than a silent
success on an already-deleted row.

**Multi-step writes need a transaction.** If a single logical operation touches more than one table
(e.g., create an invoice and decrement a usage quota) wrap both in a transaction. See `integrity.md`
for the full transaction pattern.

---

## Row-Level Security (RLS)

Postgres RLS is a **defense-in-depth backstop behind** the app-layer tenant-scope helper above — not
a replacement for it. It catches the query that bypasses the helper; it should never be the only
thing standing between a request and another tenant's row.

**Enable and force it:**

```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
```

`ENABLE` alone does not apply to the table owner or superusers — most app connections run as the
table owner, so without `FORCE ROW LEVEL SECURITY` the policy silently does nothing for the
connection that matters most. Always pair the two statements.

**Tenant-scoping policy pattern**, using a session-local setting for the current tenant:

```sql
CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

The app sets `app.tenant_id` once per request/transaction; every query against `invoices` is then
implicitly filtered, even a raw `SELECT *` from a forgotten helper bypass.

**The transaction-pooler caveat.** Behind pgBouncer (or any transaction-mode pooler), a session-level
`SET app.tenant_id = '...'` leaks across clients — the connection is returned to the pool after the
transaction, and the next unrelated client can inherit the previous session's setting. Never use
plain `SET` for this value in a pooled environment. Use `SET LOCAL` inside the *same transaction* as
the query, every time:

```sql
BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-1111-1111-111111111111';
SELECT * FROM invoices; -- scoped by the policy above
COMMIT;
```

`SET LOCAL` is transaction-scoped and reset automatically at commit/rollback — it cannot leak to the
next transaction that lands on the same pooled connection. See `connection-pooling.md` for the full
pgBouncer transaction-mode gotcha list.

### Auditing a project that deliberately chose *not* to use RLS

Plenty of sound multi-tenant systems run without RLS. Adopting it late is genuinely invasive — every
table, every policy, every pooled connection — so "turn on RLS" is often the exact rewrite demand
that makes an audit worthless. **Meet the project where it is.**

The audit question is not *"why isn't RLS enabled?"* but:

> **You chose not to use RLS. What is the named compensating control, and does it execute in CI?**

A real compensating control has four properties. Check each:

1. **The decision is recorded** — an ADR or a comment saying RLS was considered and declined, with
   the reason. An undocumented absence is a gap; a documented one is a trade-off.
2. **The control is named and mechanical** — most often a *structural test*: walk every query
   module, and for each exported function touching a tenant-scoped table, require a `tenantId` /
   `workspaceId` filter or a known scope-helper in the same function body. This is a cheap
   grep-shaped test, not a framework.
3. **It runs in CI**, not as a one-off script someone remembers to run.
4. **Deviations are allowlisted with a written justification each** — keyed by
   `file::exportName`, one line of reasoning per entry, reviewed like code. This is the load-bearing
   part: it forces every legitimate cross-tenant query (reconciliation sweeps, background jobs,
   staff-plane diagnostics) to be argued for in writing rather than silently added.

If all four hold, **the finding is "none" — say so explicitly** and move on; do not downgrade it to
a nag. If the control exists but skips background jobs, that's the finding: a scheduled job or queue
worker running outside request context is where tenant scoping is most often lost, because the audit
(and the test) only looked at HTTP handlers.

Missing entirely? Recommend the structural test *before* recommending RLS — it lands in an afternoon,
covers the same failure mode, and doesn't touch the schema or the pooler.

---

## Quick-reject checklist

Flag with `file:line` and the fix:

| Pattern | Fix |
| --- | --- |
| Query against a tenant table without `tenantId` in the `WHERE` | Route through the shared tenant-scope helper; never raw-table access |
| Tenant id accepted from the request body rather than the server session | Reject — the trusted tenant id is resolved from the session by `craft-backend` → `auth.md`; sourcing it from the body is an IDOR vector |
| `deletedAt` / `deleted_at` missing from a query on a soft-delete table | Add filter to the helper; check cascade on parent soft-deletes |
| `SELECT *` / ORM call with no `select`/`columns` option | Enumerate only the columns the call actually needs |
| `OFFSET n` pagination on a table that can grow large | Replace with keyset/cursor pagination; reserve OFFSET for bounded admin queries |
| Cursor decoded and used raw in a query without validation | Validate (and if sensitive, sign/encrypt) the cursor server-side before use |
| DB call inside a `.map()`, `for` loop, or per-item resolver | Replace with a joined load or a batched `WHERE id IN (...)` query |
| GraphQL resolver fetching a related field without DataLoader | Wire DataLoader (or ORM equivalent) to batch per-request loads |
| `UPDATE` / `DELETE` with no tenant predicate | Add `AND tenant_id = $tenantId` to every write; verify `rowsAffected === 1` |
| Soft-delete `UPDATE` without `deleted_at IS NULL` in the predicate | Add the guard; a double-delete must be a harmless no-op |
| Multi-table write (insert + update) outside a transaction | Wrap in a DB transaction — see `integrity.md` |
| Unique constraint failing after soft-delete of an active record | Add a partial unique index `WHERE deleted_at IS NULL` — see `indexing.md` |
| Count query for pagination omitting the soft-delete filter | Apply `WHERE deleted_at IS NULL`; the count must match the list query predicate |
