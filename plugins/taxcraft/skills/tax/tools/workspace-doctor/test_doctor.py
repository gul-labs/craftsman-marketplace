#!/usr/bin/env python3
"""Fixture tests for workspace-doctor's content-reading checks: entity trackers,
in-place prose history, decision-memo lineage, and the settled-positions
register (supersession.md).

Run:  python3 -B test_doctor.py   (stdlib unittest; no workspace needed)
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doctor  # noqa: E402


def _mk_entity(root: Path, slug: str, entity_type: str | None, *, books=True,
               capital_accounts=False, carryforwards=False) -> Path:
    e = root / "entities" / slug
    e.mkdir(parents=True)
    if entity_type is not None:
        (e / "entity.md").write_text(
            f"# {slug}\n\n- **Entity type**: {entity_type}\n- **Federal treatment**: n/a\n"
            "Upstream K-1s: Form 1065 from three lower-tier partnerships; Form 1120 filed.\n",
            encoding="utf-8",
        )
    else:
        (e / "entity.md").write_text(f"# {slug}\n\nno type field here\n", encoding="utf-8")
    if books:
        (e / "books").mkdir()
        if capital_accounts:
            (e / "books" / "capital-accounts.md").write_text("# cap\n", encoding="utf-8")
    if carryforwards:
        (e / "carryforwards.json").write_text("{}", encoding="utf-8")
    return e


class EntityTrackerCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def paths(self):
        return doctor.check_entity_trackers(self.root).paths

    def test_empty_root_is_clean(self):
        self.assertEqual(self.paths(), [])

    def test_partnership_missing_both_trackers(self):
        _mk_entity(self.root, "alpha-llc", "LLC-taxed-as-partnership")
        p = self.paths()
        self.assertIn("entities/alpha-llc/carryforwards.json", p)
        self.assertIn("entities/alpha-llc/books/capital-accounts.md", p)

    def test_partnership_complete_is_clean(self):
        _mk_entity(self.root, "alpha-llc", "Partnership", capital_accounts=True, carryforwards=True)
        self.assertEqual(self.paths(), [])

    def test_c_corp_with_1065_investments_needs_no_capital_accounts(self):
        # The body mentions Form 1065 K-1s; only the labelled field decides.
        _mk_entity(self.root, "beta-inc", "C-corp", carryforwards=True)
        self.assertEqual(self.paths(), [])

    def test_s_corp_missing_carryforwards_only(self):
        _mk_entity(self.root, "gamma-inc", "LLC-taxed-as-S")
        self.assertEqual(self.paths(), ["entities/gamma-inc/carryforwards.json"])

    def test_disregarded_type_is_not_a_partnership(self):
        _mk_entity(self.root, "delta-llc", "SMLLC (disregarded)", carryforwards=True)
        self.assertEqual(self.paths(), [])

    def test_missing_type_field_is_reported_not_skipped(self):
        _mk_entity(self.root, "epsilon-llc", None, carryforwards=True)
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertTrue(p[0].startswith("entities/epsilon-llc/entity.md"))
        self.assertIn("cannot classify", p[0])

    def test_no_books_dir_needs_no_carryforwards(self):
        _mk_entity(self.root, "zeta-inc", "C-corp", books=False)
        self.assertEqual(self.paths(), [])

    def test_privileged_path_is_never_walked_or_printed(self):
        _mk_entity(self.root, "matter-attorney-client-privileged", "Partnership")
        self.assertEqual(self.paths(), [])

    def test_output_never_contains_field_value(self):
        _mk_entity(self.root, "eta-llc", "Partnership SECRETVALUE")
        for line in self.paths():
            self.assertNotIn("SECRETVALUE", line)



# --- supersession.md checks ---------------------------------------------------

def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


CLEAN_CARD = (
    "# Entity — alpha-llc\n\n**As of:** 2026-09-11\n\n"
    "## 1. Standing facts\n\n- **Entity type**: Partnership\n\n"
    "## 7. Lifetime basis updated\n\nSee `decisions/`. Memo `DEC-20260911-alpha-llc-topic`.\n"
)


class ProseHistoryCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def paths(self):
        return doctor.check_in_place_prose_history(self.root).paths

    def test_clean_card_is_clean(self):
        _write(self.root, "entities/alpha-llc/entity.md", CLEAN_CARD)
        self.assertEqual(self.paths(), [])

    def test_section_0a_update_block(self):
        _write(self.root, "entities/alpha-llc/entity.md", "# E\n\n## §0a Update (2026-09-01)\n\nnew answer\n\n## Old\n")
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertTrue(p[0].startswith("entities/alpha-llc/entity.md"))
        self.assertIn("§0a-style", p[0])

    def test_bare_0b_heading_without_section_sign(self):
        _write(self.root, "individual/profile.md", "# P\n\n### 0b update\n")
        self.assertIn("§0a-style", self.paths()[0])

    def test_update_and_revised_headings(self):
        _write(self.root, "individual/FY2025/tax-summary.md", "# T\n\n## Update\n\nx\n")
        _write(self.root, "individual/FY2025/review.md", "# R\n\n## Revised analysis\n")
        hits = self.paths()
        self.assertEqual(len(hits), 2)
        for h in hits:
            self.assertIn("update/revision heading", h)

    def test_dated_update_heading_anywhere_in_heading(self):
        _write(self.root, "workspace-profile/entities-index.md", "# I\n\n## Roster — amended (2026-08-30)\n")
        self.assertIn("dated update heading", self.paths()[0])

    def test_history_and_changelog_sections(self):
        _write(self.root, "entities/a/entity.md", "# E\n\n## History\n")
        _write(self.root, "entities/b/entity.md", "# E\n\n## Change log\n")
        _write(self.root, "entities/c/entity.md", "# E\n\n## Prior analysis\n")
        _write(self.root, "entities/d/entity.md", "# E\n\n## Superseded reasoning\n")
        hits = self.paths()
        self.assertEqual(len(hits), 4)
        for h in hits:
            self.assertIn("history/prior-analysis section", h)

    def test_strikethrough(self):
        _write(self.root, "individual/profile.md", "# P\n\nFiling status ~~MFJ~~ Single\n")
        self.assertIn("strikethrough", self.paths()[0])

    def test_audit_trail_prose(self):
        _write(self.root, "individual/profile.md", "# P\n\nThe old figure is retained for the audit trail.\n")
        self.assertIn("audit-trail retention prose", self.paths()[0])

    def test_multiple_rules_reported_once_each_on_one_line(self):
        _write(self.root, "individual/profile.md", "# P\n\n## Update\n\n~~x~~ ~~y~~\n\n## Update 2\n")
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("update/revision heading", p[0])
        self.assertIn("strikethrough", p[0])
        self.assertEqual(p[0].count("strikethrough"), 1)

    def test_fenced_code_is_ignored(self):
        _write(self.root, "individual/profile.md", "# P\n\n```\n## Update\n~~x~~\nkept for the audit trail\n```\n\n~~~\n## History\n~~~\n")
        self.assertEqual(self.paths(), [])

    def test_numbered_heading_ending_in_updated_is_clean(self):
        # individual-return-package template: "## 7. Lifetime basis updated"
        _write(self.root, "individual/FY2025/return-package.md", "# RP\n\n## 7. Lifetime basis updated\n")
        self.assertEqual(self.paths(), [])

    def test_decisions_and_notes_are_out_of_scope(self):
        _write(self.root, "entities/a/decisions/2026-09-01 - topic.md", "# M\n\n## Superseded\n\n~~x~~\n")
        _write(self.root, "workspace-profile/notes/advisor.md", "## Update (2026-01-01)\n")
        _write(self.root, "workspace-profile/decisions/2026-09-01 - x.md", "## History\n")
        self.assertEqual(self.paths(), [])

    def test_records_and_evidence_folders_are_out_of_scope(self):
        for rel in (
            "individual/records/elections/memo.md",
            "individual/FY2025/.computed/EST-1-control.md",
            "individual/FY2025/filed/cover.md",
            "individual/FY2025/source/receipts/note.md",
            "entities/a/corporate/minutes/2025.md",
            "entities/a/books/README.md",
            "entities/a/accounts/chase-1234/bank.md",
            "entities/a/matters/dispute/summary.md",
        ):
            _write(self.root, rel, "# X\n\n## History\n\n~~y~~\n")
        self.assertEqual(self.paths(), [])

    def test_trackers_and_logs_are_out_of_scope(self):
        _write(self.root, "individual/history.md", "# Tax History\n\n## 2026-01-01 — update (2026-01-01)\n")
        _write(self.root, "individual/FY2025/open-questions.md", "## History\n\n~~x~~\n")
        _write(self.root, "individual/FY2025/pending-docs.md", "## Update\n")
        _write(self.root, "entities/a/cross-entity-followup-log.md", "## Closed items\n\nretained for the audit trail\n")
        _write(self.root, "entities/a/open-items-tracker.md", "## History\n")
        _write(self.root, "workspace-profile/history.md", "## Change log\n")
        self.assertEqual(self.paths(), [])

    def test_longer_fence_containing_triple_fence_stays_fenced(self):
        # A ```` fence wrapping a ``` line: the inner run must not close the block.
        _write(self.root, "individual/profile.md",
               "# P\n\n````md\n```\n## Update\n~~x~~\n```\n## History\n````\n\nclean after\n")
        self.assertEqual(self.paths(), [])

    def test_mismatched_fence_char_does_not_close(self):
        _write(self.root, "individual/profile.md", "# P\n\n```\n~~~\n## Update\n```\n")
        self.assertEqual(self.paths(), [])

    def test_content_after_closing_fence_is_scanned(self):
        _write(self.root, "individual/profile.md", "# P\n\n```\n## Update\n```\n\n## Revised\n")
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("update/revision heading", p[0])

    def test_outside_the_three_roots_is_not_scanned(self):
        _write(self.root, "reference/guide.md", "## History\n")
        _write(self.root, "archive/old.md", "~~x~~\n")
        _write(self.root, "README.md", "## Update\n")
        self.assertEqual(self.paths(), [])

    def test_privileged_path_is_never_walked_or_printed(self):
        _write(self.root, "entities/a/matters/attorney-client-privileged-x/summary.md", "## Update\n")
        _write(self.root, "entities/attorney-client-privileged-b/entity.md", "## Update\n")
        self.assertEqual(self.paths(), [])

    def test_output_never_contains_matched_text(self):
        _write(self.root, "individual/profile.md", "# P\n\n## Update SECRETHEADING\n\n~~SECRETFIGURE~~ kept for the audit trail SECRETTAIL\n")
        for line in self.paths():
            for tok in ("SECRETHEADING", "SECRETFIGURE", "SECRETTAIL"):
                self.assertNotIn(tok, line)


def _memo(memo_id: str | None, supersedes: str | None, superseded_by: str | None = "", body: str = "") -> str:
    lines = ["# Decision Memo — t", ""]
    if memo_id is not None:
        lines.append(f"**Memo ID:** `{memo_id}`")
    lines.append("**Issued:** 2026-09-11")
    if supersedes is not None:
        lines.append(f"**Supersedes:** {supersedes}")
    if superseded_by is not None:
        lines.append(f"**Superseded by:** {superseded_by}")
    lines += ["", "## Conclusion", "", body or "x", "", "**Memo ID:** `DEC-BODY-SHOULD-BE-IGNORED`", ""]
    return "\n".join(lines)


class DecisionMemoLineageCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.d = "entities/alpha-llc/decisions"

    def tearDown(self):
        self._tmp.cleanup()

    def paths(self):
        return doctor.check_decision_memo_lineage(self.root).paths

    def test_no_decisions_folder_is_clean(self):
        _write(self.root, "entities/alpha-llc/entity.md", CLEAN_CARD)
        self.assertEqual(self.paths(), [])

    def test_single_memo_supersedes_none_is_clean(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-20260901-alpha-llc-a", "none"))
        self.assertEqual(self.paths(), [])

    def test_reciprocal_chain_is_clean(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", "none", "DEC-2"))
        _write(self.root, f"{self.d}/2026-09-05 - a.md", _memo("DEC-2", "`DEC-1`", "—"))
        self.assertEqual(self.paths(), [])

    def test_template_placeholders_count_as_empty(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md",
               _memo("DEC-1", "<`DEC-…` | none>", "<leave empty at issue — filled only when a later memo names this one>"))
        self.assertEqual(self.paths(), [])

    def test_missing_memo_id_line(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo(None, "none"))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("no Memo ID line", p[0])

    def test_missing_supersedes_line(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", None))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("no Supersedes line", p[0])

    def test_missing_superseded_by_line(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", "none", None))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("no Superseded by line", p[0])

    def test_dangling_supersedes(self):
        _write(self.root, f"{self.d}/2026-09-05 - a.md", _memo("DEC-2", "DEC-1"))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("not in this folder", p[0])

    def test_predecessor_not_stamped(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", "none", ""))
        _write(self.root, f"{self.d}/2026-09-05 - a.md", _memo("DEC-2", "DEC-1"))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertTrue(p[0].startswith(f"{self.d}/2026-09-01 - a.md"))
        self.assertIn("predecessor not stamped", p[0])

    def test_stamp_pointing_at_memo_that_does_not_supersede(self):
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", "none", "DEC-2"))
        _write(self.root, f"{self.d}/2026-09-05 - b.md", _memo("DEC-2", "none"))
        p = self.paths()
        self.assertEqual(len(p), 1)
        self.assertIn("does not supersede this one", p[0])

    def test_supersedes_across_folders_is_dangling(self):
        _write(self.root, "individual/decisions/2026-09-01 - a.md", _memo("DEC-1", "none", "DEC-2"))
        _write(self.root, f"{self.d}/2026-09-05 - a.md", _memo("DEC-2", "DEC-1"))
        hits = self.paths()
        self.assertEqual(len(hits), 2)
        self.assertTrue(any("not in this folder" in h for h in hits))

    def test_duplicate_ids_across_workspace(self):
        _write(self.root, "individual/decisions/2026-09-01 - a.md", _memo("DEC-SAME", "none"))
        _write(self.root, f"{self.d}/2026-09-01 - b.md", _memo("DEC-SAME", "none"))
        hits = self.paths()
        self.assertEqual(len(hits), 2)
        for h in hits:
            self.assertIn("duplicate Memo ID", h)

    def test_body_fields_below_first_heading_are_ignored(self):
        # _memo() plants a second Memo ID line in the body; it must not register.
        _write(self.root, f"{self.d}/2026-09-01 - a.md", _memo("DEC-1", "none"))
        self.assertEqual(self.paths(), [])

    def test_privileged_folder_is_never_walked(self):
        _write(self.root, "entities/attorney-client-privileged-x/decisions/2026-09-01 - a.md", _memo(None, None))
        self.assertEqual(self.paths(), [])

    def test_output_never_contains_ids(self):
        _write(self.root, f"{self.d}/2026-09-05 - a.md", _memo("DEC-SECRETID", "DEC-OTHERSECRET"))
        for line in self.paths():
            self.assertNotIn("SECRET", line)


# Invented fixture data only (portability.md): a fictional entity, round amounts.
REG_DIR = "entities/alpha-llc/decisions"
REG = f"{REG_DIR}/settled-positions.md"
EV = "entities/alpha-llc/tax/FY2025/open-questions.md"
REG_HEADER = (
    "| ID | Anchor | Entry date | Entry | Position | Settled | Basis | Reopen only if | Evidence | Lock |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)
LEDGER_ROW = (
    "| `ALP-S001` | ledger | 2026-01-15 | Example vendor invoice | office expense | "
    "2026-02-01 owner — Q1 | owner decision | the invoice names another client | "
    f"`{EV}` | Expenses:Office 100.00 USD; Liabilities:Card -100.00 USD |\n"
)
NONLEDGER_ROW = (
    "| `ALP-S002` | non-ledger | — | Home-office method | not claimed | "
    "2026-02-01 owner — Q2 | owner fact; qualification is analysis | the owner revives it | "
    f"`{EV}` | — |\n"
)


def _register(rows: str = LEDGER_ROW + NONLEDGER_ROW, *, before: str = "", after: str = "") -> str:
    return f"# Settled positions\n\n{before}## Register\n\n{REG_HEADER}{rows}{after}"


class SettledPositionsRegisterCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _write(self.root, EV, "# Q\n")

    def tearDown(self):
        self._tmp.cleanup()

    def paths(self):
        return doctor.check_settled_positions_registers(self.root).paths

    def rules(self, text: str) -> list[str]:
        return [rule for _ln, rule in doctor.settled_register_problems(text, self.root)]

    def test_no_register_is_clean(self):
        self.assertEqual(self.paths(), [])

    def test_valid_register_is_clean(self):
        _write(self.root, REG, _register())
        self.assertEqual(self.paths(), [])

    def test_extra_sections_tables_and_reordered_columns_are_allowed(self):
        reordered = (
            "| Anchor | ID | Notes | Entry date | Entry | Position | Settled | Basis | Reopen only if | Evidence | Lock |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| non-ledger | `ALP-S002` | n | — | Home-office method | not claimed | 2026-02-01 owner | owner decision | "
            f"the owner revives it | `{EV}` | — |\n"
        )
        text = ("# S\n\n## Register\n\n" + reordered +
                "\n## Not settled\n\n| Item | Status | Where |\n|---|---|---|\n| x | open | y |\n")
        self.assertEqual(self.rules(text), [])

    def test_duplicate_identical_postings_are_valid(self):
        row = LEDGER_ROW.replace("Expenses:Office 100.00 USD;", "Expenses:Office 50.00 USD; Expenses:Office 50.00 USD;")
        self.assertEqual(self.rules(_register(row)), [])

    def test_missing_table(self):
        self.assertIn("found 0", self.rules("# S\n\nno table\n")[0])

    def test_two_designated_tables(self):
        self.assertIn("found 2", self.rules(_register() + "\n" + REG_HEADER + LEDGER_ROW)[0])

    def test_missing_required_header(self):
        text = _register().replace("| Lock |\n|---|---|---|---|---|---|---|---|---|---|", "|\n|---|---|---|---|---|---|---|---|---|")
        self.assertIn("found 0", self.rules(text)[0])

    def test_duplicate_header(self):
        text = _register().replace("| Lock |\n|---|", "| Lock | Basis |\n|---|---|", 1)
        self.assertEqual(self.rules(text), ["duplicate header"])

    def test_separator_width_mismatch(self):
        text = _register().replace("|---|---|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|---|---|")
        self.assertEqual(self.rules(text), ["separator width differs from the header"])

    def test_pipe_inside_cell_escaped_or_not(self):
        for bad in ("office \\| supplies", "office | supplies"):
            row = LEDGER_ROW.replace("office expense", bad)
            self.assertIn("malformed row (cell count, or a pipe inside a cell)", self.rules(_register(row)))

    def test_bad_and_duplicate_ids(self):
        self.assertIn("ID is not <PREFIX>-S<NNN>", self.rules(_register(LEDGER_ROW.replace("ALP-S001", "alp-1"))))
        self.assertIn("duplicate ID", self.rules(_register(LEDGER_ROW + LEDGER_ROW)))

    def test_anchor_must_be_explicit(self):
        self.assertIn("Anchor is not ledger or non-ledger",
                      self.rules(_register(LEDGER_ROW.replace("| ledger |", "| |"))))

    def test_ledger_row_with_empty_lock(self):
        row = LEDGER_ROW.replace("Expenses:Office 100.00 USD; Liabilities:Card -100.00 USD", "—")
        self.assertIn("ledger row with an empty or malformed Lock", self.rules(_register(row)))

    def test_ledger_row_with_malformed_lock(self):
        for lock in ("Expenses:Office 100.00", "Office 100.00 USD", "Expenses:Office one USD"):
            row = LEDGER_ROW.replace("Expenses:Office 100.00 USD", lock)
            self.assertIn("ledger row with an empty or malformed Lock", self.rules(_register(row)), lock)

    def test_ledger_row_with_bad_entry_date(self):
        for d in ("—", "2026-02-30", "01/15/2026"):
            row = LEDGER_ROW.replace("2026-01-15", d)
            self.assertIn("ledger row without a valid YYYY-MM-DD Entry date", self.rules(_register(row)), d)

    def test_non_ledger_row_with_lock_or_date(self):
        row = NONLEDGER_ROW.replace("| non-ledger | — |", "| non-ledger | 2026-01-15 |")
        self.assertIn("non-ledger row carries an Entry date or Lock", self.rules(_register(row)))
        row = NONLEDGER_ROW.replace("| — |\n", "| Expenses:Office 1.00 USD |\n")
        self.assertIn("non-ledger row carries an Entry date or Lock", self.rules(_register(row)))

    def test_empty_required_fields(self):
        row = NONLEDGER_ROW.replace("| the owner revives it |", "| — |")
        self.assertIn("Reopen only if is empty", self.rules(_register(row)))

    def test_basis_outside_vocabulary(self):
        row = NONLEDGER_ROW.replace("owner fact; qualification is analysis", "agreed")
        self.assertIn("Basis names none of owner decision / owner fact / analysis / verified",
                      self.rules(_register(row)))

    def test_evidence_syntax(self):
        for cell in (EV, f"`{EV}`, `{EV}`", "", f"`{EV}`; see Q1"):
            row = LEDGER_ROW.replace(f"`{EV}`", cell)
            self.assertIn("Evidence is not a ;-separated list of backticked paths", self.rules(_register(row)), cell)

    def test_evidence_absolute_missing_directory_and_escape(self):
        cases = {
            "/etc/hosts": "Evidence path is not workspace-relative",
            "entities/alpha-llc/tax/FY2025/missing.md": "Evidence path is missing or not a file",
            "entities/alpha-llc/tax": "Evidence path is missing or not a file",
            "../outside.md": "Evidence path escapes the workspace",
        }
        for path, rule in cases.items():
            row = LEDGER_ROW.replace(f"`{EV}`", f"`{path}`")
            self.assertIn(rule, self.rules(_register(row)), path)

    def test_evidence_symlink_escaping_the_workspace(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "secret.md").write_text("x", encoding="utf-8")
            link = self.root / "entities/alpha-llc/link.md"
            link.symlink_to(Path(outside) / "secret.md")
            row = LEDGER_ROW.replace(f"`{EV}`", "`entities/alpha-llc/link.md`")
            self.assertIn("Evidence path escapes the workspace", self.rules(_register(row)))

    def test_cross_scope_evidence_inside_the_workspace_is_valid(self):
        other = "entities/beta-llc/contracts/agreement.md"
        _write(self.root, other, "x")
        row = LEDGER_ROW.replace(f"`{EV}`", f"`{EV}`; `{other}`")
        self.assertEqual(self.rules(_register(row)), [])

    def test_row_stranded_by_blank_line_is_reported(self):
        text = _register(LEDGER_ROW + "\n" + NONLEDGER_ROW)
        self.assertIn("row-like line outside the register table", self.rules(text))

    def test_row_with_lost_leading_pipe_is_reported(self):
        text = _register(LEDGER_ROW + "\n" + NONLEDGER_ROW.lstrip("| "))
        self.assertIn("row-like line outside the register table", self.rules(text))

    def test_table_in_fenced_code_is_not_designated(self):
        text = "# S\n\n```\n" + REG_HEADER + LEDGER_ROW + "```\n"
        self.assertIn("found 0", self.rules(text)[0])

    def test_lock_with_empty_component_or_cost_annotation(self):
        for lock in ("Expenses:Office 100.00 USD;; Liabilities:Card -100.00 USD",
                     "Expenses:Office 100.00 USD; Liabilities:Card -100.00 USD;",
                     "Assets:Brokerage 1 SHARE {100.00 USD}; Liabilities:Card -100.00 USD",
                     "Assets:Cash 100.00 EUR @ 1.10 USD; Liabilities:Card -110.00 USD"):
            row = LEDGER_ROW.replace("Expenses:Office 100.00 USD; Liabilities:Card -100.00 USD", lock)
            self.assertIn("ledger row with an empty or malformed Lock", self.rules(_register(row)), lock)

    def test_unresolvable_evidence_is_a_rule_not_a_crash(self):
        loop = self.root / "entities/alpha-llc/loop.md"
        loop.symlink_to(loop)
        for path in ("entities/alpha-llc/loop.md", "entities/alpha-llc/bad\x00name.md"):
            row = LEDGER_ROW.replace(f"`{EV}`", f"`{path}`")
            rules = self.rules(_register(row))
            self.assertTrue(any(r.startswith("Evidence path") for r in rules), (path, rules))
            for r in rules:
                self.assertNotIn("loop", r)
                self.assertNotIn("bad", r)

    def test_table_inside_longer_fence_is_not_designated(self):
        text = "# S\n\n````\n```\n" + REG_HEADER + LEDGER_ROW + "```\n````\n"
        self.assertIn("found 0", self.rules(text)[0])

    def test_row_with_lost_pipe_and_no_backticks_is_reported(self):
        stranded = NONLEDGER_ROW.lstrip("| ").replace("`ALP-S002`", "ALP-S002")
        self.assertIn("row-like line outside the register table", self.rules(_register(LEDGER_ROW + "\n" + stranded)))

    def test_row_above_the_table_or_under_another_heading_is_reported(self):
        above = _register(LEDGER_ROW, before=NONLEDGER_ROW + "\n")
        below = _register(LEDGER_ROW, after="\n## Other\n\n" + NONLEDGER_ROW)
        for text in (above, below):
            self.assertIn("row-like line outside the register table", self.rules(text))

    def test_stranded_row_with_reordered_columns_is_reported(self):
        header = (
            "| Anchor | Entry date | ID | Entry | Position | Settled | Basis | Reopen only if | Evidence | Lock |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
        )
        row = (f"| non-ledger | — | `ALP-S002` | Home-office method | not claimed | 2026-02-01 owner | owner decision | "
               f"the owner revives it | `{EV}` | — |\n")
        text = "# S\n\n## Register\n\n" + header + row + "\n" + row
        self.assertEqual(self.rules(text), ["row-like line outside the register table"])
        no_pipe = row.lstrip("| ")
        self.assertEqual(self.rules("# S\n\n## Register\n\n" + header + row + "\n" + no_pipe),
                         ["row-like line outside the register table"])

    def test_stranded_row_with_invalid_id_is_reported(self):
        stranded = NONLEDGER_ROW.replace("ALP-S002", "ALP-S00X")
        self.assertIn("row-like line outside the register table", self.rules(_register(LEDGER_ROW + "\n" + stranded)))

    def test_ancillary_tables_and_prose_mentions_are_not_stranded_rows(self):
        after = ("\n## Not settled\n\n| Item | Status | Where |\n|---|---|---|\n"
                 "| Cruise charge | recommended; see ALP-S001 | `x` |\n\nALP-S001 was settled by the owner.\n")
        self.assertEqual(self.rules(_register(after=after)), [])
        ten_wide = ("\n## Other\n\n| A | B | C | D | E | F | G | H | I | J |\n|---|---|---|---|---|---|---|---|---|---|\n"
                    "| a | b | c | d | e | f | g | h | i | j |\n")
        self.assertEqual(self.rules(_register(after=ten_wide)), [])

    def test_ancillary_rows_shaped_like_settlement_rows_are_not_stranded(self):
        id_item = ("\n## Not settled\n\n| Item | Status | Where |\n|---|---|---|\n"
                   "| ALP-S002 | reopened, owner decision pending | `x` |\n")
        ledger_cell = ("\n## Other\n\n| A | B | C | D | E | F | G | H | I | J |\n|---|---|---|---|---|---|---|---|---|---|\n"
                       "| a | ledger | c | d | e | f | g | h | i | j |\n")
        for after in (id_item, ledger_cell):
            self.assertEqual(self.rules(_register(after=after)), [], after)

    def test_settlement_row_dropped_into_an_ancillary_table_is_reported(self):
        after = "\n## Not settled\n\n| Item | Status | Where |\n|---|---|---|\n" + NONLEDGER_ROW
        self.assertIn("row-like line outside the register table", self.rules(_register(LEDGER_ROW, after=after)))

    def test_findings_name_path_and_line_never_content(self):
        _write(self.root, REG, _register(LEDGER_ROW.replace("Expenses:Office 100.00 USD", "SECRETACCT 7")))
        hits = self.paths()
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].startswith(f"{REG}:7"), hits[0])
        for h in hits:
            self.assertNotIn("SECRET", h)
            self.assertNotIn("ALP-S001", h)

    def test_workspace_profile_register_is_checked(self):
        _write(self.root, "workspace-profile/decisions/settled-positions.md", "# S\n")
        self.assertEqual(len(self.paths()), 1)

    def test_privileged_register_is_never_walked(self):
        _write(self.root, "entities/attorney-client-privileged-x/decisions/settled-positions.md", "# S\n")
        self.assertEqual(self.paths(), [])

    def test_register_is_not_a_memo(self):
        _write(self.root, REG, _register())
        _write(self.root, f"{REG_DIR}/2026-02-01 - office.md", _memo("DEC-1", "none"))
        self.assertEqual(doctor.check_decision_memo_lineage(self.root).paths, [])

    def test_register_is_scanned_as_operative_prose(self):
        _write(self.root, REG, _register(before="Old answer ~~expense~~\n\n"))
        _write(self.root, f"{REG_DIR}/2026-02-01 - office.md", "# M\n\n## History\n")
        hits = doctor.check_in_place_prose_history(self.root).paths
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].startswith(REG))
        self.assertIn("strikethrough", hits[0])

    def test_template_header_matches_doctor(self):
        tmpl = (Path(__file__).resolve().parents[2] / "templates" / "settled-positions.md.template").read_text(encoding="utf-8")
        designated = [l for l in tmpl.splitlines() if l.startswith("| ID |")]
        self.assertEqual(len(designated), 1)
        self.assertEqual(tuple(c.strip() for c in designated[0].strip().strip("|").split("|")),
                         doctor.SETTLED_HEADERS)


class RunIncludesNewChecks(unittest.TestCase):
    def test_run_lists_both_supersession_groups(self):
        import io, contextlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workspace-profile").mkdir()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = doctor.run(root)
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("In-place prose history in operative files", out)
        self.assertIn("Decision-memo lineage", out)
        self.assertIn("Settled-positions register", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
