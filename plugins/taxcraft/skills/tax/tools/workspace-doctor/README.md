# Workspace Doctor

Report-only health check for the tax workspace layout. **Never modifies or
deletes anything** — it only reads directory structure and filenames, and
always exits `0` (this is a diagnostic report, not a CI gate).

Prints paths only, never file contents — no PII from inside documents is
ever read or shown, and any path with a segment containing `privileged`
(case-insensitive, e.g. `*attorney-client-privileged*`) is excluded by
design from every walk and never appears in output. That said, the output
still contains file/folder names, which may themselves be sensitive (entity
names, personal names, addresses used as slugs, etc.) — review before
sharing it externally; it is not a blanket "safe to paste anywhere" report.
All printed paths are relative to the workspace root, not absolute.

## Usage

Run it **from the workspace root** — the directory holding `workspace-profile/`,
`entities/`, `individual/`. That is the default root; `$TAX_WORKSPACE` overrides it.
The skill ships as an installed plugin, so the tree around this script is the plugin
cache, not your workspace: the root is never inferred from the script's own location.

```bash
TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"
python3 -B "$TAX_SKILL/tools/workspace-doctor/doctor.py"

# Diagnosing a workspace other than the current directory
python3 -B "$TAX_SKILL/tools/workspace-doctor/doctor.py" --root /path/to/workspace
```

## Checks performed

| Check | What it flags |
|---|---|
| Missing canonical workspace-profile files | Any of `entities-index.md`, `owner.md`, `history.md`, `bank-accounts.md`, `slugs.md`, `federal-accounts.md`, `org-chart.md` missing from `workspace-profile/` |
| Entity dirs violating kebab-case slug rule | `entities/<name>` directories with spaces or uppercase letters |
| Corporate-intake folders with PDFs but no `_processed.log` | Scoped to corporate-intake surfaces only: `entities/<slug>/corporate/**` and nested `entities/<slug>/disregarded/*/corporate/**`. Any such directory that directly contains a `.pdf` but has no `_processed.log` sibling file. Tax-doc intake under `FY<YYYY>/` is out of scope — it uses a different, non-log-based mechanism (see `intake.md`). |
| Empty `.parsed/` dirs alongside `.txt` sidecars | A `.parsed/` directory with nothing in it, next to a `.txt` file — usually means the parse cache is being skipped rather than populated |
| Sync-conflict litter | Cloud-sync duplicate/collision artifacts: `* (1).*`, `*-...Mac*.*`, double extensions (`.pdf.pdf`), wrong-case extensions (`.Pdf`, `.PDF`, etc.) |
| Loose K-1/tax PDFs outside FY folders | K-1/1099/1040/1065/1120/W-2-named PDFs sitting directly at the workspace root or `individual/` root instead of inside a `FY<YYYY>/` folder |
| `__pycache__` dirs in the skill tree | Stray bytecode-cache directories under the tax skill tree (see `tools/README.md` — run tools with `python3 -B` to avoid these) |
| poppler presence | Whether `pdftotext -v` succeeds (poppler installed) |
| Beancount ledgers failing bean-check | Each `entities/**/books/ledger.beancount` run through `bean-check` (books venv) |
| xledger-check (intercompany mirrors) | `books-tooling/scripts/xledger-check.py` — `#intercompany` links must have two legs netting to zero |
| Ledgers older than latest bank/CSV export | `ledger.beancount` mtime vs newest `tax/FY*/source/bank-cc` CSV |
| Entity trackers missing | `entities/<slug>/carryforwards.json` absent for any entity with a `books/` dir; `books/capital-accounts.md` absent for an entity whose `entity.md` `Entity type:` field says partnership; an `entity.md` with no readable `Entity type:` field is reported as unclassifiable. **This is the one check that reads file content** — it scans `entity.md` line by line only until it finds the labelled `Entity type:` field (or reaches end of file), reads no other file, and uses the value only to classify; the value is never printed. A §704(d) carryforward, EBIE allocation, or passed-through credit that lives only in prose is not tracked — see `entities/partnership.md` § 1065 Flow item 4. Fixture tests: `python3 -B test_doctor.py` |

Each group caps output at 20 paths, appending `…and N more` beyond that.

## What it does NOT do

- Does not read file contents, with one documented exception: the entity-tracker check scans each `entities/<slug>/entity.md` line by line until it finds the labelled `Entity type:` field (or end of file) and uses that value only to classify the entity — the value is never printed and no other file is opened. No document, ledger, or return content is read (PII-safe by construction)
- Does not modify, move, rename, or delete anything
- Does not compute or validate tax figures
- Is not a substitute for the tax skill's own routing / intake checks — it
  only checks filesystem hygiene

## Exit code

Always `0`. Findings are informational; review and act on them manually.
