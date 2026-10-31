#!/usr/bin/env python3
"""Structural contract checks for the settled-positions rule (supersession.md §8).

Pins that the rule is stated where agents will meet it (the SKILL.md router and
STRICT section), owned in one place (supersession.md §8), located by layout.md and
naming.md, shaped by one template whose header matches the workspace doctor, and
covered by the behavioral cases in evals/settled-positions.md. It also fills the
template with invented rows in a temporary workspace and runs the doctor on it, so
a template the doctor would reject cannot ship.

Stdlib only; writes nothing inside the skill tree.

Usage:
    python3 -B evals/validate_settled_positions.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "workspace-doctor"))
import doctor  # noqa: E402

TEMPLATE = "templates/settled-positions.md.template"
REGISTER = "decisions/settled-positions.md"


def read(relative: str) -> str:
    path = ROOT / relative
    assert path.is_file(), f"missing required file: {relative}"
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def require(text: str, needles: list[str], label: str) -> None:
    body = flat(text)
    for needle in needles:
        assert flat(needle) in body, f"{label}: missing required contract: {needle!r}"


def section(text: str, heading: str) -> str:
    """The body of a `## ` section, up to the next `## ` heading."""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"missing section: ## {heading}"
    return m.group(1)


def check_router() -> None:
    skill = read("SKILL.md")
    router = section(skill, "On Invocation: Router")
    require(router, ["settled-positions register", "reviewer brief", "calling an item open",
                     "changed treatment"], "SKILL.md router")
    rule = section(skill, "Settled-positions rule (STRICT)")
    require(rule, [
        "<scope-root>/decisions/settled-positions.md",
        "canonical owner of settlement state",
        "`Reopen only if`",
        "new facts about that item",
        "only with the owner's decision",
        "reported to the owner as a risk",
        "Every reviewer brief includes the register",
        "An owner fact settles the fact, not every legal conclusion that depends on it",
        "`analysis` and `verified` are provenance categories, not owner approval",
        "does not prove authorization",
        "supersession.md` §8",
        "templates/settled-positions.md.template",
    ], "SKILL.md settled-positions rule")


def check_supersession() -> None:
    text = read("supersession.md")
    s8 = section(text, "8. Settled positions")
    require(s8, [
        "operative register",
        "current-state index",
        "Memos are immutable records",
        "One designated table",
        "Only `owner decision` settles a treatment on its own",
        "An owner fact settles the fact, not every legal conclusion that depends on it",
        "provenance categories, not owner approval",
        "Report, do not reopen",
        "Reopen only on the trigger",
        "Only the owner reopens",
        "Every reviewer brief includes the register",
        "Write a new decision memo",
        "Stamp the predecessor's `Superseded by`",
        "Rewrite the register row",
        "Open period",
        "change the entry's postings and the row's `Lock` together",
        "Closed period",
        "Post a correcting entry in the open period",
        "A matching Lock detects drift; it does not prove authorization",
        "multiset",
    ], "supersession.md §8")
    s1 = section(text, "1. Operative files and records")
    require(s1, ["`decisions/settled-positions.md`", "other than `settled-positions.md`"],
            "supersession.md §1 classification")
    s9 = section(text, "9. What the doctor flags")
    require(s9, ["Settled-positions register shape", "is not a memo and is skipped"],
            "supersession.md §9")


def check_layout_and_naming() -> None:
    layout = read("layout.md")
    assert layout.count("settled-positions.md") >= 3, \
        "layout.md: register missing from the workspace-profile, individual, or entity tree"
    require(layout, ["OPERATIVE register"], "layout.md")
    naming = section(read("naming.md"), "Document filenames")
    require(naming, ["Settled-positions register", "<scope-root>/decisions/settled-positions.md",
                     "Operative register", "`<PREFIX>-S<NNN>`", "never recycled"], "naming.md")


def designated_headers(text: str) -> list[tuple[str, ...]]:
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        cells = doctor._settled_cells(line)
        sep = doctor._settled_cells(lines[i + 1])
        if cells and sep and all(doctor._SEPARATOR_CELL_RE.match(c) for c in sep) \
                and set(doctor.SETTLED_HEADERS) <= set(cells):
            found.append(tuple(cells))
    return found


def check_template() -> None:
    text = read(TEMPLATE)
    headers = designated_headers(text)
    assert len(headers) == 1, f"{TEMPLATE}: expected one designated table, found {len(headers)}"
    assert headers[0] == doctor.SETTLED_HEADERS, \
        f"{TEMPLATE}: header {headers[0]} differs from doctor.SETTLED_HEADERS"
    require(text, ["owner decision", "owner fact", "analysis", "verified", "Reopen only if",
                   "does not prove", "No pipe character inside any cell", "Closed period",
                   "Documented positions", "Not settled"], TEMPLATE)
    # portability.md: schema and instructions only, no workspace data.
    for label, rx in [("dollar amount", r"\$\s?\d"), ("absolute path", r"(?<![\w`<])/(Users|Volumes|home)/"),
                      ("EIN-shaped identifier", r"\b\d{2}-\d{7}\b"), ("filled settlement ID", r"\b[A-Z]{2,}-S\d{3}\b")]:
        assert not re.search(rx, text), f"{TEMPLATE}: contains {label}; templates carry placeholders only"


def check_template_passes_doctor() -> None:
    """Fill the template's placeholder row with invented rows; the doctor must accept it,
    must not treat it as a memo, and must reject it once a ledger row loses its Lock."""
    text = read(TEMPLATE)
    placeholder = next(l for l in text.splitlines() if l.startswith("| `<PREFIX>-S001`"))
    evidence = "entities/example-co/tax/FY2025/open-questions.md"
    ledger = (f"| `EXC-S001` | ledger | 2025-02-03 | Example invoice | office expense | 2025-03-01 owner — Q1 "
              f"| owner decision | the invoice names another client | `{evidence}` "
              f"| Expenses:Office 10.00 USD; Liabilities:Card -10.00 USD |")
    nonledger = (f"| `EXC-S002` | non-ledger | — | Example election | not claimed | 2025-03-01 owner "
                 f"| owner fact; eligibility is analysis | the owner revives it | `{evidence}` | — |")
    filled = text.replace(placeholder, ledger + "\n" + nonledger)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / evidence).parent.mkdir(parents=True)
        (root / evidence).write_text("# Q\n", encoding="utf-8")
        reg = root / "entities" / "example-co" / REGISTER
        reg.parent.mkdir(parents=True)
        reg.write_text(filled, encoding="utf-8")
        problems = doctor.check_settled_positions_registers(root).paths
        assert problems == [], f"filled template rejected by the doctor: {problems}"
        assert doctor.check_decision_memo_lineage(root).paths == [], "register treated as a memo"
        assert doctor.check_in_place_prose_history(root).paths == [], "template trips the prose-history check"
        reg.write_text(filled.replace("Expenses:Office 10.00 USD; Liabilities:Card -10.00 USD", "—"),
                       encoding="utf-8")
        problems = doctor.check_settled_positions_registers(root).paths
        assert any("empty or malformed Lock" in p for p in problems), \
            f"ledger row with no Lock was not rejected: {problems}"


REQUIRED_CASES = {
    "E1": "settled, untriggered",
    "E2": "settled, trigger met",
    "E3": "partially settled",
    "E4": "analysis is not owner approval",
    "E5": "owner-approved supersession, open period",
    "E6": "owner-approved supersession, closed period",
    "E7": "reviewer brief",
    "E8": "matching lock, no authorization",
    "E9": "not-settled item mistaken for settled",
    "E10": "settlement recorded only outside the register",
}


def check_eval_cases() -> None:
    text = read("evals/settled-positions.md")
    for case, title in REQUIRED_CASES.items():
        m = re.search(rf"^### {case} — ([^\n]+)$(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
        assert m, f"evals/settled-positions.md: missing case {case}"
        assert flat(title) in flat(m.group(1)), f"{case}: title should name {title!r}"
        assert "Mandatory result" in m.group(2), f"{case}: no mandatory result"
    for label, rx in [("dollar amount", r"\$\s?\d"), ("EIN-shaped identifier", r"\b\d{2}-\d{7}\b")]:
        assert not re.search(rx, text), f"evals/settled-positions.md: contains {label}; fixtures are invented and amount-free"


CHECKS = [check_router, check_supersession, check_layout_and_naming, check_template,
          check_template_passes_doctor, check_eval_cases]


def main() -> int:
    failed = 0
    for check in CHECKS:
        try:
            check()
            print(f"ok   {check.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {check.__name__}: {exc}")
    print(f"{len(CHECKS) - failed}/{len(CHECKS)} settled-positions checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
