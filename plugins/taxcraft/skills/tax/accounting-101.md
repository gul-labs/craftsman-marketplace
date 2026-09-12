# Accounting 101 for this Workspace

Primer on how professional bookkeeping and tax work are organized — what lives where, and why. Read once. Re-read whenever the folder structure feels arbitrary; it isn't.

## The three timelines

Real bookkeeping has three separate clocks. Conflating them is the #1 source of confusion for self-prepared entities.

| Timeline | Lives for | What belongs here |
|---|---|---|
| **Account timeline** | As long as the account exists (can span years) | Raw evidence from banks, brokers, credit-card issuers: monthly statements, CSV transaction dumps, check images, wire confirmations |
| **Book timeline** | Life of the entity — **perpetual** (never reset) | The entity's actual bookkeeping: chart of accounts, general ledger, fixed-asset register, capital accounts, opening balances, reconciled transaction ledgers |
| **Tax-year timeline** | One fiscal year | A frozen snapshot of the books at year-end + year-bound filing artifacts: trial balance, year-end P&L + balance sheet, workpapers, the filed return, K-1s issued |

**Books do not restart every year.** January 1, 2024 opens with exactly December 31, 2023's closing balances. Your General Ledger runs continuously from entity formation to dissolution.

**Tax is a periodic view of the books.** At fiscal year end you "close" — freeze a trial balance, produce year-end statements, prepare the return. Those artifacts ARE year-bound.

## AICPA framing — "permanent file" vs "current file"

Professional audit methodology (AICPA AU-C §230, firm-standard practice) distinguishes:

- **Permanent file** — info that spans years and carries forward: formation docs, operating agreement, loan agreements, lease terms, ongoing LP positions, depreciation schedules with cumulative basis, capital-account history, chart of accounts. Reviewed each year, rarely changes.
- **Current file** — year-specific workpapers: trial balance, adjusting entries, reconciliations for THAT year, analytical review, the filed return. Closed when the year is filed; read-only after.

Our folder structure maps directly:
- Permanent file → `entities/<slug>/entity.md`, `corporate/`, `books/`, `accounts/`, `disregarded/`
- Current file → `entities/<slug>/tax/FY<YYYY>/`

This is the standard lens a CPA or auditor will bring when reviewing the workspace.
The same split governs prose: operative files state the current answer, decision memos
under `decisions/` are the frozen record, and a changed conclusion is a new memo rather than
an edit — `supersession.md`.

## Folder-to-concept mapping (entity scope)

```
entities/<slug>/
├── entity.md                   ← permanent: who this entity is, EIN, state, config, elections
├── corporate/                  ← permanent: formation, minutes, resolutions, licenses
│   ├── formation/
│   ├── minutes/
│   ├── resolutions/
│   ├── annual-reports/
│   └── licenses/
├── accounts/                   ← permanent: one subfolder per financial account
│   └── <account-slug>/
│       ├── statements/         ← raw monthly PDFs (all years, account-lifetime)
│       ├── all-transactions.csv  ← raw CSV export from financial institution
│       └── check-images/       ← raw aux evidence
├── contracts/                  ← permanent: executed agreements
├── investments/                ← permanent: upstream LP/GP K-1 positions, PPMs, sub docs
├── properties/                 ← permanent: directly-owned real estate
├── books/                      ← PERPETUAL — the entity's continuous bookkeeping
│   ├── README.md                ← seeded at init; orients a reader to this books/ folder
│   ├── chart-of-accounts.md    ← the COA (account list, never FY-scoped)
│   ├── opening-balances.md     ← formation-to-first-FY trial balance
│   ├── fixed-assets.md         ← perpetual asset register with accumulated depreciation
│   ├── capital-accounts.md     ← perpetual per-partner / per-shareholder basis roll-forward (partnerships/S-corps; created at first close)
│   ├── journal-entries.md      ← perpetual register of non-cash / adjusting / reclass entries (from `templates/journal-entries.md.template`)
│   ├── general-ledger.csv      ← the actual GL — posted, categorized, all-time (created at first close)
│   └── transaction-ledgers/    ← reconciled cashbooks per account, pre-categorization (created at first close)
├── disregarded/                ← permanent: nested SMLLCs (books + corporate only, NO tax/)
│   └── <smllc-slug>/
│       ├── entity.md
│       ├── corporate/
│       ├── accounts/           ← same account-level structure at the SMLLC level
│       └── books/              ← SMLLC's perpetual books (rolls into parent's GL)
└── tax/                        ← CURRENT — year-bound work
    └── FY<YYYY>/
        ├── tax-summary.md      ← living workpaper for this year
        ├── source/             ← year-scoped source docs + derived year slices
        │   ├── bank-cc/<account-slug>.csv  ← year-filtered slice of the cashbook (derived)
        │   ├── k1s-received/   ← upstream K-1s for this tax year
        │   ├── 1099s-received/
        │   ├── receipts/
        │   └── contractors-w9/
        ├── quarterly/          ← quarterly closes within this FY
        ├── annual/             ← year-end close artifacts
        │   ├── pnl.md          ← year-end P&L
        │   ├── balance-sheet.md ← year-end balance sheet (Schedule L content)
        │   ├── m-1-reconciliation.md  ← book-to-tax
        │   ├── general-ledger.md      ← GL extract for this year
        │   └── workpapers/     ← bank rec, intercompany elim, upstream K-1 pickup, etc.
        ├── issued/             ← K-1s, 1099s, W-2s this entity ISSUED this year
        ├── filed/              ← the filed return + confirmation
        ├── amended/            ← amended-return workpapers (if applicable)
        └── .parsed/            ← JSON cache of parsed documents
```

## The data flow

The work moves in one direction — evidence becomes books, books become tax:

```
[Evidence]                    [Books]                        [Tax year]
accounts/                     books/                          tax/FY<YYYY>/
├─ statements/      ──────→   ├─ transaction-ledgers/        ├─ source/bank-cc/ (year slices)
├─ all-transactions  (parse    ├─ general-ledger       ──→   ├─ annual/workpapers/ (recs)
│   .csv            + recon)   ├─ capital-accounts            ├─ annual/pnl.md
└─ check-images/               ├─ fixed-assets                ├─ annual/balance-sheet.md
                               └─ chart-of-accounts           └─ filed/<return>.pdf
```

Each step is an independent verification layer:
1. Raw evidence proves what actually happened financially.
2. Transaction ledger proves our data matches the bank to the penny (reconciliation).
3. GL proves each transaction is classified into the right COA account.
4. Year-end statements prove the books close cleanly.
5. Filed return proves what was reported to tax authorities.

An audit walks this chain backwards: return → supports → GL posting → ledger entry → bank statement. Break any link and the audit trail is broken.

## Non-cash transactions — the second source of truth

Bank-feed-driven books have a blind spot: **only cash movements arrive automatically.** Everything else — property contributed for equity, an expense paid from a personal card, depreciation, an accrual, an intercompany fee settled by offset, an equity reclass — exists in the books only if someone posts it. The `books/journal-entries.md` register (instantiate from `templates/journal-entries.md.template`) is where every such entry lives: sequentially numbered, dated, DR/CR with COA accounts, and citing its authority (resolution, receipt, statute).

Two rules keep this honest:

1. **Every close runs the non-cash sweep** in the register template before the trial balance is trusted — the P&L cannot be complete while an unposted contribution or unaccrued expense is sitting outside the GL.
2. **Equity and intercompany entries carry their paper.** A credit to member capital names the documented contribution or issuance it belongs to; an intercompany entry names its mirror JE on the affiliate's books. This is what makes multi-tier structures reconcilable — see `entities/disregarded.md` § Books Consolidation for the parent/sub mechanics and elimination entries.

## Why `books/` has no FY subfolder

Because the books are *one perpetual record*. The entity has one chart of accounts across all years. One perpetual GL. One capital-account history spanning formation to today.

Year-bound views of the books (this year's P&L, this year's balance sheet) live in `tax/FY<YYYY>/annual/` as reports generated FROM the books, not as separate copies of them. Do not create `books/FY2024/` — that confuses the permanent/current file distinction.

## Common confusions

- **"Should this statement go in books/ or tax/?"** It's raw evidence — it goes in `accounts/<slug>/statements/`. Never in `books/` (that's for reconciled, posted data) or `tax/<year>/` (that's for year-bound artifacts).
- **"The transaction ledger spans years — should I split it per FY?"** No. The ledger is part of the books (perpetual). Per-FY filtered CSVs go to `tax/FY<YYYY>/source/bank-cc/` as derived outputs.
- **"Where does a capital call wire transfer go?"** Two places. The wire PDF (raw) → `investments/<fund-slug>/` (or `accounts/<account-slug>/check-images/` if it came through the bank's portal). The accounting entry → posted to the GL inside `books/`. The per-year transaction shows in the year slice inside `tax/<year>/source/`.
- **"A CC statement crosses Dec/Jan — which year?"** The raw statement goes to `accounts/<cc-slug>/statements/` regardless of cycle. The year-split happens in the derived year-slice CSVs (transactions dated Dec 23–31 land in that year's slice; Jan 1+ in the next year's).

## CPA / audit handoff

When handing books to a CPA, the scope of their engagement drives what they need:
- **Tax-return prep only**: give them `tax/FY<YYYY>/` + access to `books/` and `accounts/` for support
- **Compilation**: same, plus time to review `books/` reconciliation quality
- **Review** (limited assurance): access to everything + intercompany documents + representation letter
- **Audit** (reasonable assurance): full workpapers with sign-off trail, confirmations from third parties, the whole permanent file going back years

Our structure supports all four; the CPA will recognize it on sight.

## Not in the textbooks — workspace-specific conventions

Filesystem-based bookkeeping differs from software-based in two small ways:
1. **Per-year derived slices** (`tax/FY<YYYY>/source/bank-cc/<account>.csv`) — in QuickBooks, you'd query the GL for a year view instead of storing a separate file. We store the slice for efficiency since filesystem-native tooling can't query a CSV.
2. **Tools folder** (the tax skill's `tools/`) — utilities that produce derived outputs. In a firm, this would be macro-embedded Excel workbooks or pulled from firm software. Functionally equivalent.

Both are reasonable filesystem-native adaptations. Neither changes the underlying accounting logic.
