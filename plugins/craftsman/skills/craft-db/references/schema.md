# Schema Design

Schema decisions are the most expensive thing to undo in a production system — a wrong type or a missing NOT NULL constraint outlives the sprint it was written in. The discipline: **model the domain correctly before writing a migration, choose the narrowest type that exactly represents the value, and let the database enforce what the domain makes mandatory.** A schema that reflects reality needs fewer compensating checks at the application layer and fewer painful backfills six months later.

> **Scope split.** This file owns *what* the schema looks like: column types, nullability, naming conventions, timestamp and soft-delete column shape, enums vs lookup tables, and money/decimal/timestamptz correctness. *How the schema change ships* is `migrations.md`; DB-level constraints (CHECK, UNIQUE, FK definitions, constraint naming) are `integrity.md`; which columns get indexed and in what order is `indexing.md`; how queries consume the schema is `access-patterns.md`.
>
> **See also:** **`craft-backend`** → `validation.md` for app-level validation that complements (but does not replace) DB constraints. The database enforces invariants that hold even when application code, migration scripts, or direct DB access bypass the server — write the constraint first, then add app-level validation for UX.

---

## Contents

- [Discover before designing](#discover-before-designing)
- [Column types](#column-types)
- [Nullability: NOT NULL unless absence is a real domain state](#nullability-not-null-unless-absence-is-a-real-domain-state)
- [Naming conventions](#naming-conventions)
- [Timestamp columns](#timestamp-columns)
- [Soft-delete column shape](#soft-delete-column-shape)
- [Enums vs lookup tables](#enums-vs-lookup-tables)
- [Money, decimals, and floating point](#money-decimals-and-floating-point)
- [Primary keys and surrogate IDs](#primary-keys-and-surrogate-ids)
- [Relationships and foreign keys](#relationships-and-foreign-keys)
- [Multi-schema repos and search_path](#multi-schema-repos-and-search_path)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Discover before designing

Read the existing schema before adding a column or table. What you find should shape every decision in this file:

- **Column naming style** — does the repo use `snake_case` (`created_at`) or `camelCase` (`createdAt`)? Match it exactly. A mixed schema is worse than either convention.
- **Timestamp columns** — what are they called (`created_at`/`updated_at`, `createdAt`/`updatedAt`, `inserted_at`)? What type (`timestamptz`, `timestamp`, `datetime`)? Are they set by the ORM, a DB default, or a trigger?
- **Soft-delete column** — is there one? What is it called (`deleted_at`, `deletedAt`, `archived_at`)? Is it a nullable timestamp, a boolean, or an enum? Match it.
- **Primary key convention** — `id uuid default gen_random_uuid()`, `id serial`, a `cuid()` set by the ORM? Use the same pattern.
- **Tenant column** — how is the tenant ID stored and named (`tenant_id`, `organization_id`, `workspace_id`)? It must appear on every tenant-scoped table with a NOT NULL constraint and a FK.

State what you found. If conventions conflict across the existing schema, flag it and pick the more consistent one.

---

## Column types

Choose the type that most closely matches the domain value. A looser type accepts invalid data the DB will never reject.

**Text**

- `TEXT` (Postgres) / `VARCHAR(n)` where a real length limit exists in the domain (e.g. email addresses, usernames, slugs). Avoid `VARCHAR` without a length only to get a type name that looks bounded — `TEXT` and unbounded `VARCHAR` are identical in Postgres; the distinction only matters when you actually enforce a limit.
- Never store structured data (JSON, CSV, comma-separated IDs) as a plain text column. Use `JSONB` (Postgres), a proper JSON column (MySQL 5.7+), or a normalized table. Querying inside `TEXT` is a maintenance trap.

**Numbers**

- `INTEGER` / `BIGINT` for whole numbers. Use `BIGINT` for anything that could exceed ~2.1 billion rows or grow unbounded (e.g. a global event counter).
- `NUMERIC(precision, scale)` for exact decimals — financial amounts, tax rates, quantities with fixed decimal places. Never `FLOAT` or `DOUBLE PRECISION` for money (see [Money, decimals, and floating point](#money-decimals-and-floating-point)).
- `SMALLINT` is occasionally appropriate for tight, known-range values (e.g. a 0–100 score stored in millions of rows) — discover whether the row count justifies it.

**Booleans**

- Use the native boolean type (`BOOLEAN` in Postgres/MySQL). Avoid `TINYINT(1)` as a boolean in new schemas (legacy MySQL pattern); if the existing schema uses it, match it.
- A boolean with a NOT NULL default is almost always what you want. A nullable boolean (`TRUE` / `FALSE` / `NULL`) models three states and should be intentional — name the column to communicate the third state clearly, or use an enum instead.

**Dates and times**

- `TIMESTAMPTZ` (timestamp with time zone) in Postgres for every timestamp that represents a moment in time. `TIMESTAMP` (without time zone) is a footgun: it stores no offset and its interpretation changes with the session timezone. See [Timestamp columns](#timestamp-columns) for column naming.
- `DATE` when you genuinely need a calendar date with no time component (a birth date, an invoice date). Converting it to a timestamp-with-zone in application code is a smell — use the right type.
- MySQL and SQLite handle timezone-awareness differently. In MySQL, `DATETIME` stores local time with no TZ; `TIMESTAMP` auto-converts to UTC but has a year-2038 range limit. In SQLite, store timestamps as ISO-8601 text or Unix integers (SQLite has no native datetime type). Discover the dialect and match the repo's pattern.

**JSONB / JSON**

- `JSONB` (Postgres) is appropriate for genuinely dynamic, schema-on-read data: plugin configs, user preferences, structured event payloads. It is not a replacement for a normalized table when the data has stable, queryable structure.
- Indexing into JSONB (GIN indexes) is possible but requires measured justification — see `indexing.md`. Ad-hoc querying inside JSONB usually signals the data should have been normalized.

---

## Nullability: NOT NULL unless absence is a real domain state

Default to NOT NULL. Add NULL only when the domain genuinely says "this column may have no value" — not "we're not sure yet" or "it's optional for now."

```sql
-- BAD: delivery_address is nullable on an order that must be shipped somewhere
ALTER TABLE orders ADD COLUMN delivery_address TEXT;

-- GOOD: delivery_address is required for shipped orders; model the constraint
ALTER TABLE orders ADD COLUMN delivery_address TEXT NOT NULL;

-- ALSO GOOD: a draft order genuinely has no address yet — nullable is correct
ALTER TABLE draft_orders ADD COLUMN delivery_address TEXT; -- NULL = not yet provided
```

Common nullable patterns that are actually correct:
- `deleted_at TIMESTAMPTZ` — NULL means not deleted; see [Soft-delete column shape](#soft-delete-column-shape).
- Optional relationship columns (`parent_id`, `superseded_by_id`) where the relationship may not exist.
- Columns added to a large existing table where a backfill is a separate step — the column starts nullable, gets filled, then the constraint is added. This is the safe migration pattern; see `migrations.md`.

Nullable columns require the application to handle NULL explicitly in every query and every output. That cost compounds as the codebase grows. If you're adding NOT NULL to a column, confirm a DB default or a migration backfill covers existing rows before the constraint is applied.

---

## Naming conventions

Match the existing schema. If there is no existing schema, establish the convention in the first table and hold it.

**General rules (apply to whichever case style the repo uses):**
- Table names: plural nouns (`users`, `invoice_line_items`, `workspace_members`).
- Column names: single, descriptive, unambiguous. `name` on a `products` table is fine; `name` on a table where it could mean company or contact name is not.
- Boolean columns: prefix with `is_` or `has_` (`is_active`, `has_verified_email`). Avoids ambiguity when reading queries.
- Foreign key columns: `{referenced_table_singular}_{pk_column}` (e.g. `user_id`, `workspace_id`, `invoice_id`). Don't abbreviate or rename unless the relationship is self-referential (use a descriptive prefix: `parent_id`, `created_by_user_id`).
- Join/pivot tables: name after both entities (`workspace_members`, `product_tags`), ordered to match FK traversal direction.
- Avoid generic column names that appear in many tables without a qualifier (`status`, `type`, `data`). Qualify them: `payment_status`, `account_type`, `event_payload`.

**PII columns**

Know which columns hold PII — name, email, phone, IP address, physical address, government ID, anything that identifies a person — as you name them. This is a discovery habit, not a mandate to build a classification system: at MVP stage, a `-- PII` comment on the column or a naming convention the team agrees on is enough.

- Keep PII out of primary keys and out of anything that ends up in a URL — see [Primary keys and surrogate IDs](#primary-keys-and-surrogate-ids) on not leaking data via public identifiers.
- Keep PII out of columns and query results that feed logs — don't `SELECT *` or log a full row from a table that carries PII.
- For the deletion/export side of PII (cascades, data-subject requests, PII showing up in log pipelines), see `craft-security`'s `references/data-rights.md` — this section is only the schema-modeling awareness half.

---

## Timestamp columns

Every table should carry audit timestamps. Use the pattern the repo already establishes; if none exists, this is the standard:

```sql
-- Postgres (timestamptz is the correct type for moments in time)
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

- **`created_at`** — set once at insert, never updated. Enforce this with a DB default or an ORM `insertedAt` convention; never let application code omit it.
- **`updated_at`** — set at insert and refreshed on every update. Options: a DB trigger, an ORM `updatedAt` hook (e.g. Drizzle's `.$onUpdate()` for Postgres, Prisma's `@updatedAt` only for other engines), or explicit application-layer writes. Discover which approach the repo uses and match it — mixing triggers and ORM hooks on the same table creates double-updates.
- Do not use `created_at`/`updated_at` as a soft-delete flag. They are audit columns, not lifecycle columns.

---

## Soft-delete column shape

When soft-delete is used, the pattern that carries the most information:

```sql
deleted_at  TIMESTAMPTZ  -- NULL = active; non-NULL = soft-deleted, value is when it was deleted
```

- A nullable timestamp over a boolean: the timestamp tells you *when* it was deleted at no extra cost. A `is_deleted BOOLEAN DEFAULT FALSE` only tells you that it was.
- NOT NULL with a sentinel date (`'9999-12-31'`) is a common alternative for databases that treat NULLs as *equal* in unique constraints — SQL Server (and older DB2) — where a nullable-timestamp approach would incorrectly reject a second 'active' row. Postgres, MySQL, and SQLite all allow multiple NULLs in a unique constraint, so the partial-index workaround (`WHERE deleted_at IS NULL`) handles this correctly there without a sentinel. Use the sentinel only if the existing schema already does, or the target is SQL Server/DB2.
- Match the existing column name exactly. Common names: `deleted_at`, `archived_at`, `deactivated_at`. The name should reflect the domain concept (archiving is not deleting).
- Every query that reads from a soft-deleted table must filter on this column. That is a shared helper responsibility, not a per-query concern — see `access-patterns.md`.

---

## Enums vs lookup tables

Choose based on whether the set of values is closed and release-coupled:

**Use a DB enum when:**
- The set of values is stable and small (payment statuses: `pending`, `paid`, `refunded`, `failed`).
- Every new valid value requires a code change anyway — a migration to add the enum value is the right gate.
- Postgres `ENUM` type with Drizzle's `pgEnum`, or MySQL `ENUM` with the existing non-Postgres ORM mapping.

**Use a lookup/reference table when:**
- End users or administrators can add new values at runtime without a deployment.
- The set is large (countries, currencies, product categories).
- The values carry additional attributes (a `currencies` table with `code`, `symbol`, `decimal_places`).

**Common mistake:** using a `TEXT` column with no constraint to hold what is logically an enum. Any misspelling or ad-hoc value is accepted silently. If the set is closed, enforce it — either a DB enum or a FK to a lookup table with a UNIQUE constraint on the code column.

```sql
-- BAD: open text, no enforcement
ALTER TABLE orders ADD COLUMN status TEXT NOT NULL;

-- GOOD: DB enum (Postgres)
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'shipped', 'cancelled');
ALTER TABLE orders ADD COLUMN status order_status NOT NULL DEFAULT 'pending';

-- ALSO GOOD: FK to a lookup table (dialect-agnostic)
ALTER TABLE orders ADD COLUMN status_code VARCHAR(32) NOT NULL REFERENCES order_statuses(code);
```

Adding a new enum value in Postgres requires `ALTER TYPE ... ADD VALUE`. The behavior depends on the Postgres version:

- **Postgres < 12:** `ALTER TYPE ... ADD VALUE` cannot run inside a transaction block at all — it will error immediately. Run it outside a `BEGIN...COMMIT` block, or ensure your migration runner does not wrap it in a transaction.
- **Postgres 12+:** The statement can run inside a transaction block. However, the new value is **not visible to any concurrent transaction that started before the `ALTER TYPE` committed** — only transactions that begin after the commit can use the new value. This means you cannot add the enum value and then use it in DML in the same transaction; the DML will fail with "invalid input value for enum".

**Recommended practice regardless of version:** run `ALTER TYPE ... ADD VALUE` as a standalone, isolated migration step — its own file, deployed before the migration that uses the new value. Do not combine it with DML referencing the new value in the same migration file. See `migrations.md` for the naming and sequencing conventions.

---

## Money, decimals, and floating point

**Never store money as `FLOAT` or `DOUBLE PRECISION`.** Floating-point types cannot represent most decimal fractions exactly; rounding errors accumulate across sums and compound over time. This is not theoretical — it produces wrong totals.

```sql
-- BAD: floating-point money
amount FLOAT NOT NULL,           -- 0.1 + 0.2 ≠ 0.3 in IEEE 754

-- GOOD: exact decimal (Postgres, MySQL)
amount NUMERIC(19, 4) NOT NULL,  -- 15 integer digits, 4 decimal places; adjust scale to domain

-- ALSO GOOD: store as integer minor units (cents, pence, pips)
amount_cents BIGINT NOT NULL,    -- $12.34 → 1234; arithmetic stays exact in integers
```

Decide on one approach per project:
- `NUMERIC(precision, scale)` — exact arithmetic in the DB; use Drizzle's `numeric` mapping for Postgres and a decimal library in application arithmetic (e.g. `decimal.js`, Python's `Decimal`) — never `Number` in JavaScript.
- Integer minor units — simpler arithmetic, no fractional parts stored, easier to add in application code using plain integers. Requires knowing the currency's scale upfront (EUR: 2 decimal places; KWD: 3; JPY: 0).

Document the approach in a comment on the column or in the schema file. A future developer touching that column should not have to guess.

---

## Primary keys and surrogate IDs

Match the existing convention. If establishing one:

- **UUID v4 / v7** — globally unique, non-sequential (v4) or monotone (v7). Preferred for distributed systems and multi-tenant ID exposure. In Postgres: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (v4). UUID v4 is fully random and safe to include in public URLs without leaking row counts or creation time. UUID v7's time-ordered prefix reveals the approximate creation time and ordering of records — for public-facing URLs where creation time is sensitive, prefer UUID v4. Native `uuidv7()` shipped in PostgreSQL 18; on earlier versions use the `pg_uuidv7` extension (`uuid_generate_v7()`) or generate v7 UUIDs in application code via the `uuidv7` npm package — verify the target repo's Postgres version before assuming the native function is available.
- **Serial / auto-increment** — simpler, sequential. Leaks row counts if IDs appear in URLs. `BIGSERIAL` over `SERIAL` for tables expected to exceed 2.1 billion rows. MySQL `AUTO_INCREMENT`, SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`.
- **CUID2 / NanoID set by the ORM** — application-generated, URL-safe, collision-resistant. Stored as `VARCHAR(n)` or `TEXT`. Valid if the repo already uses them; discover the generator library (e.g. `@paralleldrive/cuid2`) and its generated length before sizing the column.

Never expose an auto-increment integer primary key in a public-facing API when row count secrecy matters. Use the surrogate ID for URLs; keep the sequential PK internal if needed for ordering.

---

## Relationships and foreign keys

Express every relationship as a real foreign key constraint. An ID column without a FK is documentation the DB cannot enforce.

```sql
-- BAD: stores a user id with no enforcement
workspace_id TEXT NOT NULL,

-- GOOD: enforced relationship
workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
```

Choose the `ON DELETE` strategy deliberately — see `integrity.md` for the full decision guide, including the distinction between `RESTRICT` (check fires before row-level triggers, never deferrable) and `NO ACTION` (check fires after row-level triggers, and can be deferred to end of transaction only when the FK is declared `DEFERRABLE`), soft-delete/CASCADE lifecycle considerations, and FK performance notes.

---

## Multi-schema repos and search_path

In Postgres projects that define multiple schemas (via Drizzle's `pgSchema` or raw `CREATE SCHEMA`), the `search_path` setting controls which schema is searched for unqualified table names. When the application role has no `search_path` that includes the target schema, **any raw SQL literal must use fully-qualified `<schema>.<table>` names.**

Discover this before writing migrations or raw queries:
- Does `drizzle.config.ts` reference `pgSchema` or schema prefixes?
- What `search_path` does the database role set? Do not rely on a connection startup parameter behind a transaction pooler.
- Are there existing raw migrations that use `<schema>.` prefixes?

If a schema prefix is in use, every `sql` template literal, raw migration statement, and `pg` client query that references those tables must qualify the name. Skipping it either errors (if `search_path` is absent) or silently hits the wrong table in `public`.

```sql
-- WRONG (in a repo with pipeline_v2 schema, no search_path set)
INSERT INTO regeneration_requests (id, status) VALUES ($1, 'pending');

-- RIGHT
INSERT INTO pipeline_v2.regeneration_requests (id, status) VALUES ($1, 'pending');
```

State whether the repo uses named schemas before writing any raw SQL. This belongs in the discovery section of the audit (`craft-audit` → `discovery.md`).

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| `FLOAT` / `DOUBLE` column storing money or exact decimals | Change to `NUMERIC(p,s)` or integer minor units; document the approach |
| `TIMESTAMP` (without time zone) for a moment-in-time value | Use `TIMESTAMPTZ` in Postgres; confirm dialect equivalent elsewhere |
| Nullable column where absence has no domain meaning | Add NOT NULL; provide a DB default or migration backfill |
| `TEXT` column for a closed set of values with no constraint | Add a DB enum or FK to a lookup table |
| ID column referencing another table with no FK constraint | Add `REFERENCES table(id)` with an explicit `ON DELETE` behavior |
| Column naming style differs from the rest of the schema | Match the existing convention (snake_case or camelCase) |
| Tenant id column missing from a tenant-scoped table | Add `{tenant_col} NOT NULL REFERENCES tenants(id)` |
| `updated_at` updated by both a DB trigger and ORM hook | Remove one; document which layer owns it |
| JSON/text column storing comma-separated or structured relational data | Normalize into a child table or use a proper JSON column type |
| Soft-delete modeled as `is_deleted BOOLEAN` | Prefer `deleted_at TIMESTAMPTZ` (carries when, not just whether) |
| Auto-increment integer PK exposed in a public URL | Use a UUID/CUID surrogate for the public identifier |
| Raw SQL literal uses bare table name in a multi-schema repo | Qualify as `<schema>.<table>`; confirm search_path or set it explicitly |
| Boolean column with no `is_` / `has_` prefix | Rename for clarity (`is_active`, `has_verified_email`) |
| `VARCHAR` without a length limit where a limit exists in the domain | Add the length constraint; or use `TEXT` if no real limit exists |
