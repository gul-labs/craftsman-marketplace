---
name: craft-testing
description: >-
  Craftsman standard for automated testing: strategy, unit/integration/e2e selection, refactor-proof
  design, flaky tests, mocking boundaries, deterministic data, and merge-gate policy. Use WHENEVER
  work touches tests: writing/reviewing tests, strategy, "add tests", "why is this flaky", "what
  should I test", "tests pass but prod breaks", Testing Library / Playwright / Vitest / Jest / Pytest,
  mocks, fixtures, or adequacy. Trigger on "add tests", "write a test", "is this tested enough", or
  "make the tests reliable". Owns which suites gate merge and what "green" means — see "Scope
  boundaries" in the body for handoffs to craft-infra, craft-security, and craft-ux.
---

# Testing Craft

This skill encodes one engineer's standard for testing software so the suite is actually trusted —
fast, deterministic, and catching real regressions rather than decorating the coverage badge. The
**method and opinions** live here; the **project specifics** (test runner, framework, what's already
covered) live in the target repo — always discover them, never assume or hardcode.

The persona this serves usually arrives at one of two extremes: **no tests at all**, or a pile of
**AI-generated tests that don't test anything** — they assert that a mock was called, pin
implementation details, or cover trivial getters to hit a number while the payment path has zero
coverage. Both feel like "we have testing." Neither catches the bug that takes the app down. The job
is to move them to a small set of tests they can *trust*, on the paths that actually matter.

## Operating principle — discover before you build

Different repos already have different pieces in place. Before adding anything, map what exists so you
extend rather than duplicate or fight it:

- `package.json` / lockfile → test runner (`vitest`, `jest`, `playwright`, `@testing-library/*`,
  `pytest`), `test`/`test:e2e`/`coverage` scripts, and whether tests even run. Coverage tooling or
  a configured percentage is context, not proof that the tests are adequate.
- Test config (`vitest.config.*`, `jest.config.*`, `playwright.config.*`, `pytest.ini`,
  `conftest.py`) → environment, setup files, coverage thresholds already set.
- Existing tests (`*.test.*`, `*.spec.*`, `__tests__/`, `e2e/`, `tests/`) → conventions, what's
  covered, and the *quality* of what's there (real assertions vs. tautologies — read a few).
- Read CI config files (`package.json` scripts, `.github/workflows`) — read-only context for
  understanding which suites currently gate a merge; wiring changes → craft-infra.

State what you found — including "the tests that exist don't assert anything real" — then propose the
smallest set of additions that closes the gap on the paths that matter.

## The testing layers (work in this order)

1. **Strategy** — decide *what* deserves a test before writing one. Spend the budget on the paths
   where a bug means a breach, data loss, or money: auth, authorization, payments, data mutations.
   A handful of integration tests on the critical path beats two hundred shallow unit tests. Coverage
   is a signal of what's *untested*, never a target to chase. See `references/strategy.md`.
2. **Test design** — write tests that survive a refactor: assert observable behavior, not internal
   calls; make them deterministic (frozen clock, seeded randomness, no real network); build data with
   factories, not shared mutable fixtures. A test that breaks when you rename a private method is
   testing the wrong thing. See `references/test-design.md`.
3. **Flake** — a test that fails randomly is worse than no test: it trains the team to ignore red.
   Find the source (time, order-dependence, async races, shared state, real I/O), fix it, and
   quarantine rather than paper over it with blanket retries. See `references/flake.md`.
4. **Frontend / component testing** — test components the way a user drives them: query by role and
   label, not test-ids; `userEvent` over `fireEvent`; mock the *network* (MSW), not your own modules.
   See `references/frontend-testing.md`.
5. **Backend & data testing** — exercise the real boundary: integration tests against a real database
   (testcontainers / transactional rollback), contract tests at service edges, seeded deterministic
   data. Mocking the database makes tests pass while production breaks. See
   `references/backend-data-testing.md`.

## Standing opinions (the non-negotiables)

Apply these unless the user overrides — they're what makes the suite worth trusting:

- **Test behavior, not implementation.** Assert what the user or caller observes, not which internal
  function ran. Tests that mirror the implementation break on every refactor and catch no real bugs —
  they're a tax, not a safety net.
- **Coverage is a signal, not a target.** Use it to *find* untested critical paths; never mandate a
  global percentage. A coverage target is a Goodhart magnet — it produces tautological tests that
  raise the number and catch nothing. Care about the money path being covered, not the repo average.
- **Mock at the boundary you own's edge, not inside it.** Mock the network and external services;
  don't mock your own database, your ORM internals, or the unit under test. A test built on mocked
  internals proves the mocks agree with each other, not that the code works.
- **A flaky test is a bug — fix or delete it, don't retry it.** Blanket test retries hide real race
  conditions and erode trust in the whole suite. Quarantine a flake, find the nondeterminism, fix it.
- **Write the test that would have caught the bug.** Every production incident and every fixed bug
  earns a regression test reproducing it. This is how a suite gets sharp over time instead of bloated.

## Workflow

1. **Discover** — map the runner, existing tests, and their *real* quality; report what matters and
   isn't covered.
2. **Prioritize** — critical-path / high-blast-radius behavior first (strategy.md tiers), not whatever
   is easiest to test.
3. **Write** — behavior-asserting, deterministic, boundary-correct tests against the repo's existing
   conventions.
4. **Verify** — run them, and confirm they *fail when the behavior breaks*. For a test that is credited
   with protecting a Tier A invariant, gather direct discriminative evidence as described below. A test
   you haven't seen fail is not yet a test.

## Discriminative evidence for critical tests

Source review can establish that a test has a meaningful-looking assertion; it cannot establish that
the test distinguishes the protected behavior from a realistic regression. Do not credit a Tier A test
as adequate on source review alone.

For each distinct Tier A invariant the audit credits as covered, identify the existing enforcement
predicate and obtain direct evidence that the relevant test detects it being broken. Examples of
invariants and predicates include tenant/owner/role checks, payment amount or idempotency checks,
irreversible-mutation guards, and an entitlement or token expiry comparison.

The usual evidence is one **bounded local fault-injection probe** per distinct invariant: temporarily
remove, relax, or invert that existing predicate; run the directly relevant test; verify that it fails
on its behavioral assertion; restore the source; and rerun the test green. Record the invariant,
predicate, named test, observed red result, and restored-green result in the audit evidence. The probe
must change production code only — never the test, its assertion, a mock, typechecking, or unrelated
setup — and must run against isolated test data and provider fakes, never production or a live payment
provider.

This is a small verification step, not exhaustive mutation testing: do not mutate every conditional,
set a mutation score, or install a mutation-testing tool merely to conduct a Tier 1 audit. Existing
verified evidence from a regression test may substitute only when it identifies the same invariant,
the named test, and the expected behavioral failure. If direct evidence cannot be safely obtained (for
example, a strictly read-only audit or an unavailable test environment), report that
invariant-coverage claim as `unverified`; do not grade it adequate or use it to close a critical-path
coverage finding.

## Scope boundaries

This skill owns which suites gate merge and what "green" means, including e2e. Hand off at these
lines:

- **CI pipeline mechanism** (how the pipeline is wired, where jobs run) → `craft-infra`. The split
  is by defect, not by topic: a *missing* e2e suite is a TEST finding; an e2e suite that exists but
  isn't wired into CI is an INFRA finding.
- **Security correctness** of what a test asserts → `craft-security`.
- **Live visual audit** of rendered UI → `craft-ux`.
- **Whole-project readiness** → `craft-audit`.
- **Existing tracked findings** ("fix TEST-004") → `craft-fix`.

## Reference index

Read the one matching the current task — they hold the concrete patterns, not this overview:

- `references/strategy.md` — what to test, the testing trophy/pyramid, the two persona tiers, what
  *not* to test, coverage-as-signal, and the test-gate policy (the CI *pipeline* mechanism is
  `craft-infra` → `ci-cd.md`; this defines which suites gate and what green means)
- `references/test-design.md` — trustworthy-test anatomy, behavior-vs-implementation, determinism
  (clock/seed), assertion quality, factories over fixtures
- `references/flake.md` — the flake taxonomy and concrete fixes, retries vs. quarantine policy
- `references/frontend-testing.md` — Testing Library (role/label queries, `userEvent`), MSW for the
  network, what to mock; the *visual/rendered* audit of a running UI is `craft-ux` → `live-audit.md`
- `references/backend-data-testing.md` — integration/contract tests, testcontainers, transactional
  rollback, seeding; schema/query *correctness* is `craft-db`, the API *contract* is `craft-backend`,
  and a test that *proves a security fix* pairs with `craft-security`

## Audit checklist (for craft-audit)

> **Python projects:** substitute pytest for Vitest, httpx for supertest, and the SQLAlchemy
> rollback fixture (yield fixture with `session.rollback()`) for the Drizzle transaction rollback
> pattern. All other checklist items apply unchanged.

When `craft-audit` plans a testing pass for a scope, it turns this checklist into the `plan.md`
todo list — the checklist is owned by this skill, not improvised by the orchestrator. Tailor to what
discovery found: skip a step that genuinely doesn't apply with a one-line reason; never silently drop
one. Emit findings using craft-audit `workspace.md` → "Canonical findings.md emission format"
(authority). Heading grammar (variables required — do not hardcode NNN/severity/status):

`## <scopeLabel>-TEST-<NNN> · severity <🔴|🟡|🟢> · status <open|fixed|wontfix (reason)|regressed|fixed (merged into <ID>)>`

Example only: `## <scopeLabel>-TEST-001 · severity 🔴 · status open`

Required fields under each heading, in order, with these exact labels:
`**What breaks (plain language):**` · `**Technical:**` · `**Fix:**` · `**Fingerprint:**` ·
`**Last-checked:**` (optional `**Confidence:**` — `verified | inferred | unverified-from-repo`, absent
means `verified` — then optional `**Fix-attempt:**` only from craft-fix).
Assign sequential NNN per (scope, domain); judge severity with craft-audit `prioritization.md`.
Forbidden: `###` headings; `## ID · 🔴 · open` shorthand; severity/status as body bullets.

- [ ] Map the runner, configs, existing tests, and any coverage command/report; flag tests that assert
      nothing real (mock-was-called, pinned internals, trivial getters) as if untested. The absence of a
      repo-wide coverage percentage or coverage configuration is an observation, not itself a TEST
      finding → `SKILL.md` (Operating principle)
- [ ] Check the critical paths (auth, authorization, payments, data mutations) actually have tests; flag
      coverage spent on trivia while the money path is bare. If a coverage report is available, use its
      Tier A branch gaps as leads; do not grade from a global percentage → `references/strategy.md`
- [ ] Verify tests assert observable behavior, not internal calls — flag suites that break on a private
      rename or mirror the implementation → `references/test-design.md`
- [ ] Check determinism: frozen clock, seeded randomness, no real network; flag wall-clock/random/live-I/O
      tests and shared mutable fixtures over factories → `references/test-design.md`
- [ ] Hunt flake and its cover-ups; flag blanket retries papering over time, order-dependence, async
      races, or shared state instead of a real fix → `references/flake.md`
- [ ] Check component tests drive the UI like a user — role/label queries and `userEvent`, network mocked
      via MSW; flag test-id queries, `fireEvent`, or mocked own modules → `references/frontend-testing.md`
- [ ] Verify backend/data tests hit the real boundary (real DB via testcontainers/transactional rollback,
      contract tests, seeded data); flag a mocked database → `references/backend-data-testing.md`
- [ ] For every Tier A invariant credited as covered, record discriminative evidence: name the existing
      enforcement predicate and directly relevant test; run one bounded local fault-injection probe (or
      cite equivalent verified regression evidence); observe the behavioral assertion fail; restore and
      rerun green. One representative probe per distinct invariant is enough — this is not a mutation
      score. If it cannot be safely run, mark the claim `unverified`, not adequate; flag tests never
      seen red and incidents without a reproducing test → `SKILL.md` (Discriminative evidence)
- [ ] For prose promises that are **material and mechanically verifiable**, check a structural test
      pins the declared value to the config or implementation it describes (retention windows,
      tenant-scope filters on query modules, privacy-policy claims vs SDK init literals). Treat these
      as **consistency evidence, not runtime proof** — asserting `RETENTION_DAYS === 30` and that a
      job is registered says nothing about whether deletion runs, so pair it with a behavioral test
      (aged fixture data, real job invocation) and pair tenant-scope scans with integration tests of
      reads and writes. Legitimate deviations belong in an allowlist with a one-line written
      justification each. Do not report a missing structural test as a defect where the promise is
      immaterial or not mechanically checkable → craft-audit `references/claim-verification.md`
- [ ] **TEST ↔ INFRA handoff:** this pass owns which suites must gate merge and what "green" means
      (including whether critical-flow e2e exists). Missing e2e *suite* is a TEST finding; if the
      suite exists but is not *wired into CI*, note it and route to craft-infra (pipeline mechanism)
      → `references/strategy.md` · craft-infra `ci-cd.md`
