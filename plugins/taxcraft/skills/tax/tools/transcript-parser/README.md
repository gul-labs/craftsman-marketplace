# IRS Transcript Parser

Parses the four transcript types available from the IRS Online Account portal
into a consistent JSON schema. Integrates with `tc_codes.json` (36 TC codes
with descriptions and significance notes).

> **Paths below are written from this tool's own directory.** The skill installs as a
> plugin outside your workspace, so a bare `python3 transcript_parser.py` will not resolve from
> where you are standing. Set `TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"` once and
> address the script as `"$TAX_SKILL/tools/transcript-parser/transcript_parser.py"`. Arguments are the other way
> round: they are workspace paths, resolved against the current directory.

## Supported transcript types

| IRS title | `doc_type` value |
|---|---|
| Account Transcript | `IRS-Account-Transcript` |
| Tax Return Transcript | `IRS-Return-Transcript` |
| Wage and Income Transcript | `IRS-WageIncome-Transcript` |
| Record of Account | `IRS-RecordOfAccount-Transcript` |

## Files

| File | Purpose |
|---|---|
| `transcript_parser.py` | Main library + CLI |
| `tc_codes.json` | 36 TC codes with `description` + `significance` notes |
| `README.md` | This file |
| `samples/` | Synthetic transcript text fixtures, one per layout (no real names, TINs or amounts) |
| `test_transcript_parser.py` | Offline self-test over `samples/` — `python3 -B test_transcript_parser.py`, exit 0 = pass |

## Library usage

```python
from transcript_parser import parse_transcript

data = parse_transcript("/path/to/transcript.pdf")
print(data["doc_type"])          # IRS-Account-Transcript
print(data["tax_period"])        # 202012
print(data["tc_transactions"])   # list of TC dicts
print(data["anomalies"])         # list of flag strings
```

## CLI usage

```bash
# Extract via pdftotext, parse, show summary table; prompt to write JSON
python3 transcript_parser.py "path/to/transcript.pdf"

# Non-interactive: print full JSON to stdout
python3 transcript_parser.py "path/to/transcript.pdf" --json

# Redirect JSON to file
python3 transcript_parser.py "path/to/transcript.pdf" --json > out.json
```

**PDF requirement:** `pdftotext` from poppler must be installed.

```bash
brew install poppler   # macOS
```

## JSON output schema

```json
{
  "doc_type": "IRS-Account-Transcript",
  "tax_period": "202012",
  "form_number": "1040",
  "taxpayer_name": "JOHN Q TAXPAYER",
  "taxpayer_tin": "XXX-XX-1234",
  "filing_status": "Single",
  "return_section": {
    "agi": 573362.0,
    "taxable_income": 534323.0,
    "tax_per_return": 106625.0,
    "se_tax": 0.0
  },
  "account_summary": {
    "account_balance": 1440.96,
    "accrued_interest": 1.66,
    "accrued_penalty": 0.0
  },
  "tc_transactions": [
    {
      "tc": "150",
      "explanation": "Tax return filed",
      "cycle": "20214205",
      "date": "2021-11-08",
      "amount": 106625.0,
      "tc_description": "Return filed / tax assessed"
    },
    {
      "tc": "806",
      "explanation": "W-2 or 1099 withholding",
      "cycle": "20214205",
      "date": "2021-04-15",
      "amount": -105184.04,
      "tc_description": "W-2 / 1099 withholding credit"
    }
  ],
  "tc_summary": {
    "150": [{"date": "2021-11-08", "amount": 106625.0, "cycle": "20214205"}],
    "806": [{"date": "2021-04-15", "amount": -105184.04, "cycle": "20214205"}]
  },
  "wage_income_items": [],
  "anomalies": []
}
```

### `wage_income_items` (Wage and Income and Record of Account transcripts)

One object per information return on the transcript:

```json
{
  "form": "Schedule K-1 1065 Partner's Share of Income, Deductions, Credits, etc.",
  "form_code": "K-1 (1065)",
  "ein": "XXXXX0003",
  "name": "SAMP FUN LP",
  "recipient_name": "SAMP TA",
  "recipient_tin": "XXX-XX-1234",
  "submission_type": "Original document",
  "fields": {
    "Schedule K-3": "Box checked",
    "Ordinary Business Income (loss)": -997.0,
    "Real Estate": -3250.0,
    "Interest": 64.0
  }
}
```

| Field | Description |
|---|---|
| `form` | Heading as printed, colon removed |
| `form_code` | `W-2`, `1099-B`, `1098`, `5498`, `3922`, `K-1 (1065)`, … — group and count on this |
| `ein` | First identification number in the block: employer, payer, filer or partnership (masked by the IRS) |
| `name` / `recipient_name` | First and second `Name:` lines — payer, then recipient. The IRS truncates names |
| `recipient_tin` | Second identification number in the block |
| `submission_type` | `Original document`, `Amended document`, `Corrected document` |
| `fields` | Every other `Label: value` line. Dollar values are signed floats; indicators stay strings. Address lines are not copied |

**Layouts read.** The IRS Online Account has changed its Wage and Income layout more than once;
all of these parse to the same schema:

| Layout | Heading | Value line |
|---|---|---|
| Legacy | `Form W-2 Wage and Tax Statement` | `Wages, Tips and Other Compensation:......$95,000.00` |
| 2026 plain | `Form W-2 Wage and Tax Statement`, `Schedule K-1 1065` | `Wages, Tips and Other Compensation:   $12,500.00` |
| October 2026 | `Form W-2: Wage and Tax Statement`, `Schedule K-1 1065: Partner's Share of …` | same |

Amounts keep their sign in every position the IRS prints it: `-$20,000.00`, `$-85.00`, `($8,211.00)`.
A credit balance is negative.

### `tc_transactions` field detail

| Field | Type | Description |
|---|---|---|
| `tc` | string | 3-digit TC code |
| `explanation` | string | Text from transcript line |
| `cycle` | string | IRS cycle date YYYYWWDD (if present) |
| `date` | string | ISO 8601 date YYYY-MM-DD |
| `amount` | float | Signed: negative = credit to taxpayer, positive = assessment/charge |
| `tc_description` | string | From `tc_codes.json`; falls back to `explanation` if code unknown |

## Anomaly flags

The parser emits strings in `anomalies` for the following conditions:

| Flag prefix | Trigger |
|---|---|
| `EXAM_INDICATOR` | TC 420 or 424 present — examination selected or requested |
| `EXAM_ASSESSMENT` | TC 300 present — additional tax assessed by examiner |
| `FREEZE_INDICATOR` | TC 570, 520, or 582 — refund freeze, collection hold, or federal tax lien |
| `AMENDED_RETURN` | TC 977 — Form 1040-X filed |
| `DUPLICATE_RETURN` | TC 976 — duplicate return posted |
| `BALANCE_AFTER_REFUND` | Positive account balance despite TC 846 refund issued |

## TC codes reference (`tc_codes.json`)

36 codes covering the most common transcript events. Each entry includes:

- `description` — one-line name of the transaction
- `significance` — what it means for the account (freeze, exam, credit, etc.)

Not every TC code that can appear on a transcript is in this file; unknown codes fall back to the raw `explanation` text pulled from the transcript line (see `_tc_label()` / `tc_description` field).

Key codes and what to look for:

| TC | What it means | Key actions |
|---|---|---|
| 150 | Return filed / tax assessed | Anchors ASED and CSED; verify amount = Line 24 of filed return |
| 160/166 | Failure-to-file penalty (§6651(a)(1)) | Abatement candidate — FTA or reasonable cause |
| 196 | Interest assessed (§6601) | Accrues daily; amount on transcript is as-of date |
| 270/276 | Failure-to-pay penalty (§6651(a)(2)) | Abatement candidate |
| 280 | Accuracy-related penalty (§6662) | No FTA — reasonable cause only |
| 290 | Additional tax assessed | $0 = no change; >$0 = new CSED anchor |
| 420/424 | Examination referral / request | Action required; watch ASED |
| 460 | Extension filed | Extends ASED; does NOT extend payment deadline |
| 480 | OIC pending | CSED tolled |
| 500 | Substitute for Return | File actual return immediately |
| 520 | Collection held (litigation/bankruptcy) | CSED tolled |
| 550 | ASED extended (Form 872) | Track new ASED date from consent |
| 570 | Additional liability pending / freeze | Refund blocked; watch for TC 971 companion |
| 582 | Federal Tax Lien filed | Severe; CDP rights triggered |
| 846 | Refund issued | Direct deposit ~2-3 business days post TC 846 |
| 922 | CP2000 proposed assessment | NOT final — respond within 60 days |
| 971 | Miscellaneous / notice issued | Read sub-code for specific notice type |
| 972 | Penalty abatement granted | Favorable — confirms abatement posted |
| 977 | Amended return filed | Look for TC 290/291 downstream |

## Statute date computation

The parser does **not** automatically compute statute dates — there are too many
variables (late filing, extensions, tolling) to compute reliably without human
review. Compute manually using the rules below, anchored on the relevant
`tc_transactions` dates (TC 150, TC 480/520/540/590, etc.).

**ASED** (Assessment Statute): 3 years from later of due date or TC 150 date.
6 years for substantial omission (>25% of gross income). No limit for fraud.

**CSED** (Collection Statute): 10 years from TC 150 (or TC 290/300 for later
assessments). Tolled by TC 480, 520, 540, 590 events.

## Workspace integration

Per `naming.md` §"IRS transcripts" and `scenarios/irs-transcripts.md`, pulled
transcripts use the canonical filename `FY<YYYY> - IRS <Type> Transcript -
<scope-slug>.pdf`, where `<Type>` ∈ {`Account`, `Return`, `Record of Account`,
`Wage and Income`, `Verification of Non-Filing`}, saved at:

```
individual/FY<YYYY>/transcripts/
  FY<YYYY> - IRS Account Transcript - <scope-slug>.pdf
  FY<YYYY> - IRS Account Transcript - <scope-slug>.parsed.json   ← parser output

entities/<slug>/tax/FY<YYYY>/annual/workpapers/transcripts/
  FY<YYYY> - IRS Account Transcript - <slug>.pdf
  FY<YYYY> - IRS Account Transcript - <slug>.parsed.json         ← parser output
```

The parser writes its JSON output as `<input>.parsed.json` next to the source
PDF (see CLI usage above) — it does not write into a `.parsed/` subdirectory.
Run the parser once per transcript and keep the `.parsed.json` alongside the
source PDF. Use the JSON in workpaper reconciliation.

## Dependencies

- `pdftotext` (poppler-utils — `brew install poppler`)
- `pdf_extract.py` in sibling `../pdf-extractor/` directory
- Python 3.9+ (standard library only)

No pip installs required.
