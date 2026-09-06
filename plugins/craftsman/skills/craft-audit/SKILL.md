---
name: craft-audit
description: >-
  The front door to the craft skills — a whole-project production-readiness orchestrator that drives
  the ten per-domain craft skills (ux, frontend, backend, db, security, infra, observability,
  testing, lint, ai) instead of auditing one surface at a time. It discovers the project's shape,
  plans an audit per surface, and tracks findings in a resumable `.craftsman/` workspace.
  Use WHENEVER the user wants a whole-project assessment rather than a single-file review: "is my app
  production-ready", "take this from MVP to production", "I vibe-coded this with
  Lovable/Replit/Claude and want it enterprise-grade", or "what would a senior engineer fix here".
  Trigger even without a named surface area — the whole point is finding the applicable ones.
  Does NOT fire on single-surface requests ("how do I fix this one bug", "add a feature to this
  component") — use that domain's craft skill directly.
---

# Craftsman Audit — the production-readiness orchestrator

This is the **conductor**, not another peer domain. The ten `craft-*` skills each own one surface
(ux, frontend, backend, db, security, infra, observability, testing, lint, ai). This skill stands above them: it looks
at the whole project, decides which of those surfaces apply, plans an audit for each, routes the
actual findings to the domain skills, and keeps a durable record of what's been audited and what's
left — so a large assessment can run across multiple sessions without losing the thread.

It does **not** duplicate domain knowledge. To judge the auth layer it loads `craft-security`; the
design system, `craft-ux`; static quality gates, `craft-lint`; LLM integrations, `craft-ai`. The
orchestrator owns **discovery, applicability, planning, prioritization, and tracking** — the domain
skills own the findings. Keeping that boundary is what stops the two from drifting out of sync. Once
findings are tracked, the companion action skill `craft-fix` works through the climb sequence — this
skill audits and tracks, it does not itself change code.

## Who this is for (read this first — it sets the register)

The primary user is the **builder of a cool-but-fragile MVP**: someone who used Claude, Lovable,
Replit, or v0 to ship something that *looks* impressive and *works in the demo*, but is nowhere near
production-grade — no real error/empty/loading states, no auth worth the name, no observability, AI
"slop" patterns, data that'll corrupt under concurrency, infra that falls over at the first spike.
The secondary user is more advanced but still can't reliably hit enterprise-grade.

That persona changes how you communicate, and it is **not optional polish** — it's the job. It is
why the first three "Standing principles" below are non-negotiable rather than style advice:

- **Plain language** because the reference docs are written for you, the agent, while the findings
  are written for someone who won't recognize "CLS regression" or "IDOR" — lead with "anyone can
  open another customer's invoice by changing the number in the URL," then name it.
- **Ruthless prioritization** because handing this user 200 findings makes them freeze. Your value
  is making the climb ordered and unscary, not dumping the whole mountain.
- **Meeting the project where it is** because a "rewrite to my favorites" audit is worthless to
  someone whose stack already works.

## The `.craftsman/` workspace (durable per-project state)

All audit state lives in a `.craftsman/` folder **at the root of the project being audited** (not in
this plugin). It is the audit's memory: discovery notes, applicability call, per-area plans, the
master tracker, and findings. It must be **git-ignored in the target project** — it's working state,
not source. Create it (and its `.gitignore` entry) as the first step. Full layout, file templates,
and the date/commit stamping rules are in `references/workspace.md` — read it before writing any
file there.

## The audit loop

Run these in order. Each step writes its output into `.craftsman/` so the next session can resume.

0. **Re-run pre-flight (if `.craftsman/` already exists).** A second audit is a *diff*, not a rewrite.
   Before touching anything, check for an existing `.craftsman/` at the project root. If one exists, run
   the staleness check (compare each artifact's stamp to current `HEAD`, regenerate only what actually
   changed) and switch into finding-by-finding diff mode for every re-run pass — including the
   remediation-diff review and "not seen ≠ fixed" guards, so neither a skipped pass nor a risky fix
   masquerades as a verified resolution. → `references/rerun.md`. If
   there's no `.craftsman/`, skip this step and run fresh. On a re-run: skip step 1; steps 2–5 run
   only where the staleness check marked artifacts stale; step 6 runs in diff mode; steps 7–8 ALWAYS
   re-execute (grades and climb sequence are never carried stale).

   **Concurrency marker (mandatory — every run, fresh or re-run).** Claim the workspace by writing
   `.craftsman/.run-in-progress` with today's date and a session label; delete it only on
   **successful** completion of step 8, never on a mid-run abort. If the marker already exists, warn
   the user and **ask before proceeding** — approving past it is stale-run recovery, never
   permission for concurrent writers. While it is active, `craft-fix` refuses to run. Full spec →
   `references/workspace.md` § Concurrency marker.

1. **Set up the workspace.** Before creating anything, tell the user in chat (2-3 sentences) what's
   about to happen: what will be audited, that results will live in a gitignored `.craftsman/`
   workspace (they can ask to have it committed instead if they want it tracked), the rough duration
   (a full multi-domain audit runs tens of minutes), and that they'll get a prioritized top-5-10 with
   a readiness grade at the end. Then create `.craftsman/`, add it to the project's `.gitignore`, drop
   the `README.md` that explains what the folder is. → `references/workspace.md`

2. **Discover what the project actually is.**

   **Confirm the shipping target before reading code.** Auditing a stale branch produces findings
   that are true of the tree and false of production — the fastest way to destroy trust in the
   report. Compare `HEAD` against the default remote branch
   (`git rev-list --left-right --count origin/HEAD...HEAD`); if it is behind or diverged, STOP and
   ask which tree to audit, preferring any deploy branch or production commit the project names. No
   remote at all is common and is **not** an error — record "shipping target unknown — audited the
   working checkout" and continue. Record the answer in `.craftsman/discovery.md`. →
   `references/discovery.md`

   Evidence-based, never guessed: read `package.json`, lockfiles, framework/build configs, the
   directory layout, CI config, env templates. Determine shape (monorepo vs single app vs marketing
   site vs multiple apps), package manager, frameworks, hosting, and the stack already in place.
   Also make a **maturity read** (pre- / partially- / post-Tier-1, from evidence: tests, CI,
   validated env, auth **and** per-resource authz) — it sets which register the audit uses, so a
   hardened codebase isn't audited as if it had no auth. Collect **quality tooling evidence** too
   (`eslint.config.*`, `biome.json`, `.husky/pre-commit`, `tsconfig.json` strict flags, and the
   `lint`/`format`/`typecheck`/`quality` scripts), recording what exists and what's absent: route
   lint/rule-content findings to the lint plan section and CI-gate wiring findings to the infra plan
   section. Inventory explicit repository invariants and every applicable call site, then record a
   capability profile (browser DOM/CSS vs native UI; Postgres vs SwiftData) so incompatible
   checklist sections are never silently transferred. Write `.craftsman/discovery.md` with
   **citations** — what you found and where. → `references/discovery.md` · `references/quality.md`

3. **Classify which domains apply.** Not every project needs every surface — craft-observability on a
   static marketing site is noise. Mark each of the ten domains **applies / partial / N-A** with a
   capability-backed reason, into `.craftsman/applicability.md`. Every `partial` row names the
   checklist sections that run and the incompatible sections skipped. This makes the tracker honest
   ("5 of 10 apply") and saves wasted passes. → `references/discovery.md` (applicability section)

   **Write the tracker skeleton now.** Immediately after applicability is determined, write
   `.craftsman/master-tracker.md` as a SKELETON: the file header plus the "Audit status" table with
   every applicable (scope, domain) row marked ❔ Unaudited and grades as "—". This is what makes a
   dead or interrupted session resumable — the tracker exists from this point forward, not just at
   the end.

4. **Emit the audit plan as a tracked todo list.** For the applicable domains, generate a `plan.md`
   at the **scope-aware path** and surface the steps as an actual todo list (your native task
   tooling) so a long audit executes in steps and nothing is skipped. The path is always
   `.craftsman/audits/<scope>/<domain>/plan.md`, where `<scope>` is `root` for a single app or the
   workspace-relative path in a monorepo (`apps/web`, `packages/ui`). → `references/workspace.md`

   **Context budget split:** write the plan from **discovery context only** — the subagent loads its
   own domain checklist as its first act, rather than the orchestrator loading all ten up front and
   exhausting context. Copy every applicable discovery invariant into the plan as an all-call-site
   coverage checkbox. → `references/delegation.md`

5. **Adversarial plan review (skip for ≤ 3 scope/domain pairs).** After all `plan.md` files are
   written (step 4), before launching subagent audit passes (step 6): run a review agent (or Codex
   async) with `discovery.md` + all `plan.md` files as input. Its job: find wrong stack
   identifications, missing applicable domains, and checklist items that don't apply given discovery.
   Apply corrections to the plans before subagents run. Yield: typically high — a wrong plan
   multiplied across 10 subagent passes is expensive to fix after the fact.

   **False-negative guard:** if a review pass claims an implementation is missing, verify with grep
   before accepting the claim — reviewers looking at partial context produce false negatives. The
   same guard applies to the tree itself: verify that the tree you are grepping is the tree that
   ships (step 2's shipping-target check) — a stale checkout makes already-shipped fixes look
   missing.

6. **Run each applicable surface by loading its craft skill.** Load `craft-ux` / `craft-frontend` /
   `craft-backend` / `craft-db` / `craft-security` / `craft-infra` / `craft-observability` /
   `craft-testing` / `craft-lint` / `craft-ai`, audit per
   its protocol, and record findings in the matching `findings.md` (same scope-aware path as the plan)
   using the **canonical findings.md emission format** in `references/workspace.md` (heading grammar +
   required fields + fingerprint). No alternate shapes. In a monorepo, never blend two scopes'
   findings under one dir — the per-scope split plus the fingerprint keeps records unambiguous;
   ID labels are display-only and may repeat across scopes. The domain skill owns the verdict; you own
   where it's written.

   **Watch the context budget — delegate when the audit is large.** More than 3 substantial
   `(scope, domain)` passes: give each pair its own subagent, which loads that one craft skill and
   writes *only* its own `findings.md`. The subagent prompt **MUST** carry the verbatim heading
   grammar and required field list from `references/workspace.md` → "Canonical findings.md emission
   format (mandatory)" — copy, do not paraphrase. Write capability is a precondition, not an
   assumption; there is a fenced-block fallback when a worker cannot write, and transport corruption
   is never repaired by hand. Small audits (≤ 3 pairs) stay inline — conditional, not a mandate. →
   `references/delegation.md`

   **Update the tracker after each pass, before starting the next.** After EACH domain pass
   completes, update that row in `.craftsman/master-tracker.md` — findings count, Last run date,
   mechanical grade — before launching the next pass. This is what makes a dead or interrupted
   session resumable: the tracker never lags more than one pass behind reality.

7. **Synthesize then prioritize into a climb sequence.** Collapse all findings into the master
   tracker's ordered "do-these-first" list, tiered for the persona. → `references/prioritization.md`

   **Synthesis protocol — read `references/synthesis.md` and run its four stages in order** before
   writing the tracker. It holds the full procedure; the shape of it is:

   a. **Collect and validate** every `audits/<scope>/<domain>/findings.md` — run
      `validate-findings.mjs`, and `validate-synthesis.mjs` as the gate before the tracker is
      written. **Path binding** is enforced here: a shape-valid finding in the wrong file is a
      blocker, not something to re-home during synthesis. Any file that fails is a blocker — never
      write a normalizer that accepts broken variants; re-run that domain pass instead. The
      remediation closure check gates every `open → fixed` transition.
   b. **Flatten** into one pooled list (inline for ≤ 3 pairs, delegated above that).
   c. **Deduplicate and reconcile** per steps 2–2c of `references/prioritization.md`, writing
      `dedup-map.md` before the tracker.
   d. **Rank and write:** 🔴 Tier 1 → 🟡 Tier 1 → 🔴 Tier 2 → 🟡 Tier 2 → 🟢, holding
      `unverified-from-repo` items out of the climb sequence.

   After presenting the climb sequence to the user, tell them the fix path: to start fixing, invoke
   `craft-fix` (or say "fix the findings" / "fix `<ID>`") — it works through the climb sequence with
   your approval, and the next re-run of this skill verifies what actually got fixed.

8. **Maintain the master tracker.** The file already exists — skeleton from step 3, per-row status
   kept current through step 6. This step **fills in the synthesis parts** only: the climb sequence,
   cross-cutting rollups, and the overall grade. The tracker records which audits exist, their
   status, when they last ran (date + commit), the top open findings, and a **derived readiness
   grade** per (scope, domain) plus an overall grade (the worst applicable surface). The grade is
   computed mechanically from open findings — never hand-set — so it stays honest. On re-runs it
   diffs rather than overwrites: fixed findings move to ✅, new ones get IDs, and a delta report
   leads the summary. → `references/workspace.md` (grade + tracker) · `references/rerun.md` (diff +
   delta report)

   **On successful completion of this step:** delete `.craftsman/.run-in-progress` (the concurrency
   marker claimed after step 0). Do not delete it if the run aborts earlier.

## Reference index

| Task                                                                                  | Load                                  |
| ------------------------------------------------------------------------------------- | ------------------------------------- |
| **Detect project shape + classify which domains apply** (evidence-based)              | `references/discovery.md`             |
| **Workspace layout, file templates, tracker format, readiness grade, stable finding IDs, date stamps** | `references/workspace.md`             |
| **Re-running an audit: staleness detection, finding-by-finding diff, delta report** | `references/rerun.md`                  |
| **Synthesis: validating findings files, the by-hand fallback checklist, dedup, ranking, writing the tracker** | `references/synthesis.md`      |
| **Delegating a large audit: the ≤3/>3 threshold, context budget split, subagent prompts, write-capability fallback** | `references/delegation.md` |
| **Persona-aware finding voice, severity, ruthless sequencing, MVP vs enterprise tiers** | `references/prioritization.md`       |
| **What to recommend when a surface is missing** (tiered, dated, defers to existing)   | `references/recommended-stack.md`     |
| **Quality gate detection** — linting config, CI gate, pre-commit hooks, TS strictness, `quality` script, local/CI drift | `references/quality.md` |
| **Auditing stated claims against actual behaviour** — policy/README/success-message vs code, jurisdiction gating, the legal-conclusion boundary | `references/claim-verification.md` |
| **Deep lint/static-quality audit** — resolved ESLint rules, typed linting, strict rule standard, migration/fix plan | `craft-lint` |

For the actual domain audits, load the peer skill (`craft-ux`, `craft-backend`, etc.) — this skill
routes to them, it does not restate them.

## Standing principles (the non-negotiables)

- **Meet the project where it is — never demand a rewrite.** If a working stack exists (Auth.js,
  Postgres, Railway), audit *it* against the principles. Recommend a stack only to fill a genuine
  gap, and say so explicitly. The obnoxious "rip it out and use my favorites" audit is worse than
  useless.
- **Prioritize ruthlessly.** A finding the user can't act on in order is noise. Lead with the
  handful that prevent a breach, data loss, or embarrassment.
- **Plain language first, jargon second.** Every finding states the real-world consequence before
  the term of art.
- **Evidence over assumption.** Discovery cites files; applicability gives reasons; findings cite
  `file:line`. No "you probably don't have X" — go look.
- **Prefer working sibling code over abstract best-practice.** When the team has already solved a
  gap well elsewhere — another app in this monorepo, or a repo they point you at — cite that
  concrete file as the fix template. Opt-in and gap-triggered; never auto-crawl outside the audited
  project. See `references/discovery.md` → "Reference calibration".
- **Don't restate the domains.** The orchestrator's authority is discovery, planning, prioritization,
  and tracking. The craft skills hold the standards. Loading them is mandatory, not optional.
- **Narrate the milestones.** Post a one-line chat checkpoint after discovery (e.g. "single Next.js
  app, pre-Tier-1"), after applicability (e.g. "7 of 10 domains apply — plan coming"), and after EACH
  domain pass (e.g. "security done — 4 findings, 2 critical · 3 domains remaining"). Silence for 30+
  minutes is a failure of the run, not neutrality.

## Audit checklist (for craft-audit)

When a meta-audit of the craftsman plugin itself runs (i.e. craft-audit auditing its own
orchestrator skill), use this checklist. Each item maps to the editing rules and design principles
in `CLAUDE.md`.

- [ ] Trigger description accurately and narrowly describes when this skill fires — no over-broad patterns; the description's boundary handoffs are stated and reciprocal; add a negative-trigger clause only where wrong-fires are likely
- [ ] Reference index lists every file that exists in `references/` and no files that don't exist
- [ ] Each domain skill's `## Audit checklist (for craft-audit)` section exists and surfaces the most important domain findings back to the orchestrator (if a domain skill lacks the section, that absence is itself a finding)
- [ ] Audit loop steps 0–8 correctly direct the agent to load the right reference for each step (no orphaned references, no step that references a non-existent section)
- [ ] quality.md is integrated into at least one audit loop step (not just listed in the reference index)
- [ ] quality.md findings are routed per the boundary sentence: lint/rule-content → lint plan section, CI-gate wiring → infra plan section
- [ ] Workspace template (`workspace.md`) is complete: all file templates present, `.craftsman/README.md` template orients a returning builder
- [ ] Re-run protocol (`rerun.md`) correctly describes how to resume a partial audit, including the "not seen ≠ fixed" rule, remediation-diff review before closure, and the delta report format
- [ ] Delegation thresholds are consistent throughout: ≤ 3 pairs = small project (inline), > 3 pairs = large project (delegate) — no approximations or conflicting numbers
- [ ] Cross-domain boundaries: domain skills do not duplicate each other's guidance (orchestrator owns discovery/planning/tracking; domain skills own findings)
- [ ] Discovery requires explicit-invariant all-call-site coverage and records the search basis/exclusions
- [ ] Applicability is capability-backed; native UI/storage profiles do not inherit browser/CSS or Postgres-only checks by analogy
- [ ] Synthesis requires `dedup-map.md` plus `validate-synthesis.mjs`; semantic reconciliation cannot be skipped because exact keys do not match
- [ ] Tracker separates `unverified-from-repo` human checks from eligible totals and exposes grade distance plus overdue Fix-attempt verification
