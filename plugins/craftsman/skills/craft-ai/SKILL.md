---
name: craft-ai
description: >-
  The Craftsman standard for LLM-powered features — prompt-injection surface, key and spend
  protection, PII reaching model APIs, and reliability/eval discipline. Use whenever work touches an
  LLM integration: a chatbot or agent, a RAG pipeline, an LLM call from a route or job,
  tool/function-calling, or reviewing prompts and completions. Trigger even on "add an AI feature",
  "is my chatbot secure", "my OpenAI bill exploded", or "why did the model call the wrong tool"
  without naming a provider or framework. Handoffs: see "Scope boundaries" in the body.
---

# AI Craft

This skill encodes one engineer's standard for shipping LLM-powered features safely, applied the
same way across every repo. The **method and opinions** live here; the **project specifics**
(which provider, which SDK, which framework) live in the target repo's code and config — always
discover them, never assume or hardcode.

## Operating principle — discover before you build

Different repos already have different pieces in place. Before changing anything, spend a few
minutes mapping the current posture so you extend rather than conflict:

- `package.json` / lockfile / requirements → which LLM SDK is present (OpenAI, Anthropic, Vercel
  AI SDK, LangChain, LlamaIndex)? Which is the default model tier?
- `grep` for the API key — is it read through a validated server-side env schema, or does it leak
  into a `NEXT_PUBLIC_*` / client-bundled / mobile-app constant?
- Find every call site that sends a prompt — what user-controlled or retrieved content reaches
  the system prompt or context window, and is there any structural separation between
  instructions and untrusted content?
- Check whether the integration uses tool-use / function-calling — what can the model actually
  invoke, and is there a confirmation step before a consequential action fires?
- Look for logging/observability around LLM calls — are raw prompts and completions logged, and
  where do those logs live?
- Check for rate limits, `max_tokens` caps, and timeouts on LLM-calling routes; check for retry
  logic around tool actions.
- Look for any eval harness, golden test set, or regression check tied to prompt changes.

State what you found, then propose the smallest set of changes that closes the gaps.

## The AI layers (work in this order)

1. **Prompt-injection surface** — anything that reaches the model's context that isn't the
   developer's own instructions (user input, retrieved documents, scraped pages, tool output) is
   a potential injection vector. Structural separation between instructions and untrusted content,
   allow-listed tools, and human confirmation for consequential actions are the mitigations — none
   of them fully close the gap. See `references/prompt-injection.md`.
2. **Keys & spend** — provider keys never ship to a client bundle or mobile app; every LLM-calling
   route has a rate limit, a `max_tokens` cap, and a bound on loop/agent iterations; streaming
   requests abort when the client disconnects. See `references/keys-and-spend.md`.
3. **Data privacy** — inventory what PII leaves the building in a prompt to a third-party API,
   check the provider's retention/training posture, and scrub prompts/completions before they hit
   observability logs. See `references/data-privacy.md`.
4. **Reliability & evals** — provider outages are routine, so every call has a timeout and a
   fallback; non-idempotent tool actions are never blindly retried; a minimal golden-case eval
   harness catches prompt regressions before they ship. See `references/reliability-evals.md`.

## Standing opinions (the non-negotiables)

These are the judgments that make output consistent across repos — apply them unless the user
overrides:

- **Untrusted content is never structurally indistinguishable from developer instructions.**
  User input, retrieved documents, and tool output are content, not commands — the integration is
  designed so an instruction embedded in that content can't silently expand what the model is
  willing to do.
- **Provider keys live server-side only.** No LLM API key in a client bundle, mobile binary, or
  anything a browser or device can read; every model call is proxied through your own backend.
- **Every LLM-calling endpoint has a rate limit, a token cap, and a timeout.** An unbounded loop,
  an unbounded `max_tokens`, or a hung request against a stalled provider is a spend bomb and an
  availability bug waiting to happen.
- **Tool-calling that performs a consequential action gets a confirmation step or an allow-list.**
  A model that can call a tool is a model that can take real-world action on injected instructions
  — treat that boundary with the same suspicion as remote code execution.
- **PII in a prompt to a third-party API is inventoried, not assumed away.** If personal data
  reaches a model provider, know what's sent, what the provider's retention/training terms say,
  and whether logging pipelines are scrubbing it before storage.
- **Prompts that ship non-trivial agent/prompt behavior are versioned and covered by a golden-case
  eval.** A thin single-route MVP wrapper can flag a missing harness as 🟡 recommend, not automatic
  🔴 — see `reliability-evals.md` applicability.

## Workflow

1. **Discover** — map the current posture (provider/SDK, key handling, injection surface, tool
   access, logging, rate limits, evals) and report the gaps.
2. **Propose** — ordered by the four layers above, highest-risk gap first, smallest viable changes.
3. **Implement** — against the repo's existing patterns (its SDK, its middleware chain, its env
   schema, its observability pipeline).
4. **Verify** — confirm keys aren't reachable from the client, rate limits/token caps actually
   fire, an injected instruction in test content doesn't expand tool access, and the eval suite
   passes before a prompt change ships.

## Scope boundaries

This skill owns the LLM-specific layer: what reaches the prompt, what the model can do, what leaves
the building, and whether it's reliable. Hand off at these lines:

- **Generic route authentication** → `craft-backend`. This skill does not re-audit the auth boundary.
- **Secret *storage* mechanics** (where keys live, how they rotate) → `craft-security`. This skill
  covers key *exposure through the model path* — client-reachable keys, keys in prompts or logs.
- **Provider billing alerts as infra config** → `craft-infra`. This skill owns application-level
  spend-safety *design*: rate limits, token caps, and loop bounds on model-calling routes.
- **Rate-limit ownership, so the same gap isn't emitted four times:** BE supplies the route
  middleware mechanism; SEC owns login-abuse policy; INFRA owns edge capacity; AI owns LLM
  cost/token limits.
- **Whole-project readiness** → `craft-audit`, which routes here for the AI slice.

## Reference index

Read the one matching the current task — they hold the concrete setup, not this overview:

- `references/prompt-injection.md` — injection via user content and retrieved/scraped content
  (indirect injection), tool-use/function-calling boundaries, output handling (XSS, downstream
  injection), mitigation framing
- `references/keys-and-spend.md` — client-bundle key leaks, per-route rate limits and token caps,
  unbounded loops as spend bombs, streaming abort on disconnect, billing alerts, model tiering
- `references/data-privacy.md` — PII inventory in prompts, provider retention/training flags,
  scrubbing logged prompts/completions, user consent/disclosure, regional/enterprise endpoints
- `references/reliability-evals.md` — timeouts and fallbacks, retry vs. non-idempotent tool
  actions, minimal eval harness, structured-output validation, prompt versioning

## Audit checklist (for craft-audit)

When `craft-audit` plans an AI pass for a scope, it turns this checklist into the `plan.md`
todo list — the checklist is owned by this skill, not improvised by the orchestrator. Tailor to
what discovery found: skip a step that genuinely doesn't apply with a one-line reason; never
silently drop one. Emit findings using craft-audit `workspace.md` → "Canonical findings.md emission format"
(authority). Heading grammar (variables required — do not hardcode NNN/severity/status):

`## <scopeLabel>-AI-<NNN> · severity <🔴|🟡|🟢> · status <open|fixed|wontfix (reason)|regressed|fixed (merged into <ID>)>`

Example only: `## <scopeLabel>-AI-001 · severity 🔴 · status open`

Required fields under each heading, in order, with these exact labels:
`**What breaks (plain language):**` · `**Technical:**` · `**Fix:**` · `**Fingerprint:**` ·
`**Last-checked:**` (optional `**Confidence:**` — `verified | inferred | unverified-from-repo`, absent
means `verified` — then optional `**Fix-attempt:**` only from craft-fix).
Assign sequential NNN per (scope, domain); judge severity with craft-audit `prioritization.md`.
Forbidden: `###` headings; `## ID · 🔴 · open` shorthand; severity/status as body bullets.

- [ ] Map the current posture — provider/SDK, key handling, injection surface, tool access,
      logging, rate limits, evals — flagging client-exposed keys and unbounded loops →
      SKILL.md "Operating principle — discover before you build"
- [ ] Verify user-controlled and retrieved/scraped content is structurally separated from
      developer instructions in the prompt; hunt for indirect-injection vectors (RAG documents,
      web-scraped context, uploaded files) → `references/prompt-injection.md`
- [ ] Check tool-use/function-calling boundaries — is every callable tool allow-listed, and does
      a consequential action require confirmation rather than firing on an injected instruction?
      → `references/prompt-injection.md`
- [ ] Confirm LLM output rendered as HTML/markdown is encoded, and output used to build a query
      or command is treated as untrusted → `references/prompt-injection.md`
- [ ] Confirm no provider API key is reachable from a client bundle, mobile app, or public env var;
      verify calls are proxied through the backend → `references/keys-and-spend.md`
- [ ] Verify every LLM-calling route has a rate limit, a `max_tokens` cap, and a bound on
      agent/loop iterations; check streaming requests abort on client disconnect. **Ownership:** AI
      owns LLM spend/cost limits; BE may still own the middleware mechanism — emit once, don't
      triple-count with SEC/INFRA → `references/keys-and-spend.md`
- [ ] Check for provider billing alerts/hard caps and model tiering (cheap model for cheap tasks)
      → `references/keys-and-spend.md` (cross-ref `craft-infra` for the alerting config itself)
- [ ] Inventory PII flowing into prompts to third-party APIs; check provider retention/training
      settings and note zero-retention options where offered → `references/data-privacy.md`
- [ ] Confirm prompts/completions logged for observability are scrubbed of PII, and users are
      disclosed that AI processes their data → `references/data-privacy.md`
- [ ] If the product generates content for users in regulated verticals (medical, financial, legal,
      real-estate, insurance), check **where the "must avoid" phrases and required disclaimers live —
      and whether they are enforceable at generation time or just notes in a doc**. Restrictions
      captured as structured per-tenant fields that flow into the prompt are enforceable; a wiki page
      the model never sees is not → `references/data-privacy.md`
- [ ] Where the product makes factual claims on a user's behalf, check the generation path carries a
      provenance/proof requirement (claim → evidence → source) rather than free-generating assertions,
      and that a prohibited-claims list exists for the tenant → `references/reliability-evals.md`
- [ ] Check the model tier is justified for the task's **hallucination tolerance**, not just cost —
      a cheap/lite tier fabricating citations is disqualifying for compliance-, legal-, or
      citation-bearing output even when it benchmarks fine elsewhere. The reasoning belongs in a
      comment at the call site → `references/reliability-evals.md`
- [ ] Verify LLM calls have timeouts and a graceful-degradation fallback for provider outages, and
      that retries never re-fire a non-idempotent tool action → `references/reliability-evals.md`
- [ ] Check for schema validation (repair-or-reject) on structured LLM output before it's consumed
      downstream → `references/reliability-evals.md`
- [ ] Confirm eval discipline matches surface risk: golden-case harness is **required** (🔴-class
      when missing) when shipping non-trivial prompt/agent behavior to production; for a thin
      single-route MVP wrapper, flag missing eval as 🟡 opportunity / recommend, not automatic 🔴.
      Prompts that do ship should still be versioned like code → `references/reliability-evals.md`

