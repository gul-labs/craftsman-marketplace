
# Init Sub-Skill

First-time setup of a tax/business workspace. Triggered when SKILL.md router finds no `workspace-profile/` in the current working directory, or when the user explicitly says "init".

Target layout: see `layout.md`. Naming conventions: see `naming.md`. PDF/parse rules: see `parsing.md`. Legacy workspace migration: see `migrate.md`.

## Pre-flight

1. Confirm cwd is intended as a tax/business workspace (look for year-named folders, `Entities/` or entity-named folders, `business-info.md`). Ask if ambiguous.
2. Explain: "I'll scan for existing entities and prior-year returns, draft a workspace profile + per-entity configs, and seed the standard folder structure. You confirm every batch before I write. Nothing saves until you approve."
3. Pick mode:
   - **Fresh workspace** — no existing structure; create from scratch.
   - **Migration** — legacy structure detected. After Phase 1 scan, hand to `migrate.md` for folder + filename canonicalization; return here at Phase 3 with a canonical tree.

## Phase 1 — Discover the Landscape

Glob the root for:

| Pattern | Signal |
|---|---|
| `[Ee]ntities/*/` or `*` Inc/LLC/LP folders at root | regarded entities |
| `entities/<Non-Slug Name>/` (spaces, Title-Case, not kebab-case) | non-canonical entity folder — flag for `migrate.md` guard |
| Disregarded-SMLLC-shaped folder sitting at top level (not nested under a regarded parent's `disregarded/`) | misplaced disregarded SMLLC — flag for `migrate.md` guard |
| `*/disregarded/*` OR entity folders nested inside other entity folders | disregarded SMLLCs |
| `FY[12][09][0-9][0-9]/`, `Tax [12][09][0-9][0-9]/`, `[12][09][0-9][0-9]/` under entity folders | per-entity tax years |
| `*1040*.pdf`, `Tax Return*.pdf` at root or in a personal tax folder | individual 1040 trail |
| `business-info*.md`, `entities*.md` at root | existing entity roster |
| `Corporate/`, `Books/`, `Properties/`, `Investments/`, `Bank*`, `Brokerage*` under entities | sub-structure hints |
| `*K1*.pdf`, `*K-1*.pdf` | K-1s (need routing: received by whom?) |

Report what you found:
- Entities detected (by folder name). Guess type (Inc = corp, LLC = LLC/partnership, LP = partnership).
- Disregarded candidates (nested entity folders, SMLLC names).
- Tax years present per entity.
- Individual 1040 evidence (prior returns at root or in a personal folder).
- Non-slug entity folders and misplaced top-level disregarded SMLLCs — hand off to `migrate.md`'s entity-folder guard for a proposed merge into the canonical home; never move automatically.

## Phase 2 — Deep-Read Prior Returns

For each entity folder with a filed return PDF, and for the individual's most recent 1040:

| Pattern | Doc type | Extract |
|---|---|---|
| `1120*.pdf`, `Form 1120*.pdf` | C-corp return | EIN, FY, state, officers, gross receipts, NOL, §163(j) status |
| `1120-S*.pdf`, `1120S*.pdf` | S-corp return | EIN, shareholders + % , AAA, basis |
| `1065*.pdf`, `Form 1065*.pdf` | partnership | EIN, partners + %, capital accounts, §754 status |
| `1040*.pdf`, `Tax Return*.pdf` | individual | filing status, names, address, dependents, AGI, carryforwards (see below) |

### What to extract from a filed 1040 (individual)

(See legacy `init.md` extraction list — preserved below):

- **Page 1**: filing status, taxpayer + spouse names, SSN last 4, address, dependents
- **Line 11 (AGI)**, **Line 15 (taxable income)**, **Line 24 (total tax)**, **Line 37 / 34**
- **Schedule 1** — additional income sources
- **Schedule A** — itemized if present
- **Schedule B** — interest & dividend payers (broker names)
- **Schedule D line 16** — cap gain/loss
- **Schedule E** — rental properties + K-1 pass-throughs
- **Form 6251** — AMT paid + preference items
- **Form 8606** — Roth basis / nondeductible IRA basis
- **Form 8801** — AMT credit carryforward
- **Form 8582** — passive loss carryover by activity
- **Form 1116** — foreign tax credit carryover
- **Form 8889** — HSA contributions + basis
- **Capital loss carryover worksheet** — ST + LT
- **Charitable carryover worksheet** — by vintage year, by type
- **NOL worksheet** — if any

### What to extract from a filed 1120 / 1120-S / 1065

- **Header**: EIN, fiscal year, state of incorporation, accounting method
- **Officers / partners / shareholders** + ownership %
- **Schedule L** — beginning & ending balance sheet (seeds `books/opening-balances.md`)
- **Schedule M-1/M-3** — book-tax differences
- **Prior NOL, §163(j) disallowed interest, §179 carryover, charitable carryover**
- **Capital accounts** (1065 K-1s) / **AAA** (1120-S Schedule M-2) / **E&P** (1120 if tracked)
- **K-1s issued** — note recipients

PDF read + parsed-cache rules: see `parsing.md`. Never use the built-in Read tool on structured PDFs.

## Phase 3 — Draft the Workspace Profile

Present extracted facts in batches. Q&A style; don't dump all at once.

### Batch A — Owner(s)

- Individual taxpayer name(s), SSN last 4, address
- Spouse (if applicable)
- Filing status default, dependents
- State of residency, since when
- Community-property state? (AZ, CA, ID, LA, NV, NM, TX, WA, WI)
- Foreign accounts / 5471 / 8621 / 8938 / FBAR triggers?

### Batch B — Entity Roster

For each detected entity + any the user adds (slug rules per `naming.md`):

- Legal name, display name, **slug** (user can override; default = kebab-case legal name minus Inc/LLC/etc.)
- Type: C-corp / S-corp / partnership / disregarded SMLLC
- EIN (omit for disregarded — but note if SMLLC has own EIN for state/payroll use)
- State of formation, formation date
- Fiscal year (calendar or FY end month)
- Ownership: who owns what %, when acquired
- **For disregarded SMLLCs**, identify the regarded owner explicitly:
  - Regarded entity (C-corp, S-corp, partnership) → folder `entities/<parent-slug>/disregarded/<smllc-slug>/`
  - Individual (the taxpayer directly) → folder `individual/disregarded/<smllc-slug>/` — activity flows to 1040 Schedule C/E/F
- Registered agent, mail address, DOR/B&O account
- Standing elections: §754, §179 policy, cash/accrual, S-corp election date (if converted)
- Reimbursement arrangement status (if relevant): approved date, signed date,
  effective date, first-operated date, amended/terminated dates, and evidence
  status from `scenarios/accountable-plan.md` — never reduce this to an
  "Accountable Plan adopted?" boolean

### Batch C — K-1 Investments (received by entities OR individual)

For each upstream K-1 source:

- Sponsor/entity name, entity type (partnership, S-corp, etc.)
- Who is the partner/shareholder on the K-1 — the individual, a regarded entity, or a disregarded SMLLC (which is then reported under its regarded parent)?
- Ownership %
- State sourcing flags
- Classification sensitivities (working interest vs. passive for O&G; at-risk; §199A eligibility)

### Batch D — Properties (directly owned by an entity)

Per property, per owner entity:

- Address, acquired date, basis, land allocation %
- In-service date, depreciation method
- Cost seg done? REPS election? STR (avg stay ≤7 days)?
- Rental status, leases

### Batch E — Accounts

- Bank accounts per entity
- Brokerage accounts per entity (+ individual)
- EFTPS enrollment per entity
- IRIS / FIRE TCC codes (for entities issuing 1099s/1042-S)

### Batch F — Standing Context

- CPA / EA / attorney contacts
- Any active IRS or state notices
- Prior audits, amendments
- Major transactions within last 5 years (entity formation/dissolution, property acquired/sold, major elections)

## Phase 4 — Scaffold the Workspace

Only after user confirms all batches.

### 4.1 Workspace-level files

1. Create `workspace-profile/`
2. Write `workspace-profile/owner.md` from `templates/owner.md.template` — fill from Batch A
3. Write `workspace-profile/entities-index.md` from `templates/entities-index.md.template` — one row per entity from Batch B
4. Write `workspace-profile/org-chart.md` from `templates/org-chart.md.template` — Mermaid diagram from ownership data
5. Write `workspace-profile/bank-accounts.md` from `templates/bank-accounts.md.template` — from Batch E
6. Write `workspace-profile/federal-accounts.md` from `templates/federal-accounts.md.template` — IRS / EFTPS / IRIS / SSA / state DOR / SOS registration registry. Seed one row per entity from Batch B; mark all enrollment states ❓ or 🔶 until user confirms.
7. **Always** write `workspace-profile/slugs.md` from `templates/slugs.md.template` — seed with every employer/payer/broker/sponsor/lender/vendor/recipient discovered in Phase 2 + Batches B/C/E, backfilled from `entities-index.md`. This is the canonical slug registry; all subsequent filenames resolve through it (per `naming.md`). Never skip this step, even in fresh-workspace mode with no prior documents to scan — an empty registry is still created so later slug resolution has somewhere to write to.
8. Write `workspace-profile/history.md` from `templates/history.md.template` — seed from Batch F
9. Create `workspace-profile/notes/` (empty)
10. Write root `CLAUDE.md` from `templates/CLAUDE.md.template`
11. Write root `README.md` from `templates/README.md.template`

### 4.2 Individual workspace

If there's an individual 1040 trail:

1. Create `individual/`
2. Write `individual/profile.md` from `templates/profile.md.template` — fill from Batch A + C (individual-level K-1s) + D (individual-level properties, rare)
3. Write `individual/carryforwards.json` from `templates/carryforwards.template.json` — set `"scope": "individual"` and keep only the top-level keys listed in the template's `_scope_keys.individual` (delete every other data key); fill from extracted 1040
4. Write `individual/history.md`
5. If any disregarded SMLLCs are owned directly by the individual (Batch B identified them), create `individual/disregarded/<smllc-slug>/` with the same sub-structure as entity-nested disregarded (entity.md, corporate/, accounts/, books/, contracts/) — NO `tax/` folder
6. Pick an active year (Phase 5)

### 4.3 Entity workspaces

For each regarded entity in Batch B:

1. Create `entities/<slug>/`
2. Write `entities/<slug>/entity.md` from `templates/entity-config.md.template` — fill from Batch B + elections
3. Create subfolders: `corporate/{formation,minutes,resolutions,annual-reports,licenses}/`, `accounts/`, `contracts/`, `investments/`, `properties/` (only if owns property), `matters/` (only if a litigation/regulatory/dispute matter exists), `books/`, `tax/`
4. Write `entities/<slug>/books/README.md` from `templates/books-readme.md.template`
5. Write `entities/<slug>/books/chart-of-accounts.md` from `templates/chart-of-accounts.md.template` — seed based on entity type (C-corp vs partnership have different COA defaults)
6. Write `entities/<slug>/books/fixed-assets.md` from `templates/fixed-assets.md.template` — empty header
7. Write `entities/<slug>/books/opening-balances.md` from `templates/opening-balances.md.template` — seed from prior Schedule L if extracted
8. Write `entities/<slug>/carryforwards.json` from `templates/carryforwards.template.json` — set `"scope": "entity"` and keep only the top-level keys listed in the template's `_scope_keys.entity` (delete every other data key, and the entity-list keys this entity type does not use); fill from extracted 1120/1120-S/1065 (NOL, §163(j), §179, charitable carryover; for a partnership that holds lower-tier interests also `section_704d_suspended_losses`, `partnership_outside_basis`, `section_6221b_election`), same flow as individual
9. If disregarded SMLLCs belong to this entity: create `disregarded/<smllc-slug>/` with the same sub-structure minus `tax/`

`capital-accounts.md`, `journal-entries.md`, `general-ledger.csv`, and `transaction-ledgers/` are not seeded at init — they are created at first close (see `layout.md`).

### 4.4 Migration mode

Legacy structure detected? Hand off to `migrate.md` — it owns the folder migration map, slug-registry seed, file-rename map, and parsed-cache rebuild. Return here at Phase 5 with a canonical tree.

## Phase 5 — Pick an Active Scope

Ask: *"Which scope and year would you like to work on first?"*

Options:
- Individual → FY2025 (or latest with expected docs)
- Each entity → most recent FY with expected docs but not filed

Scaffold the active year folder for that scope:

1. Create `<scope>/FY<YYYY>/`
2. Write `tax-summary.md` from `templates/tax-summary.md.template` (individual variant or entity variant depending on scope)
3. Write `pending-docs.md` from `templates/pending-docs.md.template` — seed from profile/entity-config expectations
4. Write `open-questions.md` from `templates/open-questions.md.template` — seed with any unresolved carryforward gaps
5. Create `source/`, `quarterly/`, `annual/`, `filed/`, `.parsed/`, `.computed/` (entities also get `issued/`). For an individual scope, create only the `source/<category>/` subfolders the taxpayer's facts require — see `individual/onboarding.md`; do not scaffold the full set.

## Phase 6 — Hand Off

Tell the user:
> Workspace scaffolded.
> - Workspace profile: `workspace-profile/`
> - Individual: `individual/FY<YYYY>/`
> - Entities: `entities/<slug>/` × N
>
> Next steps:
> 1. Drop documents into the appropriate `source/` folders.
> 2. Say "intake docs" to parse + update `tax-summary.md`.
> 3. Or pick another router item (quarterly close, governance audit, strategy, etc.).

Show the main menu again.

## Re-Init / Profile Refresh

Additions (new entity, new property, ownership change) → `workspace-profile/entities-index.md` + write new `entities/<slug>/` via router item 6 "Update profile / add entity". Don't re-init.

For a genuinely new workspace (user moved folders), they type "init" to force re-run.
