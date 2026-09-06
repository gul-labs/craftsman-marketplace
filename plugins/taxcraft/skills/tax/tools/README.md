# Tax Skill Tools

Executable utilities bundled with the tax skill. Reusable across any workspace that adopts the skill — unlike entity-specific workpapers, these belong with the skill itself so the logic travels with the skill, not with any one user's data.

Tools live here when they're general-purpose (work for multiple entities across any workspace), format-bound (parse a specific document type with stable conventions), and likely to be re-run as new data arrives. Tools that are truly workspace-specific belong outside the skill.

## Available tools

| Tool | Purpose | Entry |
|---|---|---|
| [chase-statement-parser](chase-statement-parser/) | Parse Chase bank + credit-card PDFs and CSV exports into unified reconciled transaction ledgers | `chase_parser.py` (import as library) |
| [pdf-extractor](pdf-extractor/) | PDF reader with the text-quality gate (`quality.py`), AcroForm field reading (`acroform.py`), producer detection, and `--mode form` (PNGs + gated text). Also home of the field envelope + two-engine merge (`envelope.py`) and the differential comparer (`compare.py`). | `pdf_extract.py` (CLI + library) |
| [form-parser](form-parser/) | Registry-driven parser for W-2, W-2G, 1099-INT/DIV/B/NEC/MISC/R/G/K/SA, 1099-Composite, SSA-1099, 1098/-T/-E, 5498/-SA, 1095-A. AcroForm → vision skeleton → gated text → merge → invariants; emits schema-2 envelopes. Box definitions + invariants in `doc_types.py`; fixture corpus in `fixtures/`. | `form_parser.py` (CLI + library) |
| [k1-parser](k1-parser/) | Parse Schedule K-1 (Form 1065 / 1120-S) PDFs into the `parsing.md` K-1-1065 JSON schema. Handles single-K-1 PDFs and multi-K-1 filing packages (`--multi`). | `k1_parser.py` (CLI + library) |
| [return-parser](return-parser/) | Parse filed entity returns (1065 / 1120 / 1120-S) into the `parsing.md` `1065-Return` / `1120-Return` schema. Auto-detects form type; captures page-1 P&L, Schedule K/L/M-1/M-2, Schedule J, partner list, Schedule B elections. | `return_parser.py` (CLI + library) |
| [transcript-parser](transcript-parser/) | Parse IRS Account / Tax Return / Wage & Income / Record of Account transcripts. Extracts TC codes + cycle dates, flags exam/freeze/lien indicators. TC code lookup in `tc_codes.json`. | `transcript_parser.py` (CLI + library) |
| [ibkr-parser](ibkr-parser/) | Parse Interactive Brokers monthly statement CSVs into a unified transaction ledger + summary. Uses the matching PDF for cross-validation; flags non-USD amounts. | `ibkr_parser.py` (CLI + library) |
| [coa-categorizer](coa-categorizer/) | Rule-based GL-bucket classifier for raw transaction rows (Chase checking/CC output). Produces enriched CSV with `gl_account`, `gl_code`, `confidence`, `needs_review` columns + a review summary. Seed rules in `default_rules.json`; override per entity. | `coa_categorizer.py` (CLI + library) |
| [parse-verify](parse-verify/) | Arithmetic and tax-law invariants over parsed tax JSON — Layer B of the extraction-confidence system in `parsing.md`. Catches issuer errors that survive any amount of extraction consensus. | `verify.py` (CLI + library) |
| [dep-check](dep-check/) | Report-only dependency preflight for the **skill itself** (not the workspace) — install integrity, Python version, poppler, the `evals/` packages, optional fallback rungs. Prints the platform-correct fix command for anything missing; never installs. Exits 1 when a required dependency is absent. | `dep_check.py` (CLI, `--json`) |
| [workspace-doctor](workspace-doctor/) | Report-only health check for workspace layout — missing workspace-profile files, non-kebab-case entity dirs, corporate-intake folders (entities/*/corporate/**) with PDFs but no `_processed.log`, empty `.parsed/` caches, sync-conflict litter, loose K-1/tax PDFs, stray `__pycache__`, poppler presence, per-entity `bean-check`, `xledger-check`, ledger-vs-CSV staleness. Never modifies anything; always exits 0. | `doctor.py` (CLI) |

## Running tools

All tools require **Python 3.9+** (standard library only — no `pip install`
needed for any tool in this directory unless its own README says otherwise).
The PDF-reading tools additionally need **poppler** on the PATH, and the
validators under `evals/` need two pip packages. `dep-check` verifies all of it
in one call; `dependencies.md` is the SSOT for install and repair.

Invoke tools with `python3 -B` (or set `PYTHONDONTWRITEBYTECODE=1`) so Python
doesn't write `__pycache__/` bytecode caches into the tree — a workspace kept in
a synced folder (OneDrive, Dropbox, iCloud Drive) turns `.pyc` churn into sync
conflicts, and the caches are noise in every other workspace too.
`__pycache__/` and `*.pyc` are also covered by the skill's `.gitignore` as a
second line of defense; `workspace-doctor` (below) flags any that slip
through.

The skill is installed as a plugin, so these paths are not relative to your
workspace. Resolve them through the plugin root once, then address every tool
through it — a bare `python3 -B k1_parser.py` only works if you happen to be
standing in the tool's own directory, which you are not:

```bash
TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"
python3 -B "$TAX_SKILL/tools/k1-parser/k1_parser.py" "path/to/k1.pdf"
```

Tool *arguments* work the other way: they are workspace paths, resolved against
the current directory. Run tools from the workspace, address them by plugin path.

## Design principles

1. **Library first, driver second.** Each tool is a library (parseable + importable). Per-entity driver scripts live with that entity's data (`entities/<slug>/books/...`) and just configure + invoke the library. Keeps entity-specific config next to the entity, shared logic here.

2. **Validation is mandatory output.** Every tool that produces derived data also produces a validation report showing reconciliation against source-of-truth balances or totals. No silent failures.

3. **Deterministic + idempotent.** Re-running a tool with the same inputs produces the same outputs. Tools overwrite prior runs rather than appending.

4. **Never write inside the skill.** Output goes to the user's workspace; scratch
   goes to `tempfile.TemporaryDirectory()` with no `dir=` argument. An installed
   plugin is read-only for most users, so a write here is a PermissionError for
   them and a silent success for you — `evals/test_no_skill_writes.py` runs the
   whole suite against a read-only copy so that asymmetry cannot survive a PR.

5. **Source of truth is never overwritten.** Tools read from `tax/<year>/source/`, `accounts/`, etc., and write derived artifacts elsewhere. Raw source PDFs / CSVs are never modified.

6. **Reproducibility.** Each tool has its own README and a documented invocation pattern so future runs (or future people) can repeat the work without reverse-engineering.

## When to add a tool here vs. entity-local

**Add to the skill's `tools/`** if the utility is:
- General-purpose (works for multiple entities in any workspace)
- Format-bound (parses a specific document type with stable conventions)
- Likely to be re-run as new data arrives

**Keep entity-local** if the work is:
- One-off analysis specific to one entity + one year
- A hand-built workpaper (trial balance, Schedule L rec)
- Configuration that only makes sense in context (e.g., account list for a specific entity)

## Adding a new tool

1. Create `tools/<tool-name>/` folder.
2. Put the library code in a clearly named file (e.g., `<tool_name>.py`).
3. Write a `README.md` at minimum covering: purpose, usage, requirements, sign conventions, failure modes.
4. Add a row to the table above.
5. If the tool is load-bearing for tax work, cross-reference from the tax skill's own files where relevant.

## Not yet built

Prioritized by how often the document type shows up in a typical multi-year individual `docs/` folder, not by how interesting the parser would be to write. P0 = blocks annual close or intake; P1 = reduces manual effort materially; P2 = nice-to-have.

| Priority | Tool | What it does | Blocked on |
|---|---|---|---|
| **P0** | W-2 parser | Parse boxes 1–12, state wages, box 14 into `parsing.md` W-2 schema. Essential for individual annual workpaper. | Schema defined; many clean samples in `individual/FY*/docs/` |
| **P0** | 1099-Composite parser | Single PDF from Fidelity / Chase / Morgan Stanley / IBKR with INT / DIV / B / foreign tax sections. Feeds Schedule B/D + Form 8949. | Schema defined in `parsing.md` |
| **P0** | 1099-R parser | Retirement-distribution forms — gross, taxable, withholding, box 7 distribution code. Affects taxable income + AGI. | Schema needed in `parsing.md` |
| **P0** | 1098 mortgage parser | Mortgage interest (box 1), property tax escrow (box 10), points, outstanding principal. Multi-property scope common. | Schema needed |
| **P1** | 1099-INT / 1099-DIV standalone | FirstTech / PenFed single-form statements — different layout from Composites. | Schema defined for Composite (reuse subsections) |
| **P1** | 1099-K parser | Payment-platform reporting (Zillow, Stripe, Venmo Business). Increasingly shows up on IRS Wage & Income transcripts. | Schema needed |
| **P1** | 5498 / 5498-SA parser | IRA/HSA contribution + FMV reports. Needed for Form 8606 basis tracking and HSA deduction. | Schema named in `parsing.md` "Other types"; needs expansion |
| **P1** | 1099-NEC / 1099-MISC parser (issued and received) | Simple 3-box layout. Issuer-side feeds Form 1096 summary; recipient-side goes to Schedule C / Schedule E. | Schema in `parsing.md` §"Other types" placeholder |
| **P2** | SSA-1099 parser | Social-security benefit statements — box 5 net benefits, box 6 voluntary withholding. | Schema needed |
| **P2** | Wire confirmation OCR | Extract amount + date from wire PDFs for capital-call evidence | `pdf-extractor` already handles OCR; needs thin wrapper + schema |
| **P2** | TurboTax `.tax20XX` reader | Decode filed TurboTax files into the same schema as `return-parser` output. | TurboTax format is proprietary; may require feature work in TurboTax Desktop export or a third-party library |
