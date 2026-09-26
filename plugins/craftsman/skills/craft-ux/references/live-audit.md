# Live Audit (Pass 2) — Driving the Real App

The static pass (`review-protocol.md`) reads source and catches everything that's grep-verifiable.
This pass catches what only the running app can show: **contrast in context, focus rings as actually
drawn, layout shift as felt, the empty/error/loading states as experienced, and real breakpoints.**
Code review proves a `focus-visible:ring-2` class exists; only the live pass proves the ring is
visible against *that* background, in *that* state, at *that* width. Run this when the product must
look polished, or when the user says "actually test it", "click through it", or "check it in the
browser".

> **Pairs with:** `review-protocol.md` — Pass 1 (static) produces findings; this is Pass 2 (live)
> that deepens them. **Same severity model** (Critical→🔴, Important→🟡, Opportunities→🟢 by the
> identical "can a real user complete their task?" test). **Emission path follows the dual-emission
> rule in `review-protocol.md` → Output Format:** under `craft-audit` / writing
> `.craftsman/**/findings.md`, emit canonical workspace findings headings — not punch-list tables as
> the durable record. Standalone reviews may keep the punch-list tables. This file adds *evidence from
> a running app*; it does not redefine severity.

> **Scope.** This pass observes and reports — it does not write fixes, and it is **not** a functional
> test suite. It walks real flows to surface *UX/visual* defects a human would feel. Functional
> correctness, business-logic assertions, and regression coverage belong to the project's e2e tests,
> not here.

---

## Contents

- [Lightweight visual checks versus flow audits](#lightweight-visual-checks-versus-flow-audits)
- [When to run it](#when-to-run-it)
- [Tooling](#tooling)
- [Preflight — gate before you touch the app](#preflight--gate-before-you-touch-the-app)
- [Setup — boot and orient](#setup--boot-and-orient)
- [What only the live pass can catch](#what-only-the-live-pass-can-catch)
- [The walk — flows × breakpoints × states](#the-walk--flows--breakpoints--states)
- [Capturing evidence](#capturing-evidence)
- [Safety rails](#safety-rails)
- [Merging into the report](#merging-into-the-report)
- [Quick-reject checklist](#quick-reject-checklist)
- [Limitations](#limitations)

---

## Lightweight visual checks versus flow audits

A build/polish task uses `visual-design.md` for a rendered desktop/mobile check of the changed
surface. A local static component preview or screenshots need no account, seeded tenant, or full
flow matrix. The preflight below applies when this deeper audit drives an application and may
reach stateful flows; it must not block inspection of an inert local specimen.

For a lightweight check, use an inert specimen, an already running preview, supplied screenshots,
or read-only inspection of the user-requested page. Record the URL/context and do not submit forms
or change data to obtain a screenshot. Before starting a local preview, inspect the documented
startup command for migrations, seeding, or outbound side effects. Start an ordinary local UI dev
server within the authorized build scope; if startup has consequential effects outside that scope,
use an inert preview or request the missing authorization. Localhost alone does not prove isolation.
Authenticating, forcing states, or driving stateful flows invokes the deeper preflight below.

## When to run it

- The static pass is done and the surface is high-stakes (the portal, onboarding, checkout — the
  paths where polish is the product).
- The user asks to *experience* it: "test the flow", "click through onboarding", "see it on mobile",
  "does the dark mode actually look right".
- A static finding is *suspected but unconfirmable from code* — e.g. "skeleton dimensions don't match
  content" or "contrast may be low on the hover state". The live pass resolves the doubt instead of
  guessing the severity.

Don't run it speculatively. It costs a running app and real interaction time; reach for it when
rendered truth changes the verdict.

---

## Tooling

Two interchangeable drivers — discover which fits the environment:

- **`claude-in-chrome` MCP** (default when available): `tabs_context_mcp` to see open tabs,
  `tabs_create_mcp` for a fresh tab, `navigate`, `computer` for click/type/scroll, `read_page` /
  `get_page_text` to inspect the DOM, `resize_window` for breakpoints, `read_console_messages` and
  `read_network_requests` for errors behind the UI, `gif_creator` to record a flow for the user.
  Load them in **one** `ToolSearch` call (the core set + `resize_window` for breakpoints).
- **Playwright** (when the repo already has it, or in CI/headless): script the same walk; use
  `page.screenshot`, `page.setViewportSize`, `page.emulateMedia({ reducedMotion, colorScheme })`,
  and `getByRole` to assert accessible names.

Always start with `tabs_context_mcp` — reuse a tab only if the user points at one; otherwise open a
fresh tab. Never reuse a tab id from a previous session.

---

## Preflight — gate before you touch the app

Stop and clear every item below *before* the first navigation or login. This pass logs in as a real
user and forces empty/loading/error states with real-looking data; against an environment wired to
live email, billing, webhooks, or shared customer-like data that can send mail, charge cards, fire
webhooks, or corrupt audit state — even though the pass is only meant to *observe*. Do not start
until:

- [ ] **Environment classified, and it is not production.** Confirm the base URL is local or a
      dedicated staging/preview — never prod. If you can't tell, ask; don't guess.
- [ ] **Throwaway identity.** A seeded/disposable account and, for multi-tenant apps, a throwaway
      tenant/workspace you may freely mutate — not a real customer's.
- [ ] **Outbound side effects neutralized.** Email, SMS, billing/payments, and webhooks are stubbed,
      sandboxed, or disabled in this environment. If they aren't, treat every flow that can trigger
      them as unsafe (below).
- [ ] **Flows triaged read-only vs state-changing.** List which flows you'll walk are safe to drive
      (navigation, viewing, opening forms) vs state-changing (submit, pay, send, invite, delete).
- [ ] **State-changing paths need explicit authorization.** Walk only read-only paths by default;
      drive a state-changing one only after the user okays that specific path. Note any data you
      created so it can be cleaned up.

If any box can't be checked, report what's blocking and stop — an unobservable-safely app is a
finding in itself, not a reason to push ahead.

---

## Setup — boot and orient

1. **Get the app running and the base URL.** Discover and inspect the dev command
   (`package.json` scripts and their startup effects) and the port. Start it within the authorized
   scope using the lightweight startup rules above, or obtain the missing environment/authorization.
   Confirm the actual URL; never assume `localhost:3000`.
2. **Log in as the throwaway account** from preflight (find the test-credential convention — `.env`,
   a seed script, a documented test account). Log in through the actual form — the login screen is
   itself in scope.
3. **Map the flows from the app, not from memory.** Read the route tree / nav to enumerate the real
   primary flows (e.g. onboarding, the main create/compose action, the main list/calendar/dashboard,
   settings/connections). Discover them — do not hardcode another project's flow names.
4. **Set a deterministic baseline.** Note viewport, theme, and whether `prefers-reduced-motion` is
   on, so findings are reproducible ("🔴 at 375px, dark mode").

---

## What only the live pass can catch

These are invisible to source-reading and are the whole reason this pass exists:

- **Aesthetic coherence.** Apply `visual-design.md` to the rendered composition: hierarchy,
  color distribution, surface depth, card anatomy, type, crop, and responsive rhythm. Passing
  interaction checks does not establish that the result meets the visual brief.
- **Contrast in context.** A token may pass a contrast formula in the abstract, but the real defect
  is text over a *gradient*, over an *image*, on a *hover/active* background, or in a *disabled*
  state. Read the rendered colors, not the class names.
- **Focus-visible as drawn.** Tab through every interactive element and watch where the ring lands —
  rings clipped by `overflow-hidden`, the same color as the background, or missing on a custom
  control are all live-only findings.
- **Layout shift as felt.** Watch the page settle: fonts swapping, images reserving no space,
  skeletons a different size than the content they become, content jumping when async data lands.
  CLS is a number; here you *see* the jump.
- **States as experienced.** Force the empty list (new account), the loading state (throttle the
  network), and the error state (kill the network / hit a failing call). The static pass proves an
  `error.tsx` exists; this proves it's not a blank white box.
- **Real breakpoints.** Resize to 375 / 768 / 1280+. Horizontal scroll, overlapping elements,
  off-screen CTAs, and untappable targets only appear at a real width with real content.
- **Real-data overflow.** Long names, empty fields, huge numbers, RTL strings — paste them in and
  watch truncation, wrapping, and `min-w-0` behave (or not).
- **Motion in motion.** Jank, wrong `transform-origin`, animations that ignore
  `prefers-reduced-motion` — only visible while they play.

---

## The walk — flows × breakpoints × states

For each primary flow, walk it at each breakpoint, forcing each state. Don't test the cartesian
product exhaustively — prioritise the high-traffic flow × the most-likely-broken axis.

| Axis | Values to cover |
| --- | --- |
| **Flow** | The real primary flows discovered in setup (auth, onboarding, main create action, main list/detail, settings/connections) |
| **Breakpoint** | 375 (mobile), 768 (tablet), 1280+ (desktop) — at minimum the smallest and the default |
| **Theme** | Light and dark, if the app supports both |
| **State** | Populated, **empty**, **loading**, **error** — force the three that don't show by default |
| **Input** | Keyboard-only pass (Tab/Shift-Tab/Enter/Esc); **activate the skip link and confirm focus actually moves to content** — on a normal route *and* on the error / 404 / empty states; `prefers-reduced-motion: reduce` |

For each cell: drive the interaction, observe, and file any defect with the *condition* attached
("🟡 — connections list overflows horizontally at 375px with a long workspace name").

---

## Capturing evidence

- **Capture a representative page and detail views**, then screenshot each defect, not just describe it — a rendered frame is the proof a code citation
  can't give. Name files for what they show (`onboarding-step2-375-overflow.png`).
- **Record the flow** with `gif_creator` when the issue is motion/sequence-dependent; capture a few
  frames before and after the action so playback reads cleanly.
- **Pull console + network** (`read_console_messages`, `read_network_requests`) when the UI looks
  wrong — a silent failed request often explains a stuck spinner or empty state.
- **Still cite `file:line`.** Where a live defect maps to a source line, name it so the fix is
  actionable — the live pass *complements* the static citations, it doesn't abandon them.

---

## Safety rails

The live pass acts on a real app — treat it like production access even when it isn't. These rails
assume the **Preflight gate above** already passed (env classified, throwaway identity, outbound
side effects neutralized, flows triaged); they're the in-flight discipline on top of it:

- **Never run against production.** Use local/staging with seeded or throwaway data.
- **Don't trigger destructive actions** (delete, cancel-subscription, send, pay) unless the user
  explicitly authorises it — and warn first. A misclick here has real consequences.
- **Avoid native dialogs.** `alert`/`confirm`/`prompt` and `beforeunload` block the automation
  channel and freeze the session. Don't click controls that fire them; if one appears, tell the user
  it needs manual dismissal.
- **Don't rabbit-hole.** If a page won't load, a control won't respond, or the driver errors after
  2–3 tries, stop and report what you attempted — don't loop.

---

## Merging into the report

Live findings join the **same severity model** the static pass uses (see `review-protocol.md` →
Output Format and dual-emission callout). Two evidence sources, one ranking:

- File each finding under 🔴 Critical / 🟡 Important / 🟢 Opportunity by the identical user-blocking
  test. A ring invisible against its background at 375px in dark mode is 🔴 if a keyboard user is
  blocked, 🟡 if degraded.
- **Under craft-audit:** write each live finding into `.craftsman/**/findings.md` with the canonical
  workspace heading + required fields (condition tag goes in **Technical:** or the plain-language
  line). Do not treat the punch-list tables as the durable record.
- **Standalone:** merge into the same punch list as the static pass. Tag live-only findings with
  their reproduction condition by prefixing the Issue in brackets — `[375px · dark · empty-state]`.
- If both passes ran, say so in the Overall Assessment / session summary ("static + live"); if only
  static ran, the report must not imply rendered behaviour was verified.

---

## Quick-reject checklist

Flag with the rendered condition (and `file:line` where it maps to source):

| Pattern (observed live) | Fix |
| --- | --- |
| Focus ring invisible / clipped / same color as background | Replace the `focus-visible:ring-*` token or lift `overflow-hidden`; cite the element |
| Text fails contrast over a gradient / image / hover state | Add a scrim or swap the token for that context |
| Skeleton size ≠ loaded content (visible jump) | Match skeleton dimensions to real content |
| Empty state is a blank box, not a designed state | Add the empty state (`layer-4-states.md`) |
| Error state is a white screen / framework default | Add a real `error` boundary with recovery |
| Horizontal scroll / off-screen CTA at 375px | Fix the layout at the smallest breakpoint |
| Long real data breaks truncation / wrapping | Add `truncate` + `min-w-0` on the flex child |
| Animation ignores `prefers-reduced-motion` | Gate motion behind the media query |
| Skip link present but focus doesn't move (no `#main-content` target on this tree, esp. error/404) | Add one `<main id="main-content">` to that tree's render (`layer-3-components.md` → skip-link unit) |
| Spinner stuck — silent failed request in network log | Surface the error in the UI; fix the call |
| Destructive action with no confirm (observed) | Add confirmation; note it was *not* triggered in audit |

---

## Limitations

- **Observes, doesn't prove correctness.** This pass surfaces what a careful human would *feel*; it
  is not a functional/e2e suite and doesn't replace one.
- **Not a substitute for human expert review** on a flagship surface — it raises the floor, it
  doesn't certify taste.
- **Driver-dependent.** Findings are only as good as the app state you could reach; if you couldn't
  log in or reach a flow, say so explicitly rather than implying coverage.
