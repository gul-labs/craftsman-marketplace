# Claim Verification — auditing what the project *says* against what it *does*

Every project ships claims: a privacy policy, a terms page, a README, a pricing table, the success
message an endpoint returns. Those claims are written once by a human and then left alone while the
code underneath them keeps moving. Nobody diffs them. That's the gap this file audits.

The check that finds these is mechanical, not legal. "Your privacy policy says you respect Do Not
Track; the analytics init sets no such option" is a **factual defect you can prove from two files**
— no statute required, no jurisdiction to determine, no lawyer to consult.

> **Pairs with:** `prioritization.md` for the finding voice. Domain skills own the underlying
> surfaces — `craft-security` → `data-rights.md` for PII/deletion mechanics, `craft-frontend` for
> consent gating, `craft-ai` for generation-time constraints. This file owns the **method** of
> comparing a declaration to an implementation, which belongs to no single domain.

---

## Contents

- [Why presence checks are near-worthless](#why-presence-checks-are-near-worthless)
- [The authority boundary — what you may and may not conclude](#the-authority-boundary--what-you-may-and-may-not-conclude)
- [Where declarations live](#where-declarations-live)
- [The high-yield checks](#the-high-yield-checks)
- [Jurisdiction gating — don't emit findings that don't apply](#jurisdiction-gating--dont-emit-findings-that-dont-apply)
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
each promise against the code.** Every claim is a testable assertion or it isn't a claim worth
auditing.

| Presence check (low value) | Claim check (the finding) |
| --- | --- |
| Privacy policy page exists | Policy says "we don't use third-party advertising cookies" — three ad SDKs are initialized |
| Cookie banner exists | Banner exists, and tracking fires anyway before it's answered |
| Terms page exists | Terms promise 30-day deletion; no job enforces it and nothing alerts if the cascade fails |
| Has a data-export endpoint | Export omits two tables the policy's "Data We Collect" section lists |

---

## The authority boundary — what you may and may not conclude

**This is not optional, and it is the reason this file is safe to ship.** Read
`SKILL.md` → "Who this is for": the persona takes your output as authoritative. A confident
"✅ GDPR compliant" from a code read manufactures false safety on a liability question, which is
strictly worse than saying nothing.

| You may verify (engineering fact) | You must NOT conclude (legal judgment) |
| --- | --- |
| What the code does — cookies set, SDKs initialized, PII stored, deletion cascades | Whether that satisfies GDPR, CCPA, ADA, or any statute |
| That a stated claim contradicts observed behaviour | Whether the claim was legally required in the first place |
| That tracking fires before consent is answered | Whether the consent obtained was validly obtained |
| That a retention constant is 90 days | Whether 90 days is a lawful retention period |

Write findings as **contradictions**, not verdicts:

- ✅ "Your privacy policy §10 says X. `instrumentation-client.ts:64` does Y. One of them needs to
  change — that's a call for whoever owns the policy."
- ❌ "You are in violation of GDPR Article 7."

When a fix genuinely turns on a legal question, say so and stop: *"Which of these two is correct is
a question for whoever wrote the policy — I can only tell you they disagree."* That hand-off is a
complete, useful finding. Inventing the legal answer is not.

---

## Where declarations live

Look in all of these; the first two are where audits usually stop.

1. **Legal pages** — privacy policy, terms, cookie policy, DPA, acceptable-use. Often a
   long hardcoded component (`privacy/page.tsx`), sometimes MDX or CMS content.
2. **Marketing surface** — landing page, pricing table, feature grid, comparison tables. "Unlimited",
   "SOC 2 compliant", "end-to-end encrypted", "99.9% uptime" are all claims.
3. **User-facing runtime strings** — the most-missed category. The message an endpoint returns after
   a destructive action is a claim about what just happened. See below.
4. **README / docs** — setup promises, architecture diagrams, "we use X for Y", security docs.
5. **Config-as-declaration** — a subprocessor table, a `SECURITY.md` disclosure window, an SLA in a
   status page config.

---

## The high-yield checks

### 1. Policy claims vs SDK initialization

The single highest-yield check in this file. Analytics, error-tracking, and session-recording SDKs
are configured in one or two init blocks; the policy describes that configuration in prose. Compare
them literal by literal.

Grep the init block for the options the policy names, then verify each:

- Do-Not-Track / consent options — **whether the option is even set**, not whether it's `true`
- session-recording enable/disable and sample rates
- text/media masking (`maskAllText`, `blockAllMedia`)
- cookie vs `localStorage` persistence, cross-subdomain behaviour
- anonymous vs identified profile capture
- autocapture on/off

**Verify the library's default before calling it a defect — and verify it in the pinned version.**
"The option is absent, therefore the behaviour is off" is an assumption. Read the installed package
in `node_modules`, not your memory of the docs. Two traps, both real:

- **The option is opt-in and absent.** Absent ≠ safe default. The claim is false.
- **The option is legacy in the pinned version.** It may still work at runtime while no longer being
  a declared property on the published config type — so the naive fix ("just add the flag") would
  not typecheck, and the honest remediation is to adopt the library's current consent model *or*
  correct the policy text. Say which, and say why.

That second case is the difference between a finding the team can act on and one they'll bounce.

### 2. Subprocessor list vs actual dependencies

The policy's subprocessor table names the third parties that receive user data. Compare it against
the SDKs actually initialized and the outbound hosts in the CSP. Both directions are findings — a
service that receives data and isn't listed, and a listed service that was removed.

### 3. Success messages vs what the code actually did

**A bug class almost nobody audits.** After a destructive or irreversible action, the string you
return is a factual claim about state. Trace the handler and check the message is true.

The recurring lie: *"Your account and all associated data have been permanently deleted"* returned
by a handler that soft-deletes, defers to an async webhook, anonymizes some rows via
`ON DELETE SET NULL`, and leaves org-owned content untouched.

A truthful version distinguishes what happened *now* from what is *promised later*, and names what
survives: "deactivated," erasure within 30 days framed as a policy commitment rather than a
completed action, and an explicit note that org-owned content remains. When you find an endpoint
that already does this, **say so and flag it as load-bearing** — precise wording like that is easily
destroyed by a routine copy edit.

### 4. Promised retention vs enforced retention

Retention is the one privacy promise that's trivially testable, because it's a constant. If a
document says 30/90/180 days, there should be a scheduled job enforcing it and a test asserting the
value. Check the promise, the job, the registration, and the alert if the job fails.

### 5. Consent gating vs tracking that actually fires

The test is not "does a banner exist." It's: **load the app in a clean profile and watch the network
panel before touching anything.** Anything third-party that ships pre-consent is the finding.

Treat these as **independent axes** — teams routinely get one right and the other wrong, and a
checklist that collapses them into one line will miss it:

- *tracking privacy* (masking, sampling, recording disabled, anonymous profiles)
- *consent gating* (does anything fire before the user answers)

Getting masking and sample rates right is real work; it says nothing about whether consent gates the
capture.

### 6. Declared architecture vs actual imports

READMEs claim boundaries — "the AI layer never touches the publish layer", "no direct DB access from
the web app". Those are greppable. A claimed boundary with no enforcing test is a boundary that has
already been crossed somewhere.

---

## Jurisdiction gating — don't emit findings that don't apply

Firing a GDPR finding at a US-only B2B tool is noise, and noise costs you the user's attention on
the findings that *do* apply — a direct violation of "prioritize ruthlessly."

Before emitting any regulation-flavoured finding, gate on evidence found in the repo:

| Signal | Gate |
| --- | --- |
| EU/EEA users — locales, currency, TLDs, region config, an EU subprocessor | GDPR/ePrivacy-shaped findings |
| US users | CCPA/CPRA-shaped findings |
| `.br` / `.ca` / UK surface | LGPD / PIPEDA / UK-GDPR-shaped findings |
| Child-directed product or age gate | COPPA-shaped findings |
| EU public-sector or e-commerce surface | EAA/accessibility-statute framing |

Two rules:

- **When the gate doesn't fire, skip silently.** Do not emit "we couldn't determine whether GDPR
  applies" — an unresolvable finding is pure noise.
- **When you can't tell, ask once rather than assuming.** Jurisdiction is cheap for the user to
  answer and expensive for you to guess wrong in either direction.

Note the framing throughout: *"GDPR-shaped"*. You are gating **which contradiction is worth
surfacing**, not ruling on which law binds the user. The finding itself stays a factual
contradiction per the authority boundary above.

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

**Recommend this pattern by pointing at the team's own sibling code whenever they already use it
somewhere** — a structural test enforcing tenant scoping, a token-usage scanner, an import-boundary
test. "You already do exactly this in `tests/structural/…`; apply it to your policy claims" lands far
better than an abstract proposal, and it satisfies "prefer working sibling code over abstract
best-practice."

---

## Deliberate decisions that look like defects

Before writing the finding, look for a comment or ADR explaining the choice. Flagging a documented
decision as a bug is the fastest way to lose the user's trust in the whole audit. Recurring examples:

- **Legal pages excluded from i18n in a multi-locale app.** Usually deliberate: translating legal
  copy is a legal-review matter, not a string-table task. If there's a comment saying so, it's a
  decision, not an oversight.
- **Tenant/org rows with no soft-delete flag**, because billing webhooks and legal holds need the row
  to stay queryable.
- **No RLS**, with a named compensating control — see the "compensating control" framing in
  `craft-db`/`craft-security` rather than demanding RLS.
- **Duplicated module boundaries** that exist because a third-party reviewer only sees one of them.

The audit question is never "why isn't this the textbook approach" — it's **"is this decision
recorded, and is the compensating control real and executable?"**

---

## Quick-reject checklist

Reject the finding if:

- [ ] It states a legal conclusion ("this violates GDPR") rather than a contradiction between two
      artifacts you can cite.
- [ ] It asserts a library default you did not read in the pinned version in `node_modules`.
- [ ] It's a presence check ("no privacy policy found") on a project where one exists and you simply
      didn't read it.
- [ ] The regulation it invokes has no jurisdictional evidence anywhere in the repo.
- [ ] It flags a decision that carries a comment or ADR explaining the trade-off, without engaging
      with that reasoning.
- [ ] It cites the claim but not the implementation, or the implementation but not the claim — a
      claim finding needs **both** `file:line` anchors or it isn't verified.
- [ ] The proposed fix is "add the flag" without checking the flag is still supported in the version
      the project actually pins.
