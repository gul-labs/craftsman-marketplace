# form-parser

Turns an **information return** — W-2, the 1099 family, 1098 / 1098-T / 1098-E,
1095-A, 5498 / 5498-SA, SSA-1099, W-2G — into one `schema_version: 2` envelope
document, then tests that document against the arithmetic the form must satisfy.

Adding a form is adding an entry to `doc_types.py`. Nothing else changes.

| File | What it is |
|---|---|
| `doc_types.py` | The registry: anchors, boxes (id, label, kind, label regex), invariants, per-type parser owner. Data only. |
| `invariants.py` | Whitelisted-AST evaluator for the registry's invariant expressions. A box that was not observed SKIPS its invariant — it is never treated as zero. |
| `form_parser.py` | The parser and CLI. |
| `templates/` | Producer-keyed layout overrides for issuers who do not print the IRS labels. See `templates/README.md`. |
| `fixtures/` | The checked-in PDF corpus and its `golden.json` values, plus the generator that made them. |
| `test_form_parser.py` | Self-test. No arguments, exit 0 on pass. |

## Why this exists

Form PDFs are the worst case for `pdftotext -layout`: values live in boxes, and
a layout pass that hops one column silently reports a wrong number that every
downstream computation then trusts. Before this tool, W-2s and 1099s had no
parser at all — they were read freehand.

So the read is **layered**, and each layer records what it is:

| Rung | Engine | When |
|---|---|---|
| 0 | AcroForm fields | Exact. Fillable IRS PDFs and some issuer PDFs carry the values as form fields. |
| 1 | Vision over page images | **Primary** for boxed forms. A model reads the PNGs and fills the registry's JSON skeleton. |
| 2 | `pdftotext -layout` anchor parse | The independent cross-check — and only after `quality.py` says the text is real text, not `(cid:37)` soup. |
| 3 | Merge | Agree → confidence 0.95. One-sided → 0.6. Disagree → keep the vision value, keep the text value as an alternate, and list the path in `_extraction.review_required`. |
| 4 | Invariants | `invariants.py` over the merged document. A CRITICAL finding blocks `--write`. |

Rung 1 cannot run inside a script — something has to look at the pixels — so the
tool is deliberately two-pass. A text-only run is legitimate for a clean digital
form, and `_extraction.engines` says so.

Three rules hold at every rung: a box that was not found is `NOT_PRESENT`, a box
whose label was found but whose value would not parse is `UNREADABLE`, and
neither is ever a zero. `tax_year` is read from the page or left null.

## Invocation

```bash
TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"
FP="python3 -B $TAX_SKILL/tools/form-parser/form_parser.py"

$FP w2.pdf                                  # detect the type, print a summary
$FP w2.pdf --type W-2 --json                # force the type, print the document
$FP w2.pdf --write                          # → ./.parsed/w2.json
$FP 1099int.pdf --json --quiet              # JSON only, no summary
```

Exit codes: **0** clean · **1** a HIGH/CRITICAL finding or a non-empty
`review_required` (the document is still printed) · **2** usage error, a missing
file, or a doc type another tool owns (the message names it — K-1s go to
`k1-parser`, filed returns to `return-parser`, transcripts to
`transcript-parser`).

`--write` refuses when an invariant marks the document `blocked`. `--force`
overrides it; record why in `open-questions.md` when you use it.

## The vision two-pass

```bash
# 1. Print the prompt, the box list and the page images.
$FP w2.pdf --type W-2 --vision-prompt

# 2. Read each PNG with the Read tool and write the filled skeleton to vision.json.
#    Plain values, not envelopes. null for a blank box. 0 only for a printed 0.

# 3. Merge the two reads and write the result.
$FP w2.pdf --type W-2 --merge vision.json --write
```

The merge never decides who was right. It decides what a human has to look at:
every field the two engines disagree on lands in `_extraction.review_required`
with the losing value kept under `alternates`, and the run exits 1.

Do this whenever the quality gate says `suspect` or `garbage`, whenever the PDF
is a scan, and on any figure large enough to matter.

## Output shape

```json
{"doc_type": "W-2", "schema_version": 2, "tax_year": 2025,
 "identity": {"employer_ein": {"value": "12-3456789", "state": "OBSERVED_VALUE",
                               "source_anchor": {"page": 1, "line_or_box": "employer_ein"},
                               "confidence": 0.95, "review": {...}}},
 "boxes":    {"box_1": {"value": 105000.0, "state": "OBSERVED_VALUE", ...}},
 "state_local": [{"state": ..., "state_wages": ..., "state_wh": ...}],
 "_extraction": {"engines": ["text"], "producer": "...", "quality": {...},
                 "merged": false, "review_required": [], "findings": [...],
                 "blocked": false, "source_path": "...", "sha256": "...",
                 "page_count": 4},
 "warnings": []}
```

`state_local` is W-2 only. `_extraction.acroform_unmapped` lists AcroForm field
names that matched no box — IRS fillable forms name their widgets `f1_09[0]`, so
seeing them there is normal, not a failure.

W-2s print Copy B/C/2 of the same figures; each copy is parsed separately and
each box takes the value the majority of copies agree on. A split keeps the
first copy's value and adds a warning naming the box.

## Adding a doc type

Registry only. In `doc_types.py`:

1. Add a `DocType` with `anchors` (regexes; enough of them to separate it from
   its neighbours — `Form\s*1098\b(?!-)` does not want to match a 1098-T),
   `identity`, `boxes`, and `invariants`.
2. Add it to `REGISTRY`. `FORM_PARSER_TYPES`, the vision skeleton, doc-type
   detection and the quality gate all follow automatically.
3. Add a fixture: values in `fixtures/make_fixtures.py`, then regenerate.
4. Run `python3 -B tools/form-parser/invariants.py` and the self-test.

Write invariants that can only fail when a *document* is wrong — a subtotal that
must not exceed its total, a rate that must hold, a column that must sum. Gate
anything that depends on the rules file with `when="... rules.get('key')"` so a
missing rules year skips the check instead of failing it.

## Adding a vendor template

Only when an issuer prints labels the IRS form does not. See
`templates/README.md`; the short version is `pdfinfo` for the producer string,
`pdftotext -layout` for the labels the vendor actually prints, then a JSON file
overriding just those boxes. Never add one speculatively.

## Regenerating the fixtures

The corpus is checked in; the generator is run by a maintainer.

```bash
python3 -B "$TAX_SKILL/tools/form-parser/fixtures/make_fixtures.py"            # all
python3 -B "$TAX_SKILL/tools/form-parser/fixtures/make_fixtures.py" --only W-2
python3 -B "$TAX_SKILL/tools/form-parser/fixtures/make_fixtures.py" --check    # parse + diff only
```

`make_fixtures.py` is a pure-stdlib PDF writer, so the corpus is regenerable from
source with nothing installed and no binary blob anyone has to take on trust. It
is deterministic: no timestamps, no `/ID`, fixed values, byte-identical on a
re-run. Every figure is internally consistent so the registry invariants PASS —
`fixtures/w-2-broken/` (box 4 inflated tenfold) is the one that must fail, which
is how the test knows the invariants still fire.

Per type: `text.pdf` + `golden.json`. For W-2 also `acroform.pdf` (fields named
after box ids), `garbage.pdf` (fonts with no ToUnicode map — the quality gate
must call it garbage), and `scan.pdf` (`text.pdf` rasterized to 150 dpi gray,
generated only when `pdftoppm` is present).

## Testing

```bash
python3 -B "$TAX_SKILL/tools/form-parser/test_form_parser.py"
```

Every fixture is parsed twice — with `--type` and by auto-detection — and
compared to its golden values. Without poppler the PDF cases print `SKIP` and the
pure-python cases still run. The test writes only to `tempfile`, so
`evals/test_no_skill_writes.py` picks it up automatically.

## Dependencies

Python 3.9+, standard library only. `pdftotext` / `pdfinfo` / `pdffonts` /
`pdftoppm` (poppler) for the text, metadata, quality and image rungs. Rung 0 uses
`pypdf` or `pdftk` when either is installed and is skipped when neither is.
`dep-check` reports on all of it.
