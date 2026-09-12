# Naming Conventions (single source of truth)

Every slug and filename the skill writes or expects. Referenced by `init.md`, `migrate.md`, `intake.md`, and every sub-skill that emits files. Do not duplicate these rules elsewhere.

## Folder slugs

| Scope | Slug form | Example |
|---|---|---|
| Entity | kebab-case legal name, drop Inc/LLC/LP/Corp suffix | `acme-holdings` |
| Disregarded SMLLC | same, nested under regarded parent | `summit-management` |
| Property | address kebab-case | `632-216th-ave-ne` |
| Investment (K-1 position) | sponsor kebab-case | `crescent-capital-fund-iv` |
| Tax year | `FY<YYYY>` — IRS tax year = CY in which fiscal period **begins** | `FY2024` |

Slugs are stable across rebrands. Display names live in `entity.md` / registry.

## Slug registry (`workspace-profile/slugs.md`)

Canonical slug for every **employer, payer, broker, sponsor, lender, custodian, vendor, recipient** referenced anywhere. Used by filenames, parsed JSON, and `tax-summary.md` rows. Never invent a slug without registering it here first. Template: `templates/slugs.md.template`.

**Self-healing:** if `workspace-profile/slugs.md` is absent, create it from `templates/slugs.md.template` and backfill from `entities-index.md` before resolving any slug — never improvise unregistered slugs.

## `<scope>` / `<scope-root>` shorthand

Two distinct anchors — do not conflate them:

- **`<scope>`** = `individual` or `entities/<slug>/tax`. Used for year-scoped working files: "wherever this scope's tax-year folder lives." Example: `<scope>/FY<YYYY>/expenses-log.md` resolves to `individual/FY<YYYY>/expenses-log.md` or `entities/<slug>/tax/FY<YYYY>/expenses-log.md`.
- **`<scope-root>`** = `individual` or `entities/<slug>` (no `tax/` segment). Used for year-crossing state that sits beside `profile.md` / `entity.md` at the scope's root. Example: `<scope-root>/carryforwards.json` resolves to `individual/carryforwards.json` or `entities/<slug>/carryforwards.json` — **not** `entities/<slug>/tax/carryforwards.json`.

## Document filenames (canonical)

All inbound documents are renamed to canonical form on ingest (`intake.md` Step 0) or during migration (`migrate.md`). Year prefix = `FY<YYYY>` (tax year).

### Received income documents

| Doc | Filename |
|---|---|
| W-2 | `FY<YYYY> - W-2 - <employer-slug>.pdf` |
| 1099-NEC | `FY<YYYY> - 1099-NEC - <payer-slug>.pdf` |
| 1099-MISC | `FY<YYYY> - 1099-MISC - <payer-slug>.pdf` |
| 1099-INT (standalone) | `FY<YYYY> - 1099-INT - <payer-slug>.pdf` |
| 1099-DIV (standalone) | `FY<YYYY> - 1099-DIV - <payer-slug>.pdf` |
| 1099-B (standalone) | `FY<YYYY> - 1099-B - <broker-slug> - <acct-last4>.pdf` |
| 1099-Composite | `FY<YYYY> - 1099-Composite - <broker-slug> - <acct-last4>.pdf` |
| 1099-R | `FY<YYYY> - 1099-R - <payer-slug>.pdf` |
| 1099-SA / 5498-SA | `FY<YYYY> - <form> - <custodian-slug>.pdf` |
| SSA-1099 | `FY<YYYY> - SSA-1099 - <recipient-slug>.pdf` |
| 1098 (mortgage) | `FY<YYYY> - 1098 - <lender-slug> - <property-slug>.pdf` |
| 1098-T / 1098-E | `FY<YYYY> - <form> - <institution-slug>.pdf` |
| 1095-A/B/C | `FY<YYYY> - 1095-<variant> - <issuer-slug>.pdf` |
| 5498 (IRA) | `FY<YYYY> - 5498 - <custodian-slug>.pdf` |
| K-1 (1065) | `FY<YYYY> - K-1 - <GP\|LP> - <sponsor-slug>.pdf` |
| K-1 (1120-S) | `FY<YYYY> - K-1-S - <issuer-slug>.pdf` |
| K-1 (1041 trust) | `FY<YYYY> - K-1-T - <trust-slug>.pdf` |
| K-3 | `FY<YYYY> - K-3 - <sponsor-slug>.pdf` |

### Tier-2 K-1s (a K-1 the sponsor itself received) — informational, NEVER in `k1s-received/`

**This section is the single home for the rule** (`entities/partnership.md` and
`reconciliation.md` point here). A K-1 issued *to* a lower-tier partnership by *its* investee
names that partnership in Part II, not this taxpayer. Nothing on it is reported, allocated, or
added to basis two tiers down. It is kept only as evidence (debt at the tier, fee flows,
year-of-inclusion questions for the sponsor) and lives with the investment — under
`<scope-root>` (`individual/` or `entities/<slug>/`, **no** `tax/` segment) — never with the
year's source documents:

| Doc | Location and filename |
|---|---|
| Tier-2 K-1 | `<scope-root>/investments/<investment-slug>/upstream-<issuer-slug>-DO-NOT-REPORT/<YYYY-MM-DD> - K-1 - <issuer-slug> - ty<YYYY> - to-<recipient-slug>[ - <STATUS>].pdf` |
| Folder README (required) | `…/upstream-<issuer-slug>-DO-NOT-REPORT/README.md` — opens with the one rule (partner named is X, not us; nothing goes on a return), lists each file's status, tabulates the informational figures, and states the open questions they raise |

`<YYYY-MM-DD>` is the document's issuance date, deliberately date-first (unlike the canonical
`FY<YYYY> - K-1 - …` grammar) so that two undisclosed versions of the same tax year sort by
issuance. `<STATUS>` is a single optional token from `CONTROLLING | SUPERSEDED`; omit it when
only one version exists. Which version is controlling is decided per `parsing.md` § Two versions
of one document, not by metadata. The folder name is the guard-rail: an agent that lists the
directory sees the rule before it sees a PDF. The parent `investments/<investment-slug>/README.md`
carries a pointer paragraph that says which tier is reportable.

### Issued documents (entity sending out)

| Doc | Filename |
|---|---|
| 1099-NEC | `FY<YYYY> - 1099-NEC issued - <recipient-slug>.pdf` |
| 1099-MISC | `FY<YYYY> - 1099-MISC issued - <recipient-slug>.pdf` |
| 1042-S | `FY<YYYY> - 1042-S issued - <recipient-slug>.pdf` |
| W-2 | `FY<YYYY> - W-2 issued - <employee-slug>.pdf` |
| K-1 (1065/1120-S) | `FY<YYYY> - K-1 issued - <recipient-slug>.pdf` |

### Payee certificates (year-independent, in `corporate/payees/<payee-slug>/`)

| Doc | Filename |
|---|---|
| Form W-9 | `<yyyy-mm-dd> - W-9 - <payee-slug>.pdf` |
| Form W-8BEN / W-8BEN-E / W-8ECI / W-8EXP / W-8IMY | `<yyyy-mm-dd> - <w8-form> - <payee-slug>.pdf` |
| Form 8233 | `<yyyy-mm-dd> - 8233 - <payee-slug>.pdf` |
| Payee register | `payee-register.md` |

The date is the date the payee signed the certificate, because that is what
governs when it expires and whether it covered a given payment.

### Year-independent / governance

| Doc | Filename |
|---|---|
| W-9 from vendor | `W-9 - <vendor-slug>.pdf` (in `source/contractors-w9/`) |
| W-9 of this entity | `W-9.pdf` (in `accounts/`) |
| Formation | `<yyyy-mm-dd> - <doc>.pdf` in `corporate/formation/` |
| Minutes | `<yyyy-mm-dd> - minutes - <board\|shareholder>.pdf` |
| Resolution | `<yyyy-mm-dd> - resolution - <topic-slug>.pdf` |
| State annual report | `FY<YYYY> - annual report - <state>.pdf` |
| BOIR | `<yyyy-mm-dd> - BOIR - <initial\|updated>.pdf` |
| Business license | `FY<YYYY> - license - <jurisdiction>.pdf` |
| Corporate record-set audit | `corporate-records-audit-FY<YYYY>.json` at the `corporate/` root (one status/evidence SSOT per audited year) |
| Stock issuance readiness/counsel packet | `<yyyy-mm-dd> - <tranche-id> - readiness.md` in `corporate/stock-issuances/` |
| Stock issuance register | `stock-issuance-register.md` in `corporate/stock-issuances/` |
| Stock ledger | `stock-ledger.md` in `corporate/stock-issuances/` |
| Stock cap table | `stock-cap-table.md` in `corporate/stock-issuances/` |
| Stock issuance tax memo | `<yyyy-mm-dd> - <tranche-id> - tax-position.md` in `corporate/stock-issuances/` |
| §351 property schedule | `<yyyy-mm-dd> - <tranche-id> - section-351-property.md` in `corporate/stock-issuances/` |
| §83(b) execution control | `<yyyy-mm-dd> - <tranche-id> - section-83b.md` in `corporate/stock-issuances/` |
| Stock issuance closing binder index | `<yyyy-mm-dd> - <tranche-id> - closing-manifest.md` in `corporate/stock-issuances/` |
| Stock issuance closing validation manifest | `<tranche-id>-closing-manifest.json` in `corporate/stock-issuances/` |
| Stock issuance annual specialist result | `stock-issuance-audit-FY<YYYY>.json` in `corporate/stock-issuances/` |
| QSBS issuance/monitoring memo | `<yyyy-mm-dd> - <tranche-id> - qsbs-position.md` in `corporate/qsbs-tracking/` |

Use tranche IDs `ISS-<YYYY>-<NNN>` (uppercase) assigned sequentially from the
stock-issuance register. A proposed tranche keeps its ID through closing or
cancellation; never recycle an ID or rename it to imply a different date.

### Individual permanent records and per-asset folders

Individual permanent records live outside any tax year. Slugs and filenames are
owned by `individual/records.md` §6, which extends this file; the folder anchors
are:

| Anchor | Path |
|---|---|
| Permanent personal records | `individual/records/{identity,basis,elections,estate,plans,legal,insurance}/` |
| Lifetime IRA basis (SSOT) | `individual/records/basis/form-8606-basis.md` (one per individual) |
| Individually-owned property | `individual/properties/<property-slug>/` |
| Individual financial account | `individual/accounts/<account-slug>/` |
| Personally-held K-1 position | `individual/investments/<sponsor-slug>/` |
| Household member | `individual/household/{spouse,dependents/<name-slug>}/` |
| Individual annual workpaper | `individual/FY<YYYY>/annual/workpapers/wp-<topic>.md` |
| Individual return review narrative | `individual/FY<YYYY>/review.md` (from `templates/individual-review.md.template`) |
| Individual CPA handoff index | `individual/FY<YYYY>/return-package.md` (from `templates/individual-return-package.md.template`) |

Workpaper filenames carry a `wp-` prefix so they can never collide with a
sub-skill filename of the same topic.

**A fact is recorded in exactly one workpaper.** Where a domain module declares a
workpaper for a topic, that file is the sole home; the source→form table in
`individual/1040.md` §2 points to it rather than creating a second one.

### IRS transcripts (pulled from IRS, not received from third parties)

Transcripts are *evidence / workpaper material*, not inbound source docs. They live in their own subfolder per scope so the source/inbound mail stream stays clean. See `scenarios/irs-transcripts.md` for the five types and when to pull them.

| Transcript type | Filename |
|---|---|
| Account Transcript | `FY<YYYY> - IRS Account Transcript - <scope-slug>.pdf` |
| Tax Return Transcript | `FY<YYYY> - IRS Return Transcript - <scope-slug>.pdf` |
| Record of Account | `FY<YYYY> - IRS Record of Account - <scope-slug>.pdf` |
| Wage and Income Transcript | `FY<YYYY> - IRS Wage and Income Transcript - <scope-slug>.pdf` |
| Verification of Non-Filing | `FY<YYYY> - IRS Verification of Non-Filing - <scope-slug>.pdf` |

**Scope slug rules:**

- Individual (1040): use the primary filer's slug from `workspace-profile/slugs.md` (e.g. `jane-doe`). Joint return does not change the slug.
- Entity (1065 / 1120 / 1120-S / 941 / etc.): use the entity's folder slug.

**Location:**

- Individual: `individual/FY<YYYY>/transcripts/`
- Entity: `entities/<slug>/tax/FY<YYYY>/annual/workpapers/transcripts/`

**Re-pull convention:** IRS updates transcripts weekly. When the same transcript is re-pulled, overwrite the prior file (canonical name is stable), bump `.parsed/_index.json` `parsed_at`, and append the tracking-number change (if any) to the scope's `history.md`. If you need to retain the prior pull for forensic comparison, suffix the older copy with `-pulled-<YYYY-MM-DD>` and move it to `archive/` — do not pollute the active folder.

### Filed returns & extensions

- Return: `FY<YYYY> - <form> - filed - <scope-slug>.pdf` (e.g. `FY2024 - 1120 - filed - acme-holdings.pdf`)
- Extension: `FY<YYYY> - <form> - extension - <scope-slug>.pdf` (e.g. `FY2024 - 7004 - extension - acme-holdings.pdf`)
- State: `FY<YYYY> - <state> - <form-or-type> - filed - <scope-slug>.pdf`
- E-file confirmation: `FY<YYYY> - <form> - confirmation - <scope-slug>.pdf`

Location: `<scope>/FY<YYYY>/filed/`.

### Generated reports (skill-authored, kept on user request)

| Report | Filename |
|---|---|
| Close/estimate control workpaper | `<run-id>-control.md` in `<scope>/FY<YYYY>/.computed/` |
| Canonical estimate artifact | `<run-id>-estimate.json` in `<scope>/FY<YYYY>/.computed/` |
| Current installment presentation | `quarterly/Q<n>/estimate.md` (pointer/headlines for latest non-superseded run) |
| Payment evidence | `quarterly/Q<n>/payment.md` only after user-reported or documentary payment evidence exists |
| Optimization deep-dive report (`optimization.md`) | `FY<YYYY> - optimization review - <yyyy-mm-dd>.md` (in `<scope>/FY<YYYY>/`; multi-scope reviews live under `individual/FY<YYYY>/`) |

Close/estimate run IDs use
`EST-<YYYYMMDDTHHMMSSZ>-<scope-slug>-<annual|I1|I2|I3|I4>`. Never recycle a
run ID. A corrected computation receives a new run ID and records
`supersedes_run_id`; do not overwrite the earlier control or JSON artifact.

### Decision memos (`supersession.md`)

| Item | Form |
|---|---|
| Folder | `<scope-root>/decisions/` or `workspace-profile/decisions/` — scope root, never `FY<YYYY>/` |
| Filename | `<yyyy-mm-dd> - <topic-slug>.md` (date-first so the folder sorts chronologically) |
| Memo ID | `DEC-<YYYYMMDD>-<scope-slug>-<topic-slug>`; `<scope-slug>` is `individual`, the entity slug, or `workspace` |
| Same day, same topic | Filename ` - 2` and ID `-2` suffix, incrementing |

IDs are never recycled and memo bodies are never rewritten; a corrected memo is a new memo
that names the old one in `Supersedes`. Parallels the run-ID rule above.

### Receipts

`FY<YYYY> - receipt - <yyyy-mm-dd> - <vendor-slug> - <short-desc>.pdf`. `<short-desc>` ≤4 words, kebab-case.

### Payment records

`FY<YYYY> - <type> - Q<n> - <scope-slug>.pdf` where type ∈ {`1040-ES`, `EFTPS confirmation` (corp §6655 — no voucher form), state estimate, `4868`, `7004`}.

## Collision rules

- **Corrected / amended**: suffix ` - corrected` or ` - amended-<n>`. Latest-suffixed wins in `.parsed/_index.json`; superseded entries retained with `superseded_by` pointer.
- **Duplicate arrival (same sha256, different path)**: keep one; log dup path in `_index.json`; delete dup only after user confirmation.
- **Different sha256, same canonical name**: append ` - v2`, flag in `open-questions.md`.
- **Unknown payer on ingest**: ask user → write to `slugs.md` → rename. Never guess.
- **Sync-conflict / duplicate copies** (OneDrive/iCloud `(1)` suffixes, device-name suffixes, double extensions): see `migrate.md` "Sync-conflict & duplicate sweep". Never auto-delete.

## Parsed cache slugs

`.parsed/FY<YYYY>-<doctype>-<payer-slug>[-<discriminator>].json`. Discriminator required when collision possible: `acct-last4` for brokerage, recipient-slug when an issuer emits multiple K-1s to different recipients in this workspace.

## Cross-workspace K-1 references

K-1 issued by one entity in this workspace to another scope:

- **Issuer (source of truth)**: `entities/<issuer>/tax/FY<YYYY>/issued/k1s-issued/FY<YYYY> - K-1 issued - <recipient-slug>.pdf`
- **Recipient**: do NOT copy. Write a pointer file `FY<YYYY> - K-1 - <GP|LP> - <issuer-slug>.ref.md` in the recipient's `source/k1s-received/`:

```
issuer_path: entities/acme-holdings/tax/FY2024/issued/k1s-issued/FY2024 - K-1 issued - summit-management.pdf
sha256: <hash-at-capture>
captured_at: 2026-04-14
```

A corrected K-1 at the issuer flags the pointer stale when sha256 drifts.
