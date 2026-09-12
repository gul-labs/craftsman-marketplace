
# Partnership (Form 1065) Sub-Skill

For multi-member LLCs taxed as partnership, general/limited partnerships, and LLPs. Output feeds each partner's K-1.

## Preflight (beyond common)

1. **Qualified Joint Venture check** — MFJ spouses in a community-property state (AZ, CA, ID, LA, NV, NM, TX, WA, WI) can elect QJV under Rev. Proc. 2002-69 (two Schedule Cs) instead of filing 1065. Evaluate admin-cost tradeoff. If both spouses work in the business and live in a community-property state, surface this option.
2. **§761(a) election** — investment partnerships with no active business can elect out of Subchapter K. Rare; flag only if clearly passive co-ownership.
3. **Partnership Representative (PR)** — required post-BBA (Bipartisan Budget Act of 2015); appointed on Form 1065 page 3. Confirm designation.
4. **PTET election status** — many states allow pass-through entity tax elections as a SALT-cap workaround. Confirm whether entity elected; affects estimated payments + partner K-1 box 15 credit.

## 1065 Flow

1. **Schedule K** — aggregate separately-stated items (ordinary, rental, interest, dividends, capital gains, §1231, §179, charitable, foreign, AMT items, §199A info).
2. **Allocate to partners via Schedule K-1**:
   - Respect §704(b) substantial economic effect (safe harbor: capital account maintenance per Reg §1.704-1(b)(2)(iv) + liquidation per capital accounts + DRO or QIO)
   - §704(c) built-in gain/loss on contributed property — traditional, curative, or remedial method; stick with the method chosen at contribution
   - Guaranteed payments under §707(c) — separately stated; deductible above the line; SE income to recipient
   - Targeted allocations — common in deal partnerships; model distributions to match economics
3. **Capital account rollforward** — **tax basis method** (required for most since 2020):
   - Beginning + Contributions + Net income (tax basis) − Distributions = Ending
   - Reconcile to §704(b) book basis separately if they differ
   - Instantiate `entities/<slug>/books/capital-accounts.md` from `templates/capital-accounts.md.template` at first close
4. **Outside basis tracking** (per partner, not on return but critical for loss deduction)
   - Basis = contributions + income allocated + share of liabilities − distributions − losses allocated
   - **§752 allocations**: recourse debt → per economic risk of loss; nonrecourse → per profit-sharing + §704(c) minimum gain
   - **§465 at-risk**: separately from basis; nonrecourse debt generally not at-risk unless qualified nonrecourse (QNR — real estate, from qualified persons)
   - **§469 passive**: separately tracked per activity
   - **§704(d) ordering — get it right or the suspended figure is wrong.** The loss is tested against basis at the *end* of the partnership year, after that year's income and after distributions already taken into account (Reg. §1.704-1(d)(2); §705(a)(2); Rev. Rul. 66-94 ⚠). A reviewer who "adds the income to basis" and forgets the distribution will announce a release that does not exist. Distributions themselves are tested at a different moment — against basis immediately before each one (§731), with year-end treatment only for advances or drawings against the current year's share (Reg. §1.731-1(a)(1)(ii)) — see the cash-classification item in the checklist below; keep the two tests separate.
   - **Zero-capital GP / promote interests with a negative capital account are normal, not defective.** Losses funded by nonrecourse debt may be allocated to a partner with no capital and no DRO under the nonrecourse-deduction rules of Reg. §1.704-2, and the partner's §752 share of that debt (K-1 Item K) is what gives the partner basis to absorb them under §704(d). Two separate questions, answered separately: (i) **basis** — Item K supports it; (ii) **allocation validity** — an Item K share does *not* establish that the allocation is respected under §704(b)/Reg. §1.704-2; that requires the partnership agreement's conditions (capital-account maintenance, the minimum-gain chargeback, consistency with the partners' interests, and the liquidation/DRO-or-QIO provisions). Review (ii) from the agreement before treating a negative-capital promote as merely "normal"; do not skip it because Item K is populated, and do not reject it because capital is negative. **A loss allocation with Item K blank and Item L blank or zero is a fact to resolve, not a basis conclusion:** Item L is tax-basis capital, not outside basis, and a blank field proves nothing either way. Build the full outside-basis rollforward (contributions, prior allocations, distributions, liability shares) and obtain the lower tier's liability allocation. Reg. §1.752-4(a) is mechanical, not the sponsor's option — the upper-tier partnership's share of a lower-tier partnership's liabilities *is* a liability of the upper tier for §752 — so the question to put to the sponsor is what the upper tier's share actually is, not whether debt was "meant to" pass down. Until that share is established, apply §704(d) to the basis you can document and record the open question; never claim basis the K-1 does not report.
   - **Where it lives:** `<scope-root>/carryforwards.json` (from `templates/carryforwards.template.json`, `scope: "entity"`) carries the partnership-level `section_704d_suspended_losses` per lower-tier partnership, EBIE by originating partnership, credits passed through, and the §6221(b) election record. **Instantiate it at the first close; a §704(d) carryforward that exists only in prose is not tracked.** `books/passive-loss-tracker.md` (or the individual's `carryforwards.json`) carries the partner-level Form 8582 figures — and at every close both are reconciled to the **filed** forms (8582 Part VII worksheet, 8995 line 16, 8990, 6198), not to the workpapers that fed them. A carryforward that does not tie to the filed form is a finding, not a balance.
5. **§754 election** — optional; once made, applies to future transfers:
   - §743(b) step-up/down on partnership-interest transfer (death, sale)
   - §734(b) adjustment on distributions causing inside/outside disparity
   - Mandatory adjustment if substantial built-in loss (>$250k) or substantial basis reduction
6. **Schedule M-1 / M-3** — book-tax reconciliation. M-3 required if $10M+ assets. Instantiate `annual/m-1-reconciliation.md` from `templates/m-1-reconciliation.md.template`.
7. **Schedule L** — balance sheet (required if > $250k assets OR receipts; always recommend).
8. **Schedule B-1 / B-2** — ownership disclosures (>50% owners; entities owning >50%).
9. **K-2 / K-3** — international items. Required for most partnerships unless domestic-filing exception is met (notify partners by 1 month before filing deadline; no partner requests K-3; no foreign activity; specific partner-type limits). Default to **filing** unless exception clearly applies.

## Common Issues Checklist

- [ ] Guaranteed payments correctly classified (box 4a/4b)
- [ ] Box 14 self-employment income computed correctly (general partners + LLC managers usually SE; limited partners generally not under §1402(a)(13), subject to recent cases — *Soroban*, *Denham Capital* — tightening this)
- [ ] Box 20 code Z §199A detail complete: QBI, W-2 wages, UBIA per trade or business
- [ ] Box 20 code N business interest expense (for §163(j) at partner level)
- [ ] State apportionment sheet per state with nexus
- [ ] Composite return / PTE election properly reflected
- [ ] Final K-1 mark if partner left
- [ ] §754 step-up reflected in depreciation if transfer occurred
- [ ] Disregarded SMLLCs consolidated into the partnership's books (their activity is partnership activity; their own W-9 might show SMLLC name but EIN is partnership's)
- [ ] Recourse vs nonrecourse liability allocation on K-1 item K correct
- [ ] **Ownership percentages come from the operating agreement's schedule / certification of members, never from counting signatures.** A signature block lists who signed, not what they own; members are routinely unequal. Read every section of the governing document before asserting a percentage, and confirm against the issuer's filed return (K-1 summary schedule) when it is on hand. An arithmetic coincidence (a fee ÷ a round percentage) is not evidence.
- [ ] **Tier-2 ("upstream of the upstream") K-1s are never picked up.** Location, filename and the required README are defined once in `naming.md` § Tier-2 K-1s; the pivot rule is in `reconciliation.md` § 8a. Use such a K-1 only to frame questions for the sponsor (its liability share, fee flows, year of inclusion).
- [ ] **Transfers of a partnership interest into or out of the entity are a fact-gathering exercise, not a K-1 read.** Obtain the agreement and closing documents, the transferor's (usually *Final*) K-1 and the transferee's K-1 as corroboration, and then: the issuing partnership carries the transferor's capital account over to the transferee (Reg. §1.704-1(b)(2)(iv)(l)) — so Item J "beginning = ending" on the transferee's K-1 is the issuer's convention for a mid-year admittee, not proof of full-year ownership; the transferee's **outside basis** is a separate computation — cost under §742/§1012 on a purchase, or the contributor's basis under §721/§723 where the interest was *contributed* to the transferee partnership; the year's items are split under §706(d) and Reg. §1.706-4 per the method the issuer actually used; and §743(b)/§754 are considered where a §754 election is in place or the interest was purchased. The K-1s corroborate; they do not decide.
- [ ] **Cash received from a lower-tier partnership that its K-1 does not report gets a classification hold before it gets a line.** It may be a distribution, a loan, an expense reimbursement, a redemption or purchase payment, a §707(c) guaranteed payment, a prior-year item, or a payment the books misidentified. Obtain the issuer's explanation and, where possible, its return/K-1 workpapers; do **not** pick it up as a current-year §702 share on the strength of a bank credit, an operating-agreement clause, or a K-1 the lower tier itself received for an *earlier* year — a distributive share belongs to the partnership's taxable year (§706(a)). If it is a distribution: §731 tests the money against basis **immediately before the distribution**; the current year's income allocation counts at that moment only for an advance or drawing against the current year's distributive share, which Reg. §1.731-1(a)(1)(ii) deems made on the last day of the year — a payout of a prior-year item is not such an advance. Gain to the extent of the excess is §731(a)(1)/§741 gain, tested for §751 ordinary recharacterization; its §469 character depends on the disposition-and-attribution analysis under Reg. §1.469-2T(e)(3), not on a label; SE and QBI character are analyzed, not assumed. The year-end §704(d) test then runs separately on basis after the year's income (Reg. §1.704-1(d)(2)) — the two tests use different moments, and conflating them moves dollars between lines. Form 8082 is filed only when the taxpayer is taking an inconsistent-treatment position under the regime that applies to the issuer — see `scenarios/contested-k1.md` — and the earlier-year omission goes to a separate amend-or-disclose decision for *that* year. Reporting "more income" in the wrong year is still the wrong year — a character-neutral "other income" line is not a cure either.
- [ ] **Two versions of the same K-1** — no figure from either goes on the return until the controlling version is settled per `parsing.md` § Two versions of one document (that section owns the rule). Separately: a figure quoted by another partner may be a statement line (e.g., the §199A rental amount), not the box.
- [ ] **UPE (unreimbursed partner expenses)** — home office, mileage, cell claimed by a partner on Schedule E page 2 as a separate "UPE" line are deductible **only if the partnership agreement or an established practice requires the partner to bear them without reimbursement**. If the agreement is silent **and no established practice exists**, or reimbursement was available and simply not sought, the deduction is **denied** (*Klein v. Comm'r*, 25 T.C. 1045 (1956); *McLauchlan v. Comm'r*, T.C. Memo. 2011-289, aff'd 558 F. App'x 374 (5th Cir. 2014)). Fix the agreement or adopt a partnership expense-reimbursement policy; do not label a partner an employee under Reg §1.62-2. UPE also reduces SE income. See `scenarios/accountable-plan.md` for the worker-capacity gate and `scenarios/home-office-280a.md` for qualification and computation.

## Basis Workpaper Template (per partner, per year)

```json
{
  "owner": "<name>",
  "entity": "<entity>",
  "tax_year": 2025,
  "outside_basis": {
    "beginning": 0,
    "contributions_cash": 0,
    "contributions_property_fmv": 0,
    "contributions_property_basis": 0,
    "share_income_ordinary": 0,
    "share_income_separately_stated": 0,
    "share_liabilities_beginning": 0,
    "share_liabilities_ending": 0,
    "distributions_cash": 0,
    "distributions_property_basis": 0,
    "share_losses": 0,
    "ending": 0
  },
  "at_risk_465": 0,
  "passive_suspended_469": 0,
  "§199A_component": {
    "qbi": 0,
    "w2_wages": 0,
    "ubia": 0,
    "sstb_flag": false
  },
  "§704c_built_in_gain": 0
}
```

Save per partner: `entities/<slug>/tax/FY<YYYY>/annual/workpapers/basis-<partner-slug>.json`

## Nested Disregarded SMLLCs

If this partnership owns a disregarded SMLLC:

- SMLLC activity lives in `entities/<partnership-slug>/disregarded/<smllc-slug>/books/`
- Consolidate into the partnership's P&L as a division; no separate 1065 for the SMLLC
- On K-1s the partnership issues upstream, the SMLLC is invisible — partners see their pro-rata share of consolidated activity
- On K-1s the SMLLC receives from its own LP positions, the K-1 shows the SMLLC's name but the **regarded owner** (the partnership) is the tax partner — see `entities/disregarded.md` for the W-9 and K-1 labeling rules

## Deadlines & Penalties

- **Form 1065 due**: 2½ months after FY end (March 15 for calendar-year). Extension via Form 7004 → 6-month extension (September 15 for calendar).
- **§6698 failure-to-file penalty**: a per-partner, per-month amount for up to 12 months — indexed, so verify the rate for the target year through `authority.md` rather than carrying a prior year's figure. Small-partnership relief under Rev. Proc. 84-35 is available if ≤ 10 partners, each reporting their full distributive share on a timely individual return — but IRS has tightened enforcement; do not rely on it as a planning position. See `scenarios/penalty-abatement.md` for Rev. Proc. 84-35 mechanics and the full penalty-abatement decision tree — that file is the canonical home for penalty abatement procedures.
- **K-1 delivery to partners**: by the partnership's extended due date. Late K-1s are the #1 partner complaint — flag early.
- **The amendment vehicle is a hold until the election-out is verified on every condition, not just timeliness.** An amended return (rather than an AAR on Forms 8082/8985/8986) is available only for a year in which a valid §6221(b) election-out was made, which requires **all** of: an eligible partnership for that year (≤ 100 statements furnished, every partner an eligible partner); the election actually made on that year's return (the year-specific Schedule B question answered yes — read the *filed* return, not the software worksheet); a Schedule B-2 that is **complete and correct in content**, not merely attached — Reg. §301.6221(b)-1(c) requires, for every partner, the name, correct TIN, federal tax classification and the affirmative eligible-partner statement, and for every S-corporation partner the same for each of its shareholders; a *timely* return including a valid extension (Reg. §301.6221(b)-1(b)(1)); and no contrary IRS determination. A B-2 with a missing or wrong partner TIN or classification is a defective election, not a verified one. A return filed on the extended date whose extension cannot be evidenced is **"election status unverified"** — not "a BBA year": the absence of a copy in the workspace does not establish that no timely Form 7004 was filed. Obtain IRS evidence (the partnership account transcript, MFT 06) or counsel direction on the unverified condition before choosing the vehicle. Corroborating sources, useful but not dispositive: the e-file acceptance notice ("Your … extension was accepted") and the Form 7004 copy (which shows preparation, not acceptance). **Save whatever acceptance evidence exists as `tax/FY<YYYY>/filed/<YYYY-MM-DD> - evidence - form-7004-acceptance.md`** (sender/subject/timestamp/body verbatim) the day it arrives; search the *local* mail store when a connector search comes up empty. Multiple partnerships in one household produce identical acceptance notices that do not name the entity — record the count-and-timing inference explicitly and mark it as an inference. Record each year's election in `<scope-root>/carryforwards.json` → `section_6221b_election` (the election-out question is year-specific on Schedule B; question 33 on the 2024 form).
