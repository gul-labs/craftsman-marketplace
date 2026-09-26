#!/usr/bin/env python3
"""Regression probes for broken/missing palette data and actual consumer pairings."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('palettes', Path(__file__).with_name('verify-palettes.py'))
palettes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(palettes)


class PaletteChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = palettes.KITS.read_text()
        cls.first_row = next(line for line in cls.text.splitlines() if line.startswith('| SaaS product |'))

    def test_shipped_palettes_and_statuses(self):
        for rows, checks in [(palettes.parse_palettes(self.text), palettes.CHECKS),
                             (palettes.parse_status_pairs(self.text), palettes.STATUS_CHECKS)]:
            for row in rows:
                self.assertEqual(palettes.check_pairs(row, checks), [], row)

    def test_reference_contrast(self):
        self.assertAlmostEqual(palettes.ratio('#000000', '#FFFFFF'), 21.0)
        self.assertEqual(palettes.ratio('#123456', '#123456'), 1.0)

    def test_original_hover_regression_is_rejected(self):
        row = palettes.parse_palettes(self.text)[0]
        row.update({'accent': '#B45309', 'on-accent': '#FFFFFF'})
        self.assertGreater(palettes.ratio(row['on-accent'], row['accent']), 4.5)
        self.assertTrue(any(x.startswith('foreground/accent ') for x in palettes.check_pairs(row, palettes.CHECKS)))

    def test_hover_surface_cannot_disappear_into_inset(self):
        row = palettes.parse_palettes(self.text)[0]
        row['accent'] = row['muted']
        self.assertTrue(any(x.startswith('accent/muted ') for x in palettes.check_pairs(row, palettes.CHECKS)))

    def test_same_named_subheading_is_not_a_second_section(self):
        self.assertEqual(len(palettes.parse_status_pairs(self.text + '\n### Status pairs\nNotes.')), 8)

    def test_muted_text_on_card_is_checked(self):
        row = palettes.parse_palettes(self.text)[0]
        row['muted-fg'] = row['card']
        self.assertTrue(any(x.startswith('muted-fg/card ') for x in palettes.check_pairs(row, palettes.CHECKS)))

    def test_hover_and_control_edges_are_checked(self):
        row = palettes.parse_palettes(self.text)[0]
        row['primary-hover'] = row['on-primary']
        row['input'] = row['card']
        failures = palettes.check_pairs(row, palettes.CHECKS)
        self.assertTrue(any(x.startswith('on-primary/primary-hover ') for x in failures))
        self.assertTrue(any(x.startswith('input/card ') for x in failures))

    def test_malformed_rows_never_disappear(self):
        for broken in [self.first_row.replace('#1D4ED8', '#INVALID', 1),
                       self.first_row.replace('| `#1D4ED8`', '', 1),
                       self.first_row.replace('`#1D4ED8`', '`221 83% 48%`', 1)]:
            with self.subTest(row=broken), self.assertRaises(ValueError):
                palettes.parse_palettes(self.text.replace(self.first_row, broken))

    def test_deleted_duplicate_or_interrupted_rows_fail(self):
        for broken in [self.text.replace(self.first_row + '\n', ''),
                       self.text.replace(self.first_row, self.first_row + '\n' + self.first_row),
                       self.text.replace(self.first_row, self.first_row + '\n\n')]:
            with self.subTest(), self.assertRaises(ValueError):
                palettes.parse_palettes(broken)

    def test_non_palette_tables_are_ignored(self):
        other = '\n## Unrelated\n\n| Label | Value |\n| --- | --- |\n| x | not a color |\n'
        self.assertEqual(len(palettes.parse_palettes(self.text + other)), 15)

    def test_status_theme_coverage_and_contrast(self):
        row = palettes.parse_status_pairs(self.text)[0]
        row['on-solid'] = row['solid']
        self.assertTrue(palettes.check_pairs(row, palettes.STATUS_CHECKS))
        with self.assertRaises(ValueError):
            palettes.parse_status_pairs(self.text.replace('| Dark | warning |', '| Light | warning |'))

    def test_bad_data_exits_nonzero(self):
        bad_row = self.first_row.replace('`#FFFFFF`', '`#1D4ED8`', 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'broken.md'
            path.write_text(self.text.replace(self.first_row, bad_row))
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('verify-palettes.py')), str(path)],
                                    text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL SaaS product', result.stdout)


if __name__ == '__main__':
    unittest.main()
