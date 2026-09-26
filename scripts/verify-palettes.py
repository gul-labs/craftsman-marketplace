#!/usr/bin/env python3
"""Validate craft-ux starter tables, including foreground, surface and state pairs.

Run: python3 scripts/verify-palettes.py [path/to/starter-kits.md]
Malformed, missing and duplicate rows fail closed. Contrast does not measure beauty.
"""
import argparse
import re
from pathlib import Path

KITS = Path(__file__).resolve().parents[1] / (
    'plugins/craftsman/skills/craft-ux/references/starter-kits.md'
)
COLUMNS = ['Kit', 'primary', 'on-primary', 'primary-hover', 'accent', 'on-accent',
           'background', 'foreground', 'card', 'muted', 'muted-fg', 'border', 'input', 'ring']
STATUS_COLUMNS = ['Theme', 'Role', 'surface', 'text', 'boundary', 'solid', 'on-solid', 'hover']
SURFACES = ['background', 'card', 'muted', 'accent']
CHECKS = (
    [(f'foreground/{s}', 'foreground', s, 7.0) for s in SURFACES]
    + [(f'muted-fg/{s}', 'muted-fg', s, 4.5) for s in SURFACES]
    + [('on-primary/primary', 'on-primary', 'primary', 4.5),
       ('on-primary/primary-hover', 'on-primary', 'primary-hover', 4.5),
       ('on-accent/accent', 'on-accent', 'accent', 4.5)]
    + [(f'{role}/{s}', role, s, 3.0)
       for role in ['primary', 'primary-hover', 'ring', 'input'] for s in SURFACES]
    + [(f'accent/{s}', 'accent', s, 1.1) for s in ['background', 'card', 'muted']]
    + [(f'border/{s}', 'border', s, 1.2) for s in ['background', 'card']]
)
STATUS_CHECKS = [
    ('text/surface', 'text', 'surface', 4.5),
    ('on-solid/solid', 'on-solid', 'solid', 4.5),
    ('on-solid/hover', 'on-solid', 'hover', 4.5),
    ('boundary/surface', 'boundary', 'surface', 3.0),
]


def luminance(hexc: str) -> float:
    h = hexc.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * weight for c, weight in zip(linear, [0.2126, 0.7152, 0.0722]))


def ratio(a: str, b: str) -> float:
    hi, lo = sorted([luminance(a), luminance(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def parse_table(text: str, heading: str, columns: list[str], name_columns: int):
    sections = re.split(rf'(?m)^## {re.escape(heading)}$', text)
    if len(sections) != 2:
        raise ValueError(f'Expected exactly one {heading!r} section')
    section = sections[1].split('\n## ', 1)[0]
    lines = section.splitlines()
    header = '| ' + ' | '.join(columns) + ' |'
    starts = [i for i, line in enumerate(lines) if line.strip() == header]
    if len(starts) != 1:
        raise ValueError(f'{heading}: expected one table with header {columns}')
    start = starts[0]
    separator = lines[start + 1] if start + 1 < len(lines) else ''
    cells = [c.strip() for c in separator.strip().strip('|').split('|')]
    if len(cells) != len(columns) or not all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
        raise ValueError(f'{heading}: malformed table separator')
    rows, seen = [], set()
    for line in lines[start + 2:]:
        if not line.strip().startswith('|'):
            break
        cells = [c.strip().strip('`') for c in line.strip().strip('|').split('|')]
        if len(cells) != len(columns):
            raise ValueError(f'{heading}: malformed row (expected {len(columns)} cells): {line}')
        key = tuple(cells[:name_columns])
        if not all(key) or key in seen:
            raise ValueError(f'{heading}: empty or duplicate row name {key}')
        if not all(re.fullmatch(r'#[0-9A-Fa-f]{6}', c) for c in cells[name_columns:]):
            raise ValueError(f'{heading}: invalid full hex color in {key}')
        seen.add(key)
        rows.append(dict(zip(columns, cells)))
    return rows


def parse_palettes(text: str):
    rows = parse_table(text, 'Starter palettes', COLUMNS, 1)
    if len(rows) != 15:
        raise ValueError(f'Expected 15 starter palettes, found {len(rows)}; update count when curating kits')
    return rows


def parse_status_pairs(text: str):
    rows = parse_table(text, 'Status pairs', STATUS_COLUMNS, 2)
    expected = {(theme, role) for theme in ('Light', 'Dark')
                for role in ('success', 'warning', 'destructive', 'info')}
    actual = {(row['Theme'], row['Role']) for row in rows}
    if actual != expected:
        raise ValueError(f'Status pairs: missing {expected - actual}, unexpected {actual - expected}')
    return rows


def check_pairs(row, checks):
    return [f'{label} {ratio(row[fg], row[bg]):.2f} < {minimum}'
            for label, fg, bg, minimum in checks if ratio(row[fg], row[bg]) < minimum]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=KITS)
    args = parser.parse_args()
    try:
        text = args.path.read_text(encoding='utf-8')
        palettes, statuses = parse_palettes(text), parse_status_pairs(text)
    except (OSError, ValueError) as error:
        print(f'ERROR: {error}')
        return 1
    failing = 0
    for rows, checks, key in [(palettes, CHECKS, lambda r: r['Kit']),
                              (statuses, STATUS_CHECKS, lambda r: f"{r['Theme']} {r['Role']}")]:
        for row in rows:
            bad = check_pairs(row, checks)
            if bad:
                failing += 1
                print(f"FAIL {key(row)}: {'; '.join(bad)}")
            else:
                print(f'PASS {key(row)}')
    count = len(palettes) * len(CHECKS) + len(statuses) * len(STATUS_CHECKS)
    print(f'\n{len(palettes)} palettes + {len(statuses)} status pairs; {count} contrast checks; {failing} failing rows')
    return int(failing > 0)


if __name__ == '__main__':
    raise SystemExit(main())
