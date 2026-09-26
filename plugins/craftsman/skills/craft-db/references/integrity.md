# Data Integrity

The database is the last line of defense for your data's correctness. **DB-level constraints beat app-level checks because they hold even when your application is bypassed — by a migration script, a second service, a developer with psql, or a future code path that never called your validator.** An app validation that the DB doesn't also enforce is a promise you can't keep. Unique constraints, foreign keys, check constraints, and NOT NULL are not redundant with app logic — they are the guarantee that app logic is never the single gatekeeper.

> **Scope split.** This file owns the *database-side* integrity story: constraints, FK strategies, constraint naming, transactions for multi-step writes, and the staged-backfill pattern for large tables. The *application-side* orchestration of those multi-step writes — ordering side effects, idempotency, compensating actions — is covered in **`craft-backend`** → `side-effects.md`. Schema design choices (types, nullability, column naming) that feed into these constraints belong to `schema.md`. The tooling mechanics of generating and applying migrations safely (including how to sequence staged steps) are in `migrations.md`. Access-pattern helpers that enforce tenant scope at the query layer are in `access-patterns.md`.
>
> **See also:** `schema.md` (column types, nullability, naming) · `migrations.md` (generation + safe apply) · `access-patterns.md` (tenant-scoped query helpers) · `indexing.md` (index types, naming, EXPLAIN workflow)

---

## Contents

- [Constraints belong at the database level](#constraints-belong-at-the-database-level)
- [Foreign keys and on-delete strategy](#foreign-keys-and-on-delete-strategy)
- [Constraint naming](#constraint-naming)
- [Transactions for multi-step writes](#transactions-for-multi-step-writes)
- [Staged backfills for large tables](#staged-backfills-for-large-tables)
- [Backups and restore](#backups-and-restore)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Constraints belong at the database level

Every uniqueness invariant, range restriction, and null prohibition your domain requires must be expressed as a database constraint, not only as application-layer validation. Application checks improve UX and fail fast — they do not replace the DB guarantee.

**Unique.** A `UNIQUE` constraint on `(email)` or `(tenant_id, slug)` is atomic and race-free. Two concurrent inserts from two app servers both passing an application-layer "does this exist?" check before writing will race to a duplicate. The DB constraint does not race — one wins, one fails with a constraint error, and you handle it. An application-only check is an unclosed window.

**Not null.** If the domain says a value is required, the column must be `NOT NULL`. A nullable column whose value is always expected is a promise the schema doesn't enforce. Every `if (value == null) throw` you write in the app is an admission that the DB hasn't said what it should.

**Check constraints.** For bounded enumerations or ranges — `status IN ('pending', 'active', 'cancelled')`, `quantity > 0`, `end_date >= start_date` — express them as `CHECK` constraints. Dialect note: Postgres enforces `CHECK` constraints at write time; MySQL historically ignored them before 8.0.16 (verify your target). An ORM-level enum type is not a DB check constraint unless the ORM emits one — inspect the generated migration.

**Write the constraint first, add the UX validation second.** The constraint is the invariant. The app-level check is the friendly error message. Both belong; the order of importance is DB first.

---

## Foreign keys and on-delete strategy

Declare foreign keys for every relationship the schema expresses. Without them, orphaned rows accumulate silently — a deleted user leaving invoices pointing at a missing user id, queries that must LEFT JOIN to paper over the gap, and data that becomes unsynchronized after migrations that don't clean up.

**Choose the on-delete strategy intentionally** — it is a domain decision, not a default:

| Strategy | When to use |
| --- | --- |
| `ON DELETE RESTRICT` | The child should never outlive the parent; a delete of the parent must be explicit. Use this as the safe default — it forces the caller to think. See Postgres dialect note below for the check-timing difference between RESTRICT and NO ACTION. |
| `ON DELETE NO ACTION` | Functionally identical to RESTRICT in virtually all practical cases. See Postgres dialect note below. |
| `ON DELETE CASCADE` | Child rows are meaningless without the parent and should be removed atomically with it (e.g. `order_items` when an `order` is deleted). Use with care: a cascade on a large table can produce a very long-running transaction with significant write amplification, WAL growth, and potential autovacuum disruption on large child tables. |
| `ON DELETE SET NULL` | The child can exist without the parent but the relationship should be severed (e.g. `created_by` on a content row when the creating user is deleted). Requires the FK column to be nullable. |
| `ON DELETE SET DEFAULT` | Rare; the child falls back to a sentinel value. Supported by Postgres, not all dialects. |

**Soft-delete complicates FK enforcement.** If the referenced table uses soft deletes (a `deleted_at` column), a FK doesn't distinguish a live row from a soft-deleted one. You end up with live child rows pointing at logically-deleted parents, and queries that must filter `deleted_at IS NULL` on every join. Options, in order of preference: (1) enforce hard deletes for parent records and let `CASCADE` clean children; (2) add an application-level check before soft-deleting a parent that has live children; (3) accept the soft-delete leak and filter consistently (the `access-patterns.md` helper must cover this). This is a domain judgment — name it explicitly in the schema decision.

**MVP default for soft-delete cascade:** For most MVPs, use application-level cascade — delete or soft-delete child rows in code before soft-deleting the parent. This is simpler to debug (the sequence of deletes is visible in application logs and traces), easier to audit (no hidden DB triggers firing), and straightforward to test. DB-level triggers for cascade soft-delete add correctness but are harder to introspect and debug when something goes wrong. Reach for trigger-based cascades only when you have confirmed they are needed and you have the observability to debug them.

**Postgres dialect note.** In Postgres, both RESTRICT and NO ACTION block the delete in virtually all practical scenarios. The technical difference is that RESTRICT checks immediately (before row-level triggers), while NO ACTION checks at the end of the statement (after row-level triggers). Neither is transaction-deferred unless you also declare `DEFERRABLE`. Do not conflate NO ACTION with deferred constraints. When using deferred constraints (`DEFERRABLE INITIALLY DEFERRED`) you can swap rows referencing each other within a transaction — useful for reordering operations but a footgun if misapplied. Declare deferrable only when you need it.

---

## Constraint naming

Name every constraint explicitly. When a constraint violation surfaces in logs, an unnamed constraint yields `"23505"` or `"$1"` — an explicit name yields `"uq_users_email"` or `"chk_orders_quantity_positive"`, pointing directly to the problem.

**Naming convention.** Pick one and apply it across the entire schema — the exact scheme matters less than consistency. A common pattern:

```
{type}_{table}_{columns}
```

Where `{type}` is one of:

| Prefix | Constraint type |
| --- | --- |
| `pk_` | Primary key |
| `uq_` | Unique |
| `fk_` | Foreign key |
| `chk_` | Check |

Index naming follows the same `{type}_{table}_{columns}` convention — see `indexing.md`.

Examples:

```sql
-- Postgres / SQL syntax (adapt to your ORM's constraint-naming API)
CONSTRAINT uq_users_email UNIQUE (email)
CONSTRAINT uq_workspaces_slug UNIQUE (workspace_id, slug)
CONSTRAINT fk_invoices_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT
CONSTRAINT chk_orders_quantity_positive CHECK (quantity > 0)
```

In ORM-generated migrations (e.g. Drizzle, Prisma, Knex), verify the emitted SQL names the constraint — some ORMs auto-generate opaque names. If yours does, pass the name explicitly via the ORM's constraint API or override in the raw migration. Read the generated migration before applying it.

---

## Transactions for multi-step writes

Any write that spans more than one table — or more than one row in a way that must stay consistent — must be wrapped in a transaction. Without a transaction, a failure between two writes leaves the DB in a half-updated state that no application code can fully recover from.

**The rule is simple:** if a second write depends on the first, they are one logical operation. One transaction, one commit or one rollback.

```ts
// Drizzle (through the repo's bounded transaction helper)
await withTransaction(async (tx) => {
  const [order] = await tx.insert(orders).values(orderData).returning();
  await tx.insert(orderItems).values(items.map(i => ({ ...i, orderId: order.id })));
  await tx.update(inventory).set({ reserved: sql`reserved + ${qty}` }).where(...);
  // All three writes commit together or none do.
});
```

**Route every transaction through the repo's transaction helper** (`connection-pooling.md` → "The transaction helper"): it bounds the whole transaction with a deadline, destroys a client that failed mid-transaction so it is never reused, and rethrows the original error rather than the rollback failure. A raw `db.transaction(...)` scattered through services gets none of that.

**Scope transactions tightly.** A transaction that holds a write lock while making an HTTP call to a third-party service will block concurrent writers for the duration of that HTTP round-trip, or longer. Do external I/O (email, webhook, payment gateway) *outside* the transaction — after commit — or use the outbox pattern. The application-side ordering of these side effects (outbox, compensating actions, idempotency keys) is the domain of **`craft-backend`** → `side-effects.md`.

**Isolation levels.** Defaults differ by engine — Postgres uses `READ COMMITTED`; MySQL/InnoDB uses `REPEATABLE READ`; SQLite is effectively serializable for writes. Don't assume a default — verify against your dialect.

Postgres `REPEATABLE READ` gives snapshot isolation: it prevents phantom reads (stronger than the SQL standard requires) but still allows write skew — two transactions can each read a consistent snapshot, both pass a check, and both write, producing a result neither would have allowed serially. For operations where that's not acceptable — a read-then-write like "decrement stock if quantity holds" — use `SERIALIZABLE`, which Postgres implements via SSI (serializable snapshot isolation) and gives true serializable correctness, not just phantom prevention. Under contention, retry the whole transaction for `40001` (serialization) or `40P01` (deadlock) at most three times with jittered backoff. Never auto-retry `57014`, a connection error on a non-idempotent call, or an unknown COMMIT outcome; see `connection-pooling.md` → "Health, errors, and retries".

**MySQL/InnoDB note:** `REPEATABLE READ` there uses MVCC for consistent non-locking reads (a snapshot as of transaction start), and additionally applies gap locks on index ranges for locking reads/DML to block concurrent inserts that would otherwise create phantoms in those ranges — a different mechanism from Postgres's snapshot isolation, so don't carry Postgres assumptions across dialects.

**Savepoints.** Postgres (and some other engines) supports `SAVEPOINT` for nested partial rollbacks within a transaction. Useful for retry loops within a transaction body, but complex to reason about — prefer flat transactions and let the outer transaction roll back cleanly.

---

## Staged backfills for large tables

**Dialect note.** The exact mechanics depend on your dialect — the pattern below is Postgres. MySQL and SQLite have different locking and constraint-validation behaviors; verify your dialect's equivalent before following these steps.

Never combine a schema change and a data backfill in a single migration when the affected table is large. A migration that ALTERs a column, backfills millions of rows, and then adds a constraint in one block will:

1. Hold an `ACCESS EXCLUSIVE` lock (Postgres) or equivalent for the entire duration on the target table — blocking reads *and* writes.
2. Fail mid-way with no clean recovery path if the data set is large — you're stuck with a partially-filled column, an aborted migration, and a table in an indeterminate state.

**The staged pattern:**

| Stage | What happens | Why |
| --- | --- | --- |
| **1. Add column nullable, no default** | `ALTER TABLE t ADD COLUMN new_col TEXT` | Schema-only, instant — acquires a brief lock, holds it for microseconds in Postgres with `ADD COLUMN`. No data written. |
| **2. Backfill in batches** | `UPDATE t SET new_col = ... WHERE id IN (SELECT id FROM t WHERE new_col IS NULL ORDER BY id LIMIT 1000)` | Run outside a migration, in a script or a background job. Work in chunks with a keyset so each batch is a small transaction. Postgres does not support `UPDATE ... LIMIT` directly; use a CTE or subquery to select the target rows by primary key. On Postgres, this avoids lock contention; on busy tables, add a sleep between batches or use `pg_sleep`. |
| **3. Add the NOT NULL constraint (or unique/check)** | **Preferred path (all supported Postgres versions):** `ALTER TABLE t ADD CONSTRAINT chk_t_new_col_not_null CHECK (new_col IS NOT NULL) NOT VALID;` in one migration, then `ALTER TABLE t VALIDATE CONSTRAINT chk_t_new_col_not_null;` in the next. `VALIDATE CONSTRAINT` only holds a `SHARE UPDATE EXCLUSIVE` lock (non-blocking for reads and normal DML). Once the CHECK constraint is validated, `ALTER TABLE t ALTER COLUMN new_col SET NOT NULL;` can be run — Postgres recognises the existing valid check and skips the full table scan, taking only a brief `ACCESS EXCLUSIVE` lock. **Direct `SET NOT NULL` without a prior valid CHECK** takes an `ACCESS EXCLUSIVE` lock *and* scans the entire table to verify no nulls — avoid on large tables. The `NOT VALID` + `VALIDATE` split is the safe path (requires Postgres 9.2+). Know your version. | A separate migration run after the backfill is complete. |
| **4. Remove the old column (if replacing one)** | `ALTER TABLE t DROP COLUMN old_col` | A final migration after confidence in the new column. |

**Postgres:** `ADD COLUMN` with a `DEFAULT` that is a constant became non-rewriting in Postgres 11+ — it only updates the catalog, not the rows. That makes Stage 1 fast. But `ADD COLUMN ... DEFAULT <volatile_expression>` (e.g. `clock_timestamp()`, `gen_random_uuid()`) still rewrites the table. Note: `NOW()` / `transaction_timestamp()` is classified as *stable* (not volatile) and does not trigger a rewrite; `clock_timestamp()` is the canonical volatile example because it returns a different value on every call within a transaction. Immutable expressions may be treated as constants by the planner, but when in doubt, verify with `EXPLAIN` or test on a copy of production data. Know which case you're in before deciding the stage is "cheap."

**Postgres:** For very high-traffic tables, use `ALTER TABLE ... ADD CONSTRAINT ... NOT VALID` even for foreign keys — it skips checking existing rows (which would take a long lock) and defers that to `VALIDATE CONSTRAINT`, which only holds a `SHARE UPDATE EXCLUSIVE` lock, which does not block reads or normal DML writes — only concurrent DDL and VACUUM FULL are blocked.

**Each stage is its own migration file.** The backfill script (Stage 2) is not a migration — it's a data operation. Put it in a `scripts/` directory, make it idempotent (`WHERE new_col IS NULL`), and run it separately with monitoring. Never embed a `UPDATE ... WHERE true` over a multi-million-row table inside a migration block.

---

## Backups and restore

Constraints and transactions protect data *while the system is running correctly*. Backups are the
last line of defense when it isn't — a bad migration, a bug that mass-deletes rows, a compromised
credential. This plugin's whole premise is preventing data loss; a repo with perfect constraints and
no tested restore path is still one incident away from losing everything.

- **Confirm managed-provider backups are actually enabled**, not just available. Most managed
  Postgres (RDS, Supabase, Neon, Render) enables automated backups by default, but plans and
  configurations vary — check the dashboard, don't assume. Confirm the retention window (7 days? 30?)
  matches how long you'd realistically need to notice and recover from a problem.
- **Enable PITR (point-in-time recovery)** where the provider offers it. Daily snapshots only let you
  restore to a snapshot boundary; PITR lets you restore to the minute before a bad migration ran or a
  bug started deleting rows — the difference between losing a day of data and losing minutes.
- **A restore that has never been tested is a hope, not a backup.** Actually run a restore at least
  once — into a scratch environment, not production — and confirm the data comes back and the app can
  connect to it. Backups silently fail (storage quota, credential rotation, a schema change the backup
  tool doesn't handle) far more often than anyone expects, and you only find out at restore time if
  you never rehearse it.
- **`pg_dump` on a cron is a floor, not a strategy, for growing data.** It's fine for a small DB early
  on, but it has no PITR granularity, gets slower and heavier as the table grows, and is easy to let
  silently rot (a failing cron job with no alert is worse than no backup, because it creates false
  confidence). Move to the provider's managed backup + PITR path once the data matters enough that
  losing a day of it would hurt.

---

## Quick-reject checklist

Flag with `file:line` and the fix:

| Pattern | Fix |
| --- | --- |
| Uniqueness enforced only with an app-layer `findFirst` check before insert | Add a `UNIQUE` constraint; the app check is a UX complement, not the invariant |
| Nullable column whose value is always expected | Make it `NOT NULL`; the nullable column is a false promise |
| Enum-like column with no `CHECK` constraint | Add a `CHECK (col IN (...))` constraint; verify the dialect actually enforces it |
| FK relationship modeled with only an integer column, no `FOREIGN KEY` | Add the FK declaration with an explicit `ON DELETE` strategy |
| `ON DELETE CASCADE` on a large child table with no mention of lock impact | Document the lock/cascade risk; consider `RESTRICT` + application-level cleanup |
| FK or check constraint with no explicit name (auto-generated opaque name) | Name the constraint: `{type}_{table}_{columns}` convention |
| ORM-generated migration with unnamed/opaque constraint names | Override via the ORM's constraint API or edit the migration SQL before applying |
| Multi-table write with no transaction wrapper | Wrap in a transaction; commit or roll back as a unit |
| HTTP/external I/O call inside a transaction | Move I/O after commit; use outbox or compensating action (`craft-backend` → `side-effects.md`) |
| Migration that adds a column, backfills rows, and adds a NOT NULL in one block | Split into staged migrations: add nullable → backfill in batches → add constraint |
| Backfill `UPDATE ... SET ... WHERE true` inside a migration on a large table | Move to a separate batched script (`scripts/`); make it idempotent; run monitored |
| `ALTER TABLE ADD CONSTRAINT ... NOT VALID` missing a follow-up `VALIDATE CONSTRAINT` | The constraint is not enforced on existing rows — add the validate step in the next migration |
| Soft-delete on parent table with no strategy for live child rows | Document the chosen approach in this file's FK decision comment (or as an inline schema comment) — `schema.md` owns type/naming choices, `integrity.md` owns FK + soft-delete strategy. |
