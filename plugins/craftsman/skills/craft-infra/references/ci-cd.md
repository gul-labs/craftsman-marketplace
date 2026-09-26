# CI/CD

A pipeline that only runs on deploy has already lost — the regression shipped, the build broke in
prod, and the rollback is now an incident. **Every merge gate must run lint, typecheck, tests, and a
production build on the PR; deploys are automated, reversible, and never require a manual prod edit.**
The discipline is not about CI velocity; it is about making broken code impossible to reach production
undetected, and making recovery deterministic when something gets through anyway.

> **Scope split.** This file owns the *pipeline structure*: required PR gates, gate ordering, deploy
> automation, and rollback patterns. **TEST ↔ INFRA handoff:** **`craft-testing`** owns *which*
> suites must gate merge and what "green" means (including e2e strategy); this skill owns *when/how*
> those jobs run, secrets injection, and deploy gates. Missing e2e suite → TEST finding; e2e not
> wired into CI → INFRA finding. How the build is made reproducible and what an immutable artifact
> looks like belongs to `build-release.md`. How config and secrets flow into the pipeline belongs to
> `config.md`. The release ordering around a separately applied Postgres migration is here;
> migration mechanics and semantics — backward compatibility, zero-downtime column changes — belong to **`craft-db`** →
> `migrations.md`. The vulnerability scanner that runs as a required gate is referenced here (it
> blocks merge), but triage thresholds and suppression rules are in **`craft-security`** →
> `supply-chain.md`. Post-deploy error-rate gates and deploy markers belong to
> **`craft-observability`** → `slo-alerts.md`.

---

## Contents

- [Required gates before merge](#required-gates-before-merge)
- [Gate ordering: fail fast, fail cheap](#gate-ordering-fail-fast-fail-cheap)
- [Where migrations fit in the release sequence](#where-migrations-fit-in-the-release-sequence)
- [Deploy automation and the no-manual-edit rule](#deploy-automation-and-the-no-manual-edit-rule)
- [Rollback: one step per deploy path](#rollback-one-step-per-deploy-path)
- [Roll back first, diagnose after](#roll-back-first-diagnose-after)
- [Post-deploy verification](#post-deploy-verification)
- [CI secrets injection](#ci-secrets-injection)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Required gates before merge

A PR that cannot pass all four of these does not merge. They run in CI, not locally, and the branch
protection rule marks them **required** so a failed or skipped run blocks the merge button — not a
convention that breaks when someone forgets.

1. **Lint.** Catches formatting, import-order, and cheap style bugs before a human reads the diff.
   One run of the repo's existing linter (ESLint, Biome, Ruff, golangci-lint — discover from config
   files). Fail on any error, not just warnings.
2. **Typecheck.** A separate, full-project type-check pass (`tsc --noEmit`, `pyright`, `mypy`, the
   Go compiler). Do not rely on the build step to surface type errors — build tools often skip or
   cache them.
3. **Tests.** The full unit + integration suite. If the suite is slow, split fast and slow into
   separate jobs (fast runs first, slow runs in parallel with the build) — don't skip tests to hit
   a speed target. Cover the deployment path where the cost is a few minutes; discover the test
   runner and parallelism already in place before adding a second one.
4. **Production build.** A real `--production` / `NODE_ENV=production` build that exercises the
   bundler, tree-shaking, and any build-time env-var injection. This catches dead imports, missing
   env references, and size regressions the typecheck never sees.

Additionally, as a required check (not advisory):

5. **Dependency vulnerability scan.** One scanner per repo (e.g. `npm audit --audit-level=high`,
   Snyk, osv-scanner — whichever is already wired). Exit non-zero on critical/high findings so the
   gate actually blocks. Triage thresholds and suppression rules: **`craft-security`** →
   `supply-chain.md`.

None of these gates runs on a schedule instead of a PR — that is too late. They run on *every push
to a PR branch*, and the status is required before merge.

### A required check must do substantive work

Required-job names are not evidence that their checks ran. Audit the workflow's trigger filters,
job-level and step-level `if:` conditions, `needs`, matrix exclusions, `continue-on-error`, and every
secret/environment-dependent branch. A gate is **vacuously green** when its required check reports
success or skipped while every substantive lint/typecheck/test/build/scan step was bypassed.

For each required gate, trace both a normal trusted PR and the restricted context it claims to support
(for example a fork PR without secrets). The gate must either run its substantive command, or execute
an explicit failing/preflight step that blocks merge and explains the unavailable prerequisite. Never
guard an entire required job with `if: secrets.X`; separate secret-dependent deploy/integration work
into a non-gating job, or make the required gate fail closed when its required environment is absent.
Record the triggering condition and observed execution path; workflow YAML that merely names a command
is not proof it runs.

---

## Gate ordering: fail fast, fail cheap

Order jobs so the cheapest failure signal arrives first. A slow test suite that runs before a
five-second type error wastes everyone's time.

```
[PR push]
    │
    ├─ lint          (seconds; fails fast relative to test suite)
    ├─ typecheck     (seconds–low minutes)
    │
    ▼ (only if both pass)
    ├─ tests         (parallel shards if slow)
    ├─ prod build    (parallel with tests)
    ├─ dep scan      (parallel with tests; required check)
    │
    ▼ (all required checks green)
  [merge allowed]
```

Practical rules:
- **Lint and typecheck run unconditionally and in parallel with each other.** They are the cheapest
  signal; failing them immediately surfaces the error without waiting for a test runner to spin up.
- **Tests, build, and scan run in parallel** after lint and typecheck pass. They are all independent
  of each other; running them serially multiplies wall-clock time for no reason.
- **Never let the build gate be the only type-error catcher.** Build tools (Webpack, esbuild, Vite,
  Turbopack) frequently skip or isolate type checking. A separate `tsc --noEmit` job is not
  redundant — it is the actual type gate.
- **Cache aggressively at the layer boundary.** Cache the dependency install (restore by lockfile
  hash), the compiler cache (`tsconfig.tsbuildinfo` — only emitted with `--incremental`; add that
  flag to the typecheck job if caching is desired; `.mypy_cache` for Python), and the build cache
  where the platform supports it. Discover what caching the CI system already provides before
  adding a custom layer.

---

## Where migrations fit in the release sequence

For standard backward-compatible schema changes, apply the migration **after the new artifact is
verified and before traffic switches to the new code.** Running it before verification risks schema
drift against a rolled-back deploy; running it after traffic switches creates a window where new
code runs against an old schema. For Postgres, invocation is a separate human-run `db:migrate`
command or a manually dispatched workflow, on `DATABASE_URL_DIRECT` with the migration role,
staging first. It is never an automatic deploy, build, boot, or `quality:ci` step.

```
[Build artifact verified]
    │
    ├─ apply migrations ← separate manual command or workflow_dispatch for Postgres
    │                      (new schema, old code still serving)
    │                      migrations MUST be backward-compatible with the OLD code
    │
    ├─ deploy new code   ← traffic swaps; new code now serves against new schema
    │
    ├─ health/readiness  ← probe confirms the new instance is ready
    │
    ▼ (rollback if probe fails — old schema is still compatible with old code)
  [traffic live on new code]
```

This ordering requires migrations to be **backward-compatible**: the new schema must work with the
old code during the overlap window. That means column additions before column removals, additive
changes first, destructive removals deferred to a later deploy. The migration semantics —
expand/contract, zero-downtime techniques, column rename patterns — live in **`craft-db`** →
`migrations.md`. The release ordering is shown here; Postgres migration execution remains separate.

**Caveats for multi-phase and online migrations:**

- **Expand/contract patterns span multiple deploys.** Phase 1: additive schema change deployed with
  old + new code tolerating it. Phase 2: async backfill (may run as a background job or a
  separately gated migration deploy). Phase 3: cleanup (drop old column/constraint) deployed only
  after old code is fully retired. Each phase has its own insertion point in its own deploy — there
  is no single universal "one safe point" across all three.
- **A failed migration does not necessarily leave the old schema intact.** This is only true for
  transactional migrations on databases that support DDL transactions (PostgreSQL has transactional
  DDL for *most* operations — but some, e.g. `CREATE INDEX CONCURRENTLY`, cannot run in a transaction
  block and can leave an artifact like an invalid index on failure; MySQL/MariaDB has no
  transactional DDL at all). Non-transactional or multi-statement migrations may leave
  the schema in a partially applied state. Know your database's behavior and design accordingly —
  idempotent, individually re-runnable migration steps reduce partial-failure risk.
- **Separately gated migration deploys** — where a migration is deliberately deployed alone (no
  code change) and validated before the dependent code ships — are the right tool for high-risk or
  long-running schema changes. The pipeline structure is the same; the payload is migration-only.

Do not edit production schema with ad hoc SQL. For Postgres, run the repo's reviewed `db:migrate`
command or manually dispatched workflow; retain its log and verify success before the dependent
code deploys. A failed migration leaves the old code serving (or a partially applied state that
must be diagnosed and resolved, not silently ignored). The deploy should check that its required
schema version is present, failing closed if the migration has not been applied.

---

## Deploy automation and the no-manual-edit rule

**Manual production edits are the failure mode, not the workflow.** They are untracked, unreviewable,
and unrollbackable. Code and configuration changes travel through the deployment pipeline. Postgres
schema changes use the separate, reviewed `db:migrate` path described above, with an apply log.

- **Code deploys trigger from the pipeline**, not from a developer SSH session or a platform dashboard
  button pressed ad hoc. A commit to the deploy branch (e.g. `main`) triggers the pipeline, which
  runs gates, then deploys.
- **The deploy step uses the artifact the build step produced** — the same binary, image, or bundle
  that passed the gates. Never rebuild in the deploy step; you would be deploying something that
  did not run the tests.
- **Environment configuration flows through validated env schemas** (`config.md`), not edited
  in-place in the running container or function. Config changes that need a redeploy are applied by
  updating the config source and redeploying — not by patching the live process.
- **Discover the deploy mechanism** in the repo before proposing one: check for a `Dockerfile`,
  `fly.toml`, `vercel.json`, `render.yaml`, Terraform resources, a `deploy` step in existing CI
  config, and a platform CLI in `devDependencies`. Extend the existing mechanism; don't layer a
  second one over it.

Structural pattern (platform-agnostic):

The example below uses GitHub Actions syntax; adapt `needs:` / `if:` to your CI system's dependency and branch-filter syntax — discover what is already in `.github/workflows/`, `.circleci/`, or equivalent first.

```yaml
# GitHub Actions — structure only, not a prescription for this exact platform
jobs:
  lint:
    # ... lint job

  typecheck:
    # ... typecheck job

  tests:
    # ... test job

  build:
    # ... production build job (uploads artifact on success)

  scan:
    # ... dependency vulnerability scan job

  deploy:
    needs: [lint, typecheck, tests, build, scan]   # only runs if every gate job succeeded
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Download build artifact
        # restore the artifact that passed the gates — do not rebuild

      - name: Verify required schema version
        # Postgres migration is applied separately through db:migrate or workflow_dispatch

      - name: Deploy artifact
        # platform CLI / API (fly deploy, vercel deploy, ecs update-service, ...)

      - name: Verify health
        # GET /health/live and protected /health/ready; fail and trigger rollback if unhealthy
```

The ordering is verified artifact → separately applied Postgres migration when needed → schema
version check → artifact deploy → health check. The commands vary by platform; never let an
automatic deploy implicitly run the Postgres migration.

---

## Rollback: one step per deploy path

Every deploy path must have a documented, tested, **one-step** rollback. "We could rebuild from the
last commit" is not a rollback plan — that is a 10-minute deploy under incident conditions. Document
the rollback command next to the deploy command.

| Deploy mechanism | Rollback |
| --- | --- |
| Vercel | `vercel rollback` or promote the previous deployment from the dashboard — instant, no rebuild |
| Fly.io | `fly deploy --image <previous-image-tag>` — redeploys the pinned image |
| Render | "Redeploy" a prior deploy from the dashboard (select the deploy, click Redeploy), or re-push the prior git commit to the deploy branch; CLI: `render deploys create <service-id> [--image <image>]` — verify current CLI syntax at render.com/docs before scripting rollback, as CLI flags change between releases |
| Docker / ECS / Cloud Run | Re-deploy the previous image tag; the registry must retain prior tags |
| Terraform / Pulumi | Revert the IaC commit and re-apply; if state must be restored after a failed mid-apply, use `terraform state` manipulation with care — the state file must be reconciled against actual cloud resources to avoid drift |
| CDK | Revert the IaC commit and re-deploy via `cdk deploy`; or use CloudFormation's native stack rollback — CDK has no independent state file |
| Serverless (Lambda, Vercel Functions) | Re-deploy a prior function version; document the version-pin mechanism per platform |

The DB side is the hard constraint. Because migrations run before the new code deploys, a code
rollback (redeploy the old artifact) is only safe if the migration was backward-compatible with
the old code. A destructive migration — dropping a column the old code reads, renaming without an
alias — makes code rollback unsafe. Design migrations so code rollback is always safe; defer schema
cleanup to a later deploy. See **`craft-db`** → `migrations.md`.

---

## Roll back first, diagnose after

When production breaks right after a deploy, the correct order is: **roll back first, diagnose after.** The vibe-coded-MVP instinct under pressure is to hotfix forward on top of the broken deploy — patch the bug, push again, hope — which compounds the incident instead of stopping it. Every minute spent debugging on a known-broken deploy is a minute of continued user-facing failure that a rollback would have already ended.

This only works if you know the platform's actual rollback mechanism **before** you need it, under pressure — see the table in "Rollback: one step per deploy path" above. Practice or at least read the exact command for your deploy path ahead of an incident; the middle of an outage is not the time to be discovering whether it's `vercel rollback` or a dashboard button.

**Put up a status page.** Even a free hosted one (a static status page, Instatus, Statuspage.io's free tier) beats an inbox or support channel getting flooded with "is it down?" messages while you're rolling back — it gives users somewhere to look instead of somewhere to escalate.

---

## Post-deploy verification

Automation that can deploy can also verify. After every production deploy, before declaring it
complete:

1. **Hit the health and readiness endpoints** programmatically from the pipeline. A `200` from
   `/health/live` and protected `/health/ready` for Postgres (or the repo's equivalent) confirms the new instance started, connected
   to its dependencies, and is ready to serve. A failed probe should halt the pipeline and trigger
   rollback before traffic fully ramps — zero-downtime platforms with a readiness check do this
   natively. Health and readiness probe design: `craft-infra` → `runtime-health.md`.
2. **Emit a deploy marker.** Record the deploy event — timestamp, commit SHA, environment — to the
   observability backend so error-rate and latency dashboards show a vertical annotation at the
   deploy boundary. A deploy-correlated error spike becomes visible in seconds, not during
   a post-incident retrospective. Marker format and dashboard wiring: **`craft-observability`** →
   `slo-alerts.md`.
3. **Gate on an error-rate window for high-risk deploys.** On platforms that support canary /
   weighted traffic split, hold at partial traffic and gate on an error-rate window — thresholds
   and automated-rollback wiring: **craft-observability** → `slo-alerts.md`.

None of these steps requires manual human action during a normal deploy. They are automated checks in
the post-deploy job. Human intervention is the exception (an alert fires), not the workflow.

---

## CI secrets injection

Secrets used inside the pipeline — API keys, deploy tokens, signing credentials — must never appear in workflow YAML or source files. Wire them through the platform's encrypted secret store and reference them by name.

### GitHub Actions encrypted secrets

Store secrets at **Settings → Secrets and variables → Actions** in the repository (or organization). Reference them in workflow steps as `${{ secrets.MY_SECRET }}`:

```yaml
jobs:
  deploy:
    steps:
      - name: Deploy to production
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        run: fly deploy --remote-only
```

**Environment-level secrets** isolate values to a specific deployment target (e.g. `staging` vs `production`). Create an environment in **Settings → Environments**, attach secrets to it, and require the job to declare `environment: production`. This prevents a staging workflow step from reading a production secret:

```yaml
jobs:
  deploy-prod:
    environment: production        # only secrets scoped to this environment are readable
    steps:
      - run: fly deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

### OIDC / Workload Identity — no stored credentials

The recommended approach for deploying to cloud providers (AWS, GCP, Azure) is **OIDC token exchange**: GitHub acts as an identity provider, your cloud account trusts it, and the workflow receives a short-lived credential at runtime — no long-lived API key or service-account JSON stored in GitHub Secrets.

Why this matters: a stored credential is a secret that can be leaked, rotated late, and used from anywhere. A workload identity token is scoped to the specific repository, branch, and job; it expires in minutes.

**AWS (via `aws-actions/configure-aws-credentials`):**

```yaml
permissions:
  id-token: write   # required to request the OIDC JWT
  contents: read

jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsDeployRole
          aws-region: us-east-1
      # subsequent steps have AWS credentials from the assumed role — no key stored anywhere
```

Set up the IAM OIDC provider (`token.actions.githubusercontent.com`) and a role with a trust policy scoped to your repository. See the [GitHub OIDC for AWS docs](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) for the exact IAM trust-policy shape.

**GCP (via `google-github-actions/auth`):**

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: projects/123/locations/global/workloadIdentityPools/my-pool/providers/my-provider
          service_account: deploy-sa@my-project.iam.gserviceaccount.com
```

**Azure (via `azure/login` with OIDC):** configure a federated credential on the app registration and use `azure/login@v2` with `client-id`, `tenant-id`, and `subscription-id` — no client secret required.

### General rules for pipeline secrets

- **Minimum scope.** Each secret should have the narrowest permission needed: a deploy token that can push one image, not a root key. Use environment-level secrets to restrict production credentials to the production job only.
- **Rotation.** Treat pipeline secrets like production secrets: document their expiry, own their rotation. OIDC tokens rotate automatically; stored credentials do not.
- **Audit.** GitHub logs when a secret is used in a workflow step (masked in logs). Review `Security → Audit log` for unusual access.
- **Never echo secrets.** A `run: echo ${{ secrets.FOO }}` step is masked in logs but the value can leak through downstream commands or artifact uploads. Avoid it.

The schema that *declares which vars are required* is in `config.md`. This section owns the *pipeline injection mechanism*.

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| CI pipeline only runs on merge/deploy, not on PR branches | Add a PR push trigger; all five gates must run on every PR push |
| Missing a required gate (no lint, no typecheck, or no prod build job) | Add the missing job and mark it required in branch protection |
| Gates are advisory (run but do not block merge) | Set branch protection required checks; a non-blocking gate is decorative |
| Required gate is green/skipped because `if: secrets.*`, event filters, matrix rules, or `needs` bypass every substantive step | Trace trusted and restricted contexts; run the command or fail closed with a visible prerequisite error — never certify a skipped gate as green |
| Build step used as the only typecheck | Add a standalone `tsc --noEmit` (or equivalent) job — build tools skip or cache type errors |
| Tests and build run serially after lint/typecheck | Parallelize tests, build, and scan — they are independent of each other |
| No dependency vulnerability scan in the pipeline | Wire one scanner as a required check (`craft-security` → `supply-chain.md`) |
| Scanner runs but exits 0 on critical/high findings | Pass the severity-threshold flag so it exits non-zero on critical/high |
| Migrations run after traffic switches to new code | Migrations run before the deploy swap; they must be backward-compatible with the old code |
| Postgres migration run automatically in build, boot, ordinary CI, or deploy | Use a separately reviewed `db:migrate` command or `workflow_dispatch` on `DATABASE_URL_DIRECT`, staging first |
| Production schema changed with ad hoc SQL instead of the registered runner | Run the repo's reviewed migration chain and retain its apply log |
| Deploy step rebuilds from source (not from the gated artifact) | Download and deploy the artifact the build job produced |
| No rollback command documented next to the deploy command | Document the one-step rollback command per deploy mechanism |
| Code rollback fails because migration was destructive | Enforce backward-compatible schema changes; defer drops to a later deploy (`craft-db` → `migrations.md`) |
| Team hotfixes forward on a broken deploy instead of rolling back first | Roll back immediately using the documented one-step command; diagnose against the reverted, stable state |
| No status page during an incident; users flood support/inbox | Stand up a free hosted status page (Instatus, Statuspage.io free tier, or a static page) before launch |
| Manual prod edits (SSH, dashboard config edits, hot-patching) | All changes travel through the pipeline; config changes redeploy via `config.md` |
| No health/readiness probe check after deploy | Hit `/health/live` and protected `/health/ready` from the post-deploy job; fail and rollback if unhealthy (`craft-infra` → `runtime-health.md`) |
| No deploy marker emitted to observability backend | Emit commit SHA + timestamp on every deploy (`craft-observability` → `slo-alerts.md`) |
