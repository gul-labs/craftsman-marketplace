# Scale and Resilience

Every outbound call — to a database, a third-party API, a message queue, or a downstream service — is a fault boundary. Left unconstrained, a single slow dependency hangs threads, exhausts connection pools, and cascades into a full-service outage. **Wire a timeout on every call, add a retry only where the operation is idempotent, protect the downstream with a circuit breaker, and size concurrency limits to the runtime you actually have.** Serverless changes the contract fundamentally: in-process state evaporates between invocations, so any library that assumes a long-lived process (in-memory circuit-breaker state, singleton Prometheus registries, local connection pools) needs a serverless-appropriate replacement before it ships.

> **Scope split.** This file owns the resilience primitives applied at call boundaries: timeouts, retries, circuit breakers, capacity/concurrency limits, and **platform/edge capacity throttling** (the mechanism — gateway throttles, CDN-level limits, shared/edge-KV counters, and load-shedding; see the quick-reject row) — and how each maps to the actual runtime model. **Rate-limit ownership (emit once):** BE = in-app route middleware (`api-design.md`); SEC = abuse-defense policy / login throttling (`authz.md`); INFRA (this file) = platform/edge capacity; AI = LLM spend/token limits on model routes (`keys-and-spend.md`). Connection-pool sizing and the long-lived vs. ephemeral runtime distinction belong to `runtime-health.md`; env-var configuration for timeout/retry values belongs to `config.md`. The ephemerality argument from the observability angle (why in-process metrics registries don't survive invocations) is in **`craft-observability`** → `serverless-vs-server.md`. The idempotency precondition that makes retries safe is owned by **`craft-backend`** → `side-effects.md` — enforce idempotency there, reference it here.

---

## Contents

- [Timeouts on every outbound call](#timeouts-on-every-outbound-call)
- [Retries with exponential backoff and jitter](#retries-with-exponential-backoff-and-jitter)
- [Circuit breakers](#circuit-breakers)
- [Capacity and concurrency limits](#capacity-and-concurrency-limits)
- [Serverless: what breaks and why](#serverless-what-breaks-and-why)
- [Pre-launch load sanity check](#pre-launch-load-sanity-check)
- [Quick-reject checklist](#quick-reject-checklist)

---

## Timeouts on every outbound call

A call without a timeout is a call that can hang forever. The failure mode: a dependency slows down (doesn't error), threads/event-loop slots pile up waiting for it, and the service stops responding to *everything* — not just the slow path.

Set a timeout on every outbound call at every layer:

- **HTTP clients:** most HTTP libraries default to no timeout, or to a long one that isn't useful in production. Set both a connection timeout (how long to wait for the TCP handshake) and a read/response timeout (how long to wait for the response body) explicitly. In Node.js, `fetch` accepts an `AbortSignal`; `got` and `undici` expose distinct connection and response timeout knobs (`timeout.connect`/`timeout.response` in got; `headersTimeout`/`bodyTimeout` in undici). `axios`'s `timeout` option covers overall request time but not the TCP connection phase separately — for a true connection timeout in axios, configure a custom `httpAgent`/`httpsAgent` with socket timeout settings (e.g. `agentkeepalive`). Discover which client the repo uses rather than assuming. In server environments, always set a timeout shorter than the platform's own request deadline (e.g. a Lambda timeout or Vercel function limit) so the function can fail gracefully rather than being killed mid-stream.

  ```ts
  // native fetch: Node 18+; AbortController available from Node 15+
  // Cleaner one-liner (Node 17.3+): fetch(url, { signal: AbortSignal.timeout(5_000) })
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 5_000); // 5 s
  try {
    const res = await fetch(url, { signal: ac.signal });
    // ...
  } finally {
    clearTimeout(timer);
  }
  ```

- **Database clients:** For Postgres, use the role's `statement_timeout` default and transaction-local limits as the server-side authority; `pg`'s `query_timeout` is a client backstop, not a replacement. Keep the connection-acquire timeout separate from either query limit. A timeout sent as a startup parameter may be dropped by a transaction pooler, and a plain session `SET` may leak to another client. The connection pattern and transaction deadline are in `craft-db` → `connection-pooling.md`. For another database engine, verify its own timeout behavior.

- **Queue and stream consumers:** set a visibility timeout (SQS) or a processing deadline; don't let a stalled consumer hold a message invisible forever while nothing processes it.

**Where the value comes from:** put timeout values in the validated env schema (see `config.md`) or a well-named constant, not hardcoded as magic numbers spread across call sites. This makes them tunable without a code change and visible at a glance.

---

## Retries with exponential backoff and jitter

A retry on a transient failure is legitimate. A tight retry loop that slams a partially-degraded service is an unintentional DDoS. The pattern that avoids this:

1. **Exponential backoff:** each attempt waits exponentially longer than the last (`base * 2^attempt`, e.g. 200 ms → 400 ms → 800 ms → ...). This gives the downstream time to recover and reduces the thundering herd.
2. **Jitter:** add a random fraction of the wait to each delay so all retrying clients don't synchronize their retry waves. A simple full-jitter implementation: `delay = random(0, base * 2^attempt)`. AWS's "Exponential Backoff and Jitter" post is the canonical reference for the math; the point is randomization prevents synchronized storms.
3. **A cap and a limit:** cap the maximum delay (e.g. 30 s) and the maximum number of attempts (typically 3–5 for synchronous request paths). Retrying forever is not resilience.

```ts
// Sketch — not a production library, but shows the shape
async function withRetry<T>(
  fn: () => Promise<T>,
  { maxAttempts = 3, baseMs = 200, capMs = 30_000 } = {}
): Promise<T> {
  if (maxAttempts < 1) throw new Error("withRetry: maxAttempts must be >= 1");
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxAttempts - 1 || !isRetryable(err)) throw err;
      const delay = Math.min(capMs, Math.random() * baseMs * 2 ** attempt);
      await new Promise(r => setTimeout(r, delay));
    }
  }
}
```

**Retry only on retryable errors.** Network timeouts, 429 (rate-limited), 503/502 (transient upstream) are retryable. 400 (bad request), 404, 422 (validation) are not — retrying them wastes quota and delays the real error response. Write an `isRetryable` predicate against the error type and status code; don't retry blindly.

Prefer a well-maintained library over hand-rolling (e.g. `async-retry`, `p-retry`, Axios retry interceptors, AWS SDK's built-in retry strategy) — discover what's already in the repo or what the SDK provides before adding another dependency.

---

**Idempotency precondition:** do not add a retry unless the operation is idempotent — retrying a non-idempotent write creates duplicates. Confirm the idempotency contract is in place first; the mechanics (idempotency keys, dedup headers, upsert semantics) are owned by **`craft-backend`** → `side-effects.md`.

---

## Circuit breakers

A circuit breaker stops calling a dependency that is already failing, giving it time to recover and preventing the caller from accumulating request backlog. Without one, a fully-down downstream still gets hammered by every incoming request, extending its recovery and cascading load back to the caller.

The three-state model:
- **Closed (normal):** requests pass through; failures are counted against a threshold.
- **Open (tripped):** requests fail fast without hitting the downstream; the breaker waits a cooldown period.
- **Half-open (probing):** a test request is allowed through; if it succeeds the breaker closes, if it fails it re-opens.

**The serverless problem:** in-process breaker state (a `CircuitBreaker` instance in module scope) lives in one function instance and evaporates when that instance is recycled. Other instances see their own fresh state. The breaker trips in instance A while instance B keeps sending. This is not a theoretical edge case — it is the default behavior of every in-process breaker library in a serverless environment.

Serverless-appropriate circuit-breaker options:
- **Managed gateways / service meshes:** Kong (circuit-breaker plugin) or Istio/Envoy (outlier detection) can enforce circuit-breaking upstream of the function — the state lives outside your code entirely. For AWS workloads, prefer **Amazon ECS Service Connect** (native service-to-service routing, no sidecar required) or **Amazon VPC Lattice** for service-to-service routing and policy enforcement; AWS App Mesh reaches end-of-support on September 30, 2026 and has not received new features since 2023 — do not adopt it for new deployments. AWS API Gateway is not in this category; it provides throttling and usage-plan rate limiting, not circuit breaking (no open/half-open/closed state machine, no failure-rate tripping). Note: a service mesh is rarely the right first tool for an MVP — start with retry + circuit-breaker at the HTTP client level before reaching for infrastructure-layer solutions.
- **External state (Redis, DynamoDB):** track failure counts and breaker state in a shared store so all instances see the same state. Adds latency to every check; acceptable for critical dependencies, not for the hot path.
- **Bulkhead / timeout-first:** in environments where a full circuit breaker is impractical, a short timeout + concurrency limit (see below) achieves a similar blast-radius containment: the function fails fast rather than waiting on the dependency, and a concurrency cap prevents a wave of in-flight calls from piling up.

For long-lived services (Node.js on Fly, Render, a container on ECS), in-process breakers work correctly. Libraries: `opossum` (Node.js), Resilience4j (JVM), Polly (.NET). Discover the runtime before proposing one.

---

## Capacity and concurrency limits

Unbounded concurrency means a traffic spike or a slow downstream can exhaust all available resources — memory, file descriptors, DB connections — and bring the process down. Cap concurrency at each layer so the system degrades gracefully (shedding load with 429s or queue backpressure) rather than collapsing.

**Concurrency limiters:** restrict how many in-flight requests to a given dependency run simultaneously. In Node.js, `p-limit` is the standard tool for promise concurrency; worker-thread pools add parallelism for CPU-bound work. Queues and message brokers often have a prefetch/concurrency setting on the consumer — set it.

```ts
import pLimit from "p-limit";

const limit = pLimit(10); // at most 10 concurrent calls to the slow downstream

const results = await Promise.all(
  items.map(item => limit(() => callSlowDownstream(item)))
);
```

**Rate limiting and throttling:**
- **Inbound:** protect your own service from overload. Return `429 Too Many Requests` with a `Retry-After` header when a client exceeds its quota. Implement with a token-bucket or sliding-window counter; for serverless, the counter must live in Redis or an edge KV store — not in process memory for the same reason as circuit breakers.
- **Outbound:** respect upstream rate limits. Honor `429` and `Retry-After` headers from third-party APIs; your retry logic should read the header rather than using its own fixed delay when the upstream tells you explicitly how long to wait.

**Connection pool sizing** (long-lived processes only): covered in `runtime-health.md`. The relationship to scale/resilience: an undersized pool causes queueing under load (latency spikes before errors); an oversized pool overloads the DB when many instances start together.

**Shed load deliberately.** A service that returns `503 Service Unavailable` under extreme load (via a request queue depth check, a CPU/memory threshold, or a concurrency gate) is better than one that accepts every request and times out all of them. Implement a `/ready` endpoint that reflects current load capacity so upstream load balancers can stop routing before the service falls over — see `runtime-health.md` for the health/readiness probe pattern.

---

## Serverless: what breaks and why

Serverless functions (Lambda, Vercel Functions, Cloudflare Workers, Supabase Edge Functions) are stateless and ephemeral. Each invocation may run in a fresh process with no shared memory across invocations or concurrent instances. This invalidates several common resilience assumptions:

| Assumption | Long-lived process | Serverless |
| --- | --- | --- |
| In-process circuit-breaker state persists | Yes | No — each instance has its own state |
| In-process concurrency limiter (`p-limit`) bounds total concurrency | Yes | No — limits one instance; others are unbounded |
| Module-scope DB connection pool is reused across requests | Yes — within the process | Partially — within a warm instance; zero connections in cold starts |
| Singleton retry state (attempt count) is safe | Yes | Yes — retry is per-invocation, scope is fine |

**Cloudflare Workers and Supabase Edge Functions (Deno Deploy)** use a V8 isolate model where a single isolate may handle multiple sequential requests, persisting module-scope state across them. An in-process circuit breaker in Workers will accumulate failure counts within one isolate's lifetime — but concurrent requests may land in different isolates, each with independent state. The practical recommendation is the same (don't rely on in-process state for global coordination) but the failure mode differs from Lambda's: it is inconsistent across concurrent isolates rather than always-fresh.

**The discovery check before wiring resilience primitives in a serverless repo:**

1. Confirm the runtime model. Look for `vercel.json`, `wrangler.toml`, `serverless.yml`, `fly.toml`, AWS SAM/CDK Lambda definitions, Supabase Functions directories. Check `package.json` adapters (`@vercel/node`, `hono`, `aws-lambda`).
2. Flag any in-process resilience library that stores state in module scope — circuit breakers, concurrency limiters, metrics registries.
3. Check connection-pool scope and sizing for the detected runtime model — especially relevant for partially-warm serverless instances where pool reuse is possible but not guaranteed. Pool-sizing under serverless is owned by `runtime-health.md`.
4. Propose the replacement: gateway-level circuit breaking, external-state breakers, platform-native rate limiting (Cloudflare Rate Limiting, Vercel's edge middleware), or a timeout + fast-fail strategy.

See **`craft-observability`** → `serverless-vs-server.md` for the metrics/observability side of this same ephemerality issue — including which metrics client and protocol to use per deployment model, and why in-process Prometheus/StatsD registries need a serverless-appropriate replacement there.

---

## Pre-launch load sanity check

Run **one** load pass before first real traffic hits the app — k6 or autocannon, roughly 50–100 concurrent users, against the critical path (signup, checkout, or whatever the app's core flow is), in a staging environment. This is a smoke test, not performance engineering: one pass at a sanity-check level, not a full performance-engineering program. Don't over-scope it into load-test tooling, dashboards, or a recurring benchmark suite — that's a separate, later effort if the app's traffic profile ever justifies it.

The consequence of skipping this: the first real traffic spike becomes the first load test, and that's how you discover connection-pool exhaustion and p95 latency collapse in front of actual users instead of in staging where it's cheap to fix. A single k6/autocannon run against the critical path surfaces the same failure modes covered above — unbounded concurrency, undersized connection pools (see "Capacity and concurrency limits") — before they're a production incident.

---

## Quick-reject checklist

Flag with `file:line` and the fix:

| Pattern | Fix |
| --- | --- |
| `fetch` / HTTP client call with no timeout | Add `AbortSignal` timeout or the client's timeout option; value from env/config |
| DB query with no statement timeout configured | Set the driver-level query timeout; confirm it's shorter than the function/request deadline |
| Retry loop with no jitter (fixed delay) | Add full-jitter: `random(0, base * 2^attempt)` |
| Retry loop with no cap on attempts or delay | Add `maxAttempts` and a delay cap (e.g. 30 s) |
| Retry on non-idempotent write without an idempotency key | Enforce idempotency key first (`craft-backend` → `side-effects.md`), then retry |
| Retry blindly on all errors (including 4xx) | Retry only on retryable status codes/error types; write an `isRetryable` predicate |
| In-process circuit breaker (`opossum` / etc.) in a serverless function | Use gateway-level breaking, external-state breaker (Redis), or timeout-first strategy |
| In-process concurrency limiter (`p-limit`) used to bound global concurrency in serverless | Acknowledge it only limits one instance; add platform-native throttle or queue depth limit |
| Inbound rate limiting stored in process memory (serverless) | Move counter to Redis / edge KV so all instances share state |
| `429` from an upstream API retried with a fixed delay ignoring `Retry-After` | Read the `Retry-After` header and use it as the delay floor |
| Timeout values hardcoded as magic numbers at each call site | Centralize in env schema / named constant; see `config.md` |
| No `/ready` degradation signal under high load | Wire a readiness check that reflects concurrency/load state (`runtime-health.md`) |
| App has never been load-tested before launch | Run one k6/autocannon pass at 50-100 concurrent users against the critical path in staging |
