# Close and Estimate Orchestrator

Use this orchestrator for annual estimates, quarterly closes, installment
computations, “how much should I pay?” requests, and reconciliation of an
already-made estimated payment. It coordinates existing modules; it does not
duplicate their doctrine.

Load only the references needed for the run:

- `authority.md` for every exact rule used;
- `parsing.md` only if source documents must be read;
- `reconciliation.md` before an entity close or current-year estimate based on
  books;
- `variance.md` after a period P&L;
- the applicable `entities/<type>.md` adapter;
- `estimate.md` for individual annual liability;
- `quarterly.md` for §6654/§6655 installment mechanics or state estimates;
- applicable state modules only for state components.

## 1. Resolve the run

Record before loading private data:

- mode;
- individual or exact entity slug;
- entity tax classification;
- tax year and fiscal-year dates;
- annual or installment period;
- federal and state components requested;
- authorization boundary;
- as-of date.

A mismatch in identity, scope, tax classification, tax year, or fiscal period is
a run-level hold.

`tax_year` identifies the year in which the return tax period begins. Preserve
`tax_period.start`, `tax_period.end`, and its `CALENDAR`, `MONTHLY`,
`WEEK_52_53`, or `SHORT` convention separately from the cumulative installment
`period`; a fiscal year beginning in 2025 and ending in 2026 uses the 2025 rules
file. For `WEEK_52_53`, also preserve and validate the elected ending month,
weekday, and nearest-month-end or last-weekday-in-month method under §441(f).
Bind the start to the day after the preceding elected year-end; a 364/371-day
duration plus a valid current endpoint is insufficient if a week is skipped.
The period also carries `basis_status` and exact evidence refs. A READY fiscal
result requires FINAL, independently reviewed, subject-matched evidence of an
existing fiscal period, a valid original adoption/election, or an approved
change (including Form 1128/consent evidence when applicable). A user assertion
or a workpaper that merely repeats the requested dates is not adoption evidence.
For `WEEK_52_53`, independently observed evidence must also show that the
taxpayer regularly computes income on the elected basis in keeping its books;
approval or election evidence alone does not satisfy §441(f)(1).
Do not infer tax year from the installment-period end.

## 2. Operating modes

| Mode | Permitted result |
|---|---|
| `READINESS` | Report authority, evidence, reconciliation, and artifact gaps. Report-only. |
| `CLOSE` | Prepare authorized local close workpapers and proposed journal entries. This skill never posts entries, files, or pays. |
| `ESTIMATE` | Compute and report liability or installment methods. Persist only when the user authorized workspace changes. |
| `CLOSE_AND_ESTIMATE` | Run an authorized close, then the dependent estimate if its gates pass. |
| `PAYMENT_RECONCILIATION` | Reconcile an already-made payment from evidence. Never initiate a payment. |

Annual versus quarterly is a period parameter, not a mode. A request to compute
how much to pay authorizes analysis, not payment submission, portal use, bank
debit, filing, or communication.

## 3. Separate status axes

Never collapse books, estimate, and payment into one `complete` flag.

### Authority

`VERIFIED_FOR_USED_RULES` → `PARTIALLY_VERIFIED_UNUSED_GAPS` → `AUTHORITY_HOLD`

### Evidence

`INPUTS_VERIFIED` → `MATERIAL_PROJECTIONS` → `INPUTS_INCOMPLETE`

Each input is `FINAL`, `PROJECTED`, `USER_PROVIDED`, `SUPERSEDED`, or
`CONTRADICTED`. User-provided is a provenance label, not verification.

### Close

`NOT_RUN` → `RECONCILIATION_HOLD` → `DRAFT_OPEN_ITEMS` → `CLOSE_RECONCILED`

### Estimate

`NOT_RUN` → `ESTIMATE_HOLD` → `PROVISIONAL` → `DRAFT_VERIFIED_INPUTS` →
`READY_FOR_PRACTITIONER_REVIEW` → `SUPERSEDED`

The agent cannot advance a result beyond `READY_FOR_PRACTITIONER_REVIEW`.

### Payment

`NO_PAYMENT_EVIDENCE` → `USER_REPORTED_PAYMENT` → `PAYMENT_EVIDENCED` →
`PAYMENT_RECONCILED`

Analysis never advances payment status. Instantiate a payment record only after
the user reports a payment or provides payment evidence.

### Method status

Every prior-year, current-year, annualized-income, adjusted-seasonal, state PTE,
or withholding method receives exactly one:

- `AVAILABLE_VERIFIED`
- `AVAILABLE_PROVISIONAL`
- `INELIGIBLE`
- `BLOCKED_MISSING_INPUT`
- `BLOCKED_RULE_UNVERIFIED`

Do not compare a blocked or ineligible method as if its amount were zero. A
lower provisional method cannot displace a higher verified method merely
because it produces a smaller number.

## 4. Failure precedence

Apply the narrowest valid hold, in this order:

1. Identity, scope, classification, tax-year, or fiscal-period mismatch holds
   the run.
2. A missing, uncovered, superseded, or unverified used rule holds the dependent
   computation or method.
3. A critical parse failure or source contradiction holds dependent lines.
4. Any nonzero unexplained cash difference, missing statement/account coverage,
   unbalanced trial balance, material unreconciled non-cash account, or
   unresolved quarantined transaction with dependent tax impact holds the close
   and dependent current-year/AI methods.
5. A material projected K-1 or other projected input makes dependent methods
   provisional.
6. Method-specific statutory ineligibility marks only that method `INELIGIBLE`.
7. A verified computation without practitioner review stops at
   `READY_FOR_PRACTITIONER_REVIEW`.

Missing current-year inputs may block current-year and AI methods while leaving
a properly evidenced prior-year method available.

## 5. Evidence and close gates

Create an input manifest containing immutable input ID, logical-document ID and
version, active/superseded state, path, SHA-256, source state, parser contract,
and evidence-bound document metadata (privacy-safe subject ID, document type,
form identity when applicable, tax year, period start and end, and final/filing
status). Every consumed field records its parser value,
semantic state, page/line-or-box anchor, independent reviewer, review time, and
validation status. Never coerce a missing value to zero: `OBSERVED_ZERO` is a
reviewed zero, while `NOT_PRESENT`, `UNREADABLE`, and `NOT_APPLICABLE` carry a
`null` value and hold dependent calculations where relevant.

For entity work, require the sign-off gates in `reconciliation.md`. Journal
entries produced during close remain **proposed**. Posting belongs to a separate,
explicitly authorized bookkeeping workflow and must return independent evidence
before this skill treats an entry as posted.
The close is not reconciled merely because debits equal credits: bank,
brokerage, intercompany, payroll, fixed-asset, capital/basis, and balance-sheet
controls must pass where applicable.

## 6. Computation and recommendation

1. Build the authority register under `authority.md`.
2. Run the applicable individual or entity computation using inputs → formula →
   result lines.
3. Preserve unknowns as `null` with a blocker; do not convert them to zero.
4. Determine each installment method's eligibility and status before computing
   a recommendation.
5. Compare only eligible methods. State whether the result is verified or
   provisional and why.
   The recommendation inherits the selected method: an
   `AVAILABLE_PROVISIONAL` selection yields `PROVISIONAL`; an
   `AVAILABLE_VERIFIED` selection with verified dependent authority/inputs and
   required close gates yields `READY_FOR_PRACTITIONER_REVIEW`. Unselected
   projected methods remain disclosed through the independent
   `MATERIAL_PROJECTIONS` evidence axis.
6. A recommended amount is never evidence of payment and never authorization to
   initiate payment.
7. State outputs remain separate from federal outputs and carry independent
   authority and evidence statuses.

### Component isolation and aggregate status

The canonical artifact contains `components.federal` and one
`components.state[]` record per requested state. Each component has independent
authority, evidence, estimate/method, amount, and blocker statuses. A held state
component does not erase a separately valid federal result.

Derive the aggregate result as follows:

- `COMPLETE_COMPONENT_RESULT` — every requested component has a non-held result;
- `PARTIAL_COMPONENT_RESULT` — at least one component has a non-held result and
  at least one requested component is held;
- `ALL_COMPONENTS_HELD` — every requested component is held.

The top-level authority axis reports the worst requested component for alerting;
the component records control whether a federal or state amount is usable.

## 7. Canonical artifacts

When persistence is authorized:

- instantiate `templates/close-estimate-control.md.template` as the control
  workpaper;
- create the canonical JSON result from `templates/estimate.template.json`;
- bind every nonblocked recommendation to one component and one structured
  method record; the method must cite verified authority dependency IDs and
  numeric canonical lines whose provenance resolves to active reviewed fields;
- permit `AVAILABLE_VERIFIED` only when every method operand and its evidence
  resolve to active `FINAL` inputs with non-draft document metadata; projected,
  user-reported, legacy-unverified, superseded, or contradicted sources cannot
  silently support a verified method;
- keep `payment_records` empty at `NO_PAYMENT_EVIDENCE`; higher payment states
  require unique record IDs and transaction evidence plus matching confirmation
  amount, bank-settlement amount, settlement, identity/form/period, and
  correct-tax-year controls; every evidence input must match the run's
  privacy-safe subject ID, and `PAYMENT_RECONCILED` dates cannot be after the
  artifact as-of date; never credit the same underlying source-hash/anchor tuple
  twice even if it is aliased through different field IDs; credit records must
  be positive—returned/reversed payments remain separately linked,
  non-creditable exceptions rather than negative payment records;
- keep `payment_execution_authorized` set to `false` in every agent-generated
  estimate artifact;
- derive presentation Markdown from the JSON;
- mirror only run ID, status, as-of date, headline totals, and a pointer into
  `tax-summary.md`;
- preserve the earlier run and mark it `SUPERSEDED` when a corrected input or
  rule changes the result. A rerun is run supersession, not a decision; it needs a
  decision memo only if a judgment also changed (`supersession.md` §3).

The control workpaper is the single home for authority, input, gate, and method
status. Do not duplicate those tables across entity files.

## 8. Payment boundary

The skill may explain payment methods and prepare user-reviewable instructions.
It never signs, files, accesses a portal, schedules a debit, transmits a
payment, or communicates with a tax authority. A future execution workflow must
be separately defined, separately invoked, and independently confirmed; a user
saying “pay it” does not convert this analytical skill into that workflow. This
skill's maximum estimate status is `READY_FOR_PRACTITIONER_REVIEW`.

Use `templates/quarterly-payment.md.template` only after payment is reported or
evidenced. Record confirmation and bank evidence separately; a confirmation
without correct taxpayer, form, period, and amount is not reconciled.

## 9. Release checks

These validators need `jsonschema` (see SKILL.md "First-run tooling check"). If it
is missing they exit non-zero with the install command rather than a stack trace —
treat that as "not verified", never as a pass.

After changing this workflow run:

```bash
python3 evals/validate_rules.py
python3 evals/validate_close_estimate.py
```

Before releasing an instantiated JSON estimate artifact, validate that exact
file (not the placeholder template):

```bash
python3 evals/validate_close_estimate.py --artifact /absolute/path/to/estimate.json
```

When that artifact sets `supersedes_run_id`, also pass the preserved predecessor
with `--predecessor-artifact /absolute/path/to/prior-estimate.json`; validation
fails without reciprocal run and input linkage.

The validator enforces schema formats, current-run authority dependencies,
field-level anchors/review, component aggregation, supersession, and the
non-execution boundary. A passing template-only release check is not evidence
that a taxpayer artifact passed.

Then run blind forward tests from `evals/close-estimate.md` with independent
tax-law, tax-operations, and skill-red-team reviewers. Empty reviewer output or
an unexecuted test is not approval.
