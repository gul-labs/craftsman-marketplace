# Infrastructure as Code

Configuration that exists only in a dashboard is configuration you can't review, diff, or recover. **Declare infrastructure in code, store it in the repo alongside the application, and treat it as a first-class engineering artifact.** For an MVP, this usually means a platform-native config file; for a complex multi-service system it may mean Terraform or Pulumi — but start with the simplest form that fits the scale.

> **Scope split.** This file owns the *infrastructure declaration*: which tool to use, state management, and the plan-before-apply discipline. The *pipeline that runs IaC* (plan in CI, apply on merge) belongs to `ci-cd.md`. Environment-specific variable values injected at apply time belong to `config.md` (schema) and `ci-cd.md` (secrets injection). Rollback mechanics per deploy path are in `ci-cd.md`.

---

## Contents

- [Start with platform-native config](#start-with-platform-native-config)
- [Platform quickstarts](#platform-quickstarts)
- [When to reach for Terraform or Pulumi](#when-to-reach-for-terraform-or-pulumi)
- [State backends](#state-backends)
- [Plan-in-CI gate](#plan-in-ci-gate)
- [Apply-only-from-main convention](#apply-only-from-main-convention)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Start with platform-native config

Before reaching for Terraform or Pulumi, check whether the hosting platform provides a first-class config file. Platform-native configs are:

- **Simpler to onboard.** One file, no state backend, no provider plugins.
- **Sufficient for most MVPs.** They express the resources the platform manages natively (instances, scaling, routes, env var schema, mounts) without needing to model shared cloud primitives.
- **Automatically version-controlled.** The file lives in the repo; `git diff` shows every infrastructure change.

Reach for Terraform or Pulumi when you need multi-cloud resources, custom networking, shared infrastructure across many services, or resources the platform doesn't expose in its own config format.

---

## Platform quickstarts

Discover the config file convention for the platform already in use before proposing a new tool.

### Fly.io — `fly.toml`

The canonical Fly config file. Every `fly launch` generates one; every `fly deploy` reads it.

```toml
# fly.toml — minimal production shape
app            = "my-app"
primary_region = "lax"

[build]
  # Dockerfile at repo root by default; override with:
  # dockerfile = "path/to/Dockerfile"

[env]
  PORT     = "8080"
  LOG_LEVEL = "info"
  # SECRET values (DATABASE_URL, AUTH_SECRET, etc.) are set via:
  #   fly secrets set KEY=value
  # Never put secret values in fly.toml — they appear in git history.

[http_service]
  internal_port       = 8080
  force_https         = true
  auto_stop_machines  = true
  auto_start_machines = true
  min_machines_running = 0      # scale-to-zero; set to 1+ for always-on

  [http_service.concurrency]
    type       = "requests"
    hard_limit = 200
    soft_limit = 150

[[vm]]
  memory      = "512mb"
  cpu_kind    = "shared"
  cpus        = 1

[checks]
  [checks.health]
    grace_period = "5s"
    interval     = "15s"
    method       = "GET"
    path         = "/health/live"
    port         = 8080
    timeout      = "2s"
    type         = "http"
```

Secrets: `fly secrets set DATABASE_URL="postgres://..."` — stored encrypted in Fly's secret store, injected as env vars at runtime. Never in `fly.toml`. For Postgres, keep this native unauthenticated probe on `/health/live`; monitor the protected `/health/ready` separately with `HEALTH_MONITOR_SECRET`.

These native `/health/live` examples check process availability. A separate protected readiness
monitor alerts on a database failure but **does not remove an instance from traffic**. If the
deployment requires dependency-based routing, wire `/health/ready` through a provider-supported
private or authenticated readiness mechanism and verify a failing probe stops new requests.
Do not publish DB details or pool counts to make a public native health check serve as readiness.

### Render — `render.yaml`

Render's infrastructure-as-code format. A `render.yaml` at the repo root unlocks Render's "Blueprint" feature — the entire service definition (instance type, region, env var schema) is declared and version-controlled.

```yaml
# render.yaml
services:
  - type: web
    name: my-app
    runtime: node
    region: oregon
    plan: starter
    buildCommand: npm ci && npm run build
    startCommand: node dist/server.js
    healthCheckPath: /health/live
    envVars:
      - key: NODE_ENV
        value: production
      - key: PORT
        value: 10000
      - key: DATABASE_URL
        sync: false     # marks as a secret — Render prompts for the value in the dashboard
      - key: AUTH_SECRET
        sync: false
```

`sync: false` means "this is a secret; do not store the value in the YAML file." Render manages the value separately.

### Railway — `railway.toml`

Railway's config file for service settings, build configuration, and deploy options.

```toml
# railway.toml
[build]
  builder = "nixpacks"      # or "dockerfile"
  buildCommand = "npm ci && npm run build"

[deploy]
  startCommand = "node dist/server.js"
  healthcheckPath = "/health/live"
  healthcheckTimeout = 100
  restartPolicyType = "on_failure"
  restartPolicyMaxRetries = 3
```

Environment variables (including secrets) are managed in the Railway dashboard or via the CLI — not in `railway.toml`. Railway also supports variable references between services within a project.

### Vercel — `vercel.json`

Vercel's project configuration file. Controls routing, build settings, headers, redirects, and function configuration.

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "installCommand": "npm ci",
  "functions": {
    "api/**/*.ts": {
      "maxDuration": 10
    }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

Environment variables (including secrets) are set in the Vercel dashboard under **Settings → Environment Variables**, scoped to `development`, `preview`, or `production`. They are never stored in `vercel.json`.

---

## When to reach for Terraform or Pulumi

Use a general-purpose IaC tool when:

- You manage resources outside the platform's native config (custom VPC, RDS, S3 buckets, IAM roles, DNS, CDN distributions).
- You share infrastructure across multiple services and need a single source of truth.
- You need cross-cloud resources.
- The platform doesn't provide a native config file format.

**Terraform** (HCL, most ecosystem tooling, widest provider support):

```hcl
# terraform/main.tf — minimal example: S3 bucket with versioning
resource "aws_s3_bucket" "uploads" {
  bucket = "my-app-uploads-${var.environment}"
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

**Pulumi** (TypeScript/Python/Go — IaC in your app language, full type safety):

```ts
// pulumi/index.ts
import * as aws from "@pulumi/aws";

const bucket = new aws.s3.BucketV2("uploads", {});

// Versioning is a separate resource, mirroring the Terraform example above —
// the inline `versioning` arg on BucketV2 is deprecated.
new aws.s3.BucketVersioningV2("uploads", {
  bucket: bucket.id,
  versioningConfiguration: {
    status: "Enabled",
  },
});

export const bucketName = bucket.id;
```

Both tools require a **state backend** (see below) and a **plan-before-apply discipline** (see below). Neither is a reason to skip the platform-native config step — if Fly or Render handles your hosting, don't add Terraform just to manage it.

---

## State backends

Terraform and Pulumi track which cloud resources they manage in a **state file**. Losing or corrupting it means the tool loses track of what exists — dangerous and tedious to recover from. Never store state locally in a team or CI environment.

### Terraform

**Native S3 locking (Terraform >= 1.10, current recommended approach):** the S3 backend can now lock
state natively, without a separate DynamoDB table:

```hcl
# terraform/backend.tf
terraform {
  backend "s3" {
    bucket       = "my-app-tf-state"
    key          = "infra/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true   # native S3 locking — Terraform >= 1.10
  }
}
```

`use_lockfile = true` uses a lock file in the same S3 bucket instead of a DynamoDB table — one less
piece of infrastructure to provision and pay for. DynamoDB-based locking (below) is deprecated
starting with Terraform 1.11; new setups should prefer `use_lockfile`.

**Remote S3 + DynamoDB lock (legacy, Terraform < 1.10 or existing setups):**

```hcl
# terraform/backend.tf
terraform {
  backend "s3" {
    bucket         = "my-app-tf-state"
    key            = "infra/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "my-app-tf-lock"   # prevents concurrent applies
  }
}
```

The DynamoDB table provides a distributed lock so two concurrent `terraform apply` runs don't corrupt state. The S3 bucket should have versioning enabled so you can recover a previous state if a partial apply leaves things inconsistent. This pattern still works on current Terraform versions, but new setups on Terraform >= 1.10 should use `use_lockfile` instead.

Terraform Cloud and HCP Terraform are managed alternatives — they host state, provide a run UI, and enforce sequential applies without self-managing the backend.

### Pulumi

**Pulumi Cloud (managed, recommended for most teams):** state is stored in Pulumi's hosted backend; no self-managed infrastructure needed. Free tier covers most small projects.

**Self-managed backend:** Pulumi supports S3, Azure Blob Storage, or GCS as state backends (`pulumi login s3://my-bucket`). Use the same DynamoDB lock pattern (via Pulumi's S3 backend configuration) if running in a team context.

### Fly.io / Render / Railway / Vercel (platform-native config)

The platform **is** the state. The `fly.toml` / `render.yaml` / `railway.toml` / `vercel.json` describes desired state; the platform reconciles it on deploy. There is no separate state file to manage — this is one of the practical advantages of staying within platform-native config for as long as it fits.

---

## Plan-in-CI gate

**Never apply infrastructure changes without reviewing a plan artifact first.** A plan shows exactly which resources will be created, modified, or destroyed — a destruction you didn't intend is caught in review, not during an incident.

The gate:

```yaml
# GitHub Actions — Terraform plan on every PR
jobs:
  tf-plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init
        working-directory: terraform/

      - name: Terraform Plan
        id: plan
        run: terraform plan -out=tfplan -no-color 2>&1 | tee plan.txt
        working-directory: terraform/

      - name: Post plan summary to PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const plan = fs.readFileSync('terraform/plan.txt', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '```\n' + plan.slice(-60000) + '\n```'  // GitHub comment size limit
            });
```

Key rules:
- The plan runs on every PR touching IaC files.
- The plan artifact (`tfplan`) is uploaded and passed to the apply step — apply must consume the exact artifact the plan produced, not re-plan.
- A plan that destroys a production resource requires explicit human approval before apply.
- For Pulumi: `pulumi preview` is the equivalent of `terraform plan`.

---

## Apply-only-from-main convention

Infrastructure applies run only from the `main` (or release) branch, never from PR branches. The separation:

- **PR branch:** `terraform plan` / `pulumi preview` — read-only, safe to run on every push.
- **Main branch (after merge):** `terraform apply` / `pulumi up` — mutates cloud resources.

This prevents concurrent applies from multiple PR branches corrupting state and ensures every infrastructure change is reviewed before it reaches production.

```yaml
# Apply job — only runs on main after all gates pass
jobs:
  tf-apply:
    needs: [tf-plan, other-gates]
    if: github.ref == 'refs/heads/main'
    environment: production    # requires environment-level approval in GitHub
    steps:
      - name: Download plan artifact
        uses: actions/download-artifact@v4
        with:
          name: tfplan

      - name: Terraform Apply
        run: terraform apply -auto-approve tfplan
        working-directory: terraform/
```

For high-stakes production environments, add a GitHub environment approval gate so the apply cannot proceed without a human review after the plan is inspected.

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| Infrastructure configured only in the platform dashboard (no config file) | Add the platform-native config file (`fly.toml`, `render.yaml`, `railway.toml`, `vercel.json`) to the repo; treat it as the source of truth |
| Terraform or Pulumi state stored in a local file or committed to the repo | Move to a remote state backend (S3 + DynamoDB for Terraform; Pulumi Cloud or S3 for Pulumi) immediately |
| `terraform apply` runs without a prior `terraform plan` review | Add a plan-in-CI gate; apply must consume the exact plan artifact, not re-plan |
| Apply runs from a PR branch, not from `main` | Restrict apply to the main branch; use branch protection and environment approval gates |
| Secret values committed in `fly.toml`, `render.yaml`, or other IaC files | Remove immediately; rotate the exposed values; store secrets via the platform's secret mechanism (`fly secrets set`, Render `sync: false`, Vercel environment variables) |
| Reaching for Terraform before trying platform-native config | Start with the platform's config file; add Terraform only when resources outgrow what the platform manages natively |
| No locking configured for a shared Terraform S3 backend | On Terraform >= 1.10, add `use_lockfile = true` (native S3 locking); on older versions, add a DynamoDB lock table — without one, concurrent applies from CI and a local machine can corrupt state |
| IaC changes merged without a plan reviewed | Require the plan step as a required CI check on PRs; post the plan output as a PR comment for human review |
| Pulumi `pulumi up` run locally against production state | Use Pulumi Cloud or enforce apply-only-from-CI via OIDC; local applies bypass CI gates |
