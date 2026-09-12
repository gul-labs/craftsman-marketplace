# Tiered Partnership SE Analysis

Invoke when a partnership holds a **general-partner interest** in another partnership — i.e., an upstream K-1 reports SE earnings (box 14a) to a regarded partnership or LLC. The question: how does that SE income flow to the human partners, and who owes SE tax?

This is a distinct fact pattern from the usual one — most partnership-scenario literature covers individual partners in an operating business. The tiered fact pattern (Fund-of-Fund-of-partners) is mechanically different.

## ⚠ Gate — read before anything below

**Every reporting step in this file is conditional on a documented, fact-specific conclusion confirmed by a CPA or tax counsel.** Whether, and how, SE character reaches an individual through an upper-tier partnership is **not settled by Reg. §1.1402(a)-2 on its face** — that regulation speaks to an individual's distributive share from partnerships of which the individual is a member; it does not itself prescribe how an upper-tier partnership reports a lower tier's box 14a, and the "look-through" description below is a position, not a mechanical rule. Until the conclusion is documented and confirmed: do **not** populate the upper tier's Schedule K line 14a / K-1 box 14a from a lower-tier K-1, do **not** file an amendment or Schedule SE on the strength of this file, and do **not** override software either way. Record the open question in `open-questions.md` and the facts in the workpaper below. Positions that rest on the 1997 proposed regulations or on *Soroban*-line cases carry a ⚠ wherever they appear.

## The flow, stripped down

1. **Lower-tier partnership** — call it L. L issues a K-1 to the **upper-tier partnership** U showing box 14a SE earnings.
2. **U's 1065** picks up L's K-1. U itself has no active trade or business — it's a holding vehicle. ⚠ The proposition that SE character passes through U to its individual partners because §1402 looks through to the underlying activity is the question this file gates (see the Gate); it is analyzed, not assumed.
3. **U's K-1s to its partners** (individuals, for our purposes) report box 14a SE earnings only per the documented, confirmed conclusion — allocated on U's allocation terms.
4. **Individual partner** computes SE tax on Schedule SE of 1040 from whatever box 14a U reports under that conclusion.

⚠ "Look-through" as used here means: the argument that SE character is determined at the level where the trade or business is conducted (L), not at U, and that U's own form (partnership / LLC taxed as partnership) doesn't change it. Treat it as the position to be tested, with the individual's own facts at every tier.

## Whether the SE income is actually SE income

§1402(a)(13) excludes a **limited partner's distributive share** from SE income (other than guaranteed payments). Two active fronts:

### The LLC-member question (unsettled before *Soroban*)

For an LLC taxed as partnership, no member is "limited" in the §1402(a)(13) sense as a matter of state law — LLC members are members, not partners. IRS has long argued LLC members who are materially participating managers are NOT limited and owe SE tax; taxpayers argued "functional limited partner" status based on lack of management rights + passive capital.

⚠ *Soroban Capital Partners LP v. Commissioner*, 161 T.C. No. 12 (2023) — Tax Court adopted a **functional test**. Being labeled "limited partner" is not dispositive; what the partner actually does determines §1402(a)(13). Active participants owe SE tax even if the partnership agreement calls them limited. *Denham Capital* (2024) reinforced.

Effect for tiered structures: whether the individual at the top of the tier owes SE tax on her distributive share depends on her actual activity relative to the underlying trade or business L conducts. Passive capital → likely limited partner treatment → no SE tax. Active management role (in L, through U) → SE tax applies. Either way it is a case-law conclusion — document the facts and hold it for confirmation.

### Guaranteed payments

§707(c) guaranteed payments are always SE income (§1402(a), including for limited partners via the (a)(13) exception itself). If L pays U a guaranteed payment and U passes it to its members, it stays SE — even if the individual partner is otherwise "limited."

## The workpaper

Build at `entities/<upper-tier-slug>/tax/FY<YYYY>/annual/workpapers/se-tier-analysis.md`:

1. **Identify each upstream GP K-1** received by U. Note issuer L, box 14a dollars, any guaranteed payments in box 4a, self-employment characterization on L's agreement.
2. **Characterize U's allocation** — is U allocating the SE item to its partners based on the same ratio as other income? Special allocations for SE-bearing income are allowed with substantial economic effect but rare.
3. **Per-individual-partner analysis**:
   - What is this partner's role vis-à-vis L? Director? Silent capital? Decision-maker?
   - Apply the *Soroban* functional test ⚠. Document conclusion.
   - Compute the SE earnings that would flow through to their K-1 box 14a under that conclusion.
4. **CPA / tax-counsel confirmation** of the conclusion in step 3 — recorded in the workpaper with date and scope. Nothing below happens without it.
5. **Issue-side K-1 box 14a** — populate per the confirmed conclusion (and leave it 0 if the confirmed conclusion is that the item is excluded).
6. **Partner 1040 Schedule SE** — the individual picks up box 14a as reported, subtracts the half-SE deduction (§164(f) — an income-tax deduction, not a reduction of SE tax), pays 15.3% on 92.35% of net earnings up to the SS wage base + 2.9% thereafter + 0.9% additional Medicare above threshold.

## The recurring fact pattern

An upper-tier partnership holds a **GP interest** in a lower-tier fund (often the exception in a portfolio of otherwise-LP positions). If the fund's K-1 to the upper-tier partnership shows SE earnings in box 14a:

- ⚠ Whether the upper-tier partnership passes box 14a through to its own partners is decided by the confirmed conclusion, not by the lower-tier K-1 alone.
- ⚠ The argument that character remains SE because §1402 looks through the upper tier to the lower-tier trade or business is the position under test.
- Whether the individual partners actually owe SE tax depends on their role: passive capital investors with no active management of the lower-tier business may claim the §1402(a)(13) limited-partner exclusion — but *Soroban* ⚠ means this turns on functions actually performed, not on the label in the operating agreement.
- If prior-year 1065s omitted a box 14a pass-through that the confirmed conclusion says was required, correcting is both a 1065 fix (amend to populate box 14a) and a partner 1040 fix (add Schedule SE) — work through `amend-partnership.md` only after the conclusion is confirmed.

## Traps

- ⚠ **A tier-2 K-1's box 14a is that tier's fact, not the lower members'.** If L's investee issues L a K-1 with box 14a earnings (L is *its* GP), that character is L's as a partner of the investee. It says nothing, by itself, about L's own non-managing members two tiers down. Document each individual's facts at every tier (authority, liability, services, hours), never import a tier-2 box 14a downward mechanically, and never report the tier-2 K-1 itself (`naming.md` § Tier-2 K-1s).
- ⚠ **The 1997 proposed regulations do not rescue a manager who has authority to contract.** Prop. Reg. §1.1402(a)-2(h)(2) (no personal liability, no authority to contract, ≤ 500 hours) is a test for an *individual*; a member-manager with authority to contract fails it. The exception in **(h)(4)** applies only to an individual who fails (h)(2) *solely* because of the 500-hour test — it does not cure authority to contract, and citing it for that is wrong. (h)(3) is a separate multiple-class rule. The proposed regulations were never finalized; *Renkemeyer*, 136 T.C. 137 (2011), is a Tax Court decision that discussed their framework, not an adoption of them. Where U conducts no trade or business of its own and the item is U's distributive share from L in which U is a non-managing member, the analysis runs at L (previous bullet); state the U-level exposure if the exclusion were denied (net earnings × 92.35% × 15.3% up to the wage base; the §164(f) half-SE deduction is an income-tax deduction, not a reduction of SE tax).
- **Silent box 14a omission**: upstream L correctly reports box 14a; U's tax software doesn't pick it up when translating K-1 input to U's Sch K line 14a because U has no "own" SE income. If the confirmed conclusion is that the item passes through, a manual override is required — easy to miss in TurboTax Business. If the confirmed conclusion is that it is excluded, the software's zero is the right answer and must not be "fixed."
- **Guaranteed payments re-labeled**: some upstream partnerships pay their manager entities guaranteed payments called "management fees." If the K-1 labels it box 4a (guaranteed payments), it's SE regardless of partner status — bulletproof.
- **Partnership holding a GP is different from "partnership as GP"**: if U itself serves as GP of L (not just holds a GP interest), U has its own active trade or business and its entire operation may be SE-tainted for its members. Confirm the contractual structure.
- **NII/NIIT interaction**: SE income is generally NOT subject to §1411 NIIT (mutually exclusive). But passive investment income flowing through is NIIT-eligible. Character matters twice.
- **State SE tax equivalents**: WA has no SE tax equivalent. CA has no SE; NYC has UBT that mimics. Multi-state partners with SE income need separate analysis.

## Don't conclude without

- Reading the L-level partnership agreement (defines U's role — GP / LP / LLC-manager-member)
- Reading U's own partnership agreement (defines each individual's role relative to U)
- Documentation of individual partner's actual activity (emails, board minutes, contracts) — *Soroban* requires facts
- Authority chain: §1402(a), §1402(a)(13), Treas. Reg. §1.1402(a)-2, *Soroban*, *Denham Capital*, Chief Counsel Memoranda as they update
- The CPA / tax-counsel confirmation recorded in the workpaper (step 4)

This is a live area of law. Flag to CPA/tax attorney for any material SE exposure; don't finalize without sign-off.
