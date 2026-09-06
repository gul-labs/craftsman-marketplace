# Claim Verification — auditing what the project *says* against what it *does*

Every project ships claims: a privacy policy, a terms page, a README, a pricing table, the success
message an endpoint returns. Those claims are written once by a human and then left alone while the
code underneath them keeps moving. Nobody diffs them. That's the gap this file audits.

Detecting the mismatch is mechanical. "Your privacy policy says analytics respects Do Not Track; the
analytics init sets no such option" is a **discrepancy you can prove by citing two files**. Detecting
it needs no statute and no lawyer. *Resolving* it may well need both — which is why this file is
strict about handing the resolution back to whoever owns the document.

> **Pairs with:** `prioritization.md` for the finding voice. Domain skills own the underlying
> surfaces — `craft-security` → `data-rights.md` for PII/deletion mechanics, `craft-frontend` for
> consent gating, `craft-ai` for generation-time constraints. This file owns the **method** of
> comparing a declaration to an implementation, which belongs to no single domain.

---

## Contents

- [Why presence checks are near-worthless](#why-presence-checks-are-near-worthless)
- [Classify the claim before you try to verify it](#classify-the-claim-before-you-try-to-verify-it)
- [The authority boundary — what you may and may not conclude](#the-authority-boundary--what-you-may-and-may-not-conclude)
- [Where declarations live](#where-declarations-live)
- [The high-yield checks](#the-high-yield-checks)
- [Regulatory framing — gate the label, never the contradiction](#regulatory-framing--gate-the-label-never-the-contradiction)
- [Turning a claim check into a CI gate](#turning-a-claim-check-into-a-ci-gate)
- [Deliberate decisions that look like defects](#deliberate-decisions-that-look-like-defects)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Why presence checks are near-worthless

The common checklist asks: *is there a privacy policy page? is there a cookie banner? is there a
terms page?* Those are one-line greps, and a project passes them with a placeholder.

The failure mode in the wild is not an absent policy. It's a **good policy that drifted**. A team
writes a careful, substantive privacy policy, then six months of feature work moves the code
underneath it, and nothing tells anyone the document is now false.

So invert the check. Don't ask whether the document exists — **read what it promises, then go verify
what you actually can.**

| Presence check (low value) | Claim check (the finding) |
| --- | --- |
| Privacy policy page exists | Policy says "we don't use third-party advertising cookies" — three ad SDKs are initialized |
| Cookie banner exists | Policy describes consent-gated analytics; the tracker fires before the banner is answered |
| Terms page exists | Terms promise 30-day deletion; no job enforces it and nothing alerts if the cascade fails |
| Has a data-export endpoint | Export omits two tables the policy's "Data We Collect" section lists |

---

## Classify the claim before you try to verify it

Not every claim is checkable from a repo, and pretending otherwise produces confident nonsense.
Sort each claim first, and **only pursue the first two categories**:

| Category | Example | What you can do |
| --- | --- | --- |
| **Source-verifiable** | "We don't set advertising cookies"; "analytics respects DNT"; "deletion cascades to related records" | Compare against code and config; cite both sides |
| **Runtime-verifiable** | "No tracking before consent"; "export includes all your data" | Observe actual behaviour — cold load, network panel, run the endpoint |
| **Operational-evidence-required** | "99.9% uptime"; "backups every 6 hours"; "we respond to requests in 30 days" | Out of scope from source alone. Note that the claim exists and needs operational evidence; do not grade it |
| **Not assessable here** | "SOC 2 certified"; "GDPR compliant"; "reviewed by counsel" | Record as unverifiable from the repo. Never affirm and never deny |

Writing "no evidence found in the repo" for a category-3 or category-4 claim is not a finding — it's
noise. Say nothing, or note it once as a scope limit.

---

## The authority boundary — what you may and may not conclude

Read `SKILL.md` → "Who this is for": the persona takes your output as authoritative. A confident
"✅ GDPR compliant" from a code read manufactures false safety on a liability question, which is
strictly worse than saying nothing. The boundary below is what keeps this method honest.

| You may verify (engineering fact) | You must NOT conclude (legal judgment) |
| --- | --- |
| What the code does — cookies set, SDKs initialized, PII stored, deletion cascades | Whether that satisfies GDPR, CCPA, ADA, or any statute |
| That a stated claim contradicts observed behaviour | Whether the claim was legally required in the first place |
| That a tracker fires before consent is answered | Whether the consent obtained was validly obtained |
| That a retention constant reads 90 days | Whether 90 days is a lawful retention period |

Write findings as **contradictions**, not verdicts:

- ✅ "Your privacy policy §10 says X. `instrumentation-client.ts:64` does Y. These disagree."
- ❌ "You are in violation of GDPR Article 7."

**Report the discrepancy; do not choose the remedy.** Every mismatch has at least two fixes — change
the code, or change the document — and picking between them is a decision about what the business
intends to promise. That is the document owner's call, not yours, even when one option looks
obviously cheaper. State both paths neutrally and stop:

> "These disagree. Either the analytics config needs to change to match §10, or §10 needs to change
> to match the config — that's a call for whoever owns the policy, and it may need legal input."

That hand-off is a complete finding. Inventing the answer is not. This rule applies everywhere below,
including the worked examples — if a passage ever seems to tell you which side to change, this
paragraph wins.

---

## Where declarations live

Look in all of these; the first two are where audits usually stop.

1. **Legal pages** — privacy policy, terms, cookie policy, DPA, acceptable-use. Often a
   long hardcoded component (`privacy/page.tsx`), sometimes MDX or CMS content.
2. **Marketing surface** — landing page, pricing table, feature grid, comparison tables. "Unlimited",
   "SOC 2 compliant", "end-to-end encrypted", "99.9% uptime" are all claims (mostly categories 3–4).
3. **User-facing runtime strings** — the most-missed category. The message an endpoint returns after
   a destructive action is a claim about what just happened. See below.
4. **README / docs** — setup promises, architecture diagrams, "we use X for Y", security docs.
5. **Config-as-declaration** — a subprocessor table, a `SECURITY.md` disclosure window, an SLA in a
   status page config.

---

## The high-yield checks

### 1. Policy claims vs SDK initialization

The highest-yield check in this file. Analytics, error-tracking, and session-recording SDKs are
configured in one or two init blocks; the policy describes that configuration in prose. Compare them
literal by literal.

Grep the init block for the options the policy names, then verify each:

- Do-Not-Track / consent options — **whether the option is even set**, not whether it's `true`
- session-recording enable/disable and sample rates
- text/media masking
- cookie vs `localStorage` persistence, cross-subdomain behaviour
- anonymous vs identified profile capture
- autocapture on/off

**Check the behaviour of the version the project actually resolves — not your memory of the docs.**
Consult the lockfile and the resolved package (its types, its docs, or its source where available;
`node_modules` when there is one — it may be absent under PnP or a partial install). Two traps worth
knowing:

- **The option is opt-in and absent.** "Absent" is not "safe default." If the policy says the
  behaviour is *configured*, an absent option contradicts that regardless of the library default.
- **The option is legacy in the resolved version.** It may still work at runtime while no longer
  being a declared property on the published config type — in which case setting it may not
  typecheck cleanly against that type, and the library has usually moved to a newer consent API.
  Report the constraint; don't prescribe which way the team resolves it.

That second case is the difference between a finding the team can act on and one they'll bounce.

### 2. Subprocessor list vs third parties in the code

The policy's subprocessor table names third parties that receive user data. Compare it against the
SDKs actually initialized and the outbound destinations in the CSP.

**State this one carefully.** An initialized SDK does not prove personal data reaches that vendor,
and a CSP entry expresses a *permitted* destination, not observed traffic — so neither is proof of a
subprocessor relationship on its own. Use them as **leads**, then trace what is actually sent before
asserting anything. Distinguish "an SDK is present", "a vendor receives data", and "a vendor is a
subprocessor" — the last is partly a contractual question you cannot settle from source.

Both directions are worth surfacing: a vendor that appears to receive data and isn't listed, and a
listed vendor with no trace in the code.

### 3. Success messages vs what the code actually did

**A bug class almost nobody audits.** After a destructive or irreversible action, the string you
return is a factual claim about state. Trace the handler and check the message is true.

The recurring lie: *"Your account and all associated data have been permanently deleted"* returned by
a handler that soft-deletes, defers to an async webhook, anonymizes some rows via `ON DELETE SET
NULL`, and leaves org-owned content untouched.

Check the message for three properties rather than drafting replacement copy (wording here is
frequently legal-reviewed — flag the mismatch and let its owner rewrite it):

- Does it distinguish what completed **now** from what is **promised later**?
- Does it name what **survives** the action?
- Is any absolute in it ("all", "permanently", "immediately") actually true of the code path?

When an endpoint already gets this right, **say so and flag the wording as load-bearing** — that
precision is easily destroyed by a routine copy edit.

### 4. Promised retention vs enforced retention

Where a document states a retention window, look for the mechanism that enforces it and the alert
that fires when it fails.

Retention is *often* pinned to a constant, which makes it one of the more checkable promises — but
don't assume it lives in one. It may be a database TTL, an object-storage lifecycle rule, a
provider-side setting, or spread across an async pipeline, and legal holds legitimately suspend it.
Trace the actual mechanism before concluding a promise is unenforced; "I found no constant" is not
the same as "nothing enforces this."

### 5. Consent gating vs tracking that actually fires

The test is not "does a banner exist." It's: **load the app in a clean profile and watch the network
panel before touching anything.**

Judge what you see against the project's own stated position: pre-consent traffic is a finding when
the policy or banner claims consent gating, or when the tracker is plainly non-essential. Strictly
necessary services (auth, security, error reporting in some postures) are a different matter, and
whether a given tracker requires prior consent is a legal question you don't answer — describe what
fires and when, and let the document owner reconcile it.

Treat these as **independent axes** — teams routinely get one right and the other wrong, and a
checklist that collapses them into one line will miss it:

- *tracking privacy* (masking, sampling, recording disabled, anonymous profiles)
- *consent gating* (does anything fire before the user answers)

Getting masking and sample rates right is real work; it says nothing about whether consent gates the
capture.

### 6. Declared architecture vs actual imports

READMEs claim boundaries — "the AI layer never touches the publish layer", "no direct DB access from
the web app". Those are greppable, so check them directly rather than inferring. An unenforced
boundary is a **risk worth noting**, not evidence of a violation; report an actual crossing only when
you can cite the import that crosses it.

---

## Regulatory framing — gate the label, never the contradiction

Two different things get confused here, and only one of them may be filtered.

**Never suppress a factual contradiction.** If the policy says X and the code does Y, that finding
stands on its own merits — it is a defect in the project's own documentation regardless of which laws
apply, and no jurisdiction analysis is required to report it.

**Do gate the regulatory *label*.** Attaching "this is a GDPR problem" to a finding is a legal
characterization, and a wrong one is both noise and a credibility risk. Before framing a finding in
terms of a specific regime, check whether anything in the repo evidences that regime's relevance —
locales, currencies, region config, an EU subprocessor, an age gate, a public-sector surface.

When that evidence is absent, **still report the contradiction — just report it plainly**, without
the regime name. "Your policy says X, the code does Y" needs no statute attached to be actionable.

And treat these signals as weak. The presence of US users does not establish that CCPA/CPRA applies
(that regime has revenue and volume thresholds); an EU locale does not settle GDPR's scope. They tell
you a regime is *plausibly* in play, which is enough to justify mentioning it as context and never
enough to assert it applies. When jurisdiction genuinely changes what's worth surfacing, ask the user
once — it's cheap for them to answer and expensive for you to guess.

---

## Turning a claim check into a CI gate

A claim check that runs once is a snapshot; the drift will recur. The durable fix is a **structural
test** — a plain unit test that reads both artifacts and asserts they agree. It needs no new
infrastructure:

1. Read the declaration (a string in the policy component, a constant, a doc table).
2. Read the implementation (the init literal, the schema, the registered job).
3. Assert they agree.
4. Give every legitimate deviation an **allowlist entry with a written justification** — one line
   per entry, reviewed like code.

That allowlist is the load-bearing part. It converts "we forgot" into "someone argued for this in
writing at review time", and it's what makes the gate survive contact with a deadline.

**Be clear about what this buys.** A structural test proves the *declaration and the configuration
agree*; it does not prove the behaviour happens. A test asserting `RETENTION_DAYS === 30` and that a
cleanup job is registered says nothing about whether the job successfully deletes anything. Pair the
consistency check with a behavioural test — aged fixture data and a real job invocation — wherever
the promise actually matters.

**Recommend this pattern by pointing at the team's own sibling code whenever they already use it
somewhere** — a structural test enforcing tenant scoping, a token-usage scanner, an import-boundary
test. "You already do exactly this in `tests/structural/…`; apply it to your policy claims" lands far
better than an abstract proposal, and it satisfies "prefer working sibling code over abstract
best-practice."

---

## Deliberate decisions that look like defects

Before writing the finding, look for a comment or ADR explaining the choice. Flagging a documented
decision as a bug is the fastest way to lose the user's trust in the whole audit. Recurring examples:

- **Legal pages excluded from i18n in a multi-locale app.** Often deliberate: translating legal copy
  is a legal-review matter, not a string-table task. If there's a comment saying so, it's a decision,
  not an oversight.
- **Tenant/org rows with no soft-delete flag**, because billing webhooks and legal holds need the row
  to stay queryable.
- **No RLS**, with a named guardrail — see `craft-db` → `access-patterns.md` for how to audit that
  posture on its own terms rather than demanding RLS.
- **Duplicated module boundaries** that exist because a third-party reviewer only sees one of them.

A recorded decision is **context, not a control**. It tells you the trade-off was made deliberately,
which changes how you write the finding; it does not by itself demonstrate that the risk is handled.
The question is *"is the decision recorded, and is the control it relies on real, scoped, and
executable?"*

---

## Quick-reject checklist

Reject the finding if:

- [ ] It states a legal conclusion ("this violates GDPR") rather than a contradiction between two
      artifacts you can cite.
- [ ] It picks which side should change — code or document — instead of handing that choice back to
      the document's owner.
- [ ] It asserts a library default you did not check against the version the project resolves.
- [ ] It treats an initialized SDK or a CSP entry as proof that a vendor receives personal data.
- [ ] It's a presence check ("no privacy policy found") on a project where one exists and you simply
      didn't read it.
- [ ] It grades a claim that isn't source- or runtime-verifiable (uptime, certifications, contractual
      promises) instead of noting it as needing operational evidence.
- [ ] It attaches a regulation's name to a finding with no evidence in the repo that the regime is in
      play — or, worse, drops a real contradiction because that evidence was missing.
- [ ] It flags a decision that carries a comment or ADR explaining the trade-off, without engaging
      with that reasoning.
- [ ] It cites the claim but not the implementation, or the implementation but not the claim — a
      claim finding needs **both** `file:line` anchors or it isn't verified.
- [ ] It claims a structural test proves runtime behaviour.
