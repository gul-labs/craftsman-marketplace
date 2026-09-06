#!/usr/bin/env python3
"""
doc_types — the declarative registry of information returns the skill parses.

One entry per document type: how to recognise it (anchor phrases), which boxes
it carries (id, label, kind, label regex for the text pass), and the arithmetic
and tax-law invariants that must hold on any internally consistent copy of it.
`form_parser.py` reads the boxes, `quality.py` reads the anchors, and
`parse-verify/verify.py` evaluates the invariants through `invariants.py`.

Adding a form is adding an entry here. Nothing else needs to change.

Box ids are stable snake_case keys that mirror the printed box number
(`box_1`, `box_2a`, `box_12`). Kinds:

    money   whole-dollar or cents amount → float
    text    free text (names, addresses, descriptions)
    id      TIN / EIN / SSN / account number (masked to last-4 in narratives)
    date    ISO date string
    code    a single letter/number code (1099-R box 7, 1099-SA box 3)
    codes   list of {"code", "amount"} (W-2 box 12, K-1 box 20)
    flag    checkbox → bool
    state   the printed 2-letter state code

Invariant expressions are evaluated by `invariants.py` in a namespace holding
every box id as a float (None when not observed), `rules` from
`rules/federal-<tax_year>.json`, and the helpers `near`, `pct`, `has`, `sum_of`.
An invariant whose inputs are not all observed is SKIPPED, never failed — a
box the extractor did not see is not a zero.

Pure stdlib. Data only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Box:
    id: str
    label: str
    kind: str = "money"
    # Regex fragments that locate the box label in `pdftotext -layout` text.
    # The parser looks for a value to the right of / below the label.
    patterns: tuple[str, ...] = ()
    required: bool = False   # a NOT_PRESENT here is itself a finding
    # True when this box CANNOT be told apart from another one by a local text
    # match — a consolidated broker statement prints "Federal income tax
    # withheld" once in its interest section and again in its dividend section,
    # and a line-local regex cannot know which it found. The text pass refuses
    # to guess and returns UNREADABLE; vision or AcroForm supplies the value.
    # This is the difference between "we did not read it" and reading the wrong
    # section's number, which is indistinguishable from a correct answer.
    text_unreliable: bool = False


@dataclass(frozen=True)
class Invariant:
    id: str
    severity: str            # CRITICAL | HIGH | MEDIUM | INFO
    expr: str                # must evaluate truthy
    message: str
    fields: tuple[str, ...] = ()
    when: Optional[str] = None   # gate; skipped when falsy


@dataclass(frozen=True)
class DocType:
    name: str                       # canonical doc_type string used in parsed JSON
    title: str                      # printed form title
    anchors: tuple[str, ...]        # regexes; all present → strong match
    boxes: tuple[Box, ...] = ()
    identity: tuple[Box, ...] = ()  # payer / recipient block
    invariants: tuple[Invariant, ...] = ()
    parser: str = "form-parser"     # which tool owns the parse
    copies_per_page: int = 1        # W-2 prints Copy B/C/2 on one sheet
    notes: str = ""

    def box(self, box_id: str) -> Optional[Box]:
        for b in (*self.identity, *self.boxes):
            if b.id == box_id:
                return b
        return None

    def vision_skeleton(self) -> dict:
        """The JSON the model fills from page images (plain values, not envelopes;
        form_parser wraps them). Every box present so a missing one is explicit."""
        sk: dict = {"doc_type": self.name, "tax_year": None, "identity": {}, "boxes": {}}
        for b in self.identity:
            sk["identity"][b.id] = None
        for b in self.boxes:
            sk["boxes"][b.id] = [] if b.kind == "codes" else None
        return sk


def _m(id_: str, label: str, *patterns: str, required: bool = False,
       text_unreliable: bool = False) -> Box:
    return Box(id_, label, "money", tuple(patterns) or (_pat(label),), required, text_unreliable)


def _t(id_: str, label: str, *patterns: str, kind: str = "text", required: bool = False,
       text_unreliable: bool = False) -> Box:
    return Box(id_, label, kind, tuple(patterns) or (_pat(label),), required, text_unreliable)


def _pat(label: str) -> str:
    """Turn a printed label into a tolerant regex: any whitespace, optional punctuation."""
    import re
    parts = re.split(r"\s+", label.strip())
    return r"\s*".join(re.escape(p) for p in parts)


# Identity blocks shared by every 1099 / 1098.
_PAYER_ID = (
    _t("payer_name", "PAYER'S name", r"PAYER['’]S name"),
    _t("payer_tin", "PAYER'S TIN", r"PAYER['’]S TIN", kind="id"),
    _t("recipient_name", "RECIPIENT'S name", r"RECIPIENT['’]S name"),
    _t("recipient_tin", "RECIPIENT'S TIN", r"RECIPIENT['’]S TIN", kind="id"),
    _t("account_number", "Account number", r"Account number", kind="id"),
)

_STATE_TRIPLE = lambda n_wh, n_id, n_inc, wh_label="State tax withheld", inc_label="State income": (  # noqa: E731
    _m(f"box_{n_wh}", wh_label),
    _t(f"box_{n_id}", "State/Payer's state no.", r"State/Payer['’]s state no", kind="text"),
    _m(f"box_{n_inc}", inc_label),
)

_WH_LE = "box_4 <= {income} + 1"

# --------------------------------------------------------------------------
# W-2
# --------------------------------------------------------------------------

W2 = DocType(
    name="W-2",
    title="Wage and Tax Statement",
    anchors=(r"Wage and Tax Statement", r"Form\s*W-2", r"Wages,\s*tips,\s*other comp"),
    copies_per_page=4,
    identity=(
        _t("employee_ssn", "Employee's social security number", r"Employee['’]s social security number", kind="id", required=True),
        _t("employer_ein", "Employer identification number (EIN)", r"Employer identification number", kind="id", required=True),
        _t("employer_name", "Employer's name, address, and ZIP code", r"Employer['’]s name", required=True),
        _t("control_number", "Control number", r"Control number"),
        _t("employee_name", "Employee's first name and initial", r"Employee['’]s (?:first )?name", required=True),
    ),
    boxes=(
        _m("box_1", "Wages, tips, other compensation", r"Wages,\s*tips,\s*other comp", required=True),
        _m("box_2", "Federal income tax withheld", r"Federal income tax withheld", required=True),
        _m("box_3", "Social security wages", r"Social security wages"),
        _m("box_4", "Social security tax withheld", r"Social security tax withheld"),
        _m("box_5", "Medicare wages and tips", r"Medicare wages and tips"),
        _m("box_6", "Medicare tax withheld", r"Medicare tax withheld"),
        _m("box_7", "Social security tips", r"Social security tips"),
        _m("box_8", "Allocated tips", r"Allocated tips"),
        _m("box_10", "Dependent care benefits", r"Dependent care benefits"),
        _m("box_11", "Nonqualified plans", r"Nonqualified plans"),
        Box("box_12", "Box 12 codes", "codes", (r"12[a-d]\b",)),
        Box("box_13_statutory_employee", "Statutory employee", "flag", (r"Statutory\s*employee",)),
        Box("box_13_retirement_plan", "Retirement plan", "flag", (r"Retirement\s*plan",)),
        Box("box_13_third_party_sick_pay", "Third-party sick pay", "flag", (r"Third-party\s*sick pay",)),
        Box("box_14", "Other", "codes", (r"\b14\s*Other",)),
        Box("box_15_state", "State", "state", (r"\b15\s*State",)),
        _t("box_15_employer_state_id", "Employer's state ID number", r"Employer['’]s state ID"),
        _m("box_16", "State wages, tips, etc.", r"State wages"),
        _m("box_17", "State income tax", r"State income tax"),
        _m("box_18", "Local wages, tips, etc.", r"Local wages"),
        _m("box_19", "Local income tax", r"Local income tax"),
        _t("box_20", "Locality name", r"Locality name"),
    ),
    invariants=(
        Invariant("W2.box2_le_box1", "HIGH", "box_2 <= box_1 + 1",
                  "Federal withholding (box 2) exceeds wages (box 1) — a box was misread.", ("box_1", "box_2")),
        # An upper bound, not an equality. Box 4 is the tax actually COLLECTED:
        # when an employer cannot collect the tax on tips or on group-term life
        # for a former employee, the wages still appear in boxes 3 and 7 while
        # the uncollected tax is reported in box 12 (codes A and M). Requiring
        # exactly 6.2% would fire on every one of those correctly issued forms.
        Invariant("W2.box4_ss_rate", "HIGH",
                  "box_4 <= (box_3 + (box_7 or 0)) * rules['ss_rate_ee'] + max(2, 0.01 * box_4)",
                  "Social security tax (box 4) exceeds 6.2% of social security wages + tips (boxes 3 + 7).",
                  ("box_3", "box_4", "box_7"), when="has('box_3') and has('box_4') and rules.get('ss_rate_ee')"),
        Invariant("W2.box3_wage_base", "HIGH",
                  "box_3 + (box_7 or 0) <= rules['ss_wage_base'] + 1",
                  "Social security wages + tips exceed the year's wage base — impossible on a single W-2.",
                  ("box_3", "box_7"), when="has('box_3') and rules.get('ss_wage_base')"),
        # Upper bound only, for the same reason as box 4: uncollected Medicare
        # tax on tips (box 12 code B) and on former-employee group-term life
        # (code N) legitimately leaves box 6 below 1.45% of box 5. The ceiling
        # is 1.45% plus the 0.9% additional Medicare tax above $200,000.
        Invariant("W2.box6_medicare_rate", "HIGH",
                  "box_6 <= box_5 * rules['medicare_rate_ee'] + max(0, box_5 - 200000) * 0.009 + max(2, 0.01 * box_6)",
                  "Medicare tax (box 6) exceeds 1.45% of Medicare wages (box 5) plus the 0.9% additional-tax band.",
                  ("box_5", "box_6"), when="has('box_5') and has('box_6') and rules.get('medicare_rate_ee')"),
        Invariant("W2.box5_ge_box3", "MEDIUM", "box_5 + 1 >= box_3",
                  "Medicare wages (box 5) are below social security wages (box 3); rare — confirm against the paper.",
                  ("box_3", "box_5")),
        # There is deliberately no "box 1 <= box 5 + deferrals" invariant. The
        # elective-deferral codes explain why box 5 can exceed box 1, not the
        # reverse, and FICA-exempt wages (clergy electing out, the student FICA
        # exception, certain nonresident aliens) put real wages in box 1 with
        # box 5 blank or lower. Any such rule fires on correctly issued forms.
        Invariant("W2.box17_le_box16", "HIGH", "box_17 <= box_16 + 1",
                  "State withholding (box 17) exceeds state wages (box 16).", ("box_16", "box_17")),
        Invariant("W2.box19_le_box18", "HIGH", "box_19 <= box_18 + 1",
                  "Local withholding (box 19) exceeds local wages (box 18).", ("box_18", "box_19")),
        Invariant("W2.box16_vs_box1", "INFO", "near(box_16, box_1, tol=max(1, 0.02 * box_1))",
                  "State wages (box 16) differ from federal wages (box 1); normal for multi-state or state add-backs, otherwise a lead.",
                  ("box_1", "box_16")),
    ),
    notes="Four copies (B, C, 2, 2) commonly print on one sheet; dedupe by taking the copy whose values are complete and consistent.",
)

# --------------------------------------------------------------------------
# 1099 family
# --------------------------------------------------------------------------

F1099_INT = DocType(
    name="1099-INT", title="Interest Income",
    anchors=(r"Form\s*1099-INT", r"Interest Income", r"Early withdrawal penalty"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Interest income", r"\b1\s*Interest income", required=True),
        _m("box_2", "Early withdrawal penalty", r"Early withdrawal penalty"),
        _m("box_3", "Interest on U.S. Savings Bonds and Treasury obligations", r"Interest on U\.?S\.? Savings Bonds"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "Investment expenses", r"Investment expenses"),
        _m("box_6", "Foreign tax paid", r"Foreign tax paid"),
        _t("box_7", "Foreign country or U.S. possession", r"Foreign country"),
        _m("box_8", "Tax-exempt interest", r"Tax-exempt interest"),
        _m("box_9", "Specified private activity bond interest", r"Specified private activity bond interest"),
        _m("box_10", "Market discount", r"Market discount"),
        _m("box_11", "Bond premium", r"\b11\s*Bond premium"),
        _m("box_12", "Bond premium on Treasury obligations", r"Bond premium on Treasury"),
        _m("box_13", "Bond premium on tax-exempt bond", r"Bond premium on tax-exempt"),
        _t("box_14", "Tax-exempt and tax credit bond CUSIP no.", r"CUSIP"),
        *_STATE_TRIPLE(17, 16, 18, inc_label="State interest"),
        Box("box_15_state", "State", "state", (r"\b15\s*State",)),
    ),
    invariants=(
        Invariant("1099INT.box9_le_box8", "HIGH", "box_9 <= box_8 + 1",
                  "Private activity bond interest (box 9) exceeds tax-exempt interest (box 8) it is a subset of.", ("box_8", "box_9")),
        Invariant("1099INT.box4_le_income", "MEDIUM", "box_4 <= box_1 + (box_3 or 0) + (box_8 or 0) + 1",
                  "Federal withholding (box 4) exceeds reported interest.", ("box_1", "box_3", "box_4", "box_8")),
        Invariant("1099INT.box12_le_box3", "MEDIUM", "box_12 <= box_3 + 1",
                  "Treasury bond premium (box 12) exceeds Treasury interest (box 3).", ("box_3", "box_12")),
        Invariant("1099INT.box13_le_box8", "MEDIUM", "box_13 <= box_8 + 1",
                  "Tax-exempt bond premium (box 13) exceeds tax-exempt interest (box 8).", ("box_8", "box_13")),
    ),
)

F1099_DIV = DocType(
    name="1099-DIV", title="Dividends and Distributions",
    anchors=(r"Form\s*1099-DIV", r"Dividends and Distributions", r"Total ordinary dividends"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1a", "Total ordinary dividends", r"Total ordinary dividends", required=True),
        _m("box_1b", "Qualified dividends", r"Qualified dividends"),
        _m("box_2a", "Total capital gain distr.", r"Total capital gain distr"),
        _m("box_2b", "Unrecap. Sec. 1250 gain", r"Unrecap\.?\s*Sec\.?\s*1250 gain"),
        _m("box_2c", "Section 1202 gain", r"Section 1202 gain"),
        _m("box_2d", "Collectibles (28%) gain", r"Collectibles \(28%\) gain"),
        _m("box_2e", "Section 897 ordinary dividends", r"Section 897 ordinary dividends"),
        _m("box_2f", "Section 897 capital gain", r"Section 897 capital gain"),
        _m("box_3", "Nondividend distributions", r"Nondividend distributions"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "Section 199A dividends", r"Section 199A dividends"),
        _m("box_6", "Investment expenses", r"Investment expenses"),
        _m("box_7", "Foreign tax paid", r"Foreign tax paid"),
        _t("box_8", "Foreign country or U.S. possession", r"Foreign country"),
        _m("box_9", "Cash liquidation distributions", r"Cash liquidation distributions"),
        _m("box_10", "Noncash liquidation distributions", r"Noncash liquidation distributions"),
        Box("box_11", "FATCA filing requirement", "flag", (r"FATCA filing requirement",)),
        _m("box_12", "Exempt-interest dividends", r"Exempt-interest dividends"),
        _m("box_13", "Specified private activity bond interest dividends", r"Specified private activity bond interest dividends"),
        Box("box_14_state", "State", "state", (r"\b14\s*State",)),
        _t("box_15", "State identification no.", r"State identification no"),
        _m("box_16", "State tax withheld", r"State tax withheld"),
    ),
    invariants=(
        Invariant("1099DIV.qualified_le_ordinary", "CRITICAL", "box_1b <= box_1a + 1",
                  "Qualified dividends (box 1b) exceed total ordinary dividends (box 1a) they are part of.", ("box_1a", "box_1b")),
        Invariant("1099DIV.199A_le_ordinary", "HIGH", "box_5 <= box_1a + 1",
                  "Section 199A dividends (box 5) exceed total ordinary dividends (box 1a).", ("box_1a", "box_5")),
        Invariant("1099DIV.cap_gain_parts", "HIGH", "(box_2b or 0) + (box_2c or 0) + (box_2d or 0) <= box_2a + 1",
                  "Boxes 2b + 2c + 2d exceed total capital gain distributions (box 2a).", ("box_2a", "box_2b", "box_2c", "box_2d"),
                  when="has('box_2a')"),
        Invariant("1099DIV.897_ordinary", "MEDIUM", "box_2e <= box_1a + 1",
                  "Section 897 ordinary dividends (box 2e) exceed box 1a.", ("box_1a", "box_2e")),
        Invariant("1099DIV.897_capgain", "MEDIUM", "box_2f <= box_2a + 1",
                  "Section 897 capital gain (box 2f) exceeds box 2a.", ("box_2a", "box_2f")),
        Invariant("1099DIV.pab_le_exempt", "HIGH", "box_13 <= box_12 + 1",
                  "Private activity bond dividends (box 13) exceed exempt-interest dividends (box 12).", ("box_12", "box_13")),
        Invariant("1099DIV.wh_le_income", "MEDIUM", "box_4 <= box_1a + (box_2a or 0) + (box_3 or 0) + 1",
                  "Federal withholding (box 4) exceeds reported distributions.", ("box_1a", "box_2a", "box_3", "box_4")),
    ),
)

# Broker 1099-B summary — the totals block, not the lot list. Lots go to the
# ibkr-parser / composite path; the summary is what Schedule D Part I/II needs.
_B_CATS = ("st_covered", "st_noncovered", "lt_covered", "lt_noncovered")
# "noncovered" contains "covered": without the lookbehind every covered pattern
# also matches the noncovered row, and the two carry different Schedule D
# treatment. Same trap in the gain column — "Wash sale loss disallowed" contains
# "loss", so a `(?:Gain|Loss)` alternative reads the wash-sale figure as the gain.
_B_LABELS = {
    "st_covered": r"Short[- ]term.*(?:(?<!non)covered|Box A|basis reported(?! to the IRS: No))",
    "st_noncovered": r"Short[- ]term.*(?:noncovered|Box B|basis not reported)",
    "lt_covered": r"Long[- ]term.*(?:(?<!non)covered|Box D|basis reported(?! to the IRS: No))",
    "lt_noncovered": r"Long[- ]term.*(?:noncovered|Box E|basis not reported)",
}
_B_BOXES = []
for _c in _B_CATS:
    _B_BOXES += [
        _m(f"{_c}_proceeds", f"{_c} proceeds", _B_LABELS[_c] + r".*Proceeds"),
        _m(f"{_c}_basis", f"{_c} cost basis", _B_LABELS[_c] + r".*Cost"),
        _m(f"{_c}_wash_sale", f"{_c} wash sale loss disallowed", _B_LABELS[_c] + r".*Wash"),
        _m(f"{_c}_market_discount", f"{_c} accrued market discount", _B_LABELS[_c] + r".*[Mm]arket discount"),
        _m(f"{_c}_gain", f"{_c} gain/loss", _B_LABELS[_c] + r".*Gain(?:\s*(?:or|/|\()\s*\(?loss\)?)?"),
    ]
_B_INV = []
for _c in _B_CATS:
    # Market discount is not subtracted without limit: on Form 8949 the
    # adjustment is the LESSER of the realized gain and the accrued market
    # discount, and that amount is reported as interest income instead. An
    # unlimited subtraction turns a loss position into a phantom mismatch.
    _pre = f"({_c}_proceeds - {_c}_basis + ({_c}_wash_sale or 0))"
    _B_INV.append(Invariant(
        f"1099B.{_c}.gain_ties", "HIGH",
        f"near({_c}_gain, {_pre} - min(max({_pre}, 0), ({_c}_market_discount or 0)), "
        f"tol=max(2, 0.001 * abs({_c}_proceeds)))",
        f"{_c}: gain/loss does not equal proceeds − basis + wash sale disallowed, less any "
        f"accrued market discount up to the realized gain.",
        (f"{_c}_proceeds", f"{_c}_basis", f"{_c}_wash_sale", f"{_c}_gain"),
        when=f"has('{_c}_gain') and has('{_c}_proceeds') and has('{_c}_basis')"))

F1099_B = DocType(
    name="1099-B", title="Proceeds From Broker and Barter Exchange Transactions",
    anchors=(r"Form\s*1099-B", r"Proceeds From Broker", r"Wash sale loss disallowed"),
    identity=_PAYER_ID,
    boxes=(
        *_B_BOXES,
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
    ),
    invariants=tuple(_B_INV),
    notes="Summary totals only. Per-lot detail is not parsed here; reconcile the summary to the broker's own totals page.",
)

F1099_COMPOSITE = DocType(
    name="1099-Composite", title="Consolidated 1099 Statement",
    anchors=(r"(?:Consolidated|Composite)\s*(?:Form\s*)?1099", r"1099-DIV", r"1099-INT", r"1099-B"),
    identity=_PAYER_ID,
    boxes=(
        # INT
        _m("int_box_1", "Interest income", r"\b1\s*Interest income"),
        _m("int_box_3", "Interest on U.S. Savings Bonds and Treasury obligations", r"Interest on U\.?S\.? Savings Bonds"),
        _m("int_box_4", "Federal income tax withheld (INT)", r"Federal income tax withheld", text_unreliable=True),
        _m("int_box_6", "Foreign tax paid (INT)", r"Foreign tax paid", text_unreliable=True),
        _m("int_box_8", "Tax-exempt interest", r"Tax-exempt interest"),
        _m("int_box_11", "Bond premium", r"\b11\s*Bond premium"),
        # DIV
        _m("div_box_1a", "Total ordinary dividends", r"Total ordinary dividends"),
        _m("div_box_1b", "Qualified dividends", r"Qualified dividends"),
        _m("div_box_2a", "Total capital gain distr.", r"Total capital gain distr"),
        _m("div_box_2b", "Unrecap. Sec. 1250 gain", r"Unrecap\.?\s*Sec\.?\s*1250"),
        _m("div_box_3", "Nondividend distributions", r"Nondividend distributions"),
        _m("div_box_4", "Federal income tax withheld (DIV)", r"Federal income tax withheld", text_unreliable=True),
        _m("div_box_5", "Section 199A dividends", r"Section 199A dividends"),
        _m("div_box_7", "Foreign tax paid (DIV)", r"Foreign tax paid", text_unreliable=True),
        _m("div_box_12", "Exempt-interest dividends", r"Exempt-interest dividends"),
        # B summary
        *_B_BOXES,
    ),
    invariants=(
        Invariant("1099C.qualified_le_ordinary", "CRITICAL", "div_box_1b <= div_box_1a + 1",
                  "Qualified dividends exceed total ordinary dividends.", ("div_box_1a", "div_box_1b")),
        Invariant("1099C.199A_le_ordinary", "HIGH", "div_box_5 <= div_box_1a + 1",
                  "Section 199A dividends exceed total ordinary dividends.", ("div_box_1a", "div_box_5")),
        Invariant("1099C.1250_le_capgain", "HIGH", "div_box_2b <= div_box_2a + 1",
                  "Unrecaptured §1250 gain exceeds total capital gain distributions.", ("div_box_2a", "div_box_2b")),
        *_B_INV,
    ),
    notes="Brokers lay these out freely; the anchor-based text pass is weak here and vision is the primary read. "
          "The withholding and foreign-tax boxes print the same caption in the interest and dividend sections, so "
          "the text pass cannot tell them apart and returns UNREADABLE for both (`text_unreliable`); vision or the "
          "broker's own summary supplies them. Reconcile to that summary page.",
)

F1099_NEC = DocType(
    name="1099-NEC", title="Nonemployee Compensation",
    anchors=(r"Form\s*1099-NEC", r"Nonemployee [Cc]ompensation"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Nonemployee compensation", r"\b1\s*Nonemployee compensation", required=True),
        Box("box_2", "Payer made direct sales totaling $5,000 or more", "flag", (r"direct sales totaling",)),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "State tax withheld", r"State tax withheld"),
        _t("box_6", "State/Payer's state no.", r"State/Payer['’]s state no"),
        _m("box_7", "State income", r"State income"),
    ),
    invariants=(
        Invariant("1099NEC.wh_le_comp", "HIGH", "box_4 <= box_1 + 1",
                  "Federal withholding (box 4) exceeds nonemployee compensation (box 1).", ("box_1", "box_4")),
        Invariant("1099NEC.state_wh_le_state_income", "HIGH", "box_5 <= box_7 + 1",
                  "State withholding (box 5) exceeds state income (box 7).", ("box_5", "box_7")),
    ),
)

F1099_MISC = DocType(
    name="1099-MISC", title="Miscellaneous Information",
    anchors=(r"Form\s*1099-MISC", r"Miscellaneous (?:Information|Income)", r"\bRents\b"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Rents", r"\b1\s*Rents"),
        _m("box_2", "Royalties", r"\b2\s*Royalties"),
        _m("box_3", "Other income", r"\b3\s*Other income"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "Fishing boat proceeds", r"Fishing boat proceeds"),
        _m("box_6", "Medical and health care payments", r"Medical and health care payments"),
        Box("box_7", "Payer made direct sales totaling $5,000 or more", "flag", (r"direct sales totaling",)),
        _m("box_8", "Substitute payments in lieu of dividends or interest", r"Substitute payments"),
        _m("box_9", "Crop insurance proceeds", r"Crop insurance proceeds"),
        _m("box_10", "Gross proceeds paid to an attorney", r"Gross proceeds paid to an attorney"),
        _m("box_11", "Fish purchased for resale", r"Fish purchased for resale"),
        _m("box_12", "Section 409A deferrals", r"Section 409A deferrals"),
        _m("box_14", "Excess golden parachute payments", r"Excess golden parachute"),
        _m("box_15", "Nonqualified deferred compensation", r"Nonqualified deferred compensation"),
        _m("box_16", "State tax withheld", r"State tax withheld"),
        _t("box_17", "State/Payer's state no.", r"State/Payer['’]s state no"),
        _m("box_18", "State income", r"State income"),
    ),
    invariants=(
        Invariant("1099MISC.wh_le_income", "HIGH",
                  "box_4 <= sum_of_boxes('box_1','box_2','box_3','box_5','box_6','box_8','box_9','box_10','box_11') + 1",
                  "Federal withholding (box 4) exceeds every reportable amount on the form combined.",
                  ("box_4", "box_1", "box_2", "box_3")),
        Invariant("1099MISC.state_wh_le_state_income", "HIGH", "box_16 <= box_18 + 1",
                  "State withholding (box 16) exceeds state income (box 18).", ("box_16", "box_18")),
    ),
)

F1099_R = DocType(
    name="1099-R", title="Distributions From Pensions, Annuities, Retirement or Profit-Sharing Plans, IRAs, Insurance Contracts, etc.",
    anchors=(r"Form\s*1099-R\b", r"Distributions From Pensions", r"Gross distribution"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Gross distribution", r"\b1\s*Gross distribution", required=True),
        _m("box_2a", "Taxable amount", r"2a\s*Taxable amount"),
        Box("box_2b_taxable_not_determined", "Taxable amount not determined", "flag", (r"Taxable amount not determined",)),
        Box("box_2b_total_distribution", "Total distribution", "flag", (r"(?<!of )Total distribution",)),
        _m("box_3", "Capital gain (included in box 2a)", r"Capital gain \(included"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "Employee contributions/Designated Roth contributions or insurance premiums", r"Employee contributions"),
        _m("box_6", "Net unrealized appreciation in employer's securities", r"Net unrealized appreciation"),
        Box("box_7", "Distribution code(s)", "code", (r"\b7\s*Distribution code",), required=True),
        Box("box_7_ira_sep_simple", "IRA/SEP/SIMPLE", "flag", (r"IRA/\s*SEP/\s*SIMPLE",)),
        _m("box_8", "Other", r"\b8\s*Other"),
        _m("box_9a", "Your percentage of total distribution", r"(?:Your )?percentage of total distribution"),
        _m("box_9b", "Total employee contributions", r"Total employee contributions"),
        _m("box_10", "Amount allocable to IRR within 5 years", r"allocable to IRR"),
        _t("box_11", "1st year of desig. Roth contrib.", r"1st year of desig"),
        Box("box_12", "FATCA filing requirement", "flag", (r"FATCA filing requirement",)),
        _t("box_13", "Date of payment", r"Date of payment", kind="date"),
        _m("box_14", "State tax withheld", r"State tax withheld"),
        _t("box_15", "State/Payer's state no.", r"State/Payer['’]s state no"),
        _m("box_16", "State distribution", r"State distribution"),
        _m("box_17", "Local tax withheld", r"Local tax withheld"),
        _t("box_18", "Name of locality", r"Name of locality"),
        _m("box_19", "Local distribution", r"Local distribution"),
    ),
    invariants=(
        Invariant("1099R.taxable_le_gross", "CRITICAL", "box_2a <= box_1 + 1",
                  "Taxable amount (box 2a) exceeds gross distribution (box 1).", ("box_1", "box_2a")),
        Invariant("1099R.wh_le_gross", "HIGH", "box_4 <= box_1 + 1",
                  "Federal withholding (box 4) exceeds gross distribution (box 1).", ("box_1", "box_4")),
        Invariant("1099R.capgain_le_taxable", "MEDIUM", "box_3 <= box_2a + 1",
                  "Capital gain (box 3) exceeds the taxable amount (box 2a) it is included in.", ("box_2a", "box_3")),
        # No "box 5 <= box 1" invariant: the IRS instructions expressly allow
        # employee contributions/basis in box 5 to exceed the gross distribution,
        # for instance when property distributed with after-tax basis is worthless.
        # MEDIUM, not HIGH: box 16 is optional on Form 1099-R and payers often
        # leave it blank while completing box 14. A blank box is NOT_PRESENT and
        # skips this check outright; only a printed zero beside real withholding
        # reaches it, which is worth a look rather than a violation.
        Invariant("1099R.state_wh_le_state_dist", "MEDIUM", "box_14 <= box_16 + 1",
                  "State withholding (box 14) exceeds the state distribution printed in box 16; "
                  "payers commonly leave box 16 blank, so confirm against the form.",
                  ("box_14", "box_16")),
        Invariant("1099R.code_present", "HIGH", "has('box_7')",
                  "Box 7 distribution code is missing — the code decides taxability and penalties; do not proceed without it.",
                  ("box_7",), when="has('box_1')"),
    ),
)

F1099_G = DocType(
    name="1099-G", title="Certain Government Payments",
    anchors=(r"Form\s*1099-G\b", r"Certain Government Payments", r"Unemployment compensation"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Unemployment compensation", r"Unemployment compensation"),
        _m("box_2", "State or local income tax refunds, credits, or offsets", r"State or local income tax refunds"),
        _t("box_3", "Box 2 amount is for tax year", r"Box 2 amount is for tax year"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _m("box_5", "RTAA payments", r"RTAA payments"),
        _m("box_6", "Taxable grants", r"Taxable grants"),
        _m("box_7", "Agriculture payments", r"Agriculture payments"),
        Box("box_8", "Trade or business income", "flag", (r"trade or business income",)),
        _m("box_9", "Market gain", r"Market gain"),
        Box("box_10a_state", "State", "state", (r"10a\s*State",)),
        _t("box_10b", "State identification no.", r"State identification no"),
        _m("box_11", "State income tax withheld", r"State income tax withheld"),
    ),
    invariants=(
        Invariant("1099G.wh_le_payments", "HIGH",
                  "box_4 <= sum_of_boxes('box_1','box_2','box_5','box_6','box_7') + 1",
                  "Federal withholding (box 4) exceeds every payment on the form combined.", ("box_4", "box_1", "box_2")),
    ),
)

_K_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
F1099_K = DocType(
    name="1099-K", title="Payment Card and Third Party Network Transactions",
    anchors=(r"Form\s*1099-K\b", r"Payment Card and Third Party Network", r"Gross amount of payment card"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1a", "Gross amount of payment card/third party network transactions", r"1a\s*Gross amount", required=True),
        _m("box_1b", "Card Not Present transactions", r"Card Not Present"),
        _t("box_2", "Merchant category code", r"Merchant category code"),
        _m("box_3", "Number of payment transactions", r"Number of payment transactions"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        *[_m(f"box_5_{m}", f"5{chr(97 + i)} {m.title()}", rf"5{chr(97 + i)}\s*{m.title()}") for i, m in enumerate(_K_MONTHS)],
        Box("box_6_state", "State", "state", (r"\b6\s*State",)),
        _t("box_7", "State identification no.", r"State identification no"),
        _m("box_8", "State income tax withheld", r"State income tax withheld"),
    ),
    invariants=(
        Invariant("1099K.months_tie", "HIGH",
                  "near(box_1a, " + " + ".join(f"box_5_{m}" for m in _K_MONTHS) + ", tol=max(1, 0.001 * box_1a))",
                  "Monthly amounts (boxes 5a–5l) do not sum to the gross amount (box 1a).",
                  ("box_1a", *[f"box_5_{m}" for m in _K_MONTHS])),
        Invariant("1099K.cnp_le_gross", "HIGH", "box_1b <= box_1a + 1",
                  "Card-not-present amount (box 1b) exceeds the gross amount (box 1a).", ("box_1a", "box_1b")),
        Invariant("1099K.wh_le_gross", "HIGH", "box_4 <= box_1a + 1",
                  "Backup withholding (box 4) exceeds the gross amount it was withheld from (box 1a) — "
                  "the classic box 1a / box 4 transposition.", ("box_1a", "box_4")),
    ),
)

F1099_SA = DocType(
    name="1099-SA", title="Distributions From an HSA, Archer MSA, or Medicare Advantage MSA",
    anchors=(r"Form\s*1099-SA\b", r"Distributions From an HSA", r"Earnings on excess cont"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Gross distribution", r"\b1\s*Gross distribution", required=True),
        _m("box_2", "Earnings on excess cont.", r"Earnings on excess cont"),
        Box("box_3", "Distribution code", "code", (r"\b3\s*Distribution code",), required=True),
        _m("box_4", "FMV on date of death", r"FMV on date of death"),
        Box("box_5_hsa", "HSA", "flag", (r"\b5\s*HSA\b", r"\bHSA\b")),
        Box("box_5_archer", "Archer MSA", "flag", (r"\b5?\s*Archer MSA",)),
        Box("box_5_ma_msa", "MA MSA", "flag", (r"\bMA MSA",)),
    ),
    invariants=(
        Invariant("1099SA.excess_le_gross", "MEDIUM", "box_2 <= box_1 + 1",
                  "Earnings on excess contributions (box 2) exceed the gross distribution (box 1).", ("box_1", "box_2")),
    ),
)

SSA_1099 = DocType(
    name="SSA-1099", title="Social Security Benefit Statement",
    anchors=(r"SSA-1099", r"Social Security Benefit Statement", r"Benefits Paid in"),
    identity=(
        _t("recipient_name", "Name", r"\b1\.?\s*Name", r"^\s*Name\b"),
        _t("recipient_ssn", "Beneficiary's Social Security Number", r"Social Security Number", kind="id"),
        _t("claim_number", "Claim Number", r"Claim Number", kind="id"),
    ),
    boxes=(
        _m("box_3", "Benefits Paid in the year", r"\b3\.?\s*Benefits Paid", required=True),
        _m("box_4", "Benefits Repaid to SSA", r"\b4\.?\s*Benefits Repaid"),
        _m("box_5", "Net Benefits for the year", r"\b5\.?\s*Net Benefits", required=True),
        _m("box_6", "Voluntary Federal Income Tax Withheld", r"Voluntary Federal Income Tax Withh"),
        _m("medicare_part_b", "Medicare Part B premiums deducted", r"Medicare Part B"),
        _m("medicare_part_d", "Medicare Part D premiums deducted", r"Medicare Part D"),
    ),
    invariants=(
        Invariant("SSA1099.net_ties", "CRITICAL", "near(box_5, box_3 - (box_4 or 0), tol=1)",
                  "Net benefits (box 5) do not equal benefits paid (box 3) minus benefits repaid (box 4).", ("box_3", "box_4", "box_5")),
        Invariant("SSA1099.wh_le_paid", "HIGH", "box_6 <= box_3 + 1",
                  "Voluntary withholding (box 6) exceeds benefits paid (box 3).", ("box_3", "box_6")),
    ),
)

W2G = DocType(
    name="W-2G", title="Certain Gambling Winnings",
    anchors=(r"Form\s*W-2G", r"Certain Gambling Winnings", r"Reportable winnings"),
    identity=_PAYER_ID,
    boxes=(
        _m("box_1", "Reportable winnings", r"Reportable winnings", required=True),
        _t("box_2", "Date won", r"Date won", kind="date"),
        _t("box_3", "Type of wager", r"Type of wager"),
        _m("box_4", "Federal income tax withheld", r"Federal income tax withheld"),
        _t("box_5", "Transaction", r"\b5\s*Transaction"),
        _t("box_6", "Race", r"\b6\s*Race"),
        _m("box_7", "Winnings from identical wagers", r"Winnings from identical wagers"),
        _t("box_8", "Cashier", r"\b8\s*Cashier"),
        _t("box_9", "Winner's taxpayer identification no.", r"Winner['’]s taxpayer identification", kind="id"),
        _t("box_10", "Window", r"\b10\s*Window"),
        _t("box_11", "First I.D.", r"First I\.?D"),
        _t("box_12", "Second I.D.", r"Second I\.?D"),
        Box("box_13_state", "State/Payer's state identification no.", "text", (r"State/Payer['’]s state identification",)),
        _m("box_14", "State winnings", r"State winnings"),
        _m("box_15", "State income tax withheld", r"State income tax withheld"),
        _m("box_16", "Local winnings", r"Local winnings"),
        _m("box_17", "Local income tax withheld", r"Local income tax withheld"),
        _t("box_18", "Name of locality", r"Name of locality"),
    ),
    invariants=(
        Invariant("W2G.wh_le_winnings", "HIGH", "box_4 <= box_1 + 1",
                  "Federal withholding (box 4) exceeds reportable winnings (box 1).", ("box_1", "box_4")),
        Invariant("W2G.state_wh_le_state_winnings", "HIGH", "box_15 <= box_14 + 1",
                  "State withholding (box 15) exceeds state winnings (box 14).", ("box_14", "box_15")),
    ),
)

# --------------------------------------------------------------------------
# 1098 family and 5498 family
# --------------------------------------------------------------------------

_LENDER_ID = (
    _t("payer_name", "RECIPIENT'S/LENDER'S name", r"RECIPIENT['’]S/LENDER['’]S name"),
    _t("payer_tin", "RECIPIENT'S/LENDER'S TIN", r"RECIPIENT['’]S/LENDER['’]S TIN", kind="id"),
    _t("recipient_name", "PAYER'S/BORROWER'S name", r"PAYER['’]S/BORROWER['’]S name"),
    _t("recipient_tin", "PAYER'S/BORROWER'S TIN", r"PAYER['’]S/BORROWER['’]S TIN", kind="id"),
    _t("account_number", "Account number", r"Account number", kind="id"),
)

F1098 = DocType(
    name="1098", title="Mortgage Interest Statement",
    anchors=(r"Form\s*1098\b(?!-)", r"Mortgage Interest Statement", r"Outstanding mortgage principal"),
    identity=_LENDER_ID,
    boxes=(
        _m("box_1", "Mortgage interest received from payer(s)/borrower(s)", r"Mortgage interest received", required=True),
        _m("box_2", "Outstanding mortgage principal", r"Outstanding mortgage principal"),
        _t("box_3", "Mortgage origination date", r"Mortgage origination date", kind="date"),
        _m("box_4", "Refund of overpaid interest", r"Refund of overpaid interest"),
        _m("box_5", "Mortgage insurance premiums", r"Mortgage insurance premiums"),
        _m("box_6", "Points paid on purchase of principal residence", r"Points paid on purchase"),
        Box("box_7", "Address of property securing mortgage is the same as PAYER'S/BORROWER'S address", "flag",
            (r"same as PAYER['’]S/BORROWER['’]S address",)),
        _t("box_8", "Address or description of property securing mortgage", r"Address or description of property"),
        _m("box_9", "Number of properties securing the mortgage", r"Number of properties securing"),
        _m("box_10", "Other", r"\b10\s*Other"),
        _t("box_11", "Mortgage acquisition date", r"Mortgage acquisition date", kind="date"),
    ),
    invariants=(
        # INFO, and deliberately a heuristic rather than a rule: nothing in the
        # form forbids interest above 15% of principal (a short-lived or
        # high-rate loan, prepaid interest, late charges). It earns its place
        # only as a detector for boxes 1 and 2 read into each other's places.
        Invariant("1098.interest_plausible", "INFO", "box_1 <= 0.15 * box_2 + 1",
                  "Interest received (box 1) exceeds 15% of outstanding principal (box 2); check whether boxes 1 and 2 were swapped.",
                  ("box_1", "box_2"), when="has('box_2') and box_2 > 0"),
        # No "box 4 <= box 1" invariant: box 4 refunds interest overpaid in a
        # PRIOR year and bears no required relationship to this year's box 1.
    ),
    notes="Box 2 is the principal as of Jan 1 (or origination). Property tax often appears in box 10 or a footer, not a numbered box.",
)

_FILER_ID = (
    _t("payer_name", "FILER'S name", r"FILER['’]S name"),
    _t("payer_tin", "FILER'S employer identification no.", r"FILER['’]S employer identification", kind="id"),
    _t("recipient_name", "STUDENT'S name", r"STUDENT['’]S name"),
    _t("recipient_tin", "STUDENT'S TIN", r"STUDENT['’]S TIN", kind="id"),
    _t("account_number", "Service Provider/Acct. No.", r"Acct\.? No", kind="id"),
)

F1098_T = DocType(
    name="1098-T", title="Tuition Statement",
    anchors=(r"Form\s*1098-T", r"Tuition Statement", r"Payments received for qualified tuition"),
    identity=_FILER_ID,
    boxes=(
        _m("box_1", "Payments received for qualified tuition and related expenses", r"Payments received for qualified tuition", required=True),
        _m("box_4", "Adjustments made for a prior year", r"Adjustments made for a prior year"),
        _m("box_5", "Scholarships or grants", r"Scholarships or grants"),
        _m("box_6", "Adjustments to scholarships or grants for a prior year", r"Adjustments to scholarships"),
        Box("box_7", "Box 1 includes amounts for an academic period beginning January–March", "flag", (r"academic period beginning",)),
        Box("box_8", "At least half-time student", "flag", (r"half-time student",)),
        Box("box_9", "Graduate student", "flag", (r"Graduate student",)),
        _m("box_10", "Ins. contract reimb./refund", r"Ins\.? contract reimb"),
    ),
    invariants=(
        Invariant("1098T.scholarships_exceed_payments", "INFO", "box_5 <= box_1 + 1",
                  "Scholarships (box 5) exceed payments received (box 1); the excess may be taxable income to the student.", ("box_1", "box_5")),
    ),
)

F1098_E = DocType(
    name="1098-E", title="Student Loan Interest Statement",
    anchors=(r"Form\s*1098-E", r"Student Loan Interest Statement", r"Student loan interest received"),
    identity=(
        _t("payer_name", "RECIPIENT'S name", r"RECIPIENT['’]S name"),
        _t("payer_tin", "RECIPIENT'S TIN", r"RECIPIENT['’]S TIN", kind="id"),
        _t("recipient_name", "BORROWER'S name", r"BORROWER['’]S name"),
        _t("recipient_tin", "BORROWER'S TIN", r"BORROWER['’]S TIN", kind="id"),
        _t("account_number", "Account number", r"Account number", kind="id"),
    ),
    boxes=(
        _m("box_1", "Student loan interest received by lender", r"Student loan interest received", required=True),
        Box("box_2", "Box 1 does not include loan origination fees and/or capitalized interest", "flag",
            (r"does not include loan origination fees",)),
    ),
)

_TRUSTEE_ID = (
    _t("payer_name", "TRUSTEE'S or ISSUER'S name", r"TRUSTEE['’]S or ISSUER['’]S name"),
    _t("payer_tin", "TRUSTEE'S or ISSUER'S TIN", r"TRUSTEE['’]S or ISSUER['’]S TIN", kind="id"),
    _t("recipient_name", "PARTICIPANT'S name", r"PARTICIPANT['’]S name"),
    _t("recipient_tin", "PARTICIPANT'S TIN", r"PARTICIPANT['’]S TIN", kind="id"),
    _t("account_number", "Account number", r"Account number", kind="id"),
)

F5498 = DocType(
    name="5498", title="IRA Contribution Information",
    anchors=(r"Form\s*5498\b(?!-)", r"IRA Contribution Information", r"Fair market value of account"),
    identity=_TRUSTEE_ID,
    boxes=(
        _m("box_1", "IRA contributions (other than amounts in boxes 2–4, 8–10, 13a, and 14a)", r"\b1\s*IRA contributions"),
        _m("box_2", "Rollover contributions", r"Rollover contributions"),
        _m("box_3", "Roth IRA conversion amount", r"Roth IRA conversion amount"),
        _m("box_4", "Recharacterized contributions", r"Recharacterized contributions"),
        _m("box_5", "Fair market value of account", r"Fair market value of account", required=True),
        _m("box_6", "Life insurance cost included in box 1", r"Life insurance cost"),
        # Box 7 is a row of four checkboxes whose captions also appear in box
        # labels above (box 3 "Roth IRA conversion", box 10 "Roth IRA
        # contributions") and in the form's own title. Anchor on the box number
        # first, and never let "Roth IRA" swallow a neighbouring money label.
        Box("box_7_ira", "IRA", "flag", (r"\b7\s*IRA\b",)),
        Box("box_7_sep", "SEP", "flag", (r"\b7[^\n]*\bSEP\b", r"\bSEP\b(?!\s*contributions)")),
        Box("box_7_simple", "SIMPLE", "flag", (r"\b7[^\n]*\bSIMPLE\b", r"\bSIMPLE\b(?!\s*contributions)")),
        Box("box_7_roth", "Roth IRA", "flag", (r"Roth IRA\b(?!\s*(?:conversion|contributions))",)),
        _m("box_8", "SEP contributions", r"SEP contributions"),
        _m("box_9", "SIMPLE contributions", r"SIMPLE contributions"),
        _m("box_10", "Roth IRA contributions", r"Roth IRA contributions"),
        Box("box_11", "Check if RMD for next year", "flag", (r"Check if RMD", r"RMD for 20\d\d")),
        _t("box_12a", "RMD date", r"12a\s*RMD date", kind="date"),
        _m("box_12b", "RMD amount", r"12b\s*RMD amount"),
        _m("box_13a", "Postponed/late contrib.", r"Postponed/late contrib"),
        _t("box_13b", "Year", r"13b\s*Year"),
        _t("box_13c", "Code", r"13c\s*Code", kind="code"),
        _m("box_14a", "Repayments", r"14a\s*Repayments"),
        _t("box_14b", "Code", r"14b\s*Code", kind="code"),
        _m("box_15a", "FMV of certain specified assets", r"FMV of certain specified assets"),
        _t("box_15b", "Code(s)", r"15b\s*Code", kind="code"),
    ),
    invariants=(
        Invariant("5498.contrib_limit", "MEDIUM",
                  "box_1 + (box_10 or 0) <= rules['ira_trad_roth'] + (rules.get('ira_catchup_50') or 0) + 1",
                  "IRA + Roth contributions exceed the year's limit plus catch-up. A trustee must report an "
                  "excess contribution, so a correctly issued form can say this — treat it as either a real "
                  "excess contribution (6% excise tax per year until corrected) or a misread, and resolve which.",
                  ("box_1", "box_10"), when="has('box_1') and rules.get('ira_trad_roth')"),
        Invariant("5498.insurance_le_contrib", "MEDIUM", "box_6 <= box_1 + 1",
                  "Life insurance cost (box 6) exceeds the box 1 contributions it is included in.", ("box_1", "box_6")),
        Invariant("5498.specified_le_fmv", "HIGH", "box_15a <= box_5 + 1",
                  "FMV of specified assets (box 15a) exceeds total account FMV (box 5).", ("box_5", "box_15a")),
    ),
)

F5498_SA = DocType(
    name="5498-SA", title="HSA, Archer MSA, or Medicare Advantage MSA Information",
    anchors=(r"Form\s*5498-SA", r"Medicare Advantage MSA Information", r"Total contributions made in"),
    identity=_TRUSTEE_ID,
    boxes=(
        _m("box_1", "Employee or self-employed person's Archer MSA contributions", r"Archer MSA contributions made in"),
        _m("box_2", "Total contributions made in the year", r"Total contributions made in", required=True),
        _m("box_3", "Total HSA or Archer MSA contributions made in the following year for the prior year",
           r"Total HSA or Archer MSA contributions", r"contributions made in 20\d\d for 20\d\d"),
        _m("box_4", "Rollover contributions", r"Rollover contributions"),
        _m("box_5", "Fair market value of HSA, Archer MSA, or MA MSA", r"Fair market value of HSA"),
        Box("box_6_hsa", "HSA", "flag", (r"\b6\s*HSA\b", r"\bHSA\b")),
        Box("box_6_archer", "Archer MSA", "flag", (r"\b6?\s*Archer MSA",)),
        Box("box_6_ma_msa", "MA MSA", "flag", (r"\bMA MSA",)),
    ),
    invariants=(
        Invariant("5498SA.archer_le_total", "MEDIUM", "box_1 <= box_2 + 1",
                  "Archer MSA contributions (box 1) exceed total contributions (box 2).", ("box_1", "box_2")),
    ),
)

# --------------------------------------------------------------------------
# 1095-A (Marketplace) — monthly grid
# --------------------------------------------------------------------------

_A_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_A_BOXES = []
for _i, _mo in enumerate(_A_MONTHS):
    _line = 21 + _i
    _A_BOXES += [
        _m(f"{_mo}_premium", f"Line {_line} col A monthly enrollment premium", rf"\b{_line}\s*{_mo.title()}"),
        _m(f"{_mo}_slcsp", f"Line {_line} col B SLCSP premium", rf"\b{_line}\s*{_mo.title()}"),
        _m(f"{_mo}_aptc", f"Line {_line} col C advance PTC", rf"\b{_line}\s*{_mo.title()}"),
    ]
_A_INV = [
    Invariant("1095A.annual_premium_ties", "HIGH",
              "near(annual_premium, " + " + ".join(f"({m}_premium or 0)" for m in _A_MONTHS) + ", tol=1)",
              "Line 33 column A annual total does not equal the sum of the monthly premiums.", ("annual_premium",)),
    Invariant("1095A.annual_slcsp_ties", "HIGH",
              "near(annual_slcsp, " + " + ".join(f"({m}_slcsp or 0)" for m in _A_MONTHS) + ", tol=1)",
              "Line 33 column B annual total does not equal the sum of the monthly SLCSP premiums.", ("annual_slcsp",)),
    Invariant("1095A.annual_aptc_ties", "HIGH",
              "near(annual_aptc, " + " + ".join(f"({m}_aptc or 0)" for m in _A_MONTHS) + ", tol=1)",
              "Line 33 column C annual total does not equal the sum of the monthly advance credit.", ("annual_aptc",)),
]
for _mo in _A_MONTHS:
    # Exempt the all-zero-premium month. When coverage is terminated for
    # nonpayment the Marketplace reports columns A and B as zero while column C
    # still carries the advance credit already paid, which the taxpayer must
    # reconcile. Requiring C <= A unconditionally fires on those valid forms.
    _A_INV.append(Invariant(f"1095A.{_mo}_aptc_le_premium", "HIGH",
                            f"({_mo}_premium == 0 and {_mo}_slcsp == 0) or {_mo}_aptc <= {_mo}_premium + 1",
                            f"{_mo.title()}: advance credit (col C) exceeds the enrollment premium (col A).",
                            (f"{_mo}_premium", f"{_mo}_slcsp", f"{_mo}_aptc")))

F1095_A = DocType(
    name="1095-A", title="Health Insurance Marketplace Statement",
    anchors=(r"Form\s*1095-A", r"Health Insurance Marketplace Statement", r"Monthly enrollment premiums"),
    identity=(
        _t("marketplace_identifier", "Marketplace identifier", r"Marketplace identifier"),
        _t("policy_number", "Marketplace-assigned policy number", r"policy number", kind="id"),
        _t("policy_issuer_name", "Policy issuer's name", r"Policy issuer['’]s name"),
        _t("recipient_name", "Recipient's name", r"Recipient['’]s name"),
        _t("recipient_ssn", "Recipient's SSN", r"Recipient['’]s SSN", kind="id"),
        _t("policy_start_date", "Policy start date", r"Policy start date", kind="date"),
        _t("policy_termination_date", "Policy termination date", r"Policy termination date", kind="date"),
    ),
    boxes=(
        *_A_BOXES,
        _m("annual_premium", "Line 33 col A annual totals", r"\b33\s*Annual Totals"),
        _m("annual_slcsp", "Line 33 col B annual totals", r"\b33\s*Annual Totals"),
        _m("annual_aptc", "Line 33 col C annual totals", r"\b33\s*Annual Totals"),
    ),
    invariants=tuple(_A_INV),
    notes="Part II covered individuals are captured as free text in warnings; Form 8962 needs the Part III grid, "
          "which is what the boxes hold. All three columns of a month deliberately share one label pattern "
          "(the printed line is `21 January <premium> <SLCSP> <APTC>`): the parser resolves them by column "
          "position on the line, not by pattern, so identical patterns here are correct rather than a bug.",
)

# --------------------------------------------------------------------------
# Types owned by other parsers: anchors only, so detection can route them.
# --------------------------------------------------------------------------

K1_1065 = DocType(
    name="K-1-1065", title="Partner's Share of Income, Deductions, Credits, etc.",
    anchors=(r"Schedule K-1", r"Form 1065", r"Partner['’]s Share of"),
    parser="k1-parser",
)
K1_1120S = DocType(
    name="K-1-1120S", title="Shareholder's Share of Income, Deductions, Credits, etc.",
    anchors=(r"Schedule K-1", r"Form 1120-?S", r"Shareholder['’]s Share of"),
    parser="k1-parser",
)
K1_1041 = DocType(
    name="K-1-1041", title="Beneficiary's Share of Income, Deductions, Credits, etc.",
    anchors=(r"Schedule K-1", r"Form 1041", r"Beneficiary['’]s Share of"),
    parser="k1-parser",
)
RETURN_1065 = DocType(
    name="1065-Return", title="U.S. Return of Partnership Income",
    anchors=(r"Form\s*1065\b", r"Return of Partnership Income", r"Schedule L"),
    parser="return-parser",
)
RETURN_1120 = DocType(
    name="1120-Return", title="U.S. Corporation Income Tax Return",
    anchors=(r"Form\s*1120\b(?!-?S)", r"Corporation Income Tax Return", r"Schedule J"),
    parser="return-parser",
)
RETURN_1120S = DocType(
    name="1120-S-Return", title="U.S. Income Tax Return for an S Corporation",
    anchors=(r"Form\s*1120-?S\b", r"Income Tax Return for an S Corporation", r"Schedule L"),
    parser="return-parser",
)
TRANSCRIPT = DocType(
    name="IRS-Transcript", title="IRS Transcript",
    anchors=(r"(?:Account|Tax Return|Wage and Income|Record of Account) Transcript", r"TRACKING NUMBER", r"CYCLE"),
    parser="transcript-parser",
)

# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

REGISTRY: dict[str, DocType] = {
    d.name: d for d in (
        W2, W2G,
        F1099_INT, F1099_DIV, F1099_B, F1099_COMPOSITE, F1099_NEC, F1099_MISC, F1099_R, F1099_G, F1099_K, F1099_SA,
        SSA_1099,
        F1098, F1098_T, F1098_E,
        F5498, F5498_SA,
        F1095_A,
        K1_1065, K1_1120S, K1_1041,
        RETURN_1065, RETURN_1120, RETURN_1120S,
        TRANSCRIPT,
    )
}

FORM_PARSER_TYPES: tuple[str, ...] = tuple(n for n, d in REGISTRY.items() if d.parser == "form-parser")


def get(name: str) -> DocType:
    key = name.strip()
    if key in REGISTRY:
        return REGISTRY[key]
    # tolerate common spellings: w2, W2, 1099int, 1099-int
    norm = key.upper().replace(" ", "").replace("_", "-")
    for cand in REGISTRY:
        if cand.upper().replace("-", "") == norm.replace("-", ""):
            return REGISTRY[cand]
    raise KeyError(f"unknown doc type {name!r}; known: {', '.join(REGISTRY)}")


if __name__ == "__main__":  # pragma: no cover - quick listing
    for n, d in REGISTRY.items():
        print(f"{n:16s} {d.parser:18s} boxes={len(d.boxes):3d} invariants={len(d.invariants):2d}  {d.title}")
