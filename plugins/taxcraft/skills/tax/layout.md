# Workspace Layout

Loaded by `init.md` and `migrate.md` only. Not needed in steady state — `CLAUDE.md` pointer map is the working reference once the workspace exists.

## Tree

```
<workspace>/                                  ← user's cwd
├── CLAUDE.md                                 ← activation + pointer map
├── README.md                                 ← human entry, federal deadlines
│
├── workspace-profile/                        ← cross-entity, year-independent
│   ├── owner.md
│   ├── entities-index.md                     ← master roster
│   ├── org-chart.md                          ← ownership Mermaid
│   ├── bank-accounts.md                      ← centralized account table
│   ├── slugs.md                              ← payer/vendor/broker/employer registry
│   ├── history.md                            ← append-only cross-entity log
│   ├── decisions/                            ← immutable cross-entity decision memos (`supersession.md`)
│   └── notes/                                ← advisor memos, IRS correspondence
│
├── individual/                               ← owner's 1040 workspace
│   ├── profile.md
│   ├── carryforwards.json
│   ├── history.md
│   ├── decisions/                            ← immutable decision memos, permanent, all years (`supersession.md`)
│   ├── records/                              ← PERMANENT, year-independent (`individual/records.md`)
│   │   ├── individual-records-audit-FY<YYYY>.json
│   │   ├── _processed.log
│   │   ├── identity/, basis/, elections/, estate/, plans/, legal/, insurance/
│   │   └── basis/                            ← lifetime basis SSOTs (map: individual/1040.md §5)
│   │       ├── form-8606-basis.md            ← one per individual — §408(d)(2) aggregates across all trad/SEP/SIMPLE IRAs
│   │       ├── roth-basis.md                 ← contribution basis, conversion layers, both 5-year clocks
│   │       ├── amt-dual-basis.md             ← ISO regular vs. AMT basis; feeds Form 8801
│   │       ├── qsbs-basis.md                 ← §1202 holding period and basis by tranche
│   │       └── basis-index.md                ← pointer registry only; holds no figures
│   ├── properties/<property-slug>/           ← individually-owned real property (conditional)
│   │   ├── property.md                       ← standing facts only: acquisition, original cost, land %,
│   │   │                                       in-service date, elections — NEVER the current adjusted basis
│   │   ├── depreciation-schedule.md          ← running adjusted basis + accumulated depreciation
│   │   └── {acquisition/, improvements/, loan/, leases/, disposition/}
│   ├── accounts/<account-slug>/              ← account-level, ALL years (same rule as entities)
│   │   ├── account.md                        ← type: taxable / IRA / Roth / HSA / 529 / SDIRA / exchange
│   │   ├── lot-basis.md                      ← durable per-account lot basis (securities: wash-sale-adjusted,
│   │   │                                       noncovered, corrected compensatory; digital assets: per wallet
│   │   │                                       or account, required by Treas. Reg. §1.1012-1(j))
│   │   ├── statements/                       ← raw PDFs, all years
│   │   └── all-transactions.csv
│   ├── investments/<sponsor-slug>/           ← K-1 positions held personally (conditional)
│   │   ├── position.md                       ← SSOT for outside basis, at-risk, commitment, state footprint
│   │   └── subscription/                     ← PPM, sub docs, side letters, transfers
│   ├── household/                            ← second taxpayer + dependents (conditional)
│   │   ├── spouse/
│   │   └── dependents/<name-slug>/           ← own return, UTMA, 8615 facts, 1098-T
│   ├── books/                                ← CONDITIONAL: only with Schedule C or Schedule E; created at first close
│   │   └── {chart-of-accounts.md, general-ledger.csv, fixed-assets.md, transaction-ledgers/}
│   ├── disregarded/<smllc-slug>/             ← SMLLCs owned personally (no tax/)
│   │   └── {entity.md, corporate/, accounts/, books/, contracts/}
│   └── FY<YYYY>/
│       ├── tax-summary.md                    ← living workpaper
│       ├── pending-docs.md
│       ├── open-questions.md
│       ├── expenses-log.md                   ← individual/FY<YYYY>/expenses-log.md
│       ├── source/                           ← year-scoped inbound docs, categorized (canonical names)
│       │   └── {w2/, 1099s-received/, k1s-received/, 1098-mortgage/, 1095-health/,
│       │       brokerage/, retirement/, digital-assets/, charitable/, receipts/}
│       ├── annual/workpapers/                ← per-schedule workpapers (`individual/1040.md` §2)
│       ├── review.md, return-package.md      ← narrative + CPA handoff index
│       ├── transcripts/                      ← IRS transcripts pulled for this TY (Account, Return, Wage&Income, RoA, VoNF)
│       ├── quarterly/Q{1..4}/{estimate.md, payment.md*}  ← latest presentation; *payment only after reported/evidenced
│       ├── filed/                            ← filed return, extension, confirmations (`naming.md`)
│       ├── amended/                          ← created on demand — amended-return workpapers (router item 14)
│       ├── .parsed/                          ← JSON cache + _index.json
│       └── .computed/                        ← canonical <run-id>-{control.md,estimate.json}; prior runs preserved/superseded
│
├── entities/<entity-slug>/                   ← REGARDED entities (file their own returns)
│   ├── entity.md
│   ├── carryforwards.json                    ← NOLs, §163(j), §179, charitable carryovers (same flow as individual)
│   ├── decisions/                            ← immutable decision memos, permanent, all years (`supersession.md`)
│   ├── corporate/
│   │   ├── corporate-records-audit-FY<YYYY>.json ← annual structured record-set evidence/status SSOT
│   │   ├── {formation, minutes, resolutions, annual-reports, licenses}/
│   │   ├── stock-issuances/                   ← per-tranche legal/tax/securities closing binders + register/ledger/cap table
│   │   ├── payees/                            ← permanent, year-independent: one folder per payee holding its W-9 / W-8 / Form 8233 certificate and the payee register (`scenarios/information-returns.md`). Belongs to the entity whose EIN issues the return, which for a disregarded entity depends on the return type — see `entities/disregarded.md`
│   │   └── qsbs-tracking/                     ← per-tranche §1202 issuance position + annual monitoring
│   ├── accounts/                             ← one subfolder per financial account
│   │   └── <account-slug>/                   ← e.g. `chase-1234`, `chase-5678-cc`, `ibkr-9012`
│   │       ├── statements/                   ← raw monthly PDFs (all years)
│   │       ├── all-transactions.csv          ← raw CSV export from bank (all years)
│   │       └── check-images/                 ← check lookups, wire confirmations
│   │   plus optional: bank.md, brokerage.md, eftps.md, w9.pdf
│   ├── contracts/
│   ├── investments/<investment-slug>/        ← K-1 positions
│   ├── properties/<property-slug>/           ← directly-owned RE
│   ├── matters/<matter-slug>/                ← litigation/regulatory/dispute matters (own CLAUDE.md persona allowed). Paths containing `privileged` are excluded from intake/parse pipelines — see SKILL.md Privacy section.
│   ├── books/
│   │   ├── README.md                         ← seeded at init
│   │   ├── chart-of-accounts.md
│   │   ├── fixed-assets.md
│   │   ├── opening-balances.md
│   │   ├── capital-accounts.md               ← partnerships/S-corps; instantiated from `templates/capital-accounts.md.template`; created at first close
│   │   ├── journal-entries.md                ← perpetual non-cash/adjusting JE register; from `templates/journal-entries.md.template`; created at first close
│   │   ├── general-ledger.csv                ← created at first close
│   │   └── transaction-ledgers/               ← created at first close
│   ├── disregarded/<smllc-slug>/             ← nested SMLLCs (no tax/)
│   │   └── {entity.md, corporate/, accounts/, books/, disregarded/...}
│   └── tax/FY<YYYY>/
│       ├── tax-summary.md, pending-docs.md, open-questions.md
│       ├── expenses-log.md                   ← entities/<slug>/tax/FY<YYYY>/expenses-log.md
│       ├── source/
│       │   ├── bank-cc/<account-slug>.csv    ← year-filtered transaction slice (derived, regenerable)
│       │   ├── brokerage/<account-slug>.csv  ← same pattern for brokerage
│       │   ├── k1s-received/, 1099s-received/, contractors-w9/, receipts/
│       ├── quarterly/Q{1..4}/{pnl.md, balance-sheet.md, general-ledger.md, estimate.md, payment.md*}  ← latest presentation; *payment only after reported/evidenced
│       ├── annual/{pnl.md, balance-sheet.md, m-1-reconciliation.md, general-ledger.md, workpapers/}  ← m-1-reconciliation.md instantiated from `templates/m-1-reconciliation.md.template`
│       ├── issued/{1099-nec/, 1099-misc/, 1042-s/, w-2/, k1s-issued/}
│       ├── filed/
│       ├── amended/                          ← created on demand — amended-return workpapers (router item 14)
│       ├── .parsed/
│       └── .computed/                        ← canonical <run-id>-{control.md,estimate.json}; prior runs preserved/superseded
│
├── reference/                                ← distributable library, no PII (optional)
└── archive/                                  ← legacy/inactive
```

## Regarded vs. disregarded (critical)

| Treatment | Location | `tax/`? | `books/`? |
|---|---|---|---|
| Files own return (1065/1120/1120-S) | `entities/<slug>/` | Yes | Yes |
| Disregarded SMLLC under regarded entity | `entities/<parent>/disregarded/<slug>/` | **No** — consolidates into parent | Yes (division) |
| Disregarded SMLLC owned by individual | `individual/disregarded/<slug>/` | **No** — flows to 1040 Sch C/E/F | Yes (division) |
| SMLLC owning SMLLC | `.../disregarded/<a>/disregarded/<b>/` | No at any depth | Yes at each level |
| Individual (1040) | `individual/` | Yes (`FY<YYYY>/`) | Conditional — only with Schedule C or Schedule E |

A disregarded SMLLC has its own legal identity (state registration, separate bank, own W-9) but is a **tax nothing** federally — activity appears on the parent's return as a division. Folder tree mirrors this: separate books and corporate records, shared tax return.

## Individual structure is conditional

Unlike the entity tree, which is created wholesale at init, the individual tree
is **grown as facts appear**. `properties/`, `investments/`, `household/`,
`books/`, and most `FY<YYYY>/source/` subfolders exist only when the taxpayer has
the corresponding facts. A W-2 filer with a standard deduction ends up with
`profile.md`, `carryforwards.json`, and a thin `FY<YYYY>/`. See
`individual/onboarding.md` for what each archetype creates.

Permanent vs. year-scoped is the load-bearing distinction on the individual side:
`records/`, `decisions/`, `properties/`, `accounts/`, and `investments/` outlive any tax year;
`FY<YYYY>/` holds only that year's documents and numbers. The permanence test and
the intake pipeline are owned by `individual/records.md`.

## Accounts are account-level, not year-level

Raw financial statements (bank PDFs, brokerage PDFs, CSV exports) belong to the **account**, not to a tax year. They live at `accounts/<account-slug>/` — statements/ for PDFs, the raw CSV at the root. One account, one home, all years together. **This applies to individuals as well as entities** — `individual/accounts/<account-slug>/`.

Tax folders (`tax/FY<YYYY>/source/bank-cc/` etc.) hold **derived year-slices** — CSVs filtered to that year's transactions, ready for reconciliation workpapers. These are generated by tools (e.g., `tools/chase-statement-parser/`) and can be regenerated any time from the raw account-level source. Don't hand-maintain them.

Rationale: credit-card cycles span calendar year boundaries (Dec 25 – Jan 24), and a single statement PDF contains transactions in two tax years. Keeping raw at account level avoids the split-a-statement dilemma; the year-slice CSV handles the per-year view for tax purposes.
