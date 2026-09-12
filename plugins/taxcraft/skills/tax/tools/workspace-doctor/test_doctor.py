#!/usr/bin/env python3
"""Fixture tests for workspace-doctor's entity-tracker check.

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
