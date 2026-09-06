# parse-verify

Arithmetic and tax-law invariants over parsed tax JSON. **Layer B** of the
extraction-confidence system in `parsing.md` → "Verify before writing".

Layer A (`tools/pdf-extractor/compare.py`) asks *did we read this correctly?*
Layer B asks *can this document be internally consistent at all?* — which is
the question that catches issuer errors, because those survive any amount of
extraction consensus.

Layer B now covers **every** document type the skill parses. K-1s and entity
returns keep the hand-written checks in `verify.py` (their invariants are
cross-sectional and sign-convention-sensitive). Every other type registered in
`tools/form-parser/doc_types.py` — W-2, the 1099 family, 1098/1098-T/1098-E,
1095-A, 5498, SSA-1099 — is routed to its declarative invariants through
`tools/form-parser/invariants.py`, and those findings come back as the same
`Finding` records with the same severities. Adding a form to the registry adds
it to this gate; nothing here needs editing.

```bash
python3 verify.py <scope>/FY<YYYY>/.parsed/         # whole scope-year + cross-doc checks
python3 verify.py <file>.json --min-severity HIGH
python3 verify.py <dir> --json                      # machine-readable
python3 test_verify.py                              # self-test
```

Exit 0 = nothing at or above `--min-severity` (default MEDIUM); 1 = findings;
2 = usage/IO error. Never modifies anything.

> **Paths below are written from this tool's own directory.** The skill installs as a
> plugin outside your workspace, so a bare `python3 verify.py` will not resolve from
> where you are standing. Set `TAX_SKILL="${CLAUDE_PLUGIN_ROOT}/skills/tax"` once and
> address the script as `"$TAX_SKILL/tools/parse-verify/verify.py"`. Arguments are the other way
> round: they are workspace paths, resolved against the current directory.

## Envelopes, and why "not evaluable" is a finding

Two document shapes arrive here and both must verify identically:

* **legacy flat** — `{"box_1_ordinary": -700, ...}`;
* **schema 2** — every load-bearing value wrapped in an envelope
  (`{"value": …, "state": "OBSERVED_VALUE", …}`, see `pdf-extractor/envelope.py`),
  which is what `k1_parser.py --merge` and `form_parser.py` emit.

Every read in `verify.py` unwraps, so a schema-2 K-1 produces exactly the
findings its flat equivalent does — `test_verify.py` asserts that set equality
rather than trusting it.

The part that changes behaviour: an envelope in state `NOT_PRESENT` or
`UNREADABLE` unwraps to `None`, not to `0`. A check whose input the extractor
explicitly did not observe is **skipped** and reported at INFO as
`<check>.not_evaluable` — for example `K1.item_l.rollforward.not_evaluable`.

That distinction is the whole point. A blank capital account read as zero
turns "we could not see the beginning balance" into "the partner has no
basis", which asserts a §704(d) violation the document never supported. The
INFO finding says what was *not* proven, so a reviewer can go get the number
instead of trusting a silence. A key that is simply absent from a legacy flat
file is **not** treated as unobserved — that file never claimed to carry it,
so the historical zero-default still applies there.

## What the extractor said about itself

If a document carries an `_extraction` block, two of its fields are surfaced:

| id | severity | Trigger |
|---|---|---|
| `EXTRACTION.review_required` | MEDIUM | one finding per path in `_extraction.review_required` — the text and vision passes read the field differently and the merge kept one of them |
| `EXTRACTION.text_suspect` | INFO | `_extraction.quality.verdict == "suspect"` — the text scored badly enough that every figure in the file is provisional |

## Checks

**Per K-1**

| id | What it asserts |
|---|---|
| `K1.item_l.rollforward` | beginning + contributions + income ± adjustments = ending |
| `K1.item_l.blank` | Item L is not blank while the K-1 allocates activity |
| `K1.item_l.negative_ending` | negative ending capital is surfaced (legal, but a §704(d) tell) |
| `K1.704d.loss_exceeds_basis` | loss ≤ capital + liability share, where basis is **known** |
| `K1.704d.basis_undeterminable` | loss allocated but Item L unpopulated — basis unknown, not zero |
| `K1.basis_worksheet.unexplained` | worksheet basis ≈ ending capital + Item K liabilities (§722/§752) |
| `K1.gp_equals_distribution` | Box 4a/4c ≠ Box 19 when both are populated |
| `K1.pct.out_of_range` | ownership percentages are percentages |
| `K1.199a.zeroed` | §199A statement is not zeroed while Box 1/2 report income |
| `K1.titling` | surfaces a titling error the extractor recorded |

**Per return (1065 / 1120 / 1120-S)**

| id | What it asserts |
|---|---|
| `1065.schedule_l.imbalance` | assets = liabilities + capital, both columns |
| `1065.m2.rollforward` | M-2 rolls forward |
| `1065.m2_vs_schedule_l` | M-2 ending = Schedule L ending partners' capital |

**Cross-document** (directory mode only)

| id | What it asserts |
|---|---|
| `cross.k_vs_k1_sum` | every Schedule K line = sum of the issued K-1 boxes |
| `cross.ownership_sum` | issued K-1 capital percentages total 100% |
| `cross.nondeductible_passthrough` | Box 18C on received K-1s reaches this entity's Schedule K |
| `W2.duplicate` | no two files carry the same employer EIN + employee SSN + tax year |

`W2.duplicate` is HIGH because the failure mode is silent and one-directional:
a Copy B and a Copy 2 of one W-2 saved as two files, summed, double the wages
*and* the withholding, and the return looks like a refund. Either include the
statement once, or establish that one file is a W-2c that replaces the other.

**Per registry doc type** (W-2, 1099-*, 1098-*, 1095-A, 5498, SSA-1099)

Ids come from `doc_types.py` (`W2.box4_ss_rate`, `1099INT.box9_le_box8`, …).
Two shapes are generated rather than declared: `<invariant>.not_evaluable`
(INFO) when a box the expression needs was not observed, and
`<DocType>.<box>.required_missing` (HIGH) when a box the form always prints is
absent. Rate invariants read `rules/federal-<tax_year>.json`, so a document
with no tax year skips them as not evaluable.

## Two things the code is deliberately careful about

**Sign conventions are not consistent in the parsed corpus.** Some files store
withdrawals as a signed negative, others as a positive magnitude to be
subtracted. Both appear here. Every rollforward is computed both ways and ties
if *either* reconciles — a validator that assumes one convention silently
reports false breaks on half the population.

**Blank is not zero.** An unpopulated Item L means outside basis is *unknown*.
Reporting "basis = 0" would assert a §704(d) violation the document cannot
support, so that case reports `basis_undeterminable` instead.

## Adding a check

For W-2s, 1099s, 1098s and the rest of the registry, add the `Invariant` to
`tools/form-parser/doc_types.py` instead — it is picked up here automatically.
Hand-written checks below are for K-1s, returns, and anything cross-document.

Add it to `check_k1`, `check_1065`, or `check_cross`, then add **two** cases to
`test_verify.py`: one document that violates it, and one that superficially
resembles a violation but is legitimate. The second is the one that matters — a
check that fires on everything is as useless as one that never fires.

Severity: `CRITICAL` = the document contradicts itself; `HIGH` = probably wrong,
needs a human; `MEDIUM` = worth review; `INFO` = context.

## Scope

These are internal-consistency checks. They cannot detect a figure that is
wrong but self-consistent — that needs reconciliation to independent data
(bank/brokerage records, prior-year workpapers), which remains a human step.
