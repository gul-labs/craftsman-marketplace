
# Disregarded Entities Sub-Skill

Handling of single-member LLCs (SMLLCs) that are disregarded for federal tax — the SMLLC is a **legal** entity (state registration, own bank account, separate liability shield) but a **tax nothing** federally. Its activity appears on the regarded owner's return as a division.

## Who this applies to

- **Default rule**: a single-member LLC is disregarded under Reg §301.7701-3 unless it elects otherwise (Form 8832 → C-corp; Form 2553 → S-corp).
- **Owner types that consume disregarded SMLLCs as divisions**:
  - Individual owner → SMLLC activity on Schedule C / E / F of 1040
  - C-corp owner → SMLLC consolidated into 1120
  - S-corp owner → SMLLC consolidated into 1120-S
  - Partnership owner → SMLLC consolidated into 1065
  - Another disregarded SMLLC → passes through transparently to the ultimate regarded owner

## Folder Structure

Disregarded SMLLCs nest under their regarded owner. Two cases by owner type:

### Case A — Entity-owned (regarded parent is a C-corp / S-corp / partnership)

```
entities/<regarded-parent-slug>/
├── entity.md
├── corporate/
├── books/
├── tax/FY<YYYY>/                     ← the tax return lives here (1120 / 1065 / 1120-S)
└── disregarded/
    └── <smllc-slug>/
        ├── entity.md                 ← state registration, mail address, own bank acct
        ├── corporate/                ← SMLLC's formation docs, operating agreement, BOIR
        ├── accounts/                 ← separate bank/brokerage accounts
        ├── books/                    ← division-level bookkeeping
        ├── contracts/
        └── disregarded/              ← recursive: SMLLC-owning-SMLLC allowed
        ↑ NO tax/ folder
```

### Case B — Individual-owned (regarded owner is the individual)

```
individual/
├── profile.md
├── carryforwards.json
├── FY<YYYY>/                         ← the individual's 1040 tax years live here
└── disregarded/
    └── <smllc-slug>/                 ← kebab-case slug of the SMLLC's legal name
        ├── entity.md                 ← state registration, own EIN (for state purposes)
        ├── corporate/                ← formation, annual reports, BOIR, renewals
        ├── accounts/                 ← separate bank account if any
        ├── books/                    ← activity tracked here; rolls into 1040 Schedule C/E/F
        └── contracts/
        ↑ NO tax/ folder — activity hits the individual's 1040 directly
```

The SMLLC's activity flows to:
- Ordinary trade/business → **Schedule C** of 1040
- Rental real estate → **Schedule E** of 1040
- Farming → **Schedule F** of 1040

The SMLLC files no federal **income tax** return. Two carve-outs:

- **Foreign-owned SMLLC — Form 5472 (the $25,000 trap).** A domestic SMLLC wholly
  owned by a **foreign person** is treated as a corporation *solely* for §6038A
  reporting (Reg §301.7701-2(c)(2)(vi)). It must obtain **its own EIN** and file a
  **pro forma Form 1120 with Form 5472 attached** — on paper or by fax, not
  e-filed — by the 1120 due date, reporting reportable transactions with related
  parties (including contributions and distributions). The §6038A(d) penalty is
  **$25,000 per year, per form**, assessed **independently of any tax owed**.
  "A tax nothing federally" is exactly the reasoning that misses this. The same
  Form 5472 obligation applies to any **25%-foreign-owned domestic corporation**.
  Escalate cross-border ownership to counsel — `governance.md`.
- **State filings** (B&O, franchise, minimum-fee, unincorporated business taxes)
  may still be required separately — see "State-Level Traps" below.

**Why no `tax/` folder**: the SMLLC files no federal return. All tax work — source documents, quarterly closes, annual P&L, issued K-1s/1099s, filed returns — happens at the regarded-parent level, which consolidates the SMLLC as a division.

**Exception — state**: some states regard SMLLCs separately (e.g., WA B&O tax treats them as distinct taxpayers; TX franchise tax; NYC unincorporated business tax). When a state registration requires its own filing, that state-return file lives at `entities/<parent>/tax/FY<YYYY>/filed/` but named clearly (e.g., `<smllc-slug>-wa-boi-fy<YYYY>.pdf`). Document state-by-state treatment in the SMLLC's `entity.md`.

## Books Consolidation

Each SMLLC keeps its own books at `entities/<parent>/disregarded/<smllc-slug>/books/`:

- `chart-of-accounts.md` — mapped to the parent's COA so consolidation is mechanical
- `fixed-assets.md` — SMLLC-specific assets
- `opening-balances.md` — SMLLC's ending trial balance prior year
- `journal-entries.md` — the SMLLC's own non-cash JE register (see `accounting-101.md`)

### The two-tier equity model (get this right or money falls through the floor)

Each tier's books must be **independently complete** — the SMLLC is a full double-entry set of books with its own equity section, not a bag of transactions inside the parent's GL. The tiers mirror each other:

| Event | Parent's books | SMLLC's books |
|---|---|---|
| Parent funds the SMLLC (capital) | DR `1860 Investment in <smllc>` / CR `1010 Cash` | DR `1010 Cash` / CR `3060 Member capital — <parent>` |
| SMLLC distributes cash up | DR `1010 Cash` / CR `1860 Investment in <smllc>` | DR `3070 Member distributions` / CR `1010 Cash` |

> **Authorising document**: a cash-up distribution needs a consent before the transfer, not after. See `governance.md` → *Distributions from a disregarded SMLLC to its parent/member*, which instantiates `templates/member-distribution-consent.md.template`.

| Parent lends to SMLLC (loan, not capital) | DR `1300 Due from <smllc>` / CR `1010 Cash` | DR `1010 Cash` / CR `2300 Due to <parent>` |
| Parent pays an SMLLC expense directly | DR `1860 Investment` (or `1300 Due from`) / CR `1010 Cash` | DR expense / CR `3060 Member capital` (or `2300 Due to`) |
| SMLLC pays a parent expense directly | DR expense / CR `1860 Investment` (or CR `2300 Due to <smllc>`) | DR `3070 Member distributions` (or `1300 Due from parent`) / CR `1010 Cash` |
| Intercompany fee (documented) | DR expense / CR `1010 Cash` | DR `1010 Cash` / CR fee income |

Rules that make consolidation mechanical instead of forensic:

- **Every cross-tier transfer is booked on BOTH sets of books, same date, same amount, same character** (capital vs. loan vs. fee — decide at the time of the wire, and say so in the memo line). One-sided or character-mismatched bookings are the root cause of equity that "disappears" between tiers.
- **The symmetry invariant** (capital flows only — the parent does NOT book equity-method pickup of the SMLLC's earnings): parent's `1860 Investment in <smllc>` must equal the SMLLC's `3060 Member capital − 3070 Member distributions`, and `1300 Due from` must equal the mirror `2300 Due to`, at every close. The SMLLC's retained earnings and current income sit only on the SMLLC's books until consolidation stacks them in as division results. Check the invariant every close — a drift means a one-sided or character-mismatched entry since the last clean close. (A `1860` balance driven negative by distributions of accumulated earnings is arithmetically fine but flag it: confirm the distributions were earnings, not an unbooked capital event.)
- **Non-cash funding still gets a JE.** Property contributed, expenses paid personally/by-the-other-tier, or debt forgiven never hit a bank feed — post them through each tier's `books/journal-entries.md` register or they simply won't exist. This is the classic way a capital contribution goes untracked for months.
- Character matters for tax even though the entity is disregarded: mislabeling capital as a loan invites §7872 imputed interest and reclass questions; the intercompany rec in `reconciliation.md` § 3 polices this.

### Elimination entries at close

Consolidation = SMLLC trial balance stacked onto the parent's as a division, **then eliminate everything that is internal to the combined entity** (a disregarded sub is the same federal taxpayer — internal flows must not gross up income, expenses, assets, or equity):

| # | Eliminate | Entry (consolidation workpaper only — never posted to either tier's books) |
|---|---|---|
| E1 | Investment vs. contributed capital | DR `3060 Member capital` (balance) / CR `3070 Member distributions` (balance — it is debit-normal, so eliminating it is a credit) / CR `1860 Investment in <smllc>` (net). The SMLLC's retained earnings and current income are **not** eliminated — they are the division's external results and carry into consolidated income/RE |
| E2 | Intercompany loans | DR `2300 Due to parent` / CR `1300 Due from <smllc>` |
| E3 | Intercompany fees/charges | DR fee income (recipient) / CR expense (payer) |
| E4 | Intercompany transfers misbooked as income/expense | Reclass to the transfer accounts above, then E1/E2 |

**After eliminations**: consolidated income = the tiers' external income only; consolidated equity = parent's own equity + the SMLLC's cumulative undistributed external earnings. If it doesn't tie to that, an elimination is missing or a tier's books are one-sided.

### Close procedure

1. Close the SMLLC's own books first: bank rec, JE register posted, trial balance produced.
1a. **Confirm the SMLLC's external results actually reach consolidated equity.** The symmetry invariant in step 2 compares *capital flows only* (investment ↔ member capital, due-from ↔ due-to) — by design it says nothing about the SMLLC's income and expenses, which are carried into the consolidation as the division's results. So a year-end where the SMLLC's P&L never made it into the stacked trial balance passes step 2 and still misstates the parent's equity (and, for a partnership parent, each partner's capital) by the whole amount. Before step 3, tie **consolidated equity = parent's own equity + the SMLLC's cumulative undistributed external earnings** (the "after eliminations" test above) and list every SMLLC `Income:*` / `Expenses:*` balance for the year as a line in the consolidation workpaper; a balance that appears in neither the stacked P&L nor a documented elimination is the finding. Do **not** invent a parent-side `1860` entry to "push up" SMLLC earnings — that is equity-method pickup, which this model forbids, and it double-counts against E1. Close the SMLLC's P&L to its own equity section on its own ledger as part of step 1; items dated after year-end belong to the next year.
2. Verify the symmetry invariant (investment = member equity; due-from = due-to). Fix at the tier level before consolidating.
3. Stack trial balances by division; post E1–E4 on the consolidation workpaper.
4. Consolidated P&L shows tiers as columns + eliminations column + total.
5. Save the workpaper at `entities/<parent>/tax/FY<YYYY>/annual/workpapers/consolidation-eliminations.md` (quarterly closes: `quarterly/Q<n>/recs/`).

See `entities/c-corp.md` § CSV → Form 1120 P&L Generation for the consolidated output format, and `reconciliation.md` § 3 for the intercompany rec that gates this.

## W-9 and EIN Handling (Critical — Frequent Error)

A disregarded SMLLC does **not** use its own EIN (if it has one) when providing a W-9 to a payer. From the IRS Form W-9 instructions:

- **Name line**: the regarded owner (the individual OR the parent entity)
- **Business name line**: the disregarded SMLLC
- **Tax classification**: matches the regarded owner (e.g., "C Corporation" if parent is a C-corp)
- **TIN**: the regarded owner's EIN/SSN, NOT the SMLLC's EIN (even if SMLLC has one for payroll/excise tax purposes)

**Common error**: SMLLC gets its own EIN for payroll, then uses that EIN on W-9s to customers → 1099s issued to the SMLLC's EIN → IRS matching fails → CP2000 notices to the regarded owner for unreported income.

Fix at intake: verify every W-9 this entity issues uses the regarded-owner EIN. Track in `entities/<parent>/accounts/w9.pdf`.

## K-1 Received by a Disregarded SMLLC

When a disregarded SMLLC is a partner/LP in someone else's partnership, the K-1 issued to it should show:

- **Partner name**: the regarded owner (NOT the SMLLC)
- **Partner EIN**: the regarded owner's EIN
- **Partner type**: matching the regarded owner (Partnership / Corporation / Individual)
- **Disregarded Entity Name**: the SMLLC name (separate row)
- **Disregarded Entity TIN**: the SMLLC's EIN if it has one, else blank

**Example** (a disregarded SMLLC owned by a partnership):
- Partner: `<Regarded Partnership Name>` (partnership EIN XX-XXXXXXX)
- Partner type: Partnership
- Disregarded Entity: `<SMLLC Legal Name>` (EIN XX-XXXXXXX, if the SMLLC has one)

If you receive a K-1 with the SMLLC as the partner (wrong), request a corrected K-1 from the issuer. Do not import it as-is — it will cause EIN matching failures.

## Dual-K-1 Sister-Entity Structure (GP + LP in the same fund)

A common setup in closely-held portfolios: the owner fragments their interest in a fund across two sister entities — one holds the **GP interest** (often a C-corp or S-corp, to absorb management-fee income and SE-like charges), and the other holds the **LP interest** (often a partnership SMLLC combination, to hold passive capital). Same fund, two separate interests, two separate K-1s.

Example structure:
- **GP Corp** (C-corp or S-corp) — holds the GP interest in Example Fund SPE LLC.
- **Family Partnership LLC** (partnership, holding through a disregarded SMLLC) — holds the LP interest in the same fund.
- The fund issues **two K-1s**: one to GP Corp (GP — usually carries management-fee income, possibly SE-character, box 14a), one to Family Partnership (LP — usually portfolio character).

Each K-1 stands alone. They are not aggregated at any level because the two recipient entities are separately regarded taxpayers.

**Expected pattern for most deals**: the GP entity and the LP entity both appear in the same fund. Exceptions (a fund held GP-only by the partnership, with no corresponding corporate interest) need explicit documentation in the entity configs. If a fund shows up with only one K-1 when the standing structure implies two should exist, that is a gap — either the second K-1 is missing or the subscription docs need re-reading.

### When a K-1 lands in the wrong sister's folder

Symptoms — K-1 is in a sister's source folder but:
- The partner-name shown on the K-1 doesn't match the folder's regarded owner, OR
- The GP/LP character doesn't match that entity's stated holding (e.g., a GP K-1 ends up in the LP entity's folder).

Treatment — log to the correct sister's follow-up queue at `entities/<parent-slug>/cross-entity-followup-log.md`; don't silently re-file across entities without a reconciliation pass. If the log doesn't exist yet, instantiate it from `templates/cross-entity-followup-log.md.template` (open items table: target entity, tax year, issue, evidence, priority, status, opened, picked-up; plus a closed-items table for audit trail). Cross-entity K-1 moves can hide behind-the-scenes issues (subscription-doc contradictions, cap-table drift, issuer data-entry errors). Document the move and evidence. **Mask SSNs/EINs/account numbers to last-4 digits only** in this log — see the Privacy section of the tax skill's `SKILL.md`.

Tax character is sister-specific: a C-corp GP pays tax on K-1 income at 21% (plus possible §531 AET if retained); a partnership LP allocates to individual partners at their marginal rates. Routing a K-1 to the wrong sister changes both the rate and the character. This is not a cosmetic error.

## 1099 Issuance By a Disregarded SMLLC

When the SMLLC pays a contractor:
- The 1099-NEC issuer is the **regarded parent** (the parent's EIN on the 1099).
- The SMLLC's name can appear as "Trading As / DBA" on the 1099 (box for filer's name).
- File through the regarded parent's IRIS / FIRE account.

## Payroll

If the SMLLC runs payroll (its own W-2 employees):
- The SMLLC **uses its own EIN** for payroll tax purposes (Forms 941, 940, W-2/W-3, state UI) — Reg §301.7701-2(c)(2)(iv) exception.
- But the wage expense still consolidates onto the regarded parent's 1120/1065/1120-S.
- The SMLLC files its own 941/940/W-2s but no 1120/1065.

Document the SMLLC's payroll EIN in its `entity.md` and flag the dual-EIN situation clearly.

## Recursive Disregarded (SMLLC-owning-SMLLC)

Legally permitted. Example: C-corp → SMLLC-A → SMLLC-B.

- SMLLC-A and SMLLC-B are both disregarded.
- SMLLC-B's activity flows through SMLLC-A (invisible) to the C-corp.
- Folder: `entities/c-corp-slug/disregarded/smllc-a-slug/disregarded/smllc-b-slug/`
- Consolidation: merge SMLLC-B into SMLLC-A's books → merge into C-corp.

## When a Disregarded SMLLC Becomes Regarded (or vice versa)

- Addition of a second member → default to partnership (file Form 1065) starting from that date.
- Election to be taxed as S-corp (Form 2553) or C-corp (Form 8832) → regarded from election effective date.
- Treat as a mid-year conversion: prior-portion activity flows to regarded owner as disregarded; post-conversion activity starts a new regarded tax year.
- **Re-structure the folder** at conversion: move the SMLLC out of `disregarded/` into `entities/<new-slug>/` with its own `tax/` folder. Document the transition in `workspace-profile/history.md`.

## State-Level Traps

- **Washington B&O** — SMLLC typically has its own DOR account and B&O filings even when federally disregarded. File separately.
- **California LLC fee / franchise tax** — disregarded SMLLCs still owe $800 minimum + gross-receipts fee on Form 568.
- **Texas franchise tax** — combined report may include disregarded SMLLC in the parent's combined group.
- **NYC UBT** — disregarded SMLLCs can be separately subject if doing business in NYC.

Always check the SMLLC's state of formation + states of operation separately from the parent's.
