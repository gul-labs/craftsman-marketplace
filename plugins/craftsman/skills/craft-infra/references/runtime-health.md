# Runtime Health

A service that can't tell its orchestrator whether it's alive — or whether it's ready to take
traffic — forces that orchestrator to guess, and the guess is wrong in every interesting failure
case. The discipline: **expose distinct health and readiness endpoints, drain in-flight requests on
shutdown, and size connection pools to match the runtime model you're actually running in.** Getting
these wrong is the difference between a rolling deploy that users never notice and one that sheds
traffic for ninety seconds.

> **Scope split.** This file owns runtime-level self-reporting: health/readiness probe contracts,
> SIGTERM/graceful-drain patterns, runtime-model scoping for connection pools (serverless vs
> long-lived vs edge), and scheduled-job/queue-worker deployment basics. The pool **sizing math**,
> pgBouncer/proxy configuration, and driver settings belong to **`craft-db`** →
> `connection-pooling.md` — this file only decides how the runtime model constrains pool *shape*, not
> the numbers. The broader runtime-model trade-offs (timeouts, retries, circuit breakers, capacity
> limits for serverless vs long-lived) live in `scale-resilience.md`. Environment-level configuration
> (which vars control timeouts and pool sizes) lives in `config.md`. The observability side — health
> feeding alert rules, SLO windows, and the ephemeral-process caveat for metrics — belongs to
> **`craft-observability`** → `slo-alerts.md` and `serverless-vs-server.md`. Side-effect ordering
> during initialization that can break a readiness probe, and job-handler idempotency, belong to
> **`craft-backend`** → `side-effects.md`.

---

## Contents

- [Health vs readiness — the distinction matters](#health-vs-readiness--the-distinction-matters)
- [What each probe checks](#what-each-probe-checks)
- [Probe contract (response shape + timing)](#probe-contract-response-shape--timing)
- [Graceful shutdown and SIGTERM draining](#graceful-shutdown-and-sigterm-draining)
- [Connection pools and the runtime model](#connection-pools-and-the-runtime-model)
- [Pool exhaustion — symptoms and fixes](#pool-exhaustion--symptoms-and-fixes)
- [Scheduled jobs and queue workers](#scheduled-jobs-and-queue-workers)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Health vs readiness — the distinction matters

These two probes answer different questions and are consumed differently:

- **Health (`/health`, `/healthz`)** — "Is the process alive and not irreparably broken?" A failing
  health check means the orchestrator should *restart the container* (in Kubernetes: the kubelet
  restarts the failing container; the pod itself is not evicted or rescheduled unless the restart
  policy and backoff trigger further action). It should be as cheap as a heartbeat: confirm the
  event loop is unblocked and the process hasn't entered a broken state. It should almost never fail
  during normal operation — if it's flapping, the service is unstable, not temporarily busy.

- **Readiness (`/ready`, `/readyz`)** — "Is this instance ready to receive new traffic right now?"
  When the orchestrator actually uses this probe for routing, a failure makes the load balancer
  *stop sending new requests* to this instance without killing it. An external monitor that calls
  the same endpoint only alerts; it does not remove the instance from rotation. Readiness can
  legitimately return `503` during startup (while
  the required schema version is not yet present, warm-up queries execute, or caches hydrate), during graceful shutdown (draining),
  and during transient overload — without triggering a kill-and-replace cycle.

Conflating them into a single `/health` endpoint is the most common mistake. When health and
readiness are the same check, a temporarily-not-ready instance gets killed and restarted instead of
just being taken out of rotation — amplifying the problem under load. Some frameworks also expose a
**liveness** probe (Kubernetes terminology) which is equivalent to health above; confirm what your
orchestrator calls each one and wire them correctly.

---

## What each probe checks

**Health / liveness** — answer yes/no on the process being usable:

- Process is alive (the endpoint responding is already most of this).
- No detected deadlock or unresponsive event loop (Node.js: a simple `setTimeout`-based loop timer
  works as a canary; Go: each request runs in its own goroutine, so a responding handler confirms
  the runtime scheduler is live. Note that partial deadlocks — individual goroutines blocked on a
  mutex or channel — will not be detected; only all-goroutine deadlocks cause the runtime to panic).
- No unrecoverable error that requires a restart (e.g. a recovered panic that corrupted shared
  state, an uncaught exception that corrupted internal state). Track these explicitly; don't infer
  from absence. Unrecovered Go panics crash the process; they show up as a container restart, not
  as a liveness-probe failure.

Health should **not** check external dependencies (database, cache, third-party APIs). A Redis
outage is not a reason to kill every pod — the app should degrade gracefully. Pulling external-dep
checks into health conflates your health with the health of every downstream service.

**Readiness** — answer yes/no on this instance being fit to handle the *next* inbound request:

- Required external dependencies are reachable. This is where the DB ping, cache connectivity check,
  or downstream service health check *belongs* — because if the DB is unreachable, the instance
  can't serve requests usefully and should be drained, but should not be killed.
- Startup phase complete (migrations applied, caches hydrated, warm-up done) — return `503` until
  this finishes, then flip to `200`.
- Draining in progress — return `503` during graceful shutdown (see below) so the LB drains this
  instance naturally.

Keep dependency checks in the readiness probe *lightweight*: a `SELECT 1` / `PING`, not a
full-table query. Expensive checks extend the probe response time past the orchestrator's timeout
and cause false negatives that flap the probe.

---

## Probe contract (response shape + timing)

Orchestrators (Kubernetes, ECS, Fly, Render, Cloud Run — discover which you're on from the repo's
IaC/platform config) consume probes by HTTP or TCP. Some platforms expose only one native
health-check URL. The app can still expose separate liveness and protected readiness routes,
but the native check observes only the route it is configured to call. Document whether it
controls routing or only restart/deploy status; a separate monitor is alerting, not routing.
The minimum contract:

- **`200 OK`** = alive / ready. `5xx` or connection failure = not alive / not ready. Some platforms
  also accept `204`; check your platform's docs.
- **Respond within the probe timeout.** Kubernetes defaults: `timeoutSeconds: 1`, `failureThreshold: 3`,
  `periodSeconds: 10` — but these are often tuned per service. A probe that takes 800 ms on a
  `timeoutSeconds: 1` setting will false-positive on any load spike. Confirm the values in the
  deployment manifest.
- **Include a JSON body for observability** (optional, but useful when debugging in prod):

  ```json
  {
    "status": "ok",
    "checks": {
      "db": "ok",
      "cache": "ok"
    },
    "uptime": 3821
  }
  ```

  Return `"degraded"` or a specific check status when something is marginal — so a human reading
  the probe can distinguish a real failure from a slow dependency without grepping logs. The body is
  irrelevant to the orchestrator; it's for you. The structured check statuses in this body are what
  alert rules can consume — see **`craft-observability`** → `slo-alerts.md` for how health gates
  map to SLO burn-rate windows.

- **Probe endpoints bypass user-session authentication middleware.** Wire them before that guard
  in route registration. For a Postgres readiness probe, require a dedicated monitor secret and
  configure the monitor to send it; do not expose DB state and pool counts publicly. Liveness
  remains a cheap process check without a DB call.

For projects adopting `craft-db` → `postgres-standard.md`, use `/health/live` without DB access
and `/health/ready` with `SELECT 1` on the
**shared** pool, a 2–5 s client-side budget, and `HEALTH_MONITOR_SECRET`. Return pool counts in
the protected readiness response. A fresh one-shot client can report green while the real pool is
exhausted. If the platform's native probe cannot send the secret, use it for liveness and configure
a separate authenticated readiness monitor; do not downgrade the readiness endpoint. In that
configuration the native probe still routes traffic to an instance whose database is down.
Record this limitation explicitly. Where dependency-based traffic gating is required, configure
a provider-supported private/authenticated readiness integration and verify that a failing DB
probe actually removes the instance from new-request routing. Never expose pool counts or DB
error details publicly to satisfy a probe limitation.

- **Do not cache probe responses.** Return fresh state on every call. A stale 200 that lingers after
  a dependency fails is worse than no probe.

---

## Graceful shutdown and SIGTERM draining

When a container/VM receives SIGTERM, the orchestrator expects the process to finish in-flight work
and exit cleanly within a deadline (Kubernetes: `terminationGracePeriodSeconds`, default 30 s). The
failure mode without proper handling: direct clients see `ECONNRESET`; clients behind a load
balancer see `502 Bad Gateway` (the LB returns 502 when the upstream closes the connection
mid-request). Either way, clients see errors during every rolling deploy.

The sequence on SIGTERM:

1. **Stop accepting new connections** — close the listening socket or remove the service from
   rotation. In Node.js: `server.close(callback)` stops accepting new connections but does not
   close idle keep-alive connections; call `server.closeIdleConnections?.()` (Node.js ≥ 18.2.0 —
   version-guard the call if the runtime version is not guaranteed) immediately *after*
   `server.close()` so the callback can fire. Without it, the callback may never be reached while
   keep-alive connections remain open. Newer Node.js versions (≥ 19) may close idle connections as
   part of `server.close()` itself — verify behavior for your runtime version. Go's
   `http.Server.Shutdown(ctx)` stops accepting new connections, closes idle keep-alive connections
   immediately, and waits for active handlers to complete — equivalent to `server.close()` plus
   `server.closeIdleConnections()` in Node.js. Do not call `process.exit()` at this point.
2. **Return `503` from the readiness probe** — if the load balancer uses that route, it drains
   traffic from this instance during the grace period. Otherwise stop accepting new requests
   through the app/server drain path; an external monitor alone cannot remove traffic. In Kubernetes,
   add a `preStop` lifecycle hook with a brief
   sleep (5 s is a common default) before the process closes its listener. Kubernetes removes the
   pod from Endpoints at SIGTERM time, but iptables propagation lag means traffic can still arrive
   for 1–2 s. The hook sleep absorbs that window.
3. **Drain in-flight requests** — wait for `server.close()`'s callback or `Shutdown()` to resolve,
   meaning all active handlers have completed.
4. **Close resource connections** — DB pool, cache client, message-consumer subscription. This is
   where you commit or roll back any open transactions before exit.
5. **Exit cleanly** — `process.exit(0)` (Node.js) or returning from `main()` (Go). If draining
   exceeds a hard deadline, exit anyway — an unclean but bounded exit beats an indefinite hang that
   forces a SIGKILL.

```js
// Node.js / Express skeleton (adapt to your framework)
const server = app.listen(PORT);

process.on('SIGTERM', async () => {
  // Step 2: fail readiness
  isReady = false;

  // Step 3: drain in-flight requests
  // server.close() stops accepting new connections; closeIdleConnections() must be called
  // AFTER server.close() so idle keep-alive connections are released and the callback can fire.
  // Version-guard: closeIdleConnections() is Node.js >= 18.2.0; newer Node may handle this
  // automatically inside server.close() — verify for your runtime.
  // Hard deadline — don't hang past the grace period.
  // clearTimeout() is called on clean drain so a normal shutdown doesn't exit(1).
  const deadline = setTimeout(() => process.exit(1), 25_000);

  server.close(async () => {
    clearTimeout(deadline); // clean drain — cancel the error-exit timer
    // Step 4: close pool / release resources
    await db.end();
    // Step 5: exit
    process.exit(0);
  });
  server.closeIdleConnections?.(); // call after server.close(), not before
});
```

Platform notes by runtime type:

- **Vercel Functions / AWS Lambda:** Do not receive SIGTERM during normal operation. The platform
  freezes the sandbox after invocation completes; a new invocation may thaw it or start a fresh
  one. Do not add SIGTERM handlers — they will never fire during normal execution. Note that Lambda
  *can* receive SIGTERM during a forced shutdown (e.g. function timeout or extension lifecycle), but
  this is not a reliable drain signal; design for invocation-scoped cleanup, not process-level drain.
- **Cloudflare Workers:** Isolated per-request; no persistent process and no SIGTERM. No drain
  handler applies.
- **Cloud Run:** Containerized (not function-as-a-service). Cloud Run instances DO receive SIGTERM
  when the platform scales down an instance. Cloud Run sends SIGTERM and then allows a short grace
  period — **10 s by default** — before SIGKILL. (`--max-instances` controls scaling, not this
  window; don't conflate the two.) This is distinct from the per-request timeout (`--timeout`): a request that
  is still in flight when SIGTERM arrives has until the grace period expires, not until the request
  timeout. Apply the full SIGTERM drain sequence above to Cloud Run services.

Don't add SIGTERM handlers to pure serverless functions (Vercel, Lambda, Workers) — they'll never
fire in the normal lifecycle. See **`craft-observability`** → `serverless-vs-server.md` for the
full breakdown of what does and doesn't apply per runtime model; `scale-resilience.md` covers the
broader runtime-model-aware design choices.

---

## Connection pools and the runtime model

This section owns *whether and how the runtime model constrains* pool shape — not the sizing math,
pgBouncer configuration, or driver settings. **For pool_size math, pgBouncer config, and driver
settings, see `craft-db` → `connection-pooling.md`.** What follows is scoping guidance only: which
model you're in changes what's even possible, before any sizing question applies.

- **Serverless instances multiply pools.** Each function instance that opens its own pool adds to
  the total connection count against the DB — 50 concurrent Lambda/Vercel instances each holding
  even a small pool can exhaust `max_connections` fast. A pool sized correctly for one instance is
  not correctly sized for N instances running the same code simultaneously. This is *the* reason
  serverless needs a connection-pooling proxy (PgBouncer, RDS Proxy, Supabase Pooler, Neon's pooled
  connection string, Supavisor) in front of the DB — see `craft-db` → `connection-pooling.md` for
  the proxy patterns and driver config.
- **Long-lived servers don't multiply the same way.** A traditional Node.js/Go/Rails/Django process
  keeps one pool per process, created lazily on first DB use and reused for the process lifetime — the
  connection count is bounded by instance count × pool size, and instance count is comparatively
  stable (not spiking per-request the way serverless concurrency can).
- **Edge runtimes can't hold Postgres TCP pools.** Cloudflare Workers, Vercel Edge Functions, and
  similar V8-isolate runtimes need a Node service for Postgres access when the project follows the
  `pg` + `drizzle-orm/node-postgres` standard. Do not add a Neon HTTP/WebSocket driver to bypass
  the pool contract.
- **Cloud Run and similar autoscaling containers also multiply pools.** Each instance serves many
  requests, but its pool still contributes to the fleet budget. With high instance concurrency,
  start at `max: 1` and raise only from measured pool wait and pooler headroom. Keep initialization
  lazy so scale-to-zero cold starts do not open an unused pool.

---

## Pool exhaustion — symptoms and fixes

Pool exhaustion is when all connections in the pool are checked out and new requests queue (or
error) waiting for one to free. It presents as:

- DB query timeouts that cluster together during load spikes, not correlated with actual DB CPU.
- Log lines like `"Connection timeout: remaining connection slots are reserved"` (PostgreSQL),
  `"too many connections"`, `"pool timeout"`, or your ORM/driver's equivalent.
- P95 latency climbing while P50 is flat — queued requests inflate the tail, not the median.
- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
  (Postgres hard limit hit).

The fix is not always "increase `max` in the pool config" — that just shifts the exhaustion to the
DB's own connection limit. Diagnose first:

1. **Check the total connection count at the DB level.** `SELECT count(*) FROM pg_stat_activity`
   (Postgres). If you're near `max_connections`, the app is opening more than the DB can handle.
2. **Check for leaked connections** — connections checked out and never returned (missing
   `finally { conn.release() }`, an uncaught exception that skips the release, or a query running
   forever). A pool of 20 with 20 "active" connections and no throughput is a leak, not contention.
3. **Check for long-running transactions** holding a connection while waiting for slow external
   calls. A DB transaction should not wrap an HTTP call to a third-party API — that can hold a
   connection for seconds. See **`craft-backend`** → `side-effects.md` for the broader pattern of
   side effects inside transactions.
4. **Right-size and proxy.** If exhaustion is real contention (not a leak): add a connection-pooling
   proxy (see above) to decouple in-process pool size from the DB's connection limit, then tune the
   proxy pool rather than the app pool.

---

## Scheduled jobs and queue workers

Job scheduling configuration is an infra concern: where the trigger lives, how the worker deploys,
and what happens under scale-to-zero. (Route-level rate limiting and the job's business logic are
`craft-backend`'s.)

**Platform cron vs in-process schedulers.** Platform-native cron — Vercel Cron, GitHub Actions
`schedule:`, a Kubernetes `CronJob` — triggers on a schedule independent of any single running
instance. An in-process scheduler (e.g. `node-cron` running inside your API server) dies with the
instance: on serverless or scale-to-zero deployments, the process that was supposed to fire the job
may simply not be running when the schedule says it should. Platform cron is the correct default on
serverless; in-process schedulers are only safe on a guaranteed always-on long-lived process, and
even then a restart or deploy can miss a tick.

**Queue-worker deployment basics.** For background job processing off a queue (SQS, BullMQ/Redis,
Cloud Tasks):

- **Concurrency** — how many jobs a single worker instance processes in parallel. Size it against
  the job's resource profile (CPU-bound vs I/O-bound) and the DB connection budget the worker's own
  pool consumes — see `craft-db` → `connection-pooling.md`.
- **Visibility-timeout alignment** — the queue's visibility/lease timeout must exceed the job's
  actual worst-case duration. A timeout shorter than the job means the message becomes visible to
  another worker before the first one finishes, causing duplicate processing.
- **Scale-to-zero pitfalls** — a worker that scales to zero when the queue is empty adds cold-start
  latency to the next job and, if the trigger is invocation-based (e.g. Lambda-per-message), can
  create the same pool-multiplication problem as serverless request handlers. Confirm the scaling
  model matches the job's latency tolerance.

**At-least-once delivery is the default expectation** for virtually every queue technology — a
message can be delivered more than once (a worker crash after processing but before acknowledging,
a visibility-timeout race). Handlers must be idempotent: processing the same message twice must
produce the same end state as processing it once. The idempotency mechanics (dedup keys, upsert
semantics) are owned by **`craft-backend`** → `side-effects.md` — this file only owns the deployment
shape the worker runs in.

---

## Quick-reject checklist

| Pattern | Fix |
| --- | --- |
| Single `/health` endpoint doing double duty for both liveness and readiness | Split into separate routes; Postgres projects use `/health/live` and protected `/health/ready` |
| Health probe checks DB connectivity | Move external-dep checks to readiness; health should be a process-level heartbeat only |
| Readiness probe runs an expensive query (e.g. table scan, slow JOIN) | Replace with a lightweight `SELECT 1` / `PING` |
| Liveness gated behind user auth, or Postgres readiness left public | Bypass user auth for liveness; protect detailed Postgres readiness with `HEALTH_MONITOR_SECRET` |
| No SIGTERM handler; process exits mid-request during deploys | Add drain logic: `server.close()` → resource cleanup → `process.exit(0)` with a hard deadline |
| SIGTERM handler in a serverless function (Vercel, Lambda, Workers) | Remove it — the platform controls lifecycle; see `craft-observability` → `serverless-vs-server.md` for the full breakdown, and `scale-resilience.md` for broader runtime-model trade-offs |
| DB pool constructed inside the request handler (new client per request) | Use one lazy, process-cached singleton pool |
| Serverless Postgres pool starts above `max: 1` without wait evidence | Use the transaction pooler, start at 1, and record fleet budget and measured wait before raising (at most 5) |
| No `connectionTimeoutMillis` / `idleTimeoutMillis` configured | Set both so stale connections are reaped after a DB restart (declare in the env schema — see `config.md`) |
| Long-running transaction wrapping an external HTTP call | Move the side-effecting call outside the transaction (`craft-backend` → `side-effects.md`) |
| Pool exhaustion diagnosed as "increase max" without checking for leaks | Audit for unreleased connections first; proxy before raising limits |
| Probe response body cached or served from a stale snapshot | Return fresh state on every probe call |
| In-process scheduler (`node-cron`, etc.) used to trigger jobs on serverless/scale-to-zero | Switch to platform cron (Vercel Cron, GitHub Actions `schedule:`, K8s `CronJob`) |
| Queue visibility/lease timeout shorter than the job's worst-case duration | Increase the timeout past worst-case job duration to avoid duplicate delivery |
| Queue/job handler not idempotent under at-least-once delivery | Add a dedup key or upsert semantics (`craft-backend` → `side-effects.md`) |
