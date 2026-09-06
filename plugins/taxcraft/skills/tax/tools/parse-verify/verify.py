#!/usr/bin/env python3
"""
parse-verify — arithmetic and tax-law invariants over parsed tax JSON.

This is Layer B of the extraction-confidence system described in
`parsing.md` → "Verify before writing". Layer A (differential extraction)
catches transcription errors. Layer B catches errors that BOTH extractors
would faithfully reproduce — including issuer errors, which no amount of
extraction consensus can detect.

An invariant here does not ask "did we read this correctly?" It asks
"can this document be internally consistent at all?" A capital account
that does not roll forward is wrong no matter who read it.

Two shapes of input arrive here and both must verify identically:

  * legacy flat documents — `{"box_1_ordinary": -700, ...}`;
  * schema-2 envelope documents — every load-bearing value wrapped as
    `{"value": ..., "state": "OBSERVED_VALUE", ...}` (see
    `pdf-extractor/envelope.py`).

Every read below unwraps. The consequence that matters: an envelope in state
NOT_PRESENT / UNREADABLE unwraps to `None`, and a check whose input was
explicitly not observed is SKIPPED and reported at INFO as
`<check>.not_evaluable` — never computed with a substituted zero. `parsing.md`
states the rule plainly: missing is not zero. A capital account nobody read is
not a capital account of nil.

Coverage: K-1s and entity returns are checked by the hand-written functions in
this file; every other type in `form-parser/doc_types.py` is routed to its
declarative invariants through `form-parser/invariants.py`, so a W-2 or a
1099-INT is verified in the same Layer B pass and reports through the same
`Finding` records.

Usage:
    python3 verify.py <file.json>              # verify one parsed doc
    python3 verify.py <dir>/.parsed/           # verify all + cross-doc checks
    python3 verify.py <dir>/.parsed/ --json    # machine-readable output
    python3 verify.py <path> --min-severity HIGH

Exit codes:
    0 = no findings at or above --min-severity (default MEDIUM)
    1 = findings present
    2 = usage/IO error

Pure stdlib. No network. Never modifies anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

# Sibling tools. A broken or partial install must degrade, not crash a whole
# verify run, so each import has a stdlib-only fallback below.
_TOOLS = Path(__file__).resolve().parent.parent
for _sib in ("pdf-extractor", "form-parser"):
    _p = str(_TOOLS / _sib)
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # pragma: no cover - exercised by the installed tree
    from envelope import get_path, is_envelope, is_present, unwrap  # type: ignore
except Exception:  # pragma: no cover - envelope.py absent
    def is_envelope(x: Any) -> bool:  # type: ignore[misc]
        return isinstance(x, dict) and "value" in x and "state" in x

    def unwrap(x: Any) -> Any:  # type: ignore[misc]
        if is_envelope(x):
            return None if x["state"] in ("NOT_PRESENT", "UNREADABLE", "NOT_APPLICABLE") else x["value"]
        return x

    def is_present(x: Any) -> bool:  # type: ignore[misc]
        if is_envelope(x):
            return x["state"] in ("OBSERVED_VALUE", "OBSERVED_ZERO", "DERIVED", "MANUAL_OVERRIDE")
        return x is not None

    def get_path(doc: Any, path: str) -> Any:  # type: ignore[misc]
        cur = doc
        for part in str(path).split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

try:  # pragma: no cover
    import doc_types  # type: ignore
    import invariants  # type: ignore
except Exception:  # pragma: no cover - form-parser absent
    doc_types = None  # type: ignore[assignment]
    invariants = None  # type: ignore[assignment]

# Absolute dollar tolerance for arithmetic ties. Parsed values are whole
# dollars; anything beyond this is a real break, not a rounding artifact.
TOLERANCE = 1.0

SEVERITY_ORDER = {"INFO": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass
class Finding:
    severity: str          # CRITICAL | HIGH | MEDIUM | INFO
    check: str             # stable id, e.g. "K1.item_l.rollforward"
    doc: str               # filename
    message: str           # what is wrong
    detail: str = ""       # the arithmetic, shown so a human can re-derive it
    fields: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Tolerant field access
#
# Parsed JSON in the wild does not match the schema doc exactly: Item K
# appears as `nonrecourse`, `nonrecourse_beginning`, or `nonrecourse_beg`
# depending on which pass produced the file. Look up by alias rather than
# assuming one spelling.
# --------------------------------------------------------------------------

def pick(d: Optional[dict], *names: str, default: Any = None) -> Any:
    """First observed value among `names`, envelopes unwrapped.

    An envelope in state NOT_PRESENT / UNREADABLE unwraps to None and is
    treated as absent, so the search moves on to the next alias rather than
    stopping on a box the extractor never saw.
    """
    if not isinstance(d, dict):
        return default
    for n in names:
        if n in d:
            v = unwrap(d[n])
            if v is not None:
                return v
    return default


def unobserved(d: Optional[dict], *alias_groups: Any) -> list[str]:
    """Names the document explicitly records as NOT observed.

    Each argument is a field name or a tuple of aliases for one field. A group
    counts as unobserved when no alias carries a value AND at least one alias
    is an envelope whose state says the extractor did not read it. A key that
    is simply absent from a legacy flat document is not "unobserved" — the file
    never claimed to carry it, so the historical zero-default still applies.
    """
    out: list[str] = []
    if not isinstance(d, dict):
        return out
    for group in alias_groups:
        names = (group,) if isinstance(group, str) else tuple(group)
        if any(unwrap(d[n]) is not None for n in names if n in d):
            continue
        flagged = [n for n in names if n in d and is_envelope(d[n]) and not is_present(d[n])]
        if flagged:
            out.append(flagged[0])
    return out


def not_evaluable(check: str, doc: str, what: str, missing: list[str],
                  fields: Optional[list[str]] = None) -> Finding:
    """The finding a skipped check leaves behind, so a reviewer can see what
    was NOT proven. Never a pass, never a failure — an open question."""
    return Finding(
        "INFO", f"{check}.not_evaluable", doc,
        f"Not evaluated: {what} — input not observed.",
        f"The extractor recorded no observation for {', '.join(missing)}. "
        f"A box that was not read is not a zero, so this check was skipped "
        f"rather than computed against a substituted zero. Supply the value "
        f"(vision pass or the paper form) to evaluate it.",
        fields if fields is not None else list(missing),
    )


def num(v: Any, default: float = 0.0) -> float:
    """Coerce to float; treat unparseable/absent as `default`. Unwraps envelopes."""
    v = unwrap(v)
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(",", "").replace("$", "").strip()
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        try:
            return float(s)
        except ValueError:
            return default
    return default


def item_k_total(item_k: Optional[dict], which: str = "ending") -> float:
    """
    Partner's share of partnership liabilities (Item K).

    `which` selects beginning- or end-of-year where the file distinguishes
    them; files that carry a single value are returned as-is.
    """
    if not isinstance(item_k, dict):
        return 0.0
    # Some files nest by year-end instead of suffixing the key:
    #   {"beginning": {"nonrecourse": 0, ...}, "ending": {...}}
    nested = item_k.get(which)
    if is_envelope(nested):
        nested = None
    if isinstance(nested, dict):
        return (num(pick(nested, "nonrecourse"))
                + num(pick(nested, "qnr"))
                + num(pick(nested, "recourse")))
    if which == "beginning":
        return (
            num(pick(item_k, "nonrecourse_beginning", "nonrecourse_beg", "nonrecourse"))
            + num(pick(item_k, "qnr_beginning", "qnr_beg", "qnr"))
            + num(pick(item_k, "recourse_beginning", "recourse_beg", "recourse"))
        )
    return (
        num(pick(item_k, "nonrecourse_ending", "nonrecourse_end", "nonrecourse"))
        + num(pick(item_k, "qnr_ending", "qnr_end", "qnr"))
        + num(pick(item_k, "recourse_ending", "recourse_end", "recourse"))
    )


_ITEM_K_GROUPS = {
    "beginning": (("nonrecourse_beginning", "nonrecourse_beg", "nonrecourse"),
                  ("qnr_beginning", "qnr_beg", "qnr"),
                  ("recourse_beginning", "recourse_beg", "recourse")),
    "ending": (("nonrecourse_ending", "nonrecourse_end", "nonrecourse"),
               ("qnr_ending", "qnr_end", "qnr"),
               ("recourse_ending", "recourse_end", "recourse")),
}


def item_k_unobserved(item_k: Optional[dict], which: str = "ending") -> list[str]:
    """Item K liability fields the document says were not observed."""
    if not isinstance(item_k, dict):
        return []
    nested = item_k.get(which)
    if isinstance(nested, dict) and not is_envelope(nested):
        return unobserved(nested, "nonrecourse", "qnr", "recourse")
    return unobserved(item_k, *_ITEM_K_GROUPS[which])


# Boxes that carry allocated income/loss. Used to decide whether a K-1 has
# any activity at all, and to size a loss against basis for §704(d).
INCOME_BOXES = [
    "box_1_ordinary", "box_2_rental_re", "box_3_other_rental", "box_3_other_net_rental",
    "box_5_interest", "box_6a_ord_div", "box_7_royalties",
    "box_8_st_cap", "box_9a_lt_cap", "box_10_1231",
]


def activity_total(d: dict) -> float:
    return sum(num(d.get(b)) for b in INCOME_BOXES)


def loss_total(d: dict) -> float:
    """Magnitude of allocated losses (positive number)."""
    return sum(-num(d.get(b)) for b in INCOME_BOXES if num(d.get(b)) < 0)


# --------------------------------------------------------------------------
# K-1 invariants
# --------------------------------------------------------------------------

# Item L aliases, one tuple per line of the capital account analysis.
_ITEM_L_GROUPS = (
    ("beginning", "beginning_capital"),
    ("contributions", "contrib", "capital_contributed"),
    ("current_year_net_income", "net_income", "current_year_increase"),
    ("other_increases",),
    ("withdrawals", "withdraw", "distributions"),
    ("other_decreases",),
    ("ending", "ending_capital"),
)


def check_k1(d: dict, doc: str) -> list[Finding]:
    out: list[Finding] = []
    item_l = d.get("part_ii_item_l") or d.get("capital_account")
    item_k = d.get("part_ii_item_k") or d.get("liabilities")
    if is_envelope(item_l):
        item_l = None
    if is_envelope(item_k):
        item_k = None

    # Any capital-account or liability line the document says was never read
    # disqualifies every check built on it. Skipping is the whole point: the
    # alternative is asserting a §704(d) violation out of a zero we invented.
    l_missing = unobserved(item_l, *_ITEM_L_GROUPS)
    k_missing = item_k_unobserved(item_k, "ending") + item_k_unobserved(item_k, "beginning")
    k_missing = sorted(set(k_missing))
    boxes_missing = unobserved(d, *INCOME_BOXES)

    # -- Item L capital account rollforward -------------------------------
    #
    # Sign conventions are NOT consistent across parsed files: some store
    # withdrawals as negative (already signed), others as a positive
    # magnitude meant to be subtracted. Both appear in this workspace and a
    # validator that assumes one silently passes half the population.
    # Compute both readings; the account ties if EITHER reconciles.
    if isinstance(item_l, dict) and l_missing:
        out.append(not_evaluable(
            "K1.item_l.rollforward", doc,
            "the Item L capital account rollforward", l_missing,
            ["part_ii_item_l"]))
    elif isinstance(item_l, dict):
        beg = num(pick(item_l, "beginning", "beginning_capital"))
        con = num(pick(item_l, "contributions", "contrib", "capital_contributed"))
        inc = num(pick(item_l, "current_year_net_income", "net_income", "current_year_increase"))
        oi = num(pick(item_l, "other_increases"))
        wd = num(pick(item_l, "withdrawals", "withdraw", "distributions"))
        od = num(pick(item_l, "other_decreases"))
        end = num(pick(item_l, "ending", "ending_capital"))

        signed = beg + con + inc + oi + wd + od
        magnitude = beg + con + inc + oi - abs(wd) - abs(od)
        ties_signed = abs(signed - end) <= TOLERANCE
        ties_mag = abs(magnitude - end) <= TOLERANCE

        populated = any(abs(x) > TOLERANCE for x in (beg, con, inc, oi, wd, od, end))

        if not populated and boxes_missing:
            # Item L is empty and we cannot even total the income boxes, so
            # "blank while allocating activity" is unprovable either way.
            out.append(not_evaluable(
                "K1.item_l.blank", doc,
                "whether Item L is blank while the K-1 allocates activity",
                boxes_missing, ["part_ii_item_l"]))
        elif not populated and abs(activity_total(d)) > TOLERANCE:
            # Blank-Item-L pattern: every Item L field blank (encoded as
            # zero) while the K-1 allocates real income or loss. The capital
            # account cannot be verified at all, and negative capital from a
            # profits interest is exactly the case that must be shown.
            out.append(Finding(
                "HIGH", "K1.item_l.blank", doc,
                "Item L capital account is entirely blank/zero while the K-1 allocates activity.",
                f"activity across income boxes = {activity_total(d):,.0f}; "
                f"every Item L field is 0 or absent — nothing to reconcile. "
                f"Request a corrected K-1 with Item L populated.",
                ["part_ii_item_l"],
            ))
        elif populated and not (ties_signed or ties_mag):
            out.append(Finding(
                "CRITICAL", "K1.item_l.rollforward", doc,
                "Item L capital account does not roll forward under either sign convention.",
                f"beginning {beg:,.0f} + contributions {con:,.0f} + net income {inc:,.0f} "
                f"+ other increases {oi:,.0f} then withdrawals {wd:,.0f} / other decreases {od:,.0f} "
                f"→ signed {signed:,.0f} or magnitude {magnitude:,.0f}, but ending is stated as {end:,.0f} "
                f"(off by {min(abs(signed - end), abs(magnitude - end)):,.0f}).",
                ["part_ii_item_l"],
            ))

        # Negative ending capital is legal but is the classic §704(d) tell.
        if populated and end < -TOLERANCE:
            out.append(Finding(
                "INFO", "K1.item_l.negative_ending", doc,
                "Ending capital account is negative.",
                f"ending {end:,.0f}. Legal (common for profits-interest holders), but confirm "
                f"the loss was allowed under §704(d) and not merely booked.",
                ["part_ii_item_l"],
            ))

    # -- §704(d): loss allowed only to the extent of outside basis --------
    #
    # Outside basis proxy = capital + share of partnership liabilities
    # (§722 / §752). A loss exceeding that should be suspended, not passed
    # through. This is the check that catches an issuer flowing a loss to a
    # partner with no basis.
    if isinstance(item_l, dict) and (l_missing or k_missing or boxes_missing):
        out.append(not_evaluable(
            "K1.704d.loss_exceeds_basis", doc,
            "whether the allocated loss exceeds outside basis (§704(d))",
            l_missing + k_missing + boxes_missing,
            ["part_ii_item_l", "part_ii_item_k"]))
    elif isinstance(item_l, dict):
        beg = num(pick(item_l, "beginning", "beginning_capital"))
        con = num(pick(item_l, "contributions", "contrib"))
        debt = item_k_total(item_k, "beginning") or item_k_total(item_k, "ending")
        basis_proxy = beg + con + debt
        loss = loss_total(d)

        # A blank Item L means basis is UNKNOWN, not zero. Reporting
        # "basis = 0" for an unpopulated capital account would assert a
        # §704(d) violation the document does not actually support.
        capital_known = any(
            pick(item_l, k) is not None
            for k in ("beginning", "beginning_capital", "contributions", "contrib")
        ) and any(
            abs(x) > TOLERANCE
            for x in (beg, con, num(pick(item_l, "ending", "ending_capital")))
        )

        if loss > TOLERANCE and loss > basis_proxy + TOLERANCE:
            if capital_known:
                out.append(Finding(
                    "CRITICAL", "K1.704d.loss_exceeds_basis", doc,
                    "Allocated loss exceeds the partner's outside basis — §704(d) suspension may apply.",
                    f"loss {loss:,.0f} vs basis {basis_proxy:,.0f} "
                    f"(beginning capital {beg:,.0f} + contributions {con:,.0f} + liability share {debt:,.0f}). "
                    f"Loss is deductible only to the extent of basis; the excess should be suspended "
                    f"and carried forward, not passed through.",
                    ["part_ii_item_l", "part_ii_item_k"],
                ))
            else:
                out.append(Finding(
                    "HIGH", "K1.704d.basis_undeterminable", doc,
                    "Loss allocated but outside basis cannot be determined from this K-1.",
                    f"loss {loss:,.0f} allocated while Item L is unpopulated and Item K liability "
                    f"share is {debt:,.0f}. Basis is unknown, not zero — §704(d) cannot be tested "
                    f"until Item L is populated or basis is established from another source.",
                    ["part_ii_item_l", "part_ii_item_k"],
                ))

    # -- Outside basis worksheet vs capital + liabilities -----------------
    #
    # A basis worksheet should approximate Item L ending capital plus the
    # Item K liability share. A large liability share is legitimate; a
    # worksheet that cannot be explained by capital + debt is a data error.
    bw = unwrap(d.get("basis_worksheet_end_of_year"))
    bw_src = d.get("basis_worksheet")
    if bw is None and isinstance(bw_src, dict) and not is_envelope(bw_src):
        bw = pick(bw_src, "end_of_year", "ending")
    if bw is not None and (l_missing or k_missing):
        out.append(not_evaluable(
            "K1.basis_worksheet.unexplained", doc,
            "whether the basis worksheet is explained by capital plus liability share",
            l_missing + k_missing,
            ["basis_worksheet_end_of_year", "part_ii_item_k", "part_ii_item_l"]))
    elif bw is not None:
        bw_v = num(bw)
        end_cap = num(pick(item_l, "ending", "ending_capital")) if isinstance(item_l, dict) else 0.0
        debt_end = item_k_total(item_k, "ending")
        explained = end_cap + debt_end
        # Only meaningful when the worksheet is materially non-zero.
        if abs(bw_v) > 1000 and abs(bw_v - explained) > max(1000.0, 0.25 * abs(bw_v)):
            out.append(Finding(
                "HIGH", "K1.basis_worksheet.unexplained", doc,
                "Basis worksheet cannot be explained by capital account plus liability share.",
                f"worksheet end-of-year basis {bw_v:,.0f} vs Item L ending capital {end_cap:,.0f} "
                f"+ Item K liabilities {debt_end:,.0f} = {explained:,.0f} "
                f"(unexplained {bw_v - explained:,.0f}). Under §722/§752 these should approximately tie; "
                f"a gap this size usually means an entity-level figure was reported as a partner share.",
                ["basis_worksheet_end_of_year", "part_ii_item_k", "part_ii_item_l"],
            ))

    # -- Guaranteed payments are not distributions ------------------------
    #
    # The documented misread in this workspace. Box 4a/4c (guaranteed
    # payments, ordinary income to the partner) and Box 19 (distributions,
    # generally not income) are adjacent on the form and get swapped.
    gp_missing = unobserved(d, ("box_4c_gp_total", "box_4a_gp_services"),
                            ("box_19_distributions", "box_19_a_cash"))
    gp = num(pick(d, "box_4c_gp_total", "box_4a_gp_services"))
    dist = num(pick(d, "box_19_distributions", "box_19_a_cash"))
    if gp_missing:
        out.append(not_evaluable(
            "K1.gp_equals_distribution", doc,
            "whether guaranteed payments were read into the distributions box",
            gp_missing, ["box_4c_gp_total", "box_19_distributions"]))
    elif abs(gp) > TOLERANCE and abs(gp - dist) <= TOLERANCE:
        out.append(Finding(
            "HIGH", "K1.gp_equals_distribution", doc,
            "Guaranteed payments and distributions are identical — likely the same figure read into both.",
            f"Box 4a/4c {gp:,.0f} == Box 19 {dist:,.0f}. Guaranteed payments are ordinary income; "
            f"distributions generally are not. Confirm against the source form before relying on either.",
            ["box_4c_gp_total", "box_19_distributions"],
        ))

    # -- Ownership percentages must be percentages ------------------------
    for k in ("pct_profit", "pct_loss", "pct_capital", "pct_profit_end",
              "pct_loss_end", "pct_capital_end"):
        if k in d and unwrap(d[k]) is not None:
            v = num(d[k], default=-1.0)
            if v < 0 or v > 100:
                out.append(Finding(
                    "MEDIUM", "K1.pct.out_of_range", doc,
                    f"Ownership percentage `{k}` is outside 0–100.",
                    f"{k} = {d[k]!r}. A fraction stored as 0.13 where 13.0 was meant "
                    f"silently understates every derived allocation.",
                    [k],
                ))

    # -- §199A QBI should correspond to allocated income ------------------
    stmt = unwrap(d.get("statement_a_199a")) or unwrap(d.get("statement_a_qbi_per_partner"))
    qbi_missing = unobserved(d, "box_1_ordinary", "box_2_rental_re")
    if isinstance(stmt, list) and stmt and qbi_missing:
        out.append(not_evaluable(
            "K1.199a.zeroed", doc,
            "whether the §199A statement is zeroed against allocated income",
            qbi_missing, ["statement_a_199a"]))
    elif isinstance(stmt, list) and stmt:
        def entry_qbi(s: dict) -> float:
            # A single combined figure if the file carries one...
            combined = pick(s, "qbi", "qbi_income_loss")
            if combined is not None:
                return num(combined)
            # ...otherwise ordinary and rental are separate COMPONENTS of the
            # same statement and must be summed, not chosen between. Field
            # spelling varies by extraction pass.
            return (num(pick(s, "qbi_ordinary_income_loss", "qbi_ordinary"))
                    + num(pick(s, "qbi_rental_income_loss", "qbi_rental")))

        qbi = sum(entry_qbi(s) for s in stmt if isinstance(s, dict))
        base = num(d.get("box_1_ordinary")) + num(d.get("box_2_rental_re"))
        if abs(base) > TOLERANCE and abs(qbi) <= TOLERANCE:
            out.append(Finding(
                "MEDIUM", "K1.199a.zeroed", doc,
                "§199A statement reports zero QBI while the K-1 allocates business/rental income.",
                f"Box 1 + Box 2 = {base:,.0f} but Statement A QBI totals {qbi:,.0f}. "
                f"A zeroed pass-through is a known preparer defect — it silently drops the deduction.",
                ["statement_a_199a"],
            ))

    # -- Surface flags the extractor already recorded ---------------------
    if unwrap(d.get("titling_error")):
        out.append(Finding(
            "MEDIUM", "K1.titling", doc,
            "Extractor flagged a partner-titling error on this K-1.",
            str(unwrap(d.get("titling_note")) or "").strip()[:400],
            ["titling_error"],
        ))
    for a in (unwrap(d.get("anomalies")) or []):
        out.append(Finding("INFO", "K1.anomaly", doc,
                           "Extractor recorded an anomaly.", str(a)[:400], ["anomalies"]))

    return out


# --------------------------------------------------------------------------
# 1065 / entity return invariants
# --------------------------------------------------------------------------

def check_1065(d: dict, doc: str) -> list[Finding]:
    out: list[Finding] = []
    sl = d.get("schedule_l") or d.get("schedule_l_balance_sheet")
    m2 = d.get("schedule_m2") or d.get("schedule_m2_capital")
    if is_envelope(sl):
        sl = None
    if is_envelope(m2):
        m2 = None

    # -- Balance sheet must balance, both columns -------------------------
    if isinstance(sl, dict):
        for col in ("beginning", "ending"):
            c = sl.get(col)
            if is_envelope(c) or not isinstance(c, dict):
                continue
            col_missing = unobserved(c, ("total_assets",),
                                     ("total_liab", "total_liabilities"),
                                     ("partners_capital", "total_capital"))
            if col_missing:
                out.append(not_evaluable(
                    "1065.schedule_l.imbalance", doc,
                    f"whether Schedule L balances ({col} of year)",
                    col_missing, ["schedule_l"]))
                continue
            assets = num(pick(c, "total_assets"))
            liab = num(pick(c, "total_liab", "total_liabilities"))
            cap = num(pick(c, "partners_capital", "total_capital"))
            if abs(assets) < TOLERANCE and abs(liab) < TOLERANCE and abs(cap) < TOLERANCE:
                continue
            if abs(assets - (liab + cap)) > TOLERANCE:
                out.append(Finding(
                    "CRITICAL", "1065.schedule_l.imbalance", doc,
                    f"Schedule L does not balance ({col} of year).",
                    f"total assets {assets:,.0f} vs liabilities {liab:,.0f} + capital {cap:,.0f} "
                    f"= {liab + cap:,.0f} (off by {assets - (liab + cap):,.0f}).",
                    ["schedule_l"],
                ))

    # -- M-2 rollforward --------------------------------------------------
    m2_missing = unobserved(m2, "beginning", "contributions", "net_income", "other_increases",
                            "distributions_cash", "distributions_property", "other_decreases",
                            "ending")
    if isinstance(m2, dict) and m2_missing:
        out.append(not_evaluable(
            "1065.m2.rollforward", doc,
            "the Schedule M-2 capital rollforward", m2_missing, ["schedule_m2"]))
    elif isinstance(m2, dict):
        beg = num(pick(m2, "beginning"))
        con = num(pick(m2, "contributions"))
        inc = num(pick(m2, "net_income"))
        oi = num(pick(m2, "other_increases"))
        dc = num(pick(m2, "distributions_cash"))
        dp = num(pick(m2, "distributions_property"))
        od = num(pick(m2, "other_decreases"))
        end = num(pick(m2, "ending"))
        signed = beg + con + inc + oi + dc + dp + od
        magnitude = beg + con + inc + oi - abs(dc) - abs(dp) - abs(od)
        if not (abs(signed - end) <= TOLERANCE or abs(magnitude - end) <= TOLERANCE):
            out.append(Finding(
                "CRITICAL", "1065.m2.rollforward", doc,
                "Schedule M-2 does not roll forward under either sign convention.",
                f"beginning {beg:,.0f} + contributions {con:,.0f} + net income {inc:,.0f} "
                f"+ other increases {oi:,.0f}, distributions {dc + dp:,.0f}, other decreases {od:,.0f} "
                f"→ {signed:,.0f} / {magnitude:,.0f} vs stated ending {end:,.0f}.",
                ["schedule_m2"],
            ))

        # -- M-2 ending must tie to Schedule L ending capital -------------
        if isinstance(sl, dict) and isinstance(sl.get("ending"), dict):
            sl_cap = num(pick(sl["ending"], "partners_capital", "total_capital"))
            if abs(sl_cap) > TOLERANCE and abs(end - sl_cap) > TOLERANCE:
                out.append(Finding(
                    "HIGH", "1065.m2_vs_schedule_l", doc,
                    "Schedule M-2 ending capital does not equal Schedule L ending partners' capital.",
                    f"M-2 ending {end:,.0f} vs Schedule L ending capital {sl_cap:,.0f} "
                    f"(off by {end - sl_cap:,.0f}). These are the same number reported twice.",
                    ["schedule_m2", "schedule_l"],
                ))

    for a in (unwrap(d.get("anomalies")) or []):
        out.append(Finding("INFO", "1065.anomaly", doc,
                           "Extractor recorded an anomaly.", str(a)[:400], ["anomalies"]))
    return out


# --------------------------------------------------------------------------
# Cross-document invariant: issued K-1s must sum to Schedule K
# --------------------------------------------------------------------------

# Schedule K line ↔ K-1 box, for the lines that must foot exactly.
K_LINE_TO_BOX = {
    "line_1_ordinary": "box_1_ordinary",
    "line_2_rental_re": "box_2_rental_re",
    "line_4c_gp_total": "box_4c_gp_total",
    "line_5_interest": "box_5_interest",
    "line_6a_ord_div": "box_6a_ord_div",
    "line_8_st_cap": "box_8_st_cap",
    "line_9a_lt_cap": "box_9a_lt_cap",
    "line_10_1231": "box_10_1231",
    "line_12_179": "box_12_179",
}


def field_of(d: dict, *names: str) -> Any:
    """A value from a schema-2 document (`identity` / `boxes` sections) or from
    the top level of a legacy flat one, envelopes unwrapped."""
    for section in ("identity", "boxes"):
        sub = d.get(section)
        if isinstance(sub, dict) and not is_envelope(sub):
            v = pick(sub, *names)
            if v is not None:
                return v
    return pick(d, *names)


def check_w2_duplicates(docs: dict[str, dict]) -> list[Finding]:
    """The same W-2 filed twice.

    Two files carrying one employer EIN, one employee SSN and one tax year are
    the same wage statement — a re-download, a Copy B and a Copy 2 saved
    separately, or the same PDF parsed under two names. Summed rather than
    deduped, they double the wages and the withholding, and the return is
    wrong in the direction that looks like a refund.
    """
    out: list[Finding] = []
    seen: dict[tuple, str] = {}
    for name in sorted(docs):
        d = docs[name]
        if str(unwrap(d.get("doc_type")) or "").strip().upper().replace(" ", "") not in ("W-2", "W2"):
            continue
        ein = field_of(d, "employer_ein", "employer_id", "employer_tin")
        ssn = field_of(d, "employee_ssn", "employee_tin", "employee_ssn_last4")
        year = unwrap(d.get("tax_year")) or field_of(d, "tax_year")
        if not (ein and ssn and year):
            continue
        key = (str(ein).strip(), str(ssn).strip()[-4:], str(year).strip())
        first = seen.get(key)
        if first is None:
            seen[key] = name
            continue
        wages_a = num(field_of(docs[first], "box_1"))
        wages_b = num(field_of(d, "box_1"))
        out.append(Finding(
            "HIGH", "W2.duplicate", name,
            "This W-2 has the same employer, employee and tax year as another parsed W-2.",
            f"`{first}` and `{name}` share employer EIN {ein}, employee SSN …{key[1]} and "
            f"tax year {year} (box 1: {wages_a:,.0f} vs {wages_b:,.0f}). Either they are two "
            f"copies of one statement — include it once — or one is a corrected W-2c that "
            f"replaces the other. Summing both doubles wages and withholding.",
            ["employer_ein", "employee_ssn", "tax_year", "box_1"],
        ))
    return out


def check_cross(docs: dict[str, dict]) -> list[Finding]:
    """Checks that need more than one parsed document."""
    out: list[Finding] = check_w2_duplicates(docs)

    returns = {n: d for n, d in docs.items()
               if str(unwrap(d.get("doc_type")) or "").startswith(("1065", "1120"))}
    issued = {n: d for n, d in docs.items()
              if unwrap(d.get("direction")) == "issued"
              and "K-1" in str(unwrap(d.get("doc_type")) or "").upper()}

    if not returns or not issued:
        return out

    for rname, rdoc in returns.items():
        sk = rdoc.get("schedule_k") or rdoc.get("schedule_k_separately_stated")
        if is_envelope(sk) or not isinstance(sk, dict):
            continue
        peers = {n: d for n, d in issued.items()
                 if str(unwrap(d.get("tax_year"))) == str(unwrap(rdoc.get("tax_year")))}
        if not peers:
            continue

        for line, box in K_LINE_TO_BOX.items():
            if line not in sk:
                continue
            line_missing = unobserved(sk, line)
            for pname, pdoc in peers.items():
                line_missing += [f"{pname}:{b}" for b in unobserved(pdoc, box)]
            if line_missing:
                out.append(not_evaluable(
                    "cross.k_vs_k1_sum", rname,
                    f"whether Schedule K {line} equals the sum of the issued K-1 {box}",
                    line_missing, [line, box]))
                continue
            entity = num(sk.get(line))
            partners = sum(num(d.get(box)) for d in peers.values())
            if abs(entity) < TOLERANCE and abs(partners) < TOLERANCE:
                continue
            if abs(entity - partners) > TOLERANCE:
                out.append(Finding(
                    "HIGH", "cross.k_vs_k1_sum", rname,
                    f"Schedule K {line} does not equal the sum of issued K-1 {box}.",
                    f"Schedule K {entity:,.0f} vs {len(peers)} partner K-1s totalling {partners:,.0f} "
                    f"(off by {entity - partners:,.0f}). Every separately-stated item must foot to "
                    f"the partners; a gap means an item was not passed through.",
                    [line, box],
                ))

        # -- Received pass-through items must reach the entity return ----
        #
        # A tiered structure leaks quietly: an item reported on a K-1 the
        # entity RECEIVED must appear on its own Schedule K, or it never
        # reaches the ultimate partners. Nondeductible expenses (Box 18C)
        # are the usual casualty — small enough to overlook, but they belong
        # in the M-2 "other decreases" and in each partner's basis.
        received = {n: d for n, d in docs.items()
                    if unwrap(d.get("direction")) == "received"
                    and str(unwrap(d.get("tax_year"))) == str(unwrap(rdoc.get("tax_year")))}
        if received:
            inbound = sum(num(d.get(k))
                          for d in received.values()
                          for k in d
                          if k.startswith("box_18") and "nondeduct" in k)
            reported = num(pick(sk, "line_18c_nondeductible_expenses", "line_18c"))
            if abs(inbound) > TOLERANCE and abs(inbound - reported) > TOLERANCE:
                out.append(Finding(
                    "MEDIUM", "cross.nondeductible_passthrough", rname,
                    "Nondeductible expenses on received K-1s do not appear on this entity's Schedule K.",
                    f"received K-1s report {inbound:,.0f} of Box 18C nondeductible expenses, but "
                    f"Schedule K line 18c shows {reported:,.0f} (gap {inbound - reported:,.0f}). "
                    f"Unreported, it is missing from the partners' basis and from M-2 other decreases.",
                    ["line_18c_nondeductible_expenses", "box_18_nondeductible_c"],
                ))

        # Ownership percentages across issued K-1s should total 100%.
        pcts = [num(pick(d, "pct_capital_end", "pct_capital"), default=-1.0) for d in peers.values()]
        pcts = [p for p in pcts if p >= 0]
        if pcts and abs(sum(pcts) - 100.0) > 0.5:
            out.append(Finding(
                "HIGH", "cross.ownership_sum", rname,
                "Issued K-1 capital percentages do not total 100%.",
                f"{len(pcts)} partner K-1s total {sum(pcts):.4f}%.",
                ["pct_capital"],
            ))

    return out


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def classify(d: dict) -> str:
    """Which check set owns this document.

    K-1s and entity returns have hand-written checks here (their invariants are
    cross-sectional and sign-convention-sensitive, which the declarative
    registry does not express). Everything the registry owns — every doc type
    whose `parser` is `form-parser`: W-2, the 1099 family, 1098s, 1095-A, 5498,
    SSA-1099 — is routed to `invariants.evaluate`. Anything unrecognised stays
    "other" and is left alone rather than guessed at.
    """
    raw = str(unwrap(d.get("doc_type")) or "")
    dt = raw.upper()
    if "K-1" in dt or "K1" in dt:
        return "k1"
    if dt.startswith(("1065", "1120")):
        return "return"
    if doc_types is not None and raw.strip():
        try:
            registered = doc_types.get(raw)
        except Exception:  # a registry miss must never crash a run
            registered = None
        if registered is not None and registered.parser == "form-parser":
            return "form"
    return "other"


def check_registry_doc(d: dict, doc: str) -> list[Finding]:
    """Run the declarative invariants for a registry doc type."""
    if invariants is None:
        return []
    try:
        raw = invariants.evaluate(d, doc_name=doc)
    except Exception as e:  # pragma: no cover - a registry bug is a finding, not a crash
        return [Finding("MEDIUM", "registry.evaluation_failed", doc,
                        "The declarative invariants for this doc type could not be evaluated.",
                        f"{type(e).__name__}: {e}", ["doc_type"])]
    out: list[Finding] = []
    for f in raw:
        sev = f.get("severity", "INFO")
        out.append(Finding(
            sev if sev in SEVERITY_ORDER else "INFO",
            str(f.get("check", "registry.unknown")),
            str(f.get("doc", doc)) or doc,
            str(f.get("message", "")),
            str(f.get("detail", "")),
            list(f.get("fields") or []),
        ))
    return out


def check_extraction(d: dict, doc: str) -> list[Finding]:
    """What the extractor itself said about this document.

    `_extraction.review_required` lists the fields where the text pass and the
    vision pass disagreed. The merge kept one of them; which one is right is a
    question only the page can answer, so each disagreement is surfaced as its
    own finding rather than buried in the JSON.
    """
    out: list[Finding] = []
    ext = d.get("_extraction")
    if not isinstance(ext, dict):
        return out

    for path in ext.get("review_required") or []:
        detail = ""
        try:
            env = get_path(d, str(path))
        except Exception:
            env = None
        if is_envelope(env):
            alts = ", ".join(f"{a.get('engine')}={a.get('value')!r}"
                             for a in (env.get("alternates") or []))
            detail = (f"merged value {env.get('value')!r} ({env.get('state')}, "
                      f"confidence {env.get('confidence')})"
                      + (f" vs {alts}" if alts else ""))
        out.append(Finding(
            "MEDIUM", "EXTRACTION.review_required", doc,
            f"Engines disagreed on `{path}` — confirm it against the page.",
            detail or "The text pass and the vision pass read this field differently; "
                      "the merge kept one of them and flagged the field.",
            [str(path)],
        ))

    quality = ext.get("quality")
    if isinstance(quality, dict) and quality.get("verdict") == "suspect":
        reasons = quality.get("reasons") or []
        out.append(Finding(
            "INFO", "EXTRACTION.text_suspect", doc,
            "The extracted text scored as suspect, so every figure here is provisional.",
            "; ".join(str(r) for r in reasons)
            or "quality.assess() returned verdict=suspect. A vision pass over the page "
               "images is the cross-check that settles it.",
            ["_extraction.quality"],
        ))
    return out


def verify_docs(docs: dict[str, dict]) -> list[Finding]:
    out: list[Finding] = []
    for name, d in sorted(docs.items()):
        kind = classify(d)
        if kind == "k1":
            out.extend(check_k1(d, name))
        elif kind == "return":
            out.extend(check_1065(d, name))
        elif kind == "form":
            out.extend(check_registry_doc(d, name))
        out.extend(check_extraction(d, name))
    out.extend(check_cross(docs))
    return out


def load(path: Path) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    files: Iterable[Path]
    if path.is_dir():
        files = sorted(p for p in path.glob("*.json") if p.name != "_index.json")
    else:
        files = [path]
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"skipped {f.name}: {e}", file=sys.stderr)
            continue
        # Some parsed files hold a bare list (e.g. an array of statements)
        # rather than a document object. Nothing to verify, but never crash
        # a whole-directory run over one odd file.
        if not isinstance(doc, dict):
            print(f"skipped {f.name}: top-level JSON is "
                  f"{type(doc).__name__}, expected object", file=sys.stderr)
            continue
        docs[f.name] = doc
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify arithmetic and tax-law invariants over parsed tax JSON.")
    ap.add_argument("path", help="parsed JSON file, or a .parsed/ directory")
    ap.add_argument("--json", action="store_true", help="emit JSON findings")
    ap.add_argument("--min-severity", default="MEDIUM",
                    choices=list(SEVERITY_ORDER), help="gate for exit code and display")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"no such path: {path}", file=sys.stderr)
        return 2

    docs = load(path)
    if not docs:
        print("no parsed JSON found", file=sys.stderr)
        return 2

    findings = verify_docs(docs)
    floor = SEVERITY_ORDER[args.min_severity]
    shown = [f for f in findings if SEVERITY_ORDER[f.severity] >= floor]
    shown.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.doc, f.check))

    if args.json:
        print(json.dumps({
            "docs_checked": len(docs),
            "findings_total": len(findings),
            "findings": [asdict(f) for f in shown],
        }, indent=2))
        return 1 if shown else 0

    print(f"parse-verify — {len(docs)} document(s) checked\n")
    if not shown:
        print(f"No findings at or above {args.min_severity}.")
        suppressed = len(findings) - len(shown)
        if suppressed:
            print(f"({suppressed} lower-severity finding(s) suppressed.)")
        return 0

    for f in shown:
        print(f"[{f.severity}] {f.doc} — {f.check}")
        print(f"  {f.message}")
        if f.detail:
            print(f"  {f.detail}")
        print()

    counts: dict[str, int] = {}
    for f in shown:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = ", ".join(f"{counts[s]} {s}" for s in
                        sorted(counts, key=lambda s: -SEVERITY_ORDER[s]))
    print(f"{len(shown)} finding(s): {summary}")
    suppressed = len(findings) - len(shown)
    if suppressed:
        print(f"({suppressed} lower-severity finding(s) suppressed — "
              f"re-run with --min-severity INFO to see them.)")
    print("\nThis tool never modifies anything. Findings are leads, not conclusions.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
