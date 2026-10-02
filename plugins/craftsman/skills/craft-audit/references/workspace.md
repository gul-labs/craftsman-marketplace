# The `.craftsman/` Workspace — durable audit state

The audit needs memory. A production-readiness pass is too big for one session and gets re-run as the
project evolves, so its state lives on disk in a `.craftsman/` folder at the **root of the project
being audited** (never in this plugin). This file is the spec: the layout, the file templates, the
stamping rules, and how re-runs behave.

> **Pairs with:** `discovery.md` writes `discovery.md` + `applicability.md` here;
> `prioritization.md` defines the finding voice and tiers the tracker quotes. Read both alongside
> this.
>
> **Worked example:** a complete, illustrative `.craftsman/` tree — discovery → applicability →
> per-domain plans/findings → master tracker with grades, climb sequence, and rollup — lives in the
> plugin at `plugins/craftsman/examples/craftsman-output/`. Read it to see how these templates compose into a
> coherent whole (it's a reference artifact, not live state).

---

## Contents

- [Where it lives and gitignore](#where-it-lives-and-gitignore)
- [Concurrency marker](#concurrency-marker)
- [Layout](#layout)
- [Stamping — every artifact is dated](#stamping--every-artifact-is-dated)
- [Stable finding IDs and status](#stable-finding-ids-and-status)
- [Re-run behavior — diff, don't overwrite](#re-run-behavior--diff-dont-overwrite)
- [File templates](#file-templates)

---

## Where it lives and gitignore

Create `.craftsman/` at the target project root as the **first** step of any audit, and add it to
that project's `.gitignore` (append the line if a `.gitignore` exists; create one if not). It's
working state — per-developer, regenerable, not source — so it should not be committed. Confirm the
ignore took effect (`git check-ignore .craftsman` or equivalent) before writing findings into it.

> If the user explicitly wants audit findings tracked in version control (some teams turn them into
> tickets/PR artifacts), that's their call — surface the option, but default to gitignored.

---

## Concurrency marker

At the start of a run, write a marker file `.craftsman/.run-in-progress` containing the date and a
brief session label. If one already exists when starting, warn the user and ask before proceeding —
a crashed or interrupted run leaves a stale marker behind, so check the marker's date against today
to tell a stale leftover from a run that's genuinely still active. Approving past an existing marker
is **stale-run recovery** (overwrite only when the prior run is abandoned), not permission for
concurrent writers. **`craft-fix` also respects this marker** — it refuses to mutate findings or
the tracker while the marker is active (user override only after acknowledging race risk). Delete
`.run-in-progress` at the end of step 8 (successful completion).

---

## Layout

```
.craftsman/
  README.md            # what this folder is, how to read it, when it was generated
  discovery.md         # project shape, stack, frameworks — with file citations (see references/discovery.md)
  applicability.md     # the 10 domains → applies / partial / N-A, capability evidence, and a count
  dedup-map.md         # required synthesis evidence: exact groups, semantic review, distinct totals
  master-tracker.md    # which audits exist, status, last-run stamp, the ordered climb sequence
  audits/
    <scope>/             # workspace-relative path: `root` (single app), `apps/web`, or `packages/ui`
      ux/
        plan.md          # the tailored audit plan for this surface (also surfaced as a todo list)
        findings.md      # findings with stable IDs, fingerprints, severity, status, file:line
        remediation-reviews.md # append-only review evidence for attempted fixes; created on first review
      backend/
        plan.md
        findings.md
      ...                # one subdir per APPLICABLE domain for this scope
```

The path is **always** `audits/<scope>/<domain>/`. A single-app repo has one scope, `root`
(`audits/root/ux/`). A multi-app monorepo gets one scope per app (`apps/*`) and per shared package
that is an independently audited surface (`packages/*` when it has its own consumers/API surface
worth separating — e.g. `audits/apps/web/ux/`, `audits/packages/ui/ux/`). A library monorepo
(publishable packages, little/no apps) prefers a single `root` scope for workspace-wide
release/CI/supply-chain findings; open per-package scopes only when packages have meaningfully
different surfaces (see `discovery.md` → "Scoping a library monorepo"). Never blend two scopes'
findings under one directory when multiple scopes exist — the per-scope split keeps records
unambiguous via the raw scope path and fingerprint tuple; the display ID labels are reference-only
and may collide across scopes.

---

## Stamping — every artifact is dated

Discovery rots the moment the project changes. Every generated file carries a header so a reader (or
the next run) knows whether to trust it:

```
> Generated: 2026-06-19 · commit a1bec8f · craft-audit
```

Use the **actual** current date and the project's current `git rev-parse --short HEAD`. If a file's
stamp is older than the project's latest commit by a meaningful margin, treat it as stale and
regenerate rather than trusting it. (Stamp with real values discovered at run time — don't copy the
example date above.)

### No-git projects

If the project is **not** a git repo, there's no commit to stamp or diff against. Stamp
`commit: none (no git)` plus the date instead of a real sha, e.g. `> Generated: 2026-06-19 · commit
none (no git) · craft-audit`. Skip the `git check-ignore` verification step in "Where it lives
and gitignore" — instead verify the ignore textually: read the `.gitignore` (or equivalent) and
confirm the `.craftsman` entry is present. Note in `discovery.md` that re-run staleness will be
**date-based only** here — there's no commit history to diff changed files against, so scope-aware
staleness (`rerun.md` → "Part 1 — Staleness detection") can't narrow what changed. Recommend the user
run `git init`: frame it as a prerequisite for cheap re-runs, and arguably for shipping at all.

---

## Stable finding IDs and status

Each finding has two parts: an **authoritative key** (used for all matching and uniqueness) and a
**human-readable ID label** (used for reference in prose and tables).

**The authoritative key is the fingerprint — never the ID string.** Scope identity is the explicit
`scope` field (the workspace-relative path, slashes kept: `root`, `apps/web`, `apps/web-admin`,
`packages/ui`). Uniqueness and rerun-matching key on the full fingerprint tuple
**(`scope` path, `domain`, `class`, `resource`)** — see the fingerprint section below. **Never reverse-parse
the ID string back into a path** to recover scope: that's exactly what breaks on hyphenated paths
(`apps/web-admin` and `apps/web/admin` would both look like `apps-web-admin`). The raw `scope` path
in the fingerprint and the Scope column is the source of truth; the ID is just a label.

**The ID label** is `<scopeLabel>-<DOMAIN>-<NNN>`, where `scopeLabel = scope.replaceAll('/', '-')`
and `<DOMAIN>` is the fixed short code for the craft domain (use these exact codes so labels don't
get invented inconsistently across runs):

| Domain | Code | Domain | Code |
| ------ | ---- | ------ | ---- |
| ux | `UX` | security | `SEC` |
| frontend | `FE` | infra | `INFRA` |
| backend | `BE` | observability | `OBS` |
| db | `DB` | testing | `TEST` |
| lint | `LINT` | ai | `AI` |

Assign `<NNN>` sequentially within a (scope, domain); **never reuse** a number — a fixed finding
keeps its label with status `fixed`:

- **Single-app project:** scope `root` — dir `audits/root/`, label `root-SEC-001`, `root-UX-014`.
- **Monorepo app:** scope `apps/web` — dir `audits/apps/web/`, label `apps-web-SEC-001`.
- **Hyphenated path:** scope `apps/web-admin` — dir `audits/apps/web-admin/`, label `apps-web-admin-SEC-001`.
- **Shared package:** scope `packages/ui` — dir `audits/packages/ui/`, label `packages-ui-UX-003`.

Because the label is derived one-way (path → label) and **never** parsed back, two distinct paths
that happen to share a label (`apps/web-admin` vs a hypothetical `apps/web/admin`) are still
unambiguous: they're told apart by the authoritative `scope` path in the Scope column and the
fingerprint, not by the label. Always show the Scope column next to the label so a reader never has to
guess. The label exists for human reference; it carries no contract on its own.

**Severity and status are two separate fields — never fold one into the other.**

- **Severity** (set once, from `prioritization.md`): `🔴` / `🟡` / `🟢`.
- **Status** (lifecycle, changes across runs): `open` · `fixed` · `regressed` · `wontfix (reason)` ·
  `fixed (merged into <ID>)`.
  The last form is a documented merge annotation under the `fixed` lifecycle family (see re-run
  behavior) — use it when two findings collapse into one kept ID.

Everywhere a finding is recorded — heading, tracker row, findings entry — severity is the emoji and
status is the lifecycle word; don't emit a combined `🔴 open` token.

**`findings.md` is append-only for humans.** Resolve a finding via status `wontfix (reason)`, never
by deleting its entry — deletion destroys the ID record and corrupts history. The re-run process
cross-checks tracker rows against the findings files and **reports** discrepancies; it never silently
repairs them. `next-NNN` (the next sequential ID number for a scope/domain) is derived from
`max(IDs in findings files ∪ tracker) + 1` — compute the next ID from the actual max across both
sources, not just by incrementing the last-seen number.

Each finding also carries a **`last-checked: <date · commit>`** line — the run that last actually
re-verified its resource (not merely the run that wrote the file). On re-runs this is what lets the
diff tell `fixed` (the pass ran and the defect is gone) apart from "not re-checked" (the pass never
ran), so a skipped pass can't masquerade as a fix. See `rerun.md` → "not seen ≠ fixed". First run:
`last-checked` equals the `Generated` stamp.

**Confidence (optional field).** A finding may carry a **`Confidence: verified | inferred |
unverified-from-repo`** line, appended after `**Last-checked:**` (the canonical optional-label order
is: `**Last-checked:**`, then optional `**Confidence:**`, optional `**Deployment-state:**`, then
optional `**Fix-attempt:**`). Absent
means `verified` — every existing `findings.md` stays valid unchanged. The three values:

- `verified` — directly observed at a cited `file:line`.
- `inferred` — reasoned from adjacent evidence, not directly observed.
- `unverified-from-repo` — the claim depends on something outside the repo: dashboard config, branch
  protection, WAF rules, deployment/env settings, secret values. A large class of production-critical
  configuration is invisible from the repo itself, and a finding like "nothing in the repo establishes
  preview/production DB separation" should not read with the same apparent certainty as a
  directly-verified vulnerability.

**Hard rule for `unverified-from-repo`:** the finding must describe the **repo gap actually observed**
plus the **human check needed** — it must **never** assert the external condition is true or false.
Absence of evidence is not evidence of absence.

**Hard rule for secret values.** A finding about a credential — a key hardcoded in source, a committed
`.env`, a token behind a public prefix — cites the `file:line` and the **variable name**, never the
value. Do not paste the value into `findings.md`, the tracker, or any workspace file, even partially
or masked; the workspace is gitignored but it is still a plain file on disk. Do not open `.env` or
`.env.local` to confirm a value exists — the committed/ignored status and the schema are the evidence.

`Confidence` is deliberately **not** folded into the `status` enum (`open|fixed|regressed|wontfix
(reason)|fixed (merged into <ID>)`): `status` is the lifecycle field the re-run fingerprint diff
matches on, and a finding that is inherently unverifiable from the repo would never resolve to `fixed`
on a normal re-run — conflating the two fields would corrupt the "not seen ≠ fixed" guarantee.

An `unverified-from-repo` finding does not gate the readiness grade the way a verified 🔴 does — see
"Readiness (derived — never hand-set)" below.

**Deployment-state (optional field).** Record this separately from finding lifecycle whenever a
finding's resolution depends on production activation: `active`, `pending (reason)`,
`unverified-from-repo`, or `not-applicable`. `pending` covers default-off flags, unapplied
migrations, staged rollouts, and any code-only change not yet active; it keeps the finding `open`.
`unverified-from-repo` means source review cannot prove the production state and also keeps the
finding `open`. Only `active` (with runtime evidence) or `not-applicable` permits a deployment-
dependent finding to become `fixed`. This field follows optional `Confidence` and precedes every
`Fix-attempt` line.

**Fix-attempt (optional field).** A finding may carry one or more
**`Fix-attempt: <YYYY-MM-DD> · <identity> · <one-line what changed>`** lines, appended by the
`craft-fix` companion (or any session that implements a fix) after the code change + regression
test land. `<identity>` is the short SHA of the commit that contains the fix when one exists, or the
literal token `working-tree` when the fix is uncommitted (never a pre-change HEAD SHA). Prefer
committing first when the user allows, so the line can carry a real SHA. A finding may accumulate
multiple Fix-attempt lines over time — never delete them, they're the repair history. A Fix-attempt is a **claim, not a verification**: status stays `open`, `last-checked` is
**not** touched by a fixer (it means "last re-verified by an audit pass," not "last edited"), and
readiness grades / tracker counts treat a finding with Fix-attempts exactly like any other `open`
finding. The re-run's fingerprint diff plus its remediation-diff review are the only verifiers —
that's what keeps the tracker honest. The review is recorded separately in the same domain's
`remediation-reviews.md`; it is not an optional field on a finding and does not alter the canonical
finding grammar.

**Verification deadline (derived, not a new lifecycle field).** Every open Fix-attempt carries a
targeted-verification due date derived from its existing date and severity: 🔴 within **7 calendar
days**, 🟡 within **14**, 🟢 before the next release or within **30**, whichever comes first. The
tracker shows `verification due <date>` after the attempt and `verification overdue <date>` after the
deadline. An overdue 🔴 attempt must be presented for targeted verification before `craft-fix` begins
another pick-set, unless the user explicitly defers it; record the defer reason in the tracker. An
overdue 🟡/🟢 attempt remains at the top of the next verification queue. None of this changes status:
only `rerun.md`’s targeted verification can close the finding.
On a re-run that re-observes the fingerprint (the fix didn't hold), the audit appends ` · did not
hold (<YYYY-MM-DD>)` to the end of **the most recent Fix-attempt line that lacks a suffix** — i.e.
the most recent one that hasn't already been marked with a "did not hold" or other suffix. (A finding
can accumulate multiple Fix-attempt lines over time; without this rule, "that Fix-attempt line" is
ambiguous.) The line itself is never deleted, and no other note field exists for this purpose.

**The ID is a label; the fingerprint is the identity.** A sequential ID alone can't survive a rerun —
line numbers move, files get renamed, duplicates get merged. So each finding also carries a
**fingerprint**: a stable, content-derived key that says *what the problem is*, independent of where
it currently sits. Compose it from:

`scope` (the workspace-relative path, exactly as used in `audits/<scope>/` — `root`, `apps/web`,
`packages/ui`; **never** a bare app slug like `web`) · `domain` · `class` (the kind of defect, e.g.
`missing-authz`, `no-empty-state`, `unparameterized-sql`) · `resource` (the canonical thing it's
about — a route, table, component, or env var — **not** a line number).

**`resource` preference, not a rule:** when the defect is about a file, prefer the repo-relative path
(`src/app/api/webhooks/square/route.ts`) as `resource` over a hand-written slug. Independent parallel
subagents coin different vocabulary for the same defect — the same bug can arrive as
`class=webhook-signature-check-dead-code resource=square-webhook-signature-verification` from one
domain pass and `class=webhook-signature-not-verified resource=POST /api/webhooks/square` from
another, with zero string overlap, which silently defeats the `prioritization.md` §2b cross-domain
rollup (it groups on an exact `(scope, class, resource)` match). A shared file path is the value
independent passes actually agree on. This is a preference, not a mandate — `resource` stays "the
canonical thing it's about," so a DB table, an env var, or a component name remains correct where no
single file is the subject; do not force a file path onto a finding about a table or env var. It
composes with, and does not relax, the cross-run stability rule below: once a `resource` string is
chosen for a finding, later runs must reuse it exactly, whether it's a path or a slug.

The `scope` here is the *same* path the directory uses (`audits/<scope>/`) and that the ID label is
derived from one-way (`scopeLabel = scope.replaceAll('/', '-')`). The fingerprint always carries the
**slash path**, never the label — the label is display-only and is never parsed back.

Two findings with the same fingerprint tuple are the same finding, even if the file moved or its line
shifted. Matching on the fingerprint — `(scope, domain, class, resource)` — not on the line or the ID
label, is what makes "fixed / regressed / new" reproducible and collision-proof.

**`class` and `resource` strings must be stable across runs**, or the match silently fails and a
fixed finding resurfaces as "new". Since a rerun reads the prior `findings.md` first (next section),
**reuse the prior run's exact `class`/`resource` strings** when it's the same defect — don't rephrase
`missing-authz` to `missing-authorization`. Treat the first run's vocabulary as canonical.

---

## Re-run behavior — diff, don't overwrite

> **The hardened, exercisable procedure lives in `rerun.md`** — staleness detection (what to
> regenerate vs keep), the finding-by-finding diff, the "not seen ≠ fixed" rule, and the delta report.
> This section is the identity model it keys on; load `rerun.md` to actually execute a re-run.

On a second audit of the same project, match by **fingerprint**, not by ID or line number:

1. Read the existing `findings.md` first and build the set of prior fingerprints (with their IDs).
2. Run the audit fresh. For each new observation, compute its fingerprint and look it up:
   - **fingerprint matches an `open` prior** → same finding, keep its ID, leave status `open`.
   - **fingerprint matches a `fixed` prior, but the problem is back** → keep its ID, set `regressed`.
   - **no fingerprint match** → genuinely new; assign the next sequential ID for that scope/domain.
3. For each prior `open` finding whose fingerprint is **not** re-observed → set status `fixed`
   **only if the domain pass for its scope actually ran this re-run and specifically re-checked that
   resource, and any applicable remediation-diff review is cleared** (don't delete either way — the
   history is the value). If the domain pass **did not run** this re-run — skipped for budget, deemed
   unchanged, or failed — or the required review is incomplete, the finding stays `open` with its prior
   `last-checked` stamp untouched. It is *stale-unknown* or *remediation-review pending*, not fixed,
   and it is never silently dropped from `findings.md`. `rerun.md` is authoritative on the full
   classification table, targeted verification, remediation review, and Fix-attempt handling — load it
   before executing a re-run rather than relying on this summary.
4. **Merge/split/rename:** if two prior findings collapse into one (e.g. "no validation anywhere"),
   keep the lowest ID, mark the other `fixed (merged into <ID>)`. If one splits into two, the
   original keeps its ID and the new aspect gets a fresh ID. A renamed file changes no fingerprint, so
   no status changes — that's the point.
5. Re-stamp the file with the new date/commit. The master tracker shows the delta ("3 fixed, 1
   regressed, 2 new since last run").

Matching on line numbers or re-numbering from scratch each run is what loses the fixed/regressed
signal — half the point of tracking. The fingerprint is the anchor.

---

## File templates

These are the **complete** set of durable-state templates. Every file the audit loop writes has one
here — if a step says "write `.craftsman/<x>`", its template is below.

### `discovery.md`

```markdown
# Discovery

> Generated: <date> · commit <sha> · craft-audit

## Shape
<one of: marketing/static · single full-stack app · SPA + separate API · monorepo (multi-app) ·
library monorepo · library/package> — <evidence: file path(s) that prove it>

## Maturity (sets the audit register — see references/discovery.md)
<pre-Tier-1 · partially Tier-1 · post-Tier-1> — <evidence: tests + CI + validated env + auth AND
per-resource authz, each with a file citation; "auth installed ≠ authz enforced" — verify both>

## Toolchain
- Package manager: <pnpm/npm/yarn/bun> (evidence: <lockfile>)
- Frameworks: <…> (evidence: <config/dep>)
- Build/deploy: <…> (evidence: <Dockerfile/CI/host config>)

## Existing stack (meet the project where it is)
| Surface | Chosen | Evidence (file) |
| ------- | ------ | --------------- |
| Auth | <Clerk/Auth.js/none> | <file> |
| DB + access | <Postgres+Drizzle/none> | <file> |
| Hosting/runtime | <Vercel/Fly/…> | <file> |
| Observability | <Sentry/none> | <file> |
| Validation | <Zod/none> | <file> |

## Apps (monorepo only)
- <app-slug> — <path> — <shape> — <one-line purpose>
  (for library monorepo, list packages instead/as well)

## Unknowns
- <anything that couldn't be determined from the repo — itself a finding>
```

### `applicability.md`

```markdown
# Applicability

> Generated: <date> · commit <sha> · craft-audit
> <N> of 10 domains apply.

| Domain | Verdict | Capability evidence | Compatible / skipped checklist sections | Reason |
| ------ | ------- | ------------------- | -------------------------------------- | ------ |
| ux | applies / partial / N-A | <browser-dom-css / native-ui-swiftui / none> | <sections run; incompatible sections + N-A reason> | <one line> |
| frontend | … | … |
| backend | … | … |
| db | … | … |
| security | … | … |
| infra | … | … |
| observability | … | … |
| testing | … | … |
| lint | … | … |
| ai | … | … |

<In a monorepo, repeat the table per app — applicability differs between a marketing site and a
dashboard in the same repo. `partial` without compatible and skipped sections is invalid.>
```

### `README.md`

This file is the first thing a builder sees when they return to a started audit. It must orient them
without requiring them to read any other file first. The template:

```markdown
# .craftsman — production-readiness audit workspace

> Generated: <date> · commit <sha> · craft-audit

This directory contains a craftsman-marketplace audit for [project name / repo]. It is gitignored —
working state, not source. See `master-tracker.md` for current status and the prioritized fix list,
and `audits/<scope>/<domain>/findings.md` for per-domain findings.

## How to read this folder

- **`master-tracker.md`** — start here. Shows audit status, the ordered climb sequence (do-these-first
  findings), readiness grades per surface, and the delta report from the last re-run.
- **`discovery.md`** — what this project is: shape, stack, maturity read, with file citations.
- **`applicability.md`** — which of the 10 craft domains apply here, and why (N of 10 apply).
- **`audits/<scope>/<domain>/plan.md`** — the tailored audit plan for each applicable surface.
- **`audits/<scope>/<domain>/findings.md`** — findings with stable IDs, severity, status, and fix links.
- **`audits/<scope>/<domain>/remediation-reviews.md`** — append-only evidence that a fix attempt's
  actual diff was reviewed before a finding was closed; absent until the first review.

`<scope>` is `root` for a single-app repo, or the workspace-relative path in a monorepo (e.g.
`apps/web`, `packages/ui`).

Grades and statuses are as of the `Generated` commit shown in `master-tracker.md` — if the project
has moved since, run `git log <sha>..HEAD --oneline` (or, if the workspace is stamped `commit: none
(no git)`, compare the Generated date to your latest changes) to check, and treat the grades/statuses
as historical and re-run the audit if so.

## Resuming a partial audit

If the audit ran only some domains, check `master-tracker.md` → "Audit status" for which entries
show ❔ Unaudited. Re-invoke craft-audit with the `.craftsman/` in place — it will pick up from
the last completed step, diffing rather than rewriting. See `references/rerun.md` in the plugin for
the full re-run protocol.
```

> **All templates below carry the raw `scope` path as the authoritative key, plus a display-only ID
> label `<scopeLabel>-<DOMAIN>-<NNN>`** (`scopeLabel = scope.replaceAll('/', '-')`; `root` for a
> single app, the workspace path for monorepos). The label is **never validated, parsed, or matched**
> for identity — it can collide across paths and that's fine. Consistency and rerun-matching are
> checked **only** by the raw `Scope` column and the `Fingerprint: scope=… · domain=… · class=… ·
> resource=…` tuple. Treat the label as a human reference, nothing more.

### `dedup-map.md`

Write this during synthesis, before `master-tracker.md`. It is the evidence that exact matching and
semantic reconciliation both happened; it is not optional when there are findings.

```markdown
# Deduplication Map

> Generated: <date> · commit <sha> · craft-audit
> Raw eligible findings: <N> · Exact-key groups: <N> · Semantic candidates reviewed: <N> · Distinct eligible defects: <N>

## Exact-key groups
| Evidence key (scope · class · resource) | IDs | Decision |
| --- | --- | --- |
| <key> | <IDs> | roll up under <canonical ID> / keep separate (<reason>) |

## Semantic reconciliation
Review candidates based on overlapping cited file:line, route, table, component, environment key,
or other concrete resource—not only matching fingerprint text.

| Candidate IDs | Evidence compared | Decision | Canonical ID / reason |
| --- | --- | --- | --- |
| <ID, ID> | <same route/table/file:line/etc.> | roll up / keep separate | <canonical ID or concrete reason> |

## Attestation
<Semantic reconciliation completed. If no candidates exist, state the search basis and `0 candidates after review` here.>
```

`Raw eligible findings` counts open/regressed findings except `Confidence: unverified-from-repo`.
`Distinct eligible defects` counts every rollup group once. The tracker’s headline and grade-distance
counts use the distinct eligible total; the domain files retain every original finding and ID.

### `master-tracker.md`

`master-tracker.md` has a **three-stage lifecycle** — it is not written once at the end:

1. **Skeleton (created early, right after applicability — SKILL.md step 3/4).** As soon as
   `applicability.md` exists, write the tracker header and the "Audit status" table with one row per
   applicable (scope, domain), every row ❔ Unaudited, every grade `—`. This is the todo list the rest
   of the run fills in.
2. **Incremental updates (as each domain pass completes).** After every domain pass, update that
   row only: findings count, Last run date, and the mechanical grade for that (scope, domain) — derived
   straight from its `findings.md`. Rows for domains not yet run are left untouched at ❔ Unaudited.
3. **Synthesis (step 8, once all passes are done).** Fill in the Climb sequence, the Cross-cutting
   rollups, and the overall project readiness grade — these require every applicable pass to have run
   and can't be computed from a partial tracker.

```markdown
# Master Tracker

> Generated: <date> · commit <sha> · craft-audit
> Applicable domains: <N> of 10 · Last full run: <date> (date of the last run in which every
> applicable pass executed; write "—" and note the partial scope otherwise)

## Climb sequence (do these first)
Ordered, persona-tiered — see prioritization.md for how this is built. The **Scope** column is what
makes every row unambiguous in a multi-app repo (the ID label is reference-only and may repeat across
scopes); always pair the label with its Scope. Filled in at synthesis (step 8) — left empty while
domain passes are still running.

| # | ID | Scope | Finding (plain language) | Severity | Blast radius | Status |
| - | -- | ----- | ------------------------ | -------- | ------------ | ------ |
| 1 | apps-web-SEC-001 | apps/web | Anyone can open another user's data by changing the URL | 🔴 | all tenants | open |
| 2 | packages-ui-UX-003 | packages/ui | ... | 🟡 | one surface | open |
| 3 | ... | ... | ... | | |

(Single-app repo: scope is `root`, so IDs are `root-SEC-001` — the prefix is never dropped.)

The climb sequence contains only grade-eligible, distinct defects. `unverified-from-repo` items
belong in **Human verification required**, not in its count or rank.

## Cross-cutting (one defect, multiple domains)
One real defect can legitimately appear in two domains' `findings.md` with two different fingerprints
(the tuple includes `domain` by design). Reconcile them **here**, at the tracker level — do **not**
alter the fingerprints or mark either finding `fixed`. Group by the rollup key `(scope, class,
resource)`, pick the canonical owner (the domain that owns the fix), show only that row in the climb
sequence above, and record the cross-link below. See `prioritization.md` step 2b.

| Rollup (scope · class · resource) | Canonical ID | Also surfaced as (rolled up under canonical) |
| --------------------------------- | ------------ | -------------------------------------------- |
| apps/api · cron-never-runs · setInterval jobs | apps-api-INFRA-001 | apps-api-BE-001 |

(Each rolled-up finding keeps its own `open`/`regressed` status in its domain `findings.md`; "rolled
up under <ID>" is tracker metadata, not a lifecycle status. Omit this section if no cross-domain
duplicates exist.)

The `craft-fix` companion sets a climb-sequence row's **Status** cell to `open · fix-attempted
<YYYY-MM-DD>` after recording a Fix-attempt on that finding. Like "rolled up under", this is tracker
**display metadata**, not a lifecycle status — counts and grades still treat the finding as plain
`open`. The next re-run resolves it per the "not seen ≠ fixed" rule: to `fixed` only if the domain
pass ran, the fingerprint isn't re-observed, and the remediation review is `cleared`; back to plain
`open` (fix-attempt annotated "did not hold") if it's re-observed, or left `open` with the stamp
untouched if the domain pass didn't run or the review is pending.

## Readiness (derived — never hand-set)
One honest grade per applicable (scope, domain), **computed mechanically from open findings** so it
can't drift into theater — it's just a restatement of "do you still have open criticals here":

| Grade | Means | Rule (recomputed every run) |
| ----- | ----- | --------------------------- |
| 🔴 **Blocked** | not production-ready | ≥1 open or regressed 🔴 in this (scope, domain) |
| 🟡 **At risk** | usable, has holes | no open 🔴, but ≥1 open 🟡 |
| 🟢 **Solid** | production-grade for this surface | only 🟢 open, or nothing open |
| — **N-A** | surface doesn't exist here | domain marked N-A in `applicability.md` |
| ❔ **Unaudited** | applies, not yet run | applicable but no `findings.md` yet |

No numeric scores — they invite false precision and become theater. The grade is the three-state
severity model already in use, surfaced per surface. **Overall project readiness = the worst grade
across all applicable scopes/domains** (a project is only as production-ready as its weakest applicable
surface). Recompute both on every run; never carry a stale grade. The companion **distance** is not a
score: it states the exact number of distinct eligible 🔴 blockers needed to reach 🟡, or eligible 🟡
risks needed to reach 🟢, and ranks that work by blast radius.

An `unverified-from-repo` finding (see "Stable finding IDs and status" above) does not gate this grade
or the ordinary distinct-defect count. It belongs in the separate **Human verification required**
section below, with the repo gap and exact human check needed.

## Audit status
| Scope | Domain | Applies | Plan | Eligible findings | Human checks | Last run | Open 🔴 / 🟡 / 🟢 | Grade · distance |
| ----- | ------ | ------- | ---- | ----------------- | ------------ | -------- | ----------------- | ---------------- |
| apps/web | security | yes | ✅ | 6 | 1 | <date> | 2 / 3 / 1 | 🔴 Blocked · 2 blockers to 🟡 |
| apps/web | ux | yes | ✅ | 4 | 0 | <date> | 0 / 2 / 2 | 🟡 At risk · 2 risks to 🟢 |
| apps/admin | security | yes | ⏳ | — | — | — | — | ❔ Unaudited |
| packages/ui | ux | partial | ⏳ | — | — | — | — | ❔ Unaudited |
| ... | | | | | | | | |

**Overall readiness: 🔴 Blocked** — 2 distinct 🔴 blockers remain in `apps/web` security; clearing
them reaches 🟡 At risk. Show the next threshold even when multiple domains are blocked.

(Single-app repo: one scope `root` — the Scope column still appears, valued `root`.)

## Human verification required
These are retained durable findings but excluded from ordinary finding totals, the climb sequence,
and grade computation until a human or runtime system verifies them.

| ID | Scope | Repo gap observed | Human/runtime check required |
| -- | ----- | ----------------- | ---------------------------- |
| apps-web-INFRA-004 | apps/web | No repository evidence of preview-to-production DB isolation | Confirm deployment environment bindings and data-source policy |

## Verification follow-up
Derived from open Fix-attempt dates; not a lifecycle status. List every due/overdue attempt and any
explicit defer so a repair claim cannot disappear into the ordinary open count.

| ID | Severity | Fix-attempt date | Targeted verification | State |
| -- | -------- | ---------------- | --------------------- | ----- |
| apps-web-SEC-001 | 🔴 | 2026-06-25 | due 2026-07-02 | overdue — verify before next pick-set |
| packages-ui-UX-003 | 🟡 | 2026-06-25 | due 2026-07-09 | queued |

## Delta since last run
See `rerun.md` → "The delta report" for the format. Example:
✅ 3 fixed · ↩ 1 regressed · ➕ 2 new · ❔ 0 not re-checked
```

### `audits/<scope>/<domain>/plan.md`

```markdown
# <Domain> Audit Plan — <scope>

> Generated: <date> · commit <sha> · driven by <domain>-craft · scope: <root | apps/web | packages/ui>

Scope for THIS surface (from discovery): <one line>.
Surface this list as a live todo so the audit runs in steps and nothing is skipped.

## Discovery contracts for this pass

- [ ] Capability profile: <capabilities evidenced for this surface>; skip <incompatible checklist sections> as N-A with reasons.
- [ ] Invariant adoption: <each applicable discovery invariant>; inventory every matching call site and record coverage, exclusions, or a finding.
- [ ] Source-of-truth consistency: for every content/configuration defect, trace the governing contract, fixture, seed, generator, or prompt and verify all generated surfaces before closure.

The steps are **sourced from the domain skill's own `## Audit checklist (for craft-audit)`
section** — the domain owns its checklist, the orchestrator copies it here and tailors it to what
discovery found (skip an inapplicable step with a one-line reason; never silently drop one). Don't
improvise the steps from scratch — if a domain skill has no checklist section, fall back to deriving
steps from its references (and that absence is itself worth reporting as a skill gap).

- [ ] <step 1 — from the domain's audit checklist, mapped to its reference>
- [ ] <step 2>

<!-- Before acting on this plan: verify each file:line reference still exists — paths drift
     between audit and fix. -->
```

### `audits/<scope>/<domain>/findings.md`

```markdown
# <Domain> Findings — <scope>

> Generated: <date> · commit <sha> · driven by <domain>-craft · scope: <root | apps/web | packages/ui>

## apps-web-SEC-001 · severity 🔴 · status open
**What breaks (plain language):** Anyone can open another customer's invoice by changing the number
in the URL — their private data is exposed.
**Technical:** No per-resource authorization on `GET /api/invoices/:id` (IDOR). `apps/web/api/invoices/[id]/route.ts:12`.
**Fix:** Scope the query to the authenticated tenant; deny by default. See craft-security → authz.md.
**Fingerprint:** `scope=apps/web · domain=security · class=missing-authz · resource=GET /api/invoices/:id`
**Last-checked:** 2026-06-19 · a1bec8f
**Deployment-state:** pending (tenant migration not applied to production)
**Fix-attempt:** 2026-06-25 · b2c9d1e · scoped the query to req.auth.orgId (optional — appended by craft-fix)
```

### `audits/<scope>/<domain>/remediation-reviews.md`

Create this append-only file when a re-run reviews its first fix attempt. It is deliberately separate
from `findings.md`: a remediation review is evidence about a code change, not a new lifecycle field or
a free-form alteration to the canonical finding grammar. One record is required for every attempted
fix that a re-run wants to close; retain failed and superseded reviews as repair history.

```markdown
# Remediation Reviews — <scope> / <domain>

> Generated: <date> · commit <sha> · craft-audit

## <finding-ID> · review <cleared|pending|follow-up-found>

**Fix-attempt:** <verbatim Fix-attempt line being reviewed, or `none — unrecorded remediation`>
**Diff provenance:** <fix SHA^! plus SHA..HEAD, or working-tree relative to HEAD; state any unavailable range>
**Invariant:** <the original security, payment, migration, or data-integrity property>
**Risk triggers:** <none | auth/authz | payment | migration | data integrity; list all that apply>
**Changed boundaries:** <callers, alternate entry points, jobs, webhooks, schema/data paths reviewed>
**Evidence checked:** <named tests, migration/backfill/rollback evidence, or why evidence is unavailable>
**Conclusion:** <why this change is clear, pending, or unsafe>
**Follow-up findings:** <none | finding IDs emitted by this review>
```

`cleared` means the original fingerprint is absent **and** the review found no unaddressed regression.
`pending` keeps the finding open; it is required when provenance, affected boundaries, or relevant
evidence could not be reviewed. For a closure with no Fix-attempt line but changed code since
`last-checked`, write `none — unrecorded remediation` and review the available range rather than
silently treating the missing annotation as proof that no remediation occurred. `follow-up-found`
also keeps the original finding open until the reviewer records the new/regressed finding IDs; never
bury a discovered side effect in this file.

(The `apps-web-SEC-001` label is display-only and derived one-way from the fingerprint's
`scope=apps/web`; matching/uniqueness key on the fingerprint tuple, never on parsing the label.
Single-app would be `scope=root` with label `root-SEC-001`.)

The **Fingerprint** line is what makes reruns deterministic (see "Re-run behavior" above) — severity
and status live in the heading, never duplicated below it. The **Last-checked** line is set by the run
that actually re-verified the resource (`rerun.md`); on the first run it equals the `Generated` stamp.

### Canonical findings.md emission format (mandatory)

This is the **only** allowed finding-block grammar for domain skills and subagents. Authority is this
section plus the template above; domain skills restate it so solo runs match orchestrated runs. Do not
invent alternate heading shapes.

**Heading grammar (exactly):**

```
## <scopeLabel>-<DOMAINCODE>-NNN · severity <🔴|🟡|🟢> · status <open|fixed|regressed|wontfix (reason)|fixed (merged into <ID>)>
```

(`fixed (merged into <ID>)` is a documented merge annotation under the `fixed` lifecycle family —
see Stable finding IDs and re-run behavior.)

Example: `## apps-web-SEC-001 · severity 🔴 · status open`

**Required fields under each heading, in this order:**

1. `**What breaks (plain language):**` …
2. `**Technical:**` … (with `file:line` when known)
3. `**Fix:**` …
4. `**Fingerprint:**` `` `scope=<path> · domain=<domain> · class=<class> · resource=<resource>` ``
5. `**Last-checked:**` `YYYY-MM-DD · <short-sha>` or `YYYY-MM-DD · none (no git)`
6. optional `**Confidence:**` `verified | inferred | unverified-from-repo` — absent means `verified`
7. optional `**Deployment-state:**` `active | not-applicable | unverified-from-repo | pending (reason)`
8. optional `**Fix-attempt:**` lines — only appended by craft-fix, never invented by the audit pass

The canonical optional-label order after the required fields is: `**Last-checked:**`, then optional
`**Confidence:**`, then optional `**Deployment-state:**`, then optional `**Fix-attempt:**`.

**Forbidden (reject / re-emit):**

- `###` (or any non-`##`) finding headings
- Heading shorthand like `## ID · 🔴 · open` — missing the words `severity` and `status`
- Folding severity+status into one token (`🔴 open`) in the heading
- Putting severity/status only as body bullets (`- **Severity:**`, `- **Status:**`) — they live in the
  heading only; never duplicate them below
- Omitting `**Fingerprint:**` or `**Last-checked:**`

**Mechanical validation checklist** (orchestrator runs this per `findings.md` before synthesis):

- Prefer the helper script in `scripts/validate-findings.mjs`.
- Run it against the target repo's workspace. The plugin is installed outside the project, so always
  address the script through `${CLAUDE_PLUGIN_ROOT}` rather than a relative or guessed path:

  ```bash
  node "${CLAUDE_PLUGIN_ROOT}/skills/craft-audit/scripts/validate-findings.mjs" /absolute/path/to/target-repo/.craftsman
  ```

- If the script isn't available or fails to run, fall back to executing the six checks below by hand
  — they are the spec the script implements, and remain the documented fallback.

1. Every finding heading matches (full line, conceptual regex):
   `^## [A-Za-z0-9][A-Za-z0-9-]*-(UX|FE|BE|DB|SEC|INFRA|OBS|TEST|LINT|AI)-\d{3} · severity [🔴🟡🟢] · status (open|fixed|regressed|wontfix \(.+\)|fixed \(merged into .+\))$`
   Status forms: `open` · `fixed` · `regressed` · `wontfix (reason)` (reason non-empty) ·
   `fixed (merged into <ID>)` (ID non-empty). ID shape is
   `<scopeLabel>-<DOMAINCODE>-NNN` (DOMAINCODE one of UX|FE|BE|DB|SEC|INFRA|OBS|TEST|LINT|AI; NNN exactly 3 digits).
2. For each finding block (from a `## ` heading until the next `## ` or EOF):
   - Contains exactly one of each required label lines in this order (allow multi-line values after
     the label until the next `**` label or heading):
     `**What breaks (plain language):**` then `**Technical:**` then `**Fix:**` then
     `**Fingerprint:**` then `**Last-checked:**`
   - Fingerprint value matches: `` `scope=... · domain=... · class=... · resource=...` ``
   - Last-checked value is non-empty and matches:
     `\d{4}-\d{2}-\d{2} · ([0-9a-f]{4,40}|none \(no git\))`
   - Optional `**Confidence:**` line, if present, comes immediately after Last-checked (before any
     Fix-attempt lines) and its value is exactly one of `verified | inferred | unverified-from-repo`;
     absent means `verified`
   - Optional `**Fix-attempt:**` lines only after Last-checked (and after Confidence, when present)
3. No `###` finding headings anywhere in the file
4. No body bullets `- **Severity:**` or `- **Status:**`
5. Empty findings file (header only, zero findings) is valid if it has the file header stamp and no
   malformed headings
6. **Path binding (orchestrated runs):** for a file at
   `audits/<scope>/<domain>/findings.md`, every finding must bind to that path:
   - Fingerprint `scope=` equals the directory `<scope>` path exactly (e.g. `apps/web`, `root`)
   - Fingerprint `domain=` equals the directory `<domain>` name exactly (e.g. `security`, `db`)
   - Heading label uses `scopeLabel = scope.replaceAll('/', '-')` and the DOMAINCODE from the
     domain-code table for that `<domain>` (e.g. `audits/apps/web/security/` → headings start
     `apps-web-SEC-`, fingerprint `scope=apps/web · domain=security · …`)
   A shape-valid finding written to the wrong scope/domain file is a blocker — reject it; do not
   re-home it during synthesis. Solo domain runs (no orchestrator path) still emit the correct
   scope/domain for the surface they audited.

A file that fails any check is a blocker — do not synthesize from it; re-prompt the domain pass (or
fix the file) with this template before continuing. Prefer re-emission over inventing a normalizer
that accepts broken variants.
