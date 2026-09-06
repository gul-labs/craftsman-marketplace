# PDF Extractor

The extraction ladder for the tax skill: get the numbers off a PDF, and know how much to trust them.

> **Paths below are written from this tool's own directory.** The skill installs as a
> plugin outside your workspace, so a bare `python3 pdf_extract.py` will not resolve from
> where you are standing. Set `TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"` once and
> address the script as `"$TAX_SKILL/tools/pdf-extractor/pdf_extract.py"`. Arguments are the other way
> round: they are workspace paths, resolved against the current directory.

## Why the old version was not enough

The first version tried text, and fell back to page images when the text looked thin. Two things went wrong in practice, and both produced *wrong numbers rather than errors*:

1. **The gate was too easy.** "More than 50 characters, more than 5 characters per KB" is cleared comfortably by `(cid:37)(cid:12)(cid:88)` — what `pdftotext` emits when a PDF's fonts carry no ToUnicode map. Downstream regexes then matched nothing, and every box came back zero. Silently.
2. **Text went first even for forms.** `pdftotext -layout` reconstructs columns by guessing at whitespace. On a W-2 or a 1099 that means box 3's number can land on box 4's line. The characters are right and the mapping is wrong, which is the worst failure mode there is.

So text is now scored before anyone believes it, and boxed forms are read by vision *first*, with text kept as an independent second opinion.

## The rungs

| # | Rung | Module | When |
|---|---|---|---|
| 0 | **AcroForm fields** | `acroform.py` | Always attempted. IRS fillable forms and many issuer PDFs carry the exact typed value in a form widget — no layout to reconstruct, nothing to misread. |
| 1 | **Rasterize → vision** | `pdf_extract.py` (`--mode form`) | **Primary for form-shaped docs**: W-2, 1099-*, 1098-*, 1095, 5498, SSA-1099, K-1. Vision reads geometry the way a human does. |
| 2 | **`pdftotext -layout` → text** | `pdf_extract.py` + `quality.py` | Primary for prose (letters, statements, filed returns). For forms, the cross-check of rung 1. Must clear the quality gate. |
| 3 | **Merge** | `envelope.py` (`merge`), `compare.py --fields` | Agree → high confidence. Disagree → keep the vision value, record the text value as an alternate, list the path for review. One-sided → medium. |
| 4 | Invariants | `../parse-verify/verify.py` | Arithmetic and tax-law checks over the merged document. |
| 5+ | ocrmypdf / pdfplumber / other backends | — | Optional, probed only when reached. |

Rungs 0 and 2 are cheap and run on every call. Rung 1 costs a rasterization, so `mode` decides whether it happens.

## Files

| File | What it is |
|---|---|
| `pdf_extract.py` | The driver. Metadata, rung 0, the quality-gated text rung, rasterization. CLI + library. |
| `quality.py` | The gate. Scores extracted text and detects the doc type from registry anchors. |
| `acroform.py` | Rung 0. Dumps a PDF's own form fields via `pypdf`, else `pdftk`, else says it could not look. |
| `envelope.py` | The per-field state contract (`value` / `state` / `source_anchor` / `confidence` / `review`) and `merge()` of two independent reads. |
| `compare.py` | Two comparisons: several text engines over one PDF, and (`--fields`) two parsed documents against each other. |
| `test_pdf_extract.py` | Self-test. Runs with no arguments; skips the poppler cases cleanly when poppler is absent. |

## `pdf_extract.py`

**As a library (preferred — one call per document):**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(TAX_SKILL) / "tools/pdf-extractor"))
from pdf_extract import extract

r = extract("docs/w2-2025.pdf", mode="form", doc_hint="W-2")

r.acroform    # {field: value} | {} (no fields) | None (rung 0 unavailable)
r.pngs        # page images — read each one with the Read tool (vision)
r.text        # layout text; None when the gate called it garbage
r.text_ok     # True only when the verdict was "ok"
r.quality     # QualityReport.as_dict(): verdict, reasons, ratios, doc type
r.doc_type    # detected registry doc type
r.producer    # PDF /Producer — what keys a vendor layout template
r.creator, r.pages, r.mode, r.diagnostics
```

`{}` and `None` on `acroform` are different answers and must stay different: `{}` means the PDF genuinely has no form fields; `None` means no engine was available to look. Never collapse the two.

### Modes

| `--mode` | Rasterizes | Text | Result `mode` |
|---|---|---|---|
| `auto` (default) | only when the text is *garbage* or *suspect* | kept unless garbage | `text`, or `image` when text was garbage |
| `form` | **always** | attempted; kept unless garbage | `form` |
| `text` | never | attempted | `text`, or `failed` |

`auto` is backward compatible: a clean text PDF still returns `mode="text"` with `.text` populated and nothing rasterized.

The **suspect** case is the interesting one. In `auto`, a suspect verdict keeps `mode="text"` — so existing callers take their existing branch — but sets `text_ok=False` **and** populates `.pngs` as well. Both reads are in hand; merge them with `envelope.merge` rather than trusting either alone.

### Flags

```bash
TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"
X="$TAX_SKILL/tools/pdf-extractor"

python3 -B "$X/pdf_extract.py" doc.pdf                     # auto
python3 -B "$X/pdf_extract.py" doc.pdf --mode form         # vision first, text as cross-check
python3 -B "$X/pdf_extract.py" doc.pdf --mode text         # prose; never rasterizes
python3 -B "$X/pdf_extract.py" doc.pdf --hint W-2          # expected doc type; tightens the gate
python3 -B "$X/pdf_extract.py" doc.pdf --json              # whole ExtractResult as JSON
python3 -B "$X/pdf_extract.py" doc.pdf --force-image       # skip text entirely (unchanged)
python3 -B "$X/pdf_extract.py" doc.pdf --pages 1-3
python3 -B "$X/pdf_extract.py" doc.pdf --dpi 300
python3 -B "$X/pdf_extract.py" doc.pdf --out-dir /tmp/pages
```

`--hint` is worth passing whenever you know what the document is meant to be: the gate then reports a *suspect* verdict when the page's anchor phrases say something else, which catches a mis-filed or mis-split PDF before any number is read off it.

Rasterization is 200 dpi by default and **220 dpi in `--mode form`** (box digits are small); an explicit `--dpi` always wins. PNGs go to a fresh `tempfile.mkdtemp()` unless `--out-dir` says otherwise — never inside the skill.

`--json` prints every field of `ExtractResult`, PNG paths included, which is the shape to pipe into a parser.

## `quality.py` — the gate

`assess(text, *, doc_hint=None, pdf_path=None) -> QualityReport`

Scores printable ratio, share of `(cid:N)` tokens, share of alphabetic tokens that are ordinary English or tax-form vocabulary, replacement characters, and — when `pdf_path` is given and `pdffonts` is on the PATH — how many embedded fonts lack a ToUnicode map. It also detects the doc type from the anchor regexes in `../form-parser/doc_types.py`.

| Verdict | Meaning | What `extract` does |
|---|---|---|
| `ok` | parse it | keeps the text; no rasterization in `auto` |
| `suspect` | parse it, but a vision pass is **mandatory** as the cross-check | keeps the text, sets `text_ok=False`, also rasterizes |
| `garbage` | do not parse | discards the text, goes to the image rung |

Standalone:

```bash
python3 -B "$X/quality.py" doc.pdf --hint W-2 --json
```

Exits 0 only on `ok`, so it works as a shell guard.

## `acroform.py` — rung 0

```bash
python3 -B "$X/acroform.py" form.pdf
python3 -B "$X/acroform.py" form.pdf --json
```

`read_fields(path) -> dict | None`. Engines in order: `pypdf` (optional pip package), then `pdftk` (optional binary). Fields with empty values are dropped — an unfilled widget is not an observed zero. A broken or encrypted PDF never raises; it returns `None` with the reason in the module-level `last_error`. `has_engine()` names the engine that would be used, or returns `None` when the rung is unavailable.

Both engines are optional. With neither installed the rung is simply skipped, and everything else still works.

## `envelope.py` — field state and merge

Every load-bearing value carries its own state, so a computation downstream can tell an observed zero from a box nobody saw:

```json
{"value": 1234.56, "state": "OBSERVED_VALUE",
 "source_anchor": {"page": 1, "line_or_box": "1"},
 "confidence": 0.95, "review": {"reviewer": null, "reviewed_at": null}}
```

States: `OBSERVED_VALUE`, `OBSERVED_ZERO`, `NOT_PRESENT`, `UNREADABLE`, `NOT_APPLICABLE`, `DERIVED`, `MANUAL_OVERRIDE`. `unwrap()` turns the three absent states into `None` — never `0`.

`merge(text_doc, vision_doc)` combines two reads of the same document:

- **agree** → keep the text value (exact digits), confidence 0.95, both engines recorded
- **one-sided** → keep it, confidence 0.6
- **disagree** → keep the *vision* value (vision reads layout), text value goes to `alternates`, confidence 0.3, path appended to `_extraction.review_required`

Money compares within `max(1.0, 0.5%)`; strings compare case- and space-insensitively; code lists (box 12, box 14, box 20) compare as multisets of `(code, amount)`.

## `compare.py` — two kinds of second opinion

**Text engines over one PDF** (unchanged): runs `pdftotext -layout`, `pdftotext -raw` and `pdfplumber`, and reports the dollar figures they do not all agree on.

```bash
python3 -B "$X/compare.py" doc.pdf
python3 -B "$X/compare.py" doc.pdf --json
python3 -B "$X/compare.py" doc.pdf --expect 58192 --expect -4168
python3 -B "$X/compare.py" doc.pdf --pngs
```

**Two parsed documents, field by field** (new): loads two `schema_version: 2` documents (`identity`, `boxes`, optional `state_local[]`), walks every envelope through `envelope.flatten` / `values_agree`, and prints the fields where the reads disagree.

```bash
python3 -B "$X/compare.py" --fields text.json vision.json
python3 -B "$X/compare.py" --fields text.json vision.json --json
```

```
! boxes.box_2              28,400.00            24,800.00
? boxes.box_3                      —           168,600.00
```

`!` = both reads saw a value and they differ. `?` = only one read saw it — which must become `NOT_PRESENT` or `UNREADABLE`, never a zero. Exit 1 when anything disagrees, 0 when nothing does, so it drops straight into a gate. This is the same comparison `envelope.merge` performs, reported instead of applied.

## Dependencies

- **poppler** — `pdftotext`, `pdftoppm`, `pdfinfo`, `pdffonts`. Required.
  `brew install poppler` (macOS) · `apt install poppler-utils` (Debian/Ubuntu) · `dnf install poppler-utils` (Fedora) · `choco install poppler` (Windows)
- **pypdf** *(optional)* — rung 0. `pip install pypdf`
- **pdftk** *(optional)* — rung 0 fallback.
- **pdfplumber** *(optional)* — a third text engine for `compare.py`.
- Python 3.9+, standard library only.

`../dep-check/dep_check.py` reports what is present and prints the platform-correct fix command. No OCR binary is needed: Claude's vision reads the rasterized pages.

## Self-test

```bash
python3 -B "$X/test_pdf_extract.py"
```

No arguments, exits 0 on pass, writes only into a temp directory. It covers the quality verdicts, doc-type detection, `values_agree` tolerances, the three merge outcomes, the AcroForm engine-absent paths, and the `--fields` exit code. Cases needing poppler print `SKIP …` and pass. `evals/test_no_skill_writes.py` picks it up automatically as `tools/*/test_*.py` and re-runs it against a read-only copy of the skill.

## Limitations

- **Vision cannot run headless.** Rung 1 hands back PNG paths; the model reads them. Nothing here can assert what vision saw.
- **Password-protected PDFs** are not handled — both poppler and rung 0 fail on them. `producer_info()` reports `encrypted`, which at least makes the reason visible.
- **The quality gate is conservative by design.** A PDF drawn with non-embedded base-14 fonts is reported *suspect* because `pdffonts` shows no ToUnicode map, even though the text is usually fine. Suspect costs a rasterization, not a wrong number.
- **No table-aware extraction.** For dense financial tables where `-layout` loses columns, `compare.py`'s pdfplumber engine is the available second opinion.
- **Downstream parsing** into per-doc-type JSON is not this tool's job — see `parsing.md` and `../form-parser/`.
