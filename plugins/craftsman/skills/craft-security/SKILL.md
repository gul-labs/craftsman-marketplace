---
name: craft-security
description: >-
  The Craftsman standard for defensive security hardening — authorization policy (per-resource authZ,
  IDOR/tenant scoping), input validation & injection prevention, secrets, security headers, CORS,
  dependency vulnerabilities, XSS/CSRF, and data exposure. Use WHENEVER work touches security:
  harden an endpoint, review auth, handle secrets, lock down headers, audit dependencies, or
  production-harden a service. Trigger on "is this secure", "harden this", "review for
  vulnerabilities", or "handle secrets properly". Owns authZ, abuse-defense policy, and security
  review of auth flows — see "Scope boundaries" in the body for handoffs.
---

# Security Craft

This skill encodes one engineer's standard for defensive security, applied the same way across every
repo. The **method and opinions** live here; the **project specifics** (which auth provider, which
secret store, which validation library) live in the target repo's code and config — always discover
them, never assume or hardcode.

## Operating principle — discover before you build

Different repos already have different pieces in place. Before changing anything, spend a few minutes
mapping the current posture so you extend rather than conflict:

- `package.json` / lockfile → which auth library, validation library, and HTTP framework are present?
- `grep` for an existing env schema (`env.ts`, `config.ts`) — are secrets loaded through a validated
  schema or read raw from `process.env`?
- Check for an existing middleware file or proxy entry point — are security headers already set, and
  where?
- Scan `package.json` for known-vulnerable pinning patterns; note whether a dependency scanner
  (`npm audit`, Snyk, Dependabot) is wired into CI.
- Look at existing route handlers — is authorization checked once in middleware, per-route, or not
  at all?

State what you found, then propose the smallest set of changes that closes the gaps.

## The security layers (work in this order)

1. **Authorization & auth-flow security** — enforce least-privilege on every resource (a valid
   session does not mean access to everything), and apply the security *standard* for the
   authentication flow (JWT verification criteria: pin the algorithm, reject `alg:none`, check
   `exp`/`iss`/`aud`). The authN *implementation* — verifying the session/token and resolving the
   principal/tenant in the request lifecycle — is owned by **craft-backend** → `auth.md`; this layer
   owns the *criteria that verification must meet* and the authZ policy on top. See
   `references/authz.md`.
2. **Input & output** — validate all input at the boundary, encode all output for its target context,
   parameterize all queries. Never trust data that crossed a trust boundary. See
   `references/input-output.md`.
3. **Secrets** — credentials, tokens, and keys belong in a validated env schema or secret store, not
   in source code, logs, or error messages. See `references/secrets.md`.
4. **Transport & headers** — TLS is table stakes; security headers (CSP, HSTS, X-Frame-Options,
   etc.) and a strict CORS policy narrow the attack surface further. See `references/headers-cors.md`.
5. **Supply chain** — pinned, scanned dependencies with critical vulnerabilities blocking CI. Every
   package you import is code you're responsible for. See `references/supply-chain.md`.
6. **Data rights** — a user-data deletion path exists and cascades, third-party processors get their
   own deletion call, an export path exists, and PII is inventoried rather than leaking into logs or
   error trackers. Engineering-observable only — not legal advice. See `references/data-rights.md`.

## Standing opinions (the non-negotiables)

These are the judgments that make output consistent across repos — apply them unless the user
overrides:

- **Authorization is checked on every request at the resource boundary.** Authentication (who you
  are) is not the same as authorization (what you're allowed to do). Passing auth middleware doesn't
  grant access to a resource; the resource handler confirms it.
- **All input is validated at the boundary, all output is context-encoded.** SQL goes through
  parameterized queries or an ORM, HTML output is escaped, JSON responses never leak internal fields
  that weren't explicitly selected.
- **Secrets flow through a validated env schema and are never logged or exposed in errors.** Raw
  `process.env` reads are replaced with the schema-validated equivalent; error handlers scrub
  credential-shaped strings before they hit logs or responses.
- **CORS is deny-by-default; CSP is explicit.** Wildcard origins and missing Content-Security-Policy
  headers are treated as gaps to close, not neutral defaults.
- **Dependencies are pinned and scanned in CI; criticals block merge.** Unpinned ranges are a
  supply-chain risk — lock them, run the scanner, and gate on the results.

This is the defensive-hardening standard. Pair it with a dedicated penetration-testing or
threat-modelling exercise when doing a full security review; that's a different discipline.

## Workflow

1. **Discover** — map the current posture (auth provider, secret loading, headers, validation,
   dependency scanner) and report the gaps.
2. **Propose** — ordered by the layers above, highest-risk gap first, smallest viable changes.
3. **Implement** — against the repo's existing patterns (its env schema, its middleware chain, its
   validation library, its CI config).
4. **Verify** — test that authorization denials fire correctly, confirm headers are present in
   responses, run a dependency scan and confirm it passes. Security you haven't seen enforce isn't
   done.

## Scope boundaries

This skill owns authorization *policy* and the security review of auth flows. Hand off at these
lines:

- **The authentication boundary itself** (how a request is authenticated, where the principal is
  resolved) → `craft-backend`. This skill owns authZ and reviews the authN flow for weaknesses.
- **Rate-limit ownership, so the same gap isn't emitted four times:** SEC owns abuse-defense
  *policy* — login throttling, brute-force, credential stuffing, lockout; the route *middleware*
  mechanism → `craft-backend`; platform/edge capacity → `craft-infra`; LLM spend and token limits →
  `craft-ai`.
- **Whole-project readiness** → `craft-audit`.
- **Existing tracked findings** ("fix SEC-003") → `craft-fix`.

## Reference index

Read the one matching the current task — they hold the concrete setup, not this overview:

- `references/authz.md` — authentication vs authorization, per-resource enforcement, JWT claims,
  IDOR / broken object-level authorization (OWASP BOLA)
- `references/input-output.md` — validation at the boundary, output encoding, parameterized queries,
  injection prevention
- `references/secrets.md` — env schema patterns, secret store integration, scrubbing secrets from
  logs and error responses
- `references/headers-cors.md` — CSP, HSTS, CORS deny-by-default, middleware placement
- `references/supply-chain.md` — dependency pinning, CI scanning, vulnerability triage thresholds
- `references/data-rights.md` — deletion path cascade, third-party processor deletion, export path,
  PII surface inventory (engineering-observable slice only, not legal advice)

## Audit checklist (for craft-audit)

When `craft-audit` plans a security pass for a scope, it turns this checklist into the `plan.md`
todo list — the checklist is owned by this skill, not improvised by the orchestrator. Tailor to what
discovery found: skip a step that genuinely doesn't apply with a one-line reason; never silently drop
one. Emit findings using craft-audit `workspace.md` → "Canonical findings.md emission format"
(authority). Heading grammar (variables required — do not hardcode NNN/severity/status):

`## <scopeLabel>-SEC-<NNN> · severity <🔴|🟡|🟢> · status <open|fixed|wontfix (reason)|regressed|fixed (merged into <ID>)>`

Example only: `## <scopeLabel>-SEC-001 · severity 🔴 · status open`

Required fields under each heading, in order, with these exact labels:
`**What breaks (plain language):**` · `**Technical:**` · `**Fix:**` · `**Fingerprint:**` ·
`**Last-checked:**` (optional `**Confidence:**` — `verified | inferred | unverified-from-repo`, absent
means `verified` — then optional `**Fix-attempt:**` only from craft-fix).
Assign sequential NNN per (scope, domain); judge severity with craft-audit `prioritization.md`.
Forbidden: `###` headings; `## ID · 🔴 · open` shorthand; severity/status as body bullets.

- [ ] Map the current posture — auth library, env loading, headers, validation lib, dependency
      scanner — flagging raw `process.env` reads and authZ that's checked nowhere → SKILL.md
      "Operating principle — discover before you build"
- [ ] Verify authorization is enforced at the resource boundary on every request, not just authN;
      hunt IDOR / broken object-level access where any session can reach another tenant's resource →
      `references/authz.md`
- [ ] Check JWT verification criteria — algorithm pinned, `alg:none` rejected, `exp`/`iss`/`aud`
      validated — and that authZ source of truth (RBAC/ABAC) is server-side → `references/authz.md`
- [ ] Confirm auth endpoints (login, password-reset, OTP, token) have abuse-defense rate-limit
      *policy* (per-IP + per-account throttling / lockout). **Ownership (emit once):** SEC owns the
      policy finding; BE owns missing in-app middleware mechanism; INFRA owns platform/edge capacity;
      AI owns LLM spend limits — do not re-emit the same gap under all four → `references/authz.md`
- [ ] Confirm all input is validated at the boundary, output is context-encoded, and queries are
      parameterized; flag unescaped HTML, DOM XSS sinks, and SSRF on outbound requests →
      `references/input-output.md`
- [ ] Trace every secret through a validated env schema; flag credentials in source, logs, or error
      responses, client-exposed env treated as private, and missing scrubbing → `references/secrets.md`
- [ ] Verify security headers (CSP, HSTS, X-Frame-Options) are present in responses and CORS is
      deny-by-default; flag wildcard origins and missing Content-Security-Policy →
      `references/headers-cors.md`
- [ ] CSRF: form submissions and state-mutation endpoints are protected (SameSite cookie or CSRF
      token); SameSite=None session cookies with no additional CSRF defense are flagged →
      `references/input-output.md`
- [ ] Confirm dependencies are pinned and a scanner gates CI with criticals blocking merge; flag
      unpinned ranges and unfixed/untriaged vulnerabilities → `references/supply-chain.md`
- [ ] Run a one-pass license check (`npx license-checker` / `pnpm licenses list`); flag any GPL/AGPL
      dependency with no replace/isolate/advice plan → `references/supply-chain.md`
- [ ] Verify the user-data deletion path cascades to every related table (not just the primary row)
      and includes deletion calls to third-party processors (Stripe, analytics, email) →
      `references/data-rights.md`
- [ ] Confirm a PII surface inventory exists (which tables/columns hold PII) and that PII isn't
      leaking into application logs, analytics events, or error trackers (Sentry) →
      `references/data-rights.md`
- [ ] Compare the privacy policy's factual claims against the actual SDK init literals (DNT/consent
      options, session-recording flags, cookie vs localStorage persistence) and its subprocessor list
      against the third parties actually initialized. Verify library defaults in the *pinned* version
      before calling an absent option a defect → craft-audit `references/claim-verification.md`
- [ ] Check that the success message returned by destructive endpoints (account/data deletion) is
      true of what the code actually did — flag "permanently deleted" on a handler that soft-deletes,
      defers to an async webhook, or leaves org-owned rows intact →
      craft-audit `references/claim-verification.md`
- [ ] On localized apps, verify protected-route matchers actually match under **every** locale — some
      matchers (e.g. Clerk's `createRouteMatcher` via `@hapi/call`) treat `(en|de|ar)` alternation as
      literal text, silently leaving every non-default-locale route public → `references/authz.md`

