# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Versioning policy

This project doesn't (yet) follow strict SemVer against a public API, but plugin `version` bumps
follow this intent:

- **MAJOR:** a skill is removed or renamed, or a `description:` trigger's semantics change in a
  way that changes when it fires (not just wording).
- **MINOR:** a new skill graduates from `drafts/` into `skills/`, a new `references/*.md` file
  is added to an existing skill, a new shipped script is added under a skill's `scripts/`, or the
  findings emission format contract gains a field.
- **PATCH:** guidance edits within an existing reference or `SKILL.md` that don't change trigger
  semantics or add/remove a skill/reference.

The project is publicly launched at `0.2.0`; the `0.x` line continues post-launch (breaking changes
may still land in MINOR while the project settles). `1.0.0` is reserved for the point the skill set
and workflow are considered stable enough to commit to strict SemVer against the trigger surface,
not a synonym for "public."

## [Unreleased]

Nothing yet.

## [0.8.0] (2026-09-06)

Marketplace `0.8.0`; `taxcraft` moves to `0.3.0`; `craftsman` is unchanged at
`0.5.0`. This release answers the most consistent piece of user feedback on the
tax skill: PDF extraction of W-2s, K-1s, 1099s and 1098s was unreliable. MINOR
because a new shipped tool (`tools/form-parser/`) and new files under
`tools/pdf-extractor/` land; nothing is removed and legacy parsed JSON stays
readable.

### Why it was unreliable

- W-2s, 1099s and 1098s had **no parser at all**. They went through the generic
  extractor and were read freehand from `pdftotext -layout` output.
- The K-1 and return parsers are regexes tuned on one preparer's layout; a K-1
  from a different package silently returned zeros.
- Text was tried before vision even though `parsing.md` itself warned that
  layout text scrambles form columns.
- The "is this real text" gate was *more than 50 characters*. A PDF whose fonts
  carry no ToUnicode map produces long, dense symbol soup that passed it, so the
  image fallback never fired and the regexes returned nothing — quietly.
- There was no PDF fixture corpus, so none of this could regress.

### Added — `tools/form-parser/`

- **A declarative registry** (`doc_types.py`) of nineteen information returns —
  W-2, W-2G, 1099-INT, -DIV, -B (summary), -Composite, -NEC, -MISC, -R, -G, -K,
  -SA, SSA-1099, 1098, 1098-T, 1098-E, 5498, 5498-SA, 1095-A — each with its
  boxes (id, label, kind, label regex), anchor phrases for detection, and the
  arithmetic and tax-law **invariants** an internally consistent copy must
  satisfy: W-2 box 4 = 6.2% of boxes 3 + 7 and under the year's wage base (read
  from `rules/federal-<year>.json`), box 6 inside the Medicare band, 1099-DIV
  1b ≤ 1a, 1099-R 2a ≤ 1 and box 7 present, SSA-1099 box 5 = 3 − 4, 1099-K
  months sum to 1a, 1095-A annual totals tie and APTC ≤ premium each month, and
  seventy-one more. Adding a form is adding a registry entry.
- **`form_parser.py`** runs the new ladder end to end: AcroForm field values
  when the PDF has them (exact, nothing "read"), a vision skeleton the model
  fills from the rasterized pages (`--vision-prompt`), a text pass behind the
  quality gate, a per-field **merge** of the two reads (`--merge`) that lists
  every disagreement under `_extraction.review_required`, and the invariants.
  It emits the field envelope `parsing.md` promised in 0.2.0 (`schema_version:
  2`: value, state, source anchor, confidence, review) and refuses `--write` on
  a CRITICAL finding. A box the extractor did not observe is `NOT_PRESENT`,
  never 0.
- **A fixture corpus** (`fixtures/`): a deterministic pure-Python PDF writer
  produces a text PDF and golden JSON for every registry type, plus a fillable
  (AcroForm) W-2, a scanned W-2, a garbage-text W-2 and a deliberately wrong
  W-2, and `test_form_parser.py` proves the text pass reads every golden value,
  the gate rejects the garbage, the scan yields a vision prompt, and the wrong
  W-2 trips its invariant. `tools/form-parser/templates/` holds
  producer-keyed label overrides for vendor layouts.

### Changed — `tools/pdf-extractor/`

- **Text-quality gate** (`quality.py`): printable ratio, `(cid:N)` share,
  dictionary hit ratio, and `pdffonts` ToUnicode inspection yield `ok`,
  `suspect` (vision pass mandatory) or `garbage` (text discarded). Also detects
  the doc type from anchor phrases.
- **`envelope.py`**: the field envelope and the merge policy — both engines
  agree → 0.95 confidence, one-sided → 0.6, disagree → 0.3 with the alternate
  recorded and the path flagged for review.
- **`acroform.py`** (rung 0) via `pypdf` or `pdftk`, both optional.
- `pdf_extract.py` records producer/creator, page count, AcroForm fields and the
  quality report; `--mode form` returns PNGs *and* gated text; `--json`.
- `compare.py --fields a.json b.json` diffs two parsed documents box by box.

### Changed — `tools/k1-parser/`, `tools/parse-verify/`

- The K-1 parser no longer raises on an image-only or garbage-text PDF; it
  returns the PNG paths and a vision prompt, accepts `--merge`, and records the
  preparer package from the PDF producer with a per-vendor warning naming the
  boxes to confirm individually (1, 2, 4a/4c, 19, Item K, Item L).
- `verify.py` unwraps envelopes everywhere, routes every registry type through
  the declarative invariants, reports an invariant whose inputs were not
  observed as `not_evaluable` (INFO) instead of passing it on a phantom zero,
  and surfaces `review_required` paths as MEDIUM findings.

### Fixed — defects an adversarial review caught before release

Three independent review passes (tax-law correctness of the invariants,
silent-wrong-value paths, doc-versus-code consistency) each returned BLOCK. What
they found, all fixed here:

- **The merge tolerance was a percentage.** At 0.5%, a text read of `58,192` and
  a vision read of `58,483` differed by $291 and were recorded as *agreement* at
  0.95 confidence, never reaching the review list. Two engines reading the same
  printed number must produce the same digits; the tolerance is now half a cent,
  which covers rendering only.
- **An unread box-12 amount compared equal to a printed zero.** `null` and `0`
  are "we could not read it" and "the employer printed zero"; merging them at
  high confidence erased the difference.
- **Unobserved inputs could satisfy an invariant silently.** An absent code list
  summed to zero, a total skipped its unreadable members, and a guard that
  closed because a box was never observed reported nothing at all — which reads
  as "checked, fine". Aggregates now refuse to evaluate over an unreadable box,
  a blank box on a preprinted return still contributes zero, and a guard that
  closes for want of data says so as `not_evaluable`.
- **A text-only read of a form looked final.** A PDF whose text layer carries a
  plausible but wrong character mapping passes every text statistic while
  reporting numbers that were never printed. A single-engine form parse is now
  marked `vision_required`, carries a warning into the written document, and
  exits non-zero.
- **Six invariants would have fired on correctly issued forms.** W-2 boxes 4 and
  6 are the tax actually *collected*, so uncollected tax on tips or group-term
  life legitimately falls below the statutory rate. Both are now bounded on each
  side, with the shortfall allowed only up to the uncollected tax the employer
  reports in box 12 (code A or M for social security, B or N for Medicare) —
  a bare upper bound would have let a box 4 read as $2,000 where $3,100 was
  printed pass in silence. The box 1 versus box 5 deferral rule is gone
  entirely: FICA-exempt wages break it. 1099-R box 5 may exceed box 1; 1098
  box 4 refunds a prior year's interest; a 1095-A month can carry advance credit
  with a zero premium when coverage was terminated for nonpayment. The 1099-B
  gain tie now limits the market-discount adjustment to the realized gain, as
  Form 8949 does.
- **A missing check for the costly 1099-K misread**: box 4 backup withholding
  above box 1a gross is the classic transposition, now HIGH.
- **Accounting negatives were read as disagreements.** `(500)` and `-500` are
  the same amount; comparing them as strings put clean reads on the review list,
  and a review list full of false alarms is one nobody reads.
- **`--force` silently bypassed the CRITICAL write block** the docs promised.
  It still overrides, because that is sometimes the right call, but it now
  stamps the override, its date, and every overridden invariant into the written
  JSON, so a forced write cannot be mistaken for a clean one.

### Changed — method and preflight

- `parsing.md` "PDF read discipline" is rewritten around the new ladder: forms
  are read by vision first and cross-checked by gated text; AcroForm is rung 0;
  merge and invariants are rungs 3–4; hosted document-AI services are an
  explicit rung 7 behind the machine-local file, with the "the document leaves
  the machine" disclosure. `intake.md` routes every registry type to
  `form-parser`.
- `dep-check` probes `pdffonts`, `pypdf` and `pdftk`, and gains `--self-test`,
  which runs the fixture corpus on the user's machine so "does the pipeline work
  here, with this poppler build" is answered before a real document is touched.
- CI installs poppler and runs the fixture tests, so a parser change that breaks
  a form fails the PR instead of reaching users.

## [0.7.0] (2026-09-04)

Marketplace `0.7.0`; `taxcraft` moves to `0.2.0`; `craftsman` is unchanged at
`0.5.0`. This release closes the gaps a full C-corporation record-book
remediation exposed, including four statements the skill made that produced a
wrong deliverable.

**MINOR is claimed for a breaking change, which the `0.x` line permits.** The
release adds two routed `scenarios/*.md` files and nine templates, and it
**breaks the persisted stock-issuance artifact format** — renamed enum members
and three new required fields. Under the versioning policy above, breaking
changes may still land in MINOR while the project settles; from `1.0.0` this
would require MAJOR.

### Breaking — stock-issuance artifacts must be migrated

Any `stock-issuance-audit-FY<YYYY>.json` or closing manifest produced before
`0.2.0` will fail validation. `migrate.md` gains **Phase M6b** with the enum
rename table and, more importantly, the fields that must be decided by a human
rather than scripted: `purported_issuance_evidenced` (a reviewed fact, never
inferred from the old status) and the jurisdiction codes and statutory citation
that now bind an authority to the jurisdiction it is claimed to state. Expect
some tranches to derive a different — and more accurate — status afterwards.

### Fixed — guidance that produced a wrong deliverable

- **§531 accumulated-earnings work no longer runs ahead of the §541 personal
  holding company test.** The skill described the two taxes side by side and, at
  the end of the AET section, suggested considering PHC risk "too". That is
  backwards: **§532(b)(1) excludes a personal holding company from the
  accumulated earnings tax entirely**. For an investment-heavy closely held
  corporation — the exact profile the skill called a common trap — the old
  ordering produced a Bardahl working-capital analysis and annual business-needs
  resolutions defending a tax the corporation cannot owe, while the real §541
  exposure went untested. `scenarios/ccorp-tax-reduction.md` now runs the §542
  test first, stops the AET work when the answer is yes, and carries the §565
  consent dividend and the §547 deficiency dividend as the actual cures.
  `entities/c-corp.md` states the precedence at the point of use.
- **The June 30 fiscal-year exception to the Form 1120 deadline.**
  `entities/c-corp.md` stated the general §6072(b) fourth-month rule only, which
  gives a June-30 C corporation a deadline two weeks after the real one. The
  third-month due date, the seven-month extension, and the pre-2026 sunset now
  appear with the rule.
- **The stock-issuance artifact could not express two of its own statuses.** The
  prose defines eight tranche statuses and makes `DISPUTED OR DEFECTIVE` override
  every other post-issuance status, but the persisted schema allowed only four
  values — so the two states the evals exist to protect,
  `PURPORTED ISSUANCE — CONSIDERATION UNVERIFIED` and `DISPUTED OR DEFECTIVE`,
  had to be misreported as `CLOSING_PENDING` or `FACT_CONFLICT`. Both are now
  first-class, derived from a new required tranche fact
  (`purported_issuance_evidenced`) that encodes the prose's own first question:
  does competent evidence show a purported issuance actually occurred? A clean
  gate set with no evidenced issuance is now an error rather than a silent
  `ISSUED_AND_RECONCILED`.
- **Washington was hard-coded into a state-generic schema and validator.** The
  securities-route enum offered only Washington's state routes, the
  reacquired-share capacity rule named only Washington, and the validator raised
  "requires validator extension" for every other state — while the prose makes a
  validated artifact a precondition to reconciling an issuance. A Delaware,
  California, Texas, or New York issuance therefore could not be reconciled at
  all. Routes are now generic (`STATE_REGISTRATION`, `STATE_EXEMPTION`,
  `STATE_NOTICE_FILING`, `STATE_FEDERALLY_COVERED_NOTICE`), the capacity rule
  covers the treasury and non-treasury branches with the arithmetic each implies,
  and the validator checks the shape and source family of an authority — an
  official `.gov` source, a substantive route per state — instead of a
  jurisdiction roster.
- **The shipped audit template carried a plausible fiscal year.** Two annual
  subcontrols shipped with `FY2000` where every other period said `REPLACE`, so a
  filled artifact that missed those two rows would validate with a real-looking
  period. They now carry `FY0000`, and a release check fails on any plausible
  year in the template.
- **§1244(c)(2)(C) is a numerical test, not a business-failure carve-out.** The
  substance was right and the framing invited the wrong reading; it now says so.

### Added — rules that were absent

- **`governance.md` → "Authority Chains and Drafting Integrity"**, twelve rules
  the skill applied nowhere: establish the legal existence date before reading
  any instrument; **authority chains must be acyclic** (disputed shares may not
  elect the director who validates them, a director does not elect himself, and a
  public filing naming an officeholder is a filing rather than an internal
  election); a table of what each filed document does and does not prove;
  execution metadata outranks recitals; **recital integrity as a defect class
  separate from signature dates** ("approved" means signed, no recital of events
  later than the instrument's own effective date, no anachronistic content, "as
  of" is not a licence); ratification is bounded and may not rewrite a recited
  capacity; the three-branch ratification triage with the "within the power of
  the corporation" caveat that may put a pre-existence act outside the statute
  altogether; capacity reconciliation belongs in an incumbency certificate;
  inventory the executed legacy instruments before drafting new policy; bilateral
  instruments need bilateral termination; the never-backdate exposure ladder
  including the **§6664(c) forfeiture**; and the privilege carve-out language.
- **`scenarios/pre-formation-binder.md`** — the formation-vendor binder executed
  before the entity legally existed, as a named fact pattern with recognition
  tells, the three separate defects it contains, a nine-step remediation
  sequence, and the things not to do.
- **`scenarios/information-returns.md`** — payer-side reporting, which existed
  only as two deadline lines and carried no thresholds at all. Thresholds are read
  from `rules/federal-<payment-year>.json` for the **calendar** year of payment
  even for a fiscal-year entity; **Form 8233, not W-8BEN**, supports a
  nonresident individual's treaty claim for US personal services; §861(a)(3)
  sourcing; the corporate exemption and its attorney and medical carve-outs;
  backup withholding and B-notices; the **aggregate ten-return e-file mandate**;
  IRIS/FIRE responsible-official governance; and §6721/§6722 as separate
  penalties on the same failure.
- **`scenarios/ccorp-tax-reduction.md`** gains shareholder-loan pricing under
  **§7872** with the demand-versus-term distinction — §1274(d) publishes the
  rates for debt issued for property and is not the authority for pricing a
  related-party cash loan — and a section stating plainly that **there is no
  constructive-wage rule arising from non-payment alone**.
- **`entities/s-corp.md`** states C→S conversion consequences as conditions with
  their own tests: §1375 requires accumulated C-year E&P, §1362(d)(3) termination
  requires three consecutive years and takes effect the following year, and §1374
  requires conversion-date valuations.
- **`scenarios/accountable-plan.md`**: an unsigned plan is not an arrangement in
  force and its effective date cannot precede execution; an annual reimbursement
  cycle falls outside both safe harbors, because the periodic-statement route
  requires at least quarterly statements.
- **`scenarios/stock-issuance.md`**: the adequacy determination is its own signed
  instrument made before the issuance, carrying the fairness findings in the same
  writing where the subscriber is interested; no retroactive true-up of money that
  arrived before a valid subscription existed; marital-property character is
  conditional and tracing-dependent.
- **`scenarios/corporate-records.md` → "Working registers the record set needs"** —
  the eight running schedules a remediation produces, the rule that registers
  carry evidence-backed statuses only, and the documents a closely held record set
  commonly lacks, including the brokerage trading mandate and the
  securities-counsel gate on an outside adviser.
- **Nine templates**: adequacy-and-fairness determination, incumbency
  certificate, bilateral termination and release, open-items tracker, tax
  elections and positions register, address/agent/titling register, related-party
  transaction policy, records retention schedule, and a compliance calendar built
  around the two clocks a non-calendar-year entity runs.
- **A stated portability rule** (`SKILL.md`). The skill ships publicly and had no
  rule against embedding a user's data; it now carries the three-bucket test, the
  prohibition on hard-coding a jurisdiction into a schema or validator, and the
  instruction to extract the rule and leave the engagement facts behind.

### Corrected after independent review

Three independent Codex reviews were run against this release: a tax and
corporate-law pass, an engineering pass, and a confirmation pass over the
applied fixes. The first two returned NOT APPROVED with 17 and 8 findings; the
confirmation pass found four of the applied fixes had left a contradiction
elsewhere in the skill, and those were fixed in turn.

**Two findings are accepted as designed rather than resolved**, and are recorded
here rather than claimed closed:

- The persisted stock-issuance artifact still carries six status values, not the
  eight in the prose. Pre-closing states are deliberately not persisted, because
  every tranche row requires a closing manifest; `scenarios/stock-issuance.md`
  now carries the full mapping and names the two machine-only values.
- The release assertions in `evals/validate_corporate_records.py` remain literal
  substring checks. They are brittle against rewording and cannot prove a rule
  survived intact. They are a regression tripwire, not a semantic gate.

The corrections that changed a stated rule:

- **An accountable plan does not require a signature to exist.** The release
  said an unsigned plan is "no arrangement". §62(c) and Reg. §1.62-2 ask what
  arrangement actually existed when the payment was made, and Publication 5137
  says the policy need not be written. A missing signature is a governance fact
  and preferred-evidence problem, not a tax conclusion. The annual-cycle rule is
  now tested item by item: an expense substantiated within 60 days is inside the
  fixed-date safe harbor whatever the employer calls its cycle.
- **A stock-adequacy determination need not be a separate instrument.** MBCA
  §6.21's comment says no explicit resolution is required and DGCL §152(a)
  permits the terms in the board resolution. A separate instrument is an
  evidentiary preference. Deferred consideration — notes, future services,
  partly paid shares under DGCL §156 — can also be lawful, so the guidance no
  longer bars issuance before payment in every state.
- **Backdating consequences are not automatic.** §7206 and 18 U.S.C. §1001
  require their own elements, and §6664(c) applies portion by portion under a
  facts-and-circumstances test. One false document is powerful evidence against
  reasonable cause; it does not forfeit relief for unrelated items.
- **The interested person does not eliminate every disinterested route.** Other
  qualified directors, and shares not owned or controlled by the interested
  person, can still supply approval. Fairness is not automatically the only route.
- **Form 1120's deadline is §6072(a), not §6072(b)** — current §6072(b) covers
  partnerships and S corporations — and the June-30 rule is the Pub. L. 114-41
  §2006 transition rather than a current-text exception. The general rule would
  put that deadline a month late, not two weeks.
- **§542(a)(1) is "at least 60%", not "more than 60%".** The §547 deficiency
  dividend has two clocks (90 days to distribute, 120 days for Form 976) and the
  §565 consent dividend creates shareholder-level tax with no cash.
- **§7872 imports its rates from §1274(d)** rather than displacing it, term and
  demand loans have different mechanics, and the §7872(c)(3) $10,000 exception is
  tested rather than assumed inapplicable.
- **A corporate officer is generally an employee under §3121(d)(1)** even when
  unpaid; the narrow regulatory exception needs no-or-minor services *and* no
  remuneration. Status and wage amount are separate questions.
- **§1375 looks to all accumulated E&P at year end**, including AE&P succeeded
  to in a reorganization, and §1374 does not require a separate appraisal of
  every asset.
- **§1244 outcomes are numerical.** The "operating startups pass, holding
  companies fail" summary contradicted the exception stated immediately above it.
- Attorneys' service fees report under §6041/§6041A while gross proceeds are the
  separate §6045(f) rule; §861(a)(3) has its own exceptions and mixed services
  allocate under Reg. §1.861-4; an IRIS Responsible Official needs authority, not
  a corporate office; 1099 recipient dates vary by form; and the retention floors
  for information returns, W-9s, and W-8s are three different rules.
- **Execution evidence is weighed, not ranked.** A trusted e-signature completion
  certificate and an editable PDF timestamp are not the same thing, and an annual
  report proves what was filed rather than good standing.
- **A two-party instrument does not always need bilateral termination**, and a
  mutual release is a separate bargain with carve-outs.
- The shipped stock **audit** template no longer pre-asserts satisfied tax
  positions or a Washington capacity rule under a placeholder jurisdiction; a
  release check fails any JSON template carrying a real jurisdiction's statute or
  URL, or a satisfied tax position. The **closing manifest** template still shows
  verified values, because a manifest exists only for a completed closing; it is
  now labelled a specimen and says so.
- **Binding an authority to its jurisdiction.** Each authority carries the
  two-letter code of the jurisdiction whose law it states, and its source must be
  an HTTPS `.gov` host. Where a host label equals the code, that proves it;
  otherwise a **named person must attest** to the match, recorded in the
  artifact. Substring and path matches are rejected. This closes the reviewers'
  proof-of-concept (a NASA page accepted as Washington authority, including via a
  `/wa/` path segment) without a roster of hostnames, and without rejecting
  legitimate state sites that do not carry their own code such as `mass.gov` and
  `cca.hawaii.gov`.

### Added — taxcraft governance doctrine

Carried forward from the previously unreleased entry; these ship in this release:


Gaps found while running a full C-corporation record-book build end to end:

- `governance.md`: **Conflicting-Interest Transactions in Owner-Controlled Entities** — test each
  statutory route on the facts: an interested sole director cannot supply qualified-director
  approval, only shares he owns or controls are excluded from the qualified-share route, and
  fairness applies where neither approval route is satisfied. Delaware's DGCL §144 is classified
  under its 2025 subsections. What the record should contain, and the fact that a corporate-law
  fairness record is not a §482, reasonable-compensation, or bona-fide-debt conclusion.
- `governance.md`: a **bylaws drafting pattern** — who adopts, no shareholder action before shares
  exist, issuance approval and the adequacy/fully-paid effect, certificate signature requirements
  versus the uncertificated information statement, indemnification in tiers (including the
  shareholder authorization a pre-issuance corporation cannot yet have), officers, and records.
- `governance.md`: **intercompany arrangements between commonly controlled entities** — there is no
  filed §482 "method election"; pricing support is best-method documentation measured against
  Reg. §1.6662-6(d), must exist by the return's filing date, must carry its true preparation date,
  and must be filed as counterparts on both sides. Plus §267(a)(2) timing and the payee-state
  consequence of the charge.
- `scenarios/corporate-records.md`: search the workspace (including the counterparty's folders)
  before recording a cited document as missing, and record `NOT_LOCATED` with the paths searched
  rather than "does not exist"; related-party and intercompany hooks into the new doctrine.
- `scenarios/stock-issuance.md`: the sole-director purchaser conflict route points at the new
  governance section instead of a generic reference.
- `entities/c-corp.md`: **§248/§195 first-year costs** — the Reg. §1.248-1(c) / §1.195-1(b) deemed
  election (no statement required), what is excluded (syndication costs), and the record-book link
  for who actually paid formation costs.
- `evals/corporate-records.md`: new prose cases **E21** (false disinterested-approval recital) and
  **E22** (cited pricing memorandum not in the entity's folder); the validator now pins the new
  doctrine. (Superseded in this release: the suite now runs E1–E27.)

### Fixed — independent review of the governance doctrine

An adversarial corporate-law/tax review of the governance-doctrine commit returned nine findings,
all applied before release:

- the qualified-**share** route survives an interested sole director — only shares he owns or
  controls are excluded (RCW 23B.08.730(2)); the fairness route applies where no unrelated
  qualified shares exist, and no draft may recite that a safe harbor was unavailable unless the
  ownership facts establish it;
- DGCL §144 as amended in 2025 separates director/officer, controlling-stockholder, and
  going-private transactions — classify the transaction before naming a route;
- the fairness route's documentation list is evidentiary, not a set of statutory elements;
- initial bylaws may be adopted by the incorporators **or** the board (RCW 23B.02.060); the
  articles may reserve issuance authority to shareholders (RCW 23B.06.210(1)); officers hold
  offices the bylaws describe, appointed by the board or a duly authorized officer (RCW 23B.08.400);
- advancement takes the statutory **unlimited general obligation** undertaking — unsecured, and
  acceptable without regard to ability to pay (RCW 23B.08.530(2));
- classify the parties federally before applying §482, §6662, or §267: a payment between an owner
  and its own disregarded entity is generally not a transaction between separate taxpayers, and
  neither an agreement nor an invoice makes one;
- Reg. §1.6662-6(d) documentation supports a reasonable-cause defense to the §6662(e)
  net-§482-adjustment penalties — it does not validate the price, create a deduction, or make a
  penalty impossible; services-cost-method use also needs a books-and-records statement of intent;
- "state tax follows the invoice" is replaced by per-jurisdiction classification, nexus, base,
  apportionment, and sourcing analysis, and §267(a)(2) is stated with its predicates;
- the lifecycle value stays `NOT_FOUND` — the only one the schema allows — with a stated search
  scope, and a counterparty-only copy is an internal record-control gap, not a filing defect;
- §248/§195: the deduction/amortization treatment is the **deemed default**; it is the choice to
  capitalize that requires a timely return. Founder-paid formation costs get contribution and
  constructive-payment analysis; abandoned issuance costs go to §165;
- the prose-eval gate is now labelled structure-only — it checks that each case states a mandatory
  result, and does not verify that the result is legally correct.

## [0.6.0] (2026-08-29)

The release that makes this marketplace a two-plugin repository. The marketplace version moves to
`0.6.0`; the plugins version independently from here on, and `craftsman` stays at `0.5.0` because
nothing in it changed. `taxcraft` ships its first release at `0.1.0`.

### Added

- **A dependency preflight for `taxcraft`, and one place that documents it.** The skill needs
  poppler (every PDF is read through `pdftotext`, never by eye) and two Python packages for the
  `evals/` validators. Claude Code installs a plugin's Node dependencies automatically and has no
  pip equivalent, so a fresh install is normally missing all three — and the skill documented the
  fix in three places that could drift apart. `skills/tax/dependencies.md` is now the SSOT: a
  per-layer detection and repair matrix covering plugin-install integrity, the runtime, poppler,
  the validator packages, and the optional fallback rungs (`ocrmypdf`, `bean-check`, `pdfplumber`).
  `skills/tax/tools/dep-check/dep_check.py` is the one-shot preflight that checks every layer and
  prints the platform-correct fix command; it exits 1 on a missing required dependency and never
  installs anything itself. `SKILL.md`, `parsing.md`, and the plugin README now defer to it instead
  of carrying their own copies of the install commands.

  The rule the preflight exists to enforce: propose, never install silently — and **if the user
  declines, stop the task that needed it.** `evals/validate_rules.py` exits 2 on expired tax data,
  so a gate that could not run is not a gate that passed, and stale rules produce confidently wrong
  numbers. No lower-fidelity substitute is permitted either; in particular there is no
  `Read`-on-PDF fallback when poppler is absent.
- **`evals/test_no_skill_writes.py`** — runs the whole eval suite a second time against a read-only
  copy of the skill. An installed plugin is read-only for most users, so anything that writes into
  its own skill directory is a latent failure that only shows up after distribution.


- **`taxcraft` (v0.1.0), a second plugin in this marketplace** — US tax and accounting workpapers,
  unrelated to auditing code. One skill (`tax`) covering 1040 / 1065 / 1120-S / 1120, disregarded
  SMLLCs, quarterly closes and estimates, carryforward and basis tracking, and corporate governance
  records. It does not file returns and it is not tax advice. Named `taxcraft` after checking
  collisions: `tax-pro` clashes with the IRS's own "Tax Pro Account" service and the industry's
  generic `-Pro` suffix; `craft-tax` reads as a Craft CMS plugin and would imply an eleventh
  craftsman audit domain; `taxbench` is taken twice. The marketplace description was widened to
  cover both plugins, and `README.md` gained an "Also in this marketplace" section.
  Three changes were needed to make the skill work as a distributed plugin rather than a
  workspace-local one: the eval harness derived the user's tax workspace from the skill's own
  install path (`ROOT.parents[2]`), which is wrong once the skill lives under `~/.claude/plugins/`
  — it now uses the working directory, overridable with `TAX_WORKSPACE`; a dozen docs and
  templates that pointed readers at `.claude/skills/tax/…` now use skill-relative wording; and one
  real client entity name left in a code comment was scrubbed.
- **`PRIVACY.md`** — the data-handling facts that were only in `SECURITY.md`, restated as a
  standalone policy so the plugin-directory submission has a real Privacy policy URL to point at.
  Adds one thing `SECURITY.md` left implicit: Craftsman transmits nothing, but the agent it runs
  inside sends your code to its own provider regardless, so "Craftsman transmits nothing" is not a
  claim that your code stays on your machine. Linked from `README.md` and `SECURITY.md`.
- **`craftsman` symlink at the repository root**, pointing at `plugins/craftsman`. This is a
  compatibility shim, not part of the plugin layout. A directory-submission made on 2026-08-04 is
  still pending review, and it may have recorded `craftsman` as its "path within repository" —
  which the move to `plugins/craftsman` would have invalidated. The symlink makes both the old and
  new coordinates resolve, so the pending submission stays viable regardless of what was recorded.
  Remove it once that submission is resolved.

### Changed

- **The tools layer no longer assumes the skill lives inside the tax workspace.** `workspace-doctor`
  and the surrounding tooling resolved paths against the skill's own location, which is wrong once
  the skill is installed under `~/.claude/plugins/`. Workspace paths now key off `$TAX_WORKSPACE`,
  falling back to the working directory; skill-owned files resolve through `CLAUDE_PLUGIN_ROOT`.
- **`scripts/check-invariants.mjs` now covers `taxcraft`** — both manifests parse, the three
  version fields agree, every marketplace `source` path exists, the `tax` description fits the
  length budget, and all 38 concrete router-table paths in `SKILL.md` resolve.
- **The reference-pointer checker is scoped by markdown block, not by a character window.** The old
  heuristic measured proximity in characters, which produced false negatives when a pointer sat
  near an unrelated skill's name. Pointers must now be syntactically attached to the skill that
  qualifies them. Three specific gaps closed, each pinned by a fixture — the checker self-tests
  against 11 fixtures before it validates anything.
- **`validate_corporate_records.py` is back in CI.** Its fixture loop needed `entities/test-corp/**`
  files that no clean checkout has. It now builds a `TemporaryDirectory`, points `WORKSPACE` at it,
  and materializes every file the artifact cites — the pattern
  `run_generic_specialist_fixtures()` already used.
- **Rewrote the three manifest descriptions.** Dropped the "Written by a software engineer of 25
  years, including at Microsoft and Amazon" sentence. It was authority-by-assertion in a product
  whose own non-negotiables are "plain-language findings, consequence before jargon" and "evidence
  over assumption, go look" — and "including at" was ungrammatical besides. Ex-FAANG is also close
  to inert as a differentiator in a directory of 2,282 plugins, where `A full worked example is
  included` does more work because a skeptic can verify it. The credential stays on the README,
  where a reader has already opted in, rephrased so it explains the standard rather than just
  asserting it. Characters reinvested in the searchable opener and the scope disclaimers.
- **Reworked plugin keywords.** The old list was half internal structure (`ux`, `frontend`,
  `backend`, `infra`, `lint`) and carried a bare `ai` tag that reads as "this is an AI plugin"
  rather than "this audits your LLM integration". Replaced with tags describing the situation a
  searcher is actually in: `vibe-coding`, `lovable`, `replit`, `bolt`, `v0`, `ai-generated-code`,
  `code-audit`, `llm-integration`, `prompt-injection`, `multi-tenant`.

  Scope note, so nobody re-litigates this later: keywords do **not** reach the Anthropic community
  directory. Zero of its 2,282 catalog entries carry a `keywords` field — the ingestion strips it,
  confirmed against a plugin whose own manifest declares keywords. The catalog keeps `name`,
  `description`, `source`, `homepage`, and sometimes `category`. This change is for the
  self-hosted marketplace, which is the install path the README documents; discovery in the
  directory rides entirely on `description`.

## [0.5.0] (2026-08-24)

### Added

- **`craft-ux` copy and decoration anti-slop catalog.** A new "Copy & Decoration Tells" section
  in `anti-patterns.md`, scoped to landing/portfolio/marketing surfaces: an em-dash ban, an
  eyebrow-count formula (greppable), ~25 production-tested tells (section-number eyebrows,
  scroll cues, fake version footers, decorative status dots), and a premium-consumer
  beige+brass palette tell with grep seeds. `composition.md` gains hero-discipline hard numbers,
  CTA intent/wrap/contrast rules, and layout rhythm caps (zigzag, marquee, split-header, bento
  cell count). `layer-5-motion.md` gains a Forbidden Animation Patterns section (the
  `window.addEventListener('scroll')` ban, GSAP `start: "top top"` pinning). Reference material
  informed by the current upstream `taste-skill`, re-scoped from its absolute-ban voice into
  craft-ux's flag-with-override-path disposition.
- **`craft-ux/references/motion/fluid-gestures.md`** — momentum physics for gesture-driven
  surfaces (sheets, drag, swipe, carousels): velocity handoff, exponential-decay momentum
  projection, rubberbanding, interruptible-spring principles (animate from the presentation
  value, blend velocity on reversal, decompose X/Y springs), Apple-style damping/response
  values, a gesture feel checklist, and material/vibrancy rules — scoped away from plain
  dashboards. Portions adapted from `emilkowalski/skill` (MIT; see `THIRD_PARTY_NOTICES.md`),
  which also prompted a correction to `emil-craft.md`'s Framer Motion hardware-acceleration
  claim to match current upstream docs.
- **`craft-ux/references/starter-kits.md`** — 19 vetted Google Fonts pairings (15 by use case +
  4 SaaS-landing Persuade-mode variants) and 15 palettes in this skill's token roles, every pair
  WCAG-verified (`scripts/verify-palettes.py`, CI-gateable). A mandatory variation protocol
  prevents deterministic "always the same pairing" generation: pairings and palettes are
  independent axes (285 combinations), rotation is required, and brief adjectives override the
  category default. Font/palette research informed by `ui-ux-pro-max` (MIT; see
  `THIRD_PARTY_NOTICES.md`); all values independently re-curated against craft-ux's own bans.
- **`THIRD_PARTY_NOTICES.md`** — MIT notices for the two upstream sources above.
- **Operational readiness in `craft-observability`.** A new `references/operational-readiness.md`
  covers the layer between "the service is instrumented" and "a human can operate it": naming the
  core business transaction and instrumenting its lifecycle, detecting stuck work and terminal
  states whose promised artifact never appeared, committing ops queries as a file rather than
  prose, separating expected business failures from system failures so customer mistakes don't
  bury real bugs in the error tracker, the on-call contract and a five-minute "is it broken?" tree,
  an acceptance drill (success, system failure, business failure, stuck detection, alert delivered),
  and measuring readiness from a source of truth with verified history instead of a currently-green
  check. Six matching audit-checklist items, maturity-aware rather than one-size-fits-all: the
  transaction, stuck-work, and delivery checks apply from day one, while team-shaped requirements
  (a backup operator, an ack convention, an escalation path) are gated on a second person actually
  being able to respond — so a solo pre-launch builder is not handed a pager rotation.
- **Cross-references for the new layer.** `grafana.md` now prefers a deep-link panel over a graph
  known to return no data; `slo-alerts.md` requires retained history behind the SLO window and
  points service-level on-call facts at one place; craft-audit's `recommended-stack.md` gains a
  Tier-1 row for "no way to see whether the core transaction finished".
- **`craft-audit/references/synthesis.md`** — the full step-7 synthesis protocol: findings-file
  validation, the by-hand fallback checklist, path binding, the remediation closure check, dedup,
  and ranking. Extracted from `SKILL.md` rather than newly written.
- **`craft-audit/references/delegation.md`** — the ≤3/>3 `(scope, domain)` threshold, the context
  budget split between orchestrator and subagent, subagent prompt requirements, and the
  write-capability fallback. Also extracted from `SKILL.md`.

### Changed

- **Skill trigger descriptions trimmed 28%** (11,377 → 8,122 characters across the twelve skills).
  Claude Code's skill listing has a character budget of roughly 1% of the context window, shared
  with every other skill the user has installed; on overflow it drops descriptions starting with
  the least-invoked skills, which would strip the trigger keywords from exactly the domain skills
  that rely on ambient matching. Trigger phrasing is preserved and front-loaded; the cross-domain
  boundary arbitration that used to live in the descriptions moved into a new `## Scope boundaries`
  section in the body of `craft-ai`, `craft-backend`, `craft-frontend`, `craft-infra`,
  `craft-security`, and `craft-testing`.
- **`craft-audit/SKILL.md` reduced from 3,941 to ~3,000 words**, back under the router-skill
  ceiling, by extracting the two references above rather than cutting guidance.
- **`drafts/` moved from `craftsman/drafts/` to the repository root**, so the incubator is no
  longer part of the installed plugin payload. It was already excluded from skill loading; now it
  is excluded from what ships.

### Fixed

- **Helper scripts are now addressed through `${CLAUDE_PLUGIN_ROOT}`.** `craft-audit` and
  `craft-lint` previously told the agent to run their `.mjs` helpers at a literal
  `/absolute/path/to/craftsman/...` placeholder. Once the plugin is installed it lives outside the
  audited project, so that path had to be guessed. Four call sites fixed, across both `SKILL.md`
  files and `craft-audit/references/workspace.md`.

## [0.4.0] (2026-08-10)

Released without a changelog entry at the time; see the release notes for `v0.4.0` and commit
`2a29f21` (audit workflow hardening, install documentation, craft-ux supply-chain fix).

## [0.3.2] (2026-08-05)

### Security

- **Hardened public-repository controls.** CI actions are pinned to full immutable SHAs and
  Dependabot now tracks GitHub Actions updates. Published releases and `v*` tags are protected;
  private vulnerability reporting, Dependabot alerts and updates, malware alerts, grouped security
  updates, secret push protection, and CodeQL default setup are enabled in GitHub.

## [0.3.1] (2026-08-05)

### Added

- **Marketplace discovery metadata.** Claude marketplace metadata now carries a release version
  and development category, while the public GitHub listing presents Craftsman as a Claude Code
  and Codex plugin rather than a Claude-only tool.
- **Maintainer-gated open-source governance.** Contributions now have an explicit fork-and-PR
  policy, automatic sole-maintainer ownership assignment, a Contributor Covenant Code of Conduct,
  and a public Discussions space for open-ended feedback.
- **Native Codex presentation mark.** The Codex manifest now provides a lightweight local SVG for
  its composer icon and plugin logo. The GitHub README includes a clearly labelled visual preview
  of the real worked-example report shape.
- **Lint-audit CLI regression check.** CI now proves the helper's help and invalid-path flows do not
  create a `.craftsman/` workspace.

### Fixed

- **Verified Codex installation documentation.** Both READMEs now document the native marketplace
  install flow alongside Claude Code rather than describing Codex as unverified.
- **Unsafe lint-audit argument handling.** `eslint-rule-audit.mjs` validates the positional root
  before creating output and treats `--help` as a non-mutating help request.

## [0.3.0] (2026-08-03)

The response to the first detailed field report from a live production audit: a nine-domain,
107-finding run against a real revenue-carrying app. Every change here closes a gap that run
actually hit.

### Added

- **Shipping-target check in discovery.** A run from a branch behind the default branch reported
  already-shipped fixes as missing. `craft-audit` now compares `HEAD` against the default remote
  branch (or a project-declared deploy branch/commit) before reading any code, and stops to ask
  which tree to audit when behind or diverged. No remote at all is common and not an error. It's
  recorded as "shipping target unknown," and the audit proceeds against the working checkout.
- **Subagent write precondition and the fenced-block fallback contract.** The subagent prompt now
  states outright that the worker must write its own `findings.md` and confirm it did. When a
  harness policy blocks that, the worker instead returns the complete file as one fenced code
  block and nothing else, and the orchestrator persists it verbatim before running validation.
  Transport corruption (HTML entities, truncation) is never patched over with a normalizer:
  a persisted file that fails validation gets re-prompted, not repaired.
- **`scripts/validate-findings.mjs`**, a deterministic implementation of the six-check mechanical
  validation checklist already documented in `workspace.md`. It's now the preferred way to run
  that checklist. Hand-checking remains the documented fallback, which makes "a file that fails
  any check is a blocker" an enforceable rule instead of an aspiration.
- **Optional `Confidence` field** (`verified | inferred | unverified-from-repo`) on a finding,
  appended after `Last-checked`. Absence means `verified`, so every existing `findings.md` stays
  valid unchanged. `unverified-from-repo` covers claims that depend on something outside the repo
  (dashboard config, branch protection, secrets) and must describe the repo gap plus the human
  check needed, without asserting the external condition is true.
- **Semantic cross-domain rollup fallback.** The exact `(scope, class, resource)` key rollup
  produced zero groups on the real 107-finding run even though genuine duplicates existed:
  independent domain passes invent different `class`/`resource` vocabulary for the same defect on
  a first run. A mandatory second pass now groups by what a finding actually cites (file:line,
  route, table, env key) instead of by string match.
- **Repo-native context docs** (`CLAUDE.md`, `AGENTS.md`, `README.md`, applicable `docs/`) added to
  the discovery evidence list, with an explicit re-verify caveat: cite the doc, then check the
  code, never treat it as ground truth on its own. "Documentation contradicts code" is now a
  finding class in its own right.
- **Gated surfaces in `craft-fix`.** Optional, no setup required: a project can declare surfaces
  (payment webhooks, billing math, etc.) via `.craftsman/gated-surfaces.md`, its own
  `CLAUDE.md`/`AGENTS.md`/README, or the user saying so in chat. A finding touching a declared
  surface is never auto-fixed, regardless of severity or how small the diff looks. It's routed to
  a human-approval bucket instead.

### Changed

- The step-5 false-negative guard (verify with grep before accepting a reviewer's "this is
  missing" claim) now has its converse stated: the tree being grepped has to be the tree that
  ships, per the new shipping-target check. A stale checkout makes already-shipped fixes look
  missing just as easily as a bad grep makes a real gap look present.

### Notes

Deliberately declined, and why:

- **A controlled `class` vocabulary per domain.** Would fight context bloat and overfit to one
  large repo; the semantic rollup fallback solves the actual problem (missed duplicates) without
  forcing every future domain into a fixed taxonomy.
- **Mandating `resource` be a repo-relative file path.** Would break re-run matching for findings
  about DB tables and env vars, which aren't files. `resource` keeps meaning "the canonical thing
  it's about," with a file path preferred only where a single file is genuinely the subject.
- **A required `fix-risk` field on every finding.** The plan-first gate and the new gated-surfaces
  gate already cover the dangerous cases; adding a required field to a schema that four other
  things parse wasn't worth it for the marginal cases left over.
- **Making a git remote a hard prerequisite for the shipping-target check.** Local-only projects
  are valid audit targets; no remote is handled as "unknown," not as a blocker.

## [0.2.1] (2026-08-03)

Corrections found after the 0.2.0 tag was cut, so this release brings the published version in
line with what the project actually does.

### Added

- **README Quickstart and Compatibility sections.** Walks a first-time reader from install through
  the trigger phrase, the `.craftsman/` workspace files that appear, and acting on findings via
  `craft-fix`.

### Changed

- README/ROADMAP/CHANGELOG/manifest wording no longer describes the re-run protocol as a compiled
  "fingerprint diff" or readiness grades as "mechanical." Both are agent-executed against a
  written rule, and the text now says so.
- Corrected the worked example's domain count in two places (nine of ten, not four).
- Compatibility section no longer converts an absent minimum Claude Code version into a positive
  guarantee.
- Stale `*-craft` naming corrected to `craft-*` in `ROADMAP.md`, `CONTRIBUTING.md`, and
  `craft-audit/SKILL.md`.

### Fixed

- A re-run whose domain pass didn't execute could mark prior open findings `fixed`, inverting the
  project's "not seen ≠ fixed" rule and contradicting `rerun.md` (which is authoritative). Both
  sites in `workspace.md` now require the pass to have actually run and re-checked the resource.
- The cross-skill pointer check in `scripts/check-invariants.mjs` still matched the pre-rename
  `<name>-craft` form, so it had been passing vacuously since the rename: it validated nothing.
  Corrected to `craft-*`; it now exercises the real pointers.

### Removed

- `displayName` from the plugin manifest, since it imposed a Claude Code v2.1.143 floor for a
  purely cosmetic field.

## [0.2.0] (2026-08-03, public launch)

Dev work (craft-ai graduation) landed 2026-07-15; the version was held back from public installs
until pre-ship cleanup finished, so this entry carries the public-release date.

### Added

- **Graduated `craft-ai`** (10th domain skill) from `drafts/` into `skills/`. LLM-integration
  surface: prompt-injection, key/spend safety, PII-to-model APIs, reliability/evals. Four
  references (`prompt-injection`, `keys-and-spend`, `data-privacy`, `reliability-evals`). Wired
  into craft-audit (discovery applicability, domain code `AI`, load list, emission HEADING_RE) and
  `scripts/check-invariants.mjs`. Worked example marks craft-ai N-A for Invoicely (no LLM surface).

### Changed

- Domain count: nine → ten. Skill total: craft-audit + craft-fix + 10 domains = 12 skills.
- Plugin/marketplace descriptions and README skill table updated for craft-ai.
- `drafts/` empty (no domains currently incubating).

### Removed

- Pre-ship cleanup: internal dogfooding feedback folder and its marker blocks stripped from the
  skills, README, ROADMAP, CLAUDE.md, and `.gitignore` ahead of the public launch pass.

### Released

- **Public launch.** Marketplace and plugin opened to external installs at this version.

## [0.1.0] (2026-07-15)

Dogfooding milestone: fix companion, `craft-` rename, findings emission contract, CI grammar
gates, full nine-domain worked example. Internal dogfooding instrumentation remains by design.

### Breaking (for pre-release installs)

- Renamed all skills to the `craft-` prefix (craftsman-audit → craft-audit, craftsman-fix →
  craft-fix, X-craft → craft-X) for consistent naming and slash-menu grouping.

### Added

- **New skill: `craft-fix`.** An action companion (not a domain; the count stays 9) that drives
  fixes against an existing `craft-audit` workspace: parses a finding ID / domain / "top 5 off the
  climb sequence" invocation, re-verifies each pick's fingerprint against current code, gets explicit
  user approval before editing, gates 🔴 auth/migration/data-handling fixes behind a written plan,
  batches by surface (disjoint file ownership for parallel subagents), and appends a `Fix-attempt`
  annotation without ever setting a finding's status to `fixed` itself. Only a `craft-audit`
  re-run's re-observation of the finding can, per "not seen ≠ fixed". `scripts/check-invariants.mjs` exempts
  `craft-fix` from the domain `## Audit checklist (for craft-audit)` heading requirement.
- **Findings emission contract:** canonical `findings.md` heading grammar + mechanical validation
  before synthesis (path-bound scope/domain, re-prompt on fail, no normalizer). Restated in all
  nine domain skills. Library-monorepo scoping in discovery/workspace.
- **Invariant checks (f):** `scripts/check-invariants.mjs` validates worked-example findings against
  the emission grammar (fail-closed on non-canonical headings, including indent/blockquote/list/
  Setext), requires domain skills to restate the format, and ships regression fixtures.
- **Worked example:** full Invoicely Tier-1 snapshot, all 9 domains under
  `craftsman/examples/craftsman-output/`.
- **Intake cadence (P4):** documented drain protocol in ROADMAP (still temporary pre-ship).
- Packaging and repo-hygiene: `CONTRIBUTING.md`, `SECURITY.md`, issue templates, CI workflow.
- `craft-ai` incubating in `drafts/`, not loaded; graduates per `drafts/README.md`.

### Changed

- Compliance/incident/cost/load/email checks folded into existing domain checklists rather than
  standing up new domains (see `ROADMAP.md` for graduation triggers).
- Root `README.md` rewritten for an external reader.
- `marketplace.json` / plugin descriptions reworded for product framing; `homepage` + `license`.
- `craftsman/README.md`: real marketplace install flow; Codex/Cursor paths labeled experimental.
- `ROADMAP.md` "Removal map" completed for pre-ship instrumentation sites.

### Fixed

- Stale skill count in `CLAUDE.md` (now 10 skills / 9 domains + craft-fix action skill).
- Findings format drift from dogfooding: domain subagents inventing alternate heading shapes.

### Chore

- `.gitignore`: `.remember/` (session memory) excluded from `git add -A`.

## [0.0.1] (baseline dogfooding state)

Baseline state of the plugin as of this changelog's introduction:

- **10 skills**: `craft-audit` (orchestrator) + 9 domain skills (`craft-ux`, `craft-frontend`,
  `craft-backend`, `craft-db`, `craft-security`, `craft-infra`, `craft-observability`,
  `craft-testing`, `craft-lint`), each with a complete `references/*.md` set. (Pre-rename names
  used the older `*-craft` / `craftsman-*` forms.)
- **Orchestrator with a durable workspace.** `craft-audit` discovers project shape, decides
  which domains apply, and plans/tracks a whole-project audit in a `.craftsman/` workspace inside
  the audited project: discovery, applicability, a master tracker with per-domain readiness
  grades, and per-scope/per-domain findings.
- **Re-run protocol.** Fingerprint-based diffing across audit runs: staleness detection against the
  current commit, re-observation and classification of prior findings (open / fixed / regressed /
  new), and a "not seen ≠ fixed" rule that prevents a skipped check from masquerading as a
  resolved one.
- **Worked example.** A complete synthetic `.craftsman/` audit tree ships under
  `craftsman/examples/craftsman-output/` as a teaching artifact (four domains in the original
  snapshot; expanded to nine in 0.1.0).
- **Pre-ship dogfooding instrumentation still present** (by design, not yet removed): an internal
  feedback folder and marker blocks embedded in each skill, both stripped before public launch.
