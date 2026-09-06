# K-1 Parser

Extract Schedule K-1 (Form 1065 or 1120-S) fields from a PDF into the `parsing.md` `K-1-1065` / `K-1-1120S` JSON schema.

> **Paths below are written from this tool's own directory.** The skill installs as a
> plugin outside your workspace, so a bare `python3 k1_parser.py` will not resolve from
> where you are standing. Set `TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"` once and
> address the script as `"$TAX_SKILL/tools/k1-parser/k1_parser.py"`. Arguments are the other way
> round: they are workspace paths, resolved against the current directory.

## Purpose

Every K-1 received by an entity or individual flows into the enclosing scope's `tax-summary.md`. This tool extracts the structured fields (partner/issuer identity, boxes 1–20, capital account, liabilities, §199A codes) so the intake workflow can diff filed amounts against expected amounts and update workpapers without hand-typing.

## Library usage

```python
from k1_parser import parse_k1, parse_multi_k1

# Single-K-1 PDF (issued directly to a partner)
result = parse_k1("path/to/FY2024 - K-1 - LP - <sponsor-slug>.pdf")

# Multi-K-1 PDF (full 1065 return containing K-1 for each partner)
results = parse_multi_k1("path/to/2024 - Example Fund Records.pdf")
```

Returns a dict (or list) shaped per `parsing.md` §K-1-1065. Fields that cannot be detected are left as `null` / `0.0` and surfaced in the `warnings` list.

## CLI

```bash
python3 k1_parser.py "path/to/k1.pdf"                   # single-K-1: table + JSON printed, nothing written
python3 k1_parser.py "path/to/records.pdf" --multi      # multi-K-1 (one PDF per partner)
python3 k1_parser.py "path/to/k1.pdf" --json            # JSON only (no table, no prompt, no write)
python3 k1_parser.py "path/to/k1.pdf" --write           # confirmation table, then prompt to write to .parsed/
python3 k1_parser.py "path/to/k1.pdf" --write --no-confirm  # write disabled — prints table + JSON only
python3 k1_parser.py "path/to/k1.pdf" --vision-prompt   # print the vision prompt + JSON skeleton, exit 0
python3 k1_parser.py "path/to/k1.pdf" --merge vision.json   # fold a vision read into the text read
```

By default (no `--write`), the CLI prints the confirmation table (partner, issuer, boxes, capital, liabilities, warnings) followed by the full JSON and never writes anything — there is no prompt. `--json` suppresses the table and prints JSON only. The interactive `[yes / edit / skip]` write prompt only fires when `--write` is passed; without it nothing is ever written. `--no-confirm` combined with `--write` skips the prompt but also skips the write (the CLI falls through to printing table + JSON instead) — use `--write` alone to actually write interactively.

## When the text cannot be trusted

Before any regex runs, the extracted text is scored by
`pdf-extractor/quality.py`. Three outcomes:

| verdict | What happens |
|---|---|
| `ok` | parse normally |
| `suspect` | parse anyway, but `warnings` gains *"text quality suspect — vision pass required"* and the reasons land in `_extraction.quality`. Treat every figure as provisional until a vision read confirms it. |
| `garbage` | **no parse.** Returns a result with `needs_vision: true`, the rasterized `pngs`, the `quality` report and instructions — never a document full of zeros. |

An image-only or scanned K-1 takes the same `needs_vision` path. This used to
raise `RuntimeError`; it no longer does, because a caller can act on a result
and cannot act on a traceback. On that path the CLI prints the vision prompt
and **exits 1**.

### The vision round trip

```bash
# 1. Parse. A scanned or unreadable K-1 prints the prompt and exits 1.
python3 k1_parser.py "k1.pdf" > prompt.txt

# 2. Read the PNGs the prompt lists (Claude's Read tool does vision), fill the
#    printed JSON skeleton, save it as vision.json.

# 3. Merge the two reads.
python3 k1_parser.py "k1.pdf" --merge vision.json --json > k1.merged.json
```

The skeleton carries the same K-1 keys this parser emits, all blank, plus the
instructions that matter: copy digits exactly, `null` for a blank or unreadable
box and `0` **only** where the form prints a zero, boxes 4a/4c guaranteed
payments are ordinary income and are **not** box 19 distributions, and Item K
liabilities are debt, not income.

`--vision-prompt` prints the same prompt for a PDF that *did* parse from text —
worth doing whenever the boxes matter, since two independent reads is the whole
premise of Layer A.

## Output shapes: flat by default, envelopes on merge

Without `--merge` the output is **exactly the legacy flat schema** it has always
been, plus one new key:

```json
"_extraction": {"engines": ["text"], "producer": "Intuit Lacerte Tax 2024",
                "vendor": "Lacerte", "quality": {"verdict": "suspect", ...}}
```

With `--merge` the output is `schema_version: 2`: the same flat K-1 keys, but
each load-bearing scalar (`box_*`, `capital_account.*`, `liabilities.*`,
`partner_ein_ssn`, `issuer_ein`, `tax_year`) wrapped in a field envelope
carrying `state`, `confidence` and, on disagreement, the other engine's value
under `alternates`. Agreement raises confidence to 0.95; a one-sided read is
0.6; a disagreement is 0.3, keeps the **vision** value, and lists the path in
`_extraction.review_required` — which the CLI prints as a review summary and
`parse-verify` reports as a MEDIUM finding.

The state is what stops the classic error: a box in state `NOT_PRESENT` or
`UNREADABLE` reads back as `None`, never `0`, so `verify.py` skips the checks
that depend on it instead of asserting a violation against a number nobody saw.

## Producer and vendor

`pdfinfo` (guarded — no poppler, no problem) supplies `_extraction.producer` and
`_extraction.creator`. When the producer names a known preparer package
(Lacerte, ProSeries, UltraTax, Drake, CCH Axcess, ProSystem, TurboTax, TaxAct,
GoSystem) the name is recorded as `_extraction.vendor` and a warning appears:

> vendor layout Lacerte — confirm boxes 1, 2, 4a/4c, 19, Item K and Item L individually

**No regex is switched on the vendor.** There are no sample K-1s from these
packages to validate a vendor-specific rule against, and a wrong one is worse
than a generic one. The vendor is recorded so the operator knows which boxes
deserve a second look — nothing more.

## Dependencies

- Python 3.9+ (stdlib only)
- `pdftotext` via `poppler-utils` (`brew install poppler` on macOS)
- `pdftoppm` (same poppler package) for the vision path; `pdfinfo` (also poppler) for producer detection — both optional, both guarded
- Imports the sibling `pdf-extractor/pdf_extract.py` (text-or-image fallback), `quality.py` (the text gate) and `envelope.py` (field states and merge)

## Disregarded-entity handling

K-1s routed through a disregarded SMLLC appear two ways:

1. **SMLLC as partner, regarded owner in Item H2** (e.g. a fund issues to SUB SMLLC with Item H2 = PARENT LLC): `partner_name = "SUB SMLLC"`, `disregarded_entity_name = "PARENT LLC"`.
2. **Regarded owner as partner, SMLLC in Item H2** (e.g. a fund issues to PARENT LLC with Item H2 = SUB SMLLC): `partner_name = "PARENT LLC"`, `disregarded_entity_name = "SUB SMLLC"`.

Either convention is valid — both TINs are captured.

## Validation warnings (non-fatal)

- `Final K-1 flagged` — entity exit, confirm with books
- `Partner TIN not detected` / `Issuer EIN not detected`
- `Tax year not detected`
- `Box 20 code Z (§199A) not found` — Statement A may be missing or on a continuation page
- `text quality suspect — vision pass required` — the text scored badly (bad fonts, low dictionary hit ratio); every figure is provisional
- `vendor layout <X>` — the PDF came from a preparer package this parser was not tuned on

Warnings appear in the confirmation table **and** in `result["warnings"]`.

## Known limitations

- Two-column form layout is handled via column-range window scan; when the source PDF is heavily custom-formatted (non-Lacerte / non-CCH) the box scanner can miss or cross-talk between adjacent boxes. Always review the confirmation table before approving a write.
- Box 20 sub-codes are picked up but their per-code amounts are resolved from Statement A (`Rental income (loss)` line for Code Z). Other codes (AJ, N, ZZ, etc.) are surfaced as `{code, 0.0, "see statement"}` placeholders for manual review.
- Multi-K-1 detection splits on `Part III Partner's Share of Current Year Income`. Filed-copy PDFs sometimes include only one exemplar K-1 even for multi-partner returns; check against the partner roster on page 1.
- Image-only (scanned) K-1s do not parse from text at all: they return `needs_vision` with page images and a prompt, and the merged result rests on the vision read alone (single-engine, confidence 0.6). That is a real limitation, just an honest one.
- Vendor layouts are recorded, not handled. A K-1 from a package this parser was not tuned on may still cross-talk between adjacent boxes; the vendor warning tells you where to look, the vision merge is what actually settles it.

## Output artifacts (on `--write` with confirmation)

`<scope>/FY<YYYY>/.parsed/<source-slug>.json` — one JSON file per K-1 matching the schema. The index at `<scope>/FY<YYYY>/.parsed/_index.json` is updated by the intake workflow, not by this tool directly.
