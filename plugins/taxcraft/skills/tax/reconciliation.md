# Reconciliation Sub-Skill

Audit-defense layer between raw source documents and P&L / balance-sheet generation. Every quarterly and annual close runs reconciliations **before** `quarterly.md` P&L generation or `entities/<type>.md` workpapers. Skipping reconciliation = unverified numbers in a return.

Owns methodology, aging, and sign-off. Naming → `naming.md`. Inputs come from parsed cache per `parsing.md`.

## When to run (by scope)

| Close | Recs required |
|---|---|
| Individual quarterly | Brokerage (if active trading), bank (if Schedule C) |
| Individual annual | + K-1 basis rec, passive-activity basis rec |
| Entity quarterly | Bank/CC, brokerage, intercompany (if multi-entity), AR/AP (accrual), K-1 basis (partner/SH) |
| Entity annual | + fixed-asset rec, intercompany elimination, capital/AAA/E&P rec, Schedule L rollforward |
| Disregarded SMLLC | Runs its own bank rec at nested level; rolls up into parent's rec set before parent's P&L |

## Rec types

### 1. Bank / credit-card rec

**Three-way**: bank statement ending balance ↔ GL ending cash ↔ reconciliation workpaper.

```
Bank statement ending balance       XXX
+ Deposits in transit               XXX
– Outstanding checks                (XXX)
± Bank errors                       XXX
= Adjusted bank balance             XXX
                                    ===
GL ending cash                      XXX
± Unrecorded items (found)          XXX
± Timing items (DIT / OS)           XXX
= Adjusted GL balance               XXX  (must equal adjusted bank)
```

Output: `<scope>/FY<YYYY>/quarterly/Q<n>/recs/bank-<acct-slug>.md`.
Adjusted bank and adjusted GL cash must agree exactly after each supported timing
item. An unexplained cash difference is a close blocker regardless of income-tax
materiality; materiality does not establish cash completeness. A documented
timing item remains open until it reverses in the expected period.

### 2. Brokerage rec

Covered vs. noncovered lot coverage: 1099-B proceeds should tie to broker statement activity ± unrealized changes. Verify wash-sale totals parse to match 1099-B box. Flag basis-of-$0 on covered lots (common error: DRIP reinvest not stepped up).

Output: `recs/brokerage-<broker-slug>-<acct-last4>.md`.

### 3. Intercompany rec (multi-entity workspaces)

Every intercompany transaction must match on both sides of the same ledger. If Entity A books a loan to Entity B for $100k, Entity B must book a loan from Entity A for $100k on the same date, same amount, same classification (note vs. open account).

```
Entity A AR from Entity B           XXX
Entity B AP to Entity A            (XXX)
= Must be zero                        0
```

Non-zero → fix before consolidated P&L. Common failure: one side booked as contribution, other as loan. Tax consequence: §7872 imputed interest, §301 distribution reclass, basis mismatches. Output: `workspace-profile/notes/intercompany-rec-FY<YYYY>-Q<n>.md` (workspace-level because it spans entities).

**Parent ↔ disregarded-SMLLC additions** (same rec, extra invariants — mechanics in `entities/disregarded.md` § Books Consolidation):

```
Parent 1860 Investment in <smllc>     XXX
SMLLC contributed capital, net       (XXX)   (3060 − 3070; RE/current income excluded —
                                              the parent books no equity-method pickup)
= Must be zero                          0

Parent 1300 Due from <smllc>          XXX
SMLLC 2300 Due to parent             (XXX)
= Must be zero                          0
```

Drift = a one-sided or character-mismatched entry since the last clean close — locate it in the JE registers (both tiers cite mirror JE #s) before consolidating. The consolidation elimination entries (E1–E4 in `entities/disregarded.md`) are prepared **from this rec** and saved to `entities/<parent>/tax/FY<YYYY>/annual/workpapers/consolidation-eliminations.md` (quarterly: `quarterly/Q<n>/recs/`).

### 4. K-1 / capital-account rec (partnerships + S-corps)

Partnership — tax capital rollforward per partner:

```
Beginning tax capital (prior K-1 Part II L)         XXX
+ Contributions (L3a)                                XXX
+ Net income allocation (L3c)                        XXX
– Distributions (L3b)                               (XXX)
– Withdrawals                                       (XXX)
= Ending tax capital                                 XXX   (must match K-1 to be issued)
```

S-corp — stock + debt basis rollforward per shareholder, AAA rollforward at entity level. BIG (built-in-gains) window tracking for ex-C-corps inside 5-year watch.

Output: `entities/<slug>/tax/FY<YYYY>/annual/workpapers/capital-rec-<partner-slug>.md`.

**Tracker-to-filed-form tie (part of this rec, every close).** Each carryforward the entity or its partners carry — §704(d) suspended per lower-tier partnership, §163(j) EBIE per originating partnership, §465 per activity, partner-level Form 8582 per activity, §199A loss carryover — is tied to the **filed** form of the prior year (8582 Part VII worksheet, 8990, 6198, 8995 line 16), and the tie is written into `<scope-root>/carryforwards.json`. A figure that ties only to the workpaper that produced the return, or that has no tracker file at all, is a reconciling item: a suspended loss can drop off a filed return, and a carryforward kept only in prose can drift, without anything else in the close noticing.

### 5. Partner outside-basis / S-corp shareholder basis (recipient side)

The partner's/SH's **outside basis** is reconstructed independently of the issuer's capital account — they can diverge (§743(b) adjustments, §704(c) built-in gain, debt-financed basis, etc.). Track per-position in `<scope-root>/carryforwards.json` under `partnership_outside_basis` / `scorp_stock_basis` / `scorp_debt_basis`.

### 6. AR / AP rec (accrual entities only)

GL control account ↔ aged subledger. Aging buckets: 0–30, 31–60, 61–90, 90+. Anything 90+ → bad-debt candidate + §166 analysis.

### 7. Fixed-asset rec (annual)

Beginning basis + additions – dispositions = ending basis. Depreciation expense per `books/fixed-assets.md` ties to Form 4562. §179 / bonus / §168(g) straight-line election decisions flagged. Disposals: §1231/§1245/§1250 recapture calcs.

Output: `entities/<slug>/tax/FY<YYYY>/annual/workpapers/fixed-assets-rec.md`.

### 8. Payroll rec (entities running payroll)

941 Q1–Q4 + W-3 total ↔ GL wages expense ↔ W-2 Box 1 totals. Mismatches pre-filing are cheap; mismatches post-filing may require 941-X + W-2c and related federal/state corrections. Flag S-corp 2%-shareholder health (must be in Box 1 + state). For employee reimbursements, use `scenarios/accountable-plan.md`'s consequence and payroll-timing matrices: only qualifying accountable amounts remain outside wages; failed amounts, unreturned excess, taxable mileage/per-diem excess, and arrangement-level failures enter the proper wage boxes and payroll period.

### 8a. Upstream K-1 pickup (partnership-of-partnerships / holding structure)

Required when a partnership or S-corp holds LP/GP interests in **other** partnerships and must consume their K-1s as a conduit. Often missed — software doesn't auto-populate every box; manual override frequently needed. This is where K-1s silently drop off returns.

**Method — pivot then column-sum**:

Rows = each upstream K-1 received. Columns = every K-1 box that carries a dollar amount (box 1, 2, 3, 5, 6a/6b, 8, 9a, 10, 11, 14a, 17, 19, 20-Z §199A, 20-N §163(j), etc.). Values = dollars.

```
                 box1   box5   box6a  box8   box9a  box10  box14a  box20Z  ...
Upstream A        100      0      0      0      0      0       0     100
Upstream B          0   1,500    200      0      0      0       0       0
Upstream C          0      0      0   (300)  5,000      0       0       0
                 -----  -----  -----  -----  -----  -----   -----   -----
Column sum        100   1,500    200   (300) 5,000      0       0     100
                 =====  =====  =====  =====  =====  =====   =====   =====
Partnership Sch K 100   1,500    200   (300) 5,000      0       0     100  ✓
```

Every column sum must appear on the partnership's Schedule K for the same box / line. Deltas are:
- **Under-pickup** (Sch K < column sum): upstream K-1 was dropped; understatement. Almost always requires amendment.
- **Over-pickup** (Sch K > column sum): double-counted, wrong character, or direct activity mixed in (confirm direct activity exists).

Character carries through. A box-9a LTCG on an upstream K-1 is LTCG on the holding partnership's Sch K, not ordinary. State K-3 apportionment also stacks: the sum of upstream state sourcing becomes the holding partnership's state sourcing.

**§199A rolls per-upstream-trade-or-business**, not aggregated. Each upstream fund's Statement A (QBI, W-2 wages, UBIA, SSTB flag, REIT/PTP indicator) must pass through intact as a separate "trade or business" on the holding partnership's Statement A, unless a §199A aggregation election was properly made.

**§163(j)** business interest rides through box 20-N; excess BIE at upstream is excess at the holding entity.

Output: `entities/<slug>/tax/FY<YYYY>/annual/workpapers/upstream-k1-pickup.md` with the pivot, column sums, the as-filed Sch K row, and a reconciling-items list.

Disregarded SMLLCs holding upstream K-1s: run this rec at the SMLLC's level, then the result consolidates into the regarded parent's Sch K. Don't run separate recs at both levels — single source of truth at the level that actually receives the K-1. Confirm the SMLLC's external results reach consolidated equity (`entities/disregarded.md` § Close procedure step 1a) — the capital-flow symmetry check cannot see a P&L balance the consolidation missed.

**Rows are the K-1s issued TO this entity — nothing higher.** A K-1 that a lower-tier partnership itself received (a *tier-2* K-1, which names *that* partnership as the partner) never appears in the pivot, in Sch K, or in basis; picking one up overstates the return by the lower tier's entire allocated amount. Where it is kept and how it is named is defined in `naming.md` § Tier-2 K-1s; keep it out of `source/k1s-received/`.

**A position that moved during the year is not a pivot row until the transfer facts are settled** — see `entities/partnership.md` Common Issues (transfers).

### 9. Schedule L rollforward (C-corps, balance-sheet 1065s)

Prior-year ending Schedule L = current-year beginning Schedule L. **Must tie to the penny.** Failure here is the single most common IRS-flagged inconsistency on an entity return. Compare to `books/opening-balances.md` — if drift, investigate before closing the year.

## Reconciling-item aging

Every open reconciling item has:

| Field | Values |
|---|---|
| `type` | timing / error / cutoff / unrecorded / unresolved |
| `age_days` | 0–30 / 31–60 / 61–90 / 90+ |
| `materiality` | below threshold / flagged / escalation |
| `disposition` | cleared next period / AJE required / research open |

90+ items auto-escalate to `open-questions.md`. Never file a return with an unresolved 90+ item on a material account without documented rationale.

## Sign-off rule

Every rec file ends with an enforceable approval record. Checked Markdown boxes
without the immutable input manifest, preparer/reviewer identity, dates, and
approval scope do not clear the period.

```
## Sign-off
- Input-manifest hash: <sha256>
- Validation-report hash: <sha256>
- Prepared by / at: <identity> / <timestamp>
- Reviewed by / at: <identity> / <timestamp>
- Approval scope: <accounts, period, artifacts>
- Unresolved-item disposition: <none | exact exclusions and dollar impact>
- Cleared for compute: yes | no
```

`quarterly.md` and `close-estimate.md` check this record before exposing book
values to a computation. A source, source hash, active version, classification,
rule, journal entry, or reconciliation change invalidates the sign-off and all
dependent P&L, variance, estimate, and projected K-1 artifacts. Missing account
coverage, a nonzero unexplained cash difference, or an unresolved quarantine
item with dependent tax impact creates `RECONCILIATION_HOLD`.
