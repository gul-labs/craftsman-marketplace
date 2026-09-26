# 07a — Emil Kowalski's Craft Deep Dive

Emil Kowalski (Linear, ex-Vercel). Restraint, speed, purposeful motion. Best for productivity
tools, high-frequency interactions, and professional UI. **Canonical home** for: when-to-
animate decisions, custom easing curves, spring physics, clip-path tricks, gesture
interactions, the `scale(0.9)` rule, transform-origin discipline, and the Sonner principles.

> **Source note:** substantial portions adapted from Emil Kowalski's MIT-licensed skill repo
> ([github.com/emilkowalski/skill](https://github.com/emilkowalski/skill)) and his
> animations.dev material — full MIT notice in `THIRD_PARTY_NOTICES.md` at the repo root.
> Not affiliated with or endorsed by Emil Kowalski, Linear, Vercel, or animations.dev.

> **See also**
>
> - For momentum projection, rubberbanding, velocity handoff, and gesture-surface physics → `./fluid-gestures.md`
> - For the motion audit framework (which designer applies, weighting by context) → `../layer-5-motion.md`
> - For production-polish patterns (subtle enter/exit, shadows, optical alignment) → `./jakub-polish.md`
> - For experimental CSS (linear(), @property, scroll-driven) → `./jhey-experimental.md`
> - For motion timing tokens and easing token values → `../layer-1-tokens.md` → Transitions and Motion Timing
> - For implementation specifics (Framer Motion rAF vs WAAPI, reduced-motion in React) → `../layer-2-primitives.md`
> - For animation anti-patterns catalog → `../anti-patterns.md`

---

## Contents

- [Core Philosophy](#core-philosophy)
- [Review Format (Required When Auditing)](#review-format-required-when-auditing)
- [The Animation Decision Framework](#the-animation-decision-framework)
  - [1. Should this animate at all?](#1-should-this-animate-at-all)
  - [2. What is the purpose?](#2-what-is-the-purpose)
  - [3. What easing should it use?](#3-what-easing-should-it-use)
  - [4. How fast should it be?](#4-how-fast-should-it-be)
- [Spring Animations](#spring-animations)
- [Component Building Principles](#component-building-principles)
- [CSS Transform Mastery](#css-transform-mastery)
- [clip-path for Animation](#clip-path-for-animation)
- [Gesture and Drag Interactions](#gesture-and-drag-interactions)
- [Performance Rules](#performance-rules)
- [Accessibility](#accessibility)
- [The Sonner Principles](#the-sonner-principles-building-loved-components)
- [Stagger Animations](#stagger-animations)
- [Debugging Animations](#debugging-animations)
- [Review Checklist](#review-checklist)

---

## Core Philosophy

> Restraint is the signal. Every animation you add should be harder to justify than the last.

The lens: high-frequency professional tools (Linear, Raycast, Vercel). Users repeat actions
hundreds of times a day. An animation that delights on first use becomes friction by the tenth.
Animate to reduce perceived latency, confirm state change, or communicate spatial relationship —
never to decorate.

---

## Review Format (Required When Auditing)

For a standalone focused motion review, a `| Before | After | Why |` table is useful. Under
craft-audit, the canonical findings format takes precedence; see `../review-protocol.md`.

| Before                                | After                                                             | Why                                                         |
| ------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------- |
| `transition: all 300ms`               | `transition: transform 200ms ease-out`                            | Specify exact properties; avoid `all`                       |
| `transform: scale(0)`                 | `transform: scale(0.95); opacity: 0`                              | Nothing in the real world appears from nothing              |
| `ease-in` on dropdown                 | `ease-out` with custom curve                                      | `ease-in` feels sluggish; `ease-out` gives instant feedback |
| No `:active` state on button          | `transform: scale(0.97)` on `:active`                             | Buttons must feel responsive to press                       |
| `transform-origin: center` on popover | `transform-origin: var(--radix-popover-content-transform-origin)` | Popovers scale from their trigger; modals stay centered     |

---

## The Animation Decision Framework

Answer these four questions before writing animation code.

### 1. Should this animate at all?

| Frequency                                                    | Decision                     |
| ------------------------------------------------------------ | ---------------------------- |
| 100+ times/day (keyboard shortcuts, command palette toggle)  | Usually instant; preserve clear feedback          |
| Tens of times/day (hover effects, list navigation)           | Remove or drastically reduce |
| Occasional (modals, drawers, toasts)                         | Standard animation           |
| Rare / first-time (onboarding, feedback forms, celebrations) | Can add delight              |

Keyboard use is a strong reason to minimize delay, not a blanket ban on all transitions. Focus
and feedback must be immediate; repeated commands should not wait for decorative movement.

### 2. What is the purpose?

Valid purposes:

- **Spatial consistency** — toast enters and exits from the same direction; swipe-to-dismiss feels intuitive
- **State indication** — morphing feedback button communicates the change
- **Explanation** — marketing animation showing how a feature works
- **Feedback** — button scales down on press, confirming input was received
- **Preventing jarring changes** — preserve orientation when a substantial spatial change would confuse

If the purpose is "it looks cool" and users see it often, don't animate.

### 3. What easing should it use?

```
Entering view?                           → ease-out (starts fast, feels responsive)
Exiting view, long (≥ 150 ms)?           → ease-out or ease-in-out
Exiting view, short (< 150 ms)?          → ease-in acceptable (brief exit reads natural)
Moving/morphing on-screen?               → ease-in-out (natural acceleration/deceleration)
Hover / color change?                    → ease
Constant motion (marquee)?               → linear
Default                                  → ease-out
```

> Avoid `ease-in` for entering animations and for any animation longer than 150 ms. Ease-in
> delays initial movement — exactly when the user is watching most closely. A dropdown entering
> with `ease-in` at 300 ms _feels_ slower than `ease-out` at 300 ms. Exception: `ease-in` on
> quick exits (< 150 ms) is acceptable — the element is leaving, and a brief exit
> reads naturally.

Use a shared curve that fits the interaction. Built-in easing is valid; these custom curves are
options when the rendered motion benefits from a different response:

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1); /* Strong ease-out for UI interactions */
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1); /* Strong ease-in-out for on-screen movement */
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1); /* iOS-like drawer curve (from Ionic) */
```

Resources: [easing.dev](https://easing.dev/) · [easings.co](https://easings.co/)

### 4. How fast should it be?

| Element                  | Duration      |
| ------------------------ | ------------- |
| Button press feedback    | 100–160 ms    |
| Tooltips, small popovers | 125–200 ms    |
| Dropdowns, selects       | 150–250 ms    |
| Modals, drawers          | 200–500 ms    |
| Marketing/explanatory    | Can be longer |

Keep frequent UI feedback brief. Larger surfaces may need longer travel; the table is a starting
range, not a universal ceiling. Never accelerate a spinner just to imply faster real progress.

---

## Spring Animations

Springs feel more natural than duration-based animations — they simulate physics and maintain
velocity when interrupted (CSS keyframes restart from zero).

### When to use springs

- Drag interactions with momentum
- Elements that should feel "alive" (Apple Dynamic Island)
- Gestures that can be interrupted mid-animation
- Decorative mouse-tracking interactions

### Spring configuration

```js
// Apple's approach — easier to reason about
{ type: "spring", duration: 0.5, bounce: 0.2 }

// Traditional physics — more control
{ type: "spring", mass: 1, stiffness: 100, damping: 10 }
```

Keep `bounce` at 0.1–0.3. Avoid bounce in most professional UI; use it for drag-to-dismiss and
playful contexts only.

### Spring-based mouse interactions

Tying visual changes directly to mouse position feels artificial without motion. Use `useSpring`
to interpolate with physics instead of updating immediately:

```jsx
import { useSpring } from 'framer-motion'

// Without spring: instant, artificial
const rotation = mouseX * 0.1

// With spring: has momentum, feels natural
const springRotation = useSpring(mouseX * 0.1, { stiffness: 100, damping: 10 })
```

Use this only for decorative interactions. A functional graph in a data dashboard should not
animate on mouse move.

---

## Component Building Principles

### Buttons must feel responsive

```css
.button {
  transition: transform 160ms ease-out;
}
.button:active {
  transform: scale(0.97);
}
```

Use scale selectively on controls large enough to retain legibility. A color/depth change is also
valid press feedback. Disable movement for reduced motion and do not delay the action.

### Never animate from scale(0)

> Start entries from `scale(0.9)` or higher, combined with `opacity: 0`.

Nothing in the real world disappears and reappears completely. `scale(0)` looks like teleportation.

```css
/* Bad */
.entering {
  transform: scale(0);
}

/* Good */
.entering {
  transform: scale(0.95);
  opacity: 0;
}
```

### Make popovers origin-aware

> Popovers scale from their trigger. Modals keep `transform-origin: center` — they are not
> anchored to a trigger.

```css
/* Radix UI */
.popover {
  transform-origin: var(--radix-popover-content-transform-origin);
}

/* Base UI */
.popover {
  transform-origin: var(--transform-origin);
}
```

### Tooltips: first delayed, subsequent instant

Delay the first tooltip to prevent accidental activation. Once one is open, adjacent tooltips
open instantly with no animation — the toolbar feels faster without defeating the initial delay.

```css
.tooltip {
  transition:
    transform 125ms ease-out,
    opacity 125ms ease-out;
  transform-origin: var(--transform-origin);
}
.tooltip[data-starting-style],
.tooltip[data-ending-style] {
  opacity: 0;
  transform: scale(0.97);
}
/* Skip animation on subsequent tooltips */
.tooltip[data-instant] {
  transition-duration: 0ms;
}
```

### CSS transitions over keyframes for interruptible UI

CSS transitions retarget mid-animation. Keyframes restart from zero.

```css
/* Interruptible — good for rapidly-triggered UI */
.toast {
  transition: transform 400ms ease;
}

/* Not interruptible — avoid for dynamic UI */
@keyframes slideIn {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}
```

### Use blur to mask imperfect crossfades

When a crossfade feels off despite correct easing and duration, add `filter: blur(2px)` during
the transition. It blends the two states together, tricking the eye into a single transformation.
Keep blur under 20 px — heavy blur is expensive in Safari.

```css
.button-content.transitioning {
  filter: blur(2px);
  opacity: 0.7;
  transition:
    filter 200ms ease,
    opacity 200ms ease;
}
```

### Animate enters with @starting-style

Modern CSS entry animation without JavaScript:

```css
.toast {
  opacity: 1;
  transform: translateY(0);
  transition:
    opacity 400ms ease,
    transform 400ms ease;

  @starting-style {
    opacity: 0;
    transform: translateY(100%);
  }
}
```

Replaces the `useEffect → setMounted(true)` pattern. Fall back to `data-mounted` attribute when
browser support requires it.

---

## CSS Transform Mastery

### translateY with percentages

`translateY(100%)` moves an element by its own height regardless of dimensions. This is how
Sonner positions toasts and Vaul hides the drawer before animating in. Prefer percentages over
hardcoded pixels.

### scale() scales children too

Unlike `width`/`height`, `scale()` scales children proportionally. When scaling a button on
press, font size, icons, and content all scale. Feature, not bug.

### 3D transforms for depth

```css
.wrapper {
  transform-style: preserve-3d;
}

@keyframes orbit {
  from {
    transform: translate(-50%, -50%) rotateY(0deg) translateZ(72px) rotateY(360deg);
  }
  to {
    transform: translate(-50%, -50%) rotateY(360deg) translateZ(72px) rotateY(0deg);
  }
}
```

### transform-origin

Default is `center`. Set it to match where the trigger lives for origin-aware interactions.

---

## clip-path for Animation

### The inset shape

`clip-path: inset(top right bottom left)` clips a rectangle from each side.

```css
/* Hidden (clipped from right) */
.hidden {
  clip-path: inset(0 100% 0 0);
}
.visible {
  clip-path: inset(0 0% 0 0);
}
```

### Hold-to-delete pattern

```css
/* Release: fast */
.overlay {
  transition: clip-path 200ms ease-out;
}

/* Press: slow and deliberate */
.button:active .overlay {
  transition: clip-path 2s linear;
}
```

On `:active`, animate `inset(0 100% 0 0)` → `inset(0 0 0 0)` over 2 s. On release, snap back
with 200 ms ease-out. Add `scale(0.97)` on the button for press feedback.

### Tabs with perfect color transitions

Duplicate the tab list. Style the copy as "active." Clip it so only the active tab is visible.
Animate the clip on tab change. Timing individual color transitions can never match this.

### Image reveals on scroll

Start with `clip-path: inset(0 0 100% 0)`. Animate to `inset(0 0 0 0)` on viewport entry via
`IntersectionObserver` or Framer Motion's `useInView` with `{ once: true, margin: "-100px" }`.

### Comparison sliders

Overlay two images. Clip the top with `clip-path: inset(0 50% 0 0)`. Adjust right inset based
on drag position. No extra DOM; verify paint/compositing for the target browser and image size.

---

## Gesture and Drag Interactions

### Momentum-based dismissal

Don't require dragging past a threshold alone. Check velocity too:

```js
const timeTaken = new Date().getTime() - dragStartTime.current.getTime()
const velocity = Math.abs(swipeAmount) / timeTaken

if (Math.abs(swipeAmount) >= SWIPE_THRESHOLD || velocity > 0.11) {
  dismiss()
}
```

A quick flick should dismiss regardless of distance traveled.

### Damping at boundaries

When a user drags past a natural boundary (e.g., drawer already at top), apply damping — the
more they drag, the less the element moves. Friction instead of hard stops.

### Pointer capture for drag

Set the element to capture all pointer events once dragging starts. Dragging continues even when
the pointer leaves element bounds.

### Multi-touch protection

Ignore additional touch points after initial drag begins. Switching fingers mid-drag otherwise
jumps the element to the new position.

```js
function onPress() {
  if (isDragging) return
  // Start drag...
}
```

---

## Performance Rules

### Prefer transform and opacity for movement

These often avoid layout/paint; verify compositing under real load. Small color transitions are
valid. Size/spacing animation can trigger layout, so keep it bounded and profile it; consider
transform-based layout animation when appropriate.

### Update transform directly, not CSS variables

CSS variables on a parent recalculate styles for all children. In a drawer with many items,
updating `--swipe-amount` on the container is expensive.

```js
// Bad: triggers recalc on all children
element.style.setProperty('--swipe-amount', `${distance}px`)

// Good: only affects this element
element.style.transform = `translateY(${distance}px)`
```

### Framer Motion — rAF vs compositor offload

"Hardware accelerated" is not a binary property of a prop name, and Motion's internals have
changed across major versions — **verify against the installed version's docs
([motion.dev/docs/performance](https://motion.dev/docs/performance)) before asserting either
way in a review.**

What holds across versions:

- JS-driven animation computes frames on the main thread via `requestAnimationFrame`, so it can
  stutter when the main thread is blocked — regardless of which property it targets.
- Per Motion's current performance guidance, the individual transform props (`x`, `y`, `scale`,
  `rotate`) are implemented via CSS variables and are **not** compositor-accelerated; when
  acceleration is crucial, animate the full `transform` string — at the cost of per-axis
  springs and independent transform control.
- For simple, independent `transform`/`opacity` motion that must survive a busy main thread,
  prefer compositor-eligible CSS transitions/animations or WAAPI directly
  (`element.animate(...)`), then verify actual performance.

**Rule: don't fight this inside the library.** Use the individual props for gesture-driven,
interruptible, per-axis motion (their whole point); use CSS/WAAPI for predetermined motion that
must stay smooth under load — see `../layer-2-primitives.md` → Animation under Load.

### WAAPI for programmatic CSS animations

Programmatic control without a new library. Property and browser determine compositing; the
clip-path example still needs performance measurement:

```js
element.animate([{ clipPath: 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0 0)' }], {
  duration: 1000,
  fill: 'forwards',
  easing: 'cubic-bezier(0.77, 0, 0.175, 1)',
})
```

---

## Accessibility

### prefers-reduced-motion

Reduced motion means fewer and gentler animations, not zero. Keep opacity and color transitions
that aid comprehension. Remove movement and position animations.

```css
@media (prefers-reduced-motion: reduce) {
  .element {
    animation: fade 0.2s ease;
    /* No transform-based motion */
  }
}
```

See `../layer-5-motion.md` for the static-first reduced-motion pattern and `../layer-2-primitives.md`
for `useReducedMotion` in React.

### Touch device hover states

Gate hover animations behind this media query — touch devices fire hover on tap:

```css
@media (hover: hover) and (pointer: fine) {
  .element:hover {
    transform: scale(1.05);
  }
}
```

---

## The Sonner Principles (Building Loved Components)

Lessons from Sonner that can inform other components:

1. **Developer experience is key.** No hooks, no context, no complex setup. Insert `<Toaster />`
   once, call `toast()` anywhere. Less adoption friction = more users.

2. **Good defaults matter more than options.** Ship beautiful out of the box. Most users never
   customize. The default easing, timing, and visual design must be excellent.

3. **Naming creates identity.** "Sonner" (French for "to ring") is more memorable than
   "react-toast." Sacrifice discoverability for memorability when appropriate.

4. **Handle edge cases invisibly.** Pause timers on hidden tab. Fill gaps between stacked toasts
   with pseudo-elements to maintain hover state. Capture pointer events during drag. Users never
   notice — exactly right.

5. **Use transitions, not keyframes, for dynamic UI.** Toasts are added rapidly; keyframes restart
   from zero on interruption. Transitions retarget smoothly.

6. **Build a great documentation site.** Interactive examples with ready-to-use code lower the
   adoption barrier.

### Match motion to mood

Sonner uses `ease` rather than `ease-out` and is slightly slower than typical UI animations —
it feels more elegant than fast. A playful component can be bouncier; a professional dashboard
should be crisp. Match animation personality to component personality.

### Asymmetric enter/exit timing

Slow where the user is deciding; fast where the system is responding.

```css
/* Release: fast */
.overlay {
  transition: clip-path 200ms ease-out;
}

/* Press: slow and deliberate */
.button:active .overlay {
  transition: clip-path 2s linear;
}
```

---

## Stagger Animations

A small stagger can introduce a bounded group in a fitting first-visit or explanatory moment.
Do not add it to every list or repeated data refresh. Keep content available if animation fails.

```css
.item {
  animation: fadeIn 300ms ease-out backwards;
}
.item:nth-child(1) {
  animation-delay: 0ms;
}
.item:nth-child(2) {
  animation-delay: 50ms;
}
.item:nth-child(3) {
  animation-delay: 100ms;
}
.item:nth-child(4) {
  animation-delay: 150ms;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

Under `prefers-reduced-motion: reduce`, use `.item { animation: none; }`.

> For a small group, 30–80 ms between items is a starting point; cap total delay. Longer delays make the interface feel slow.
> Stagger is decorative — never block interaction while stagger animations are playing.

---

## Debugging Animations

### Slow motion testing

Temporarily increase duration 2–5×, or use browser DevTools animation inspector.

Check for:

- Two distinct states visible during crossfade (check overlap/timing first; blur is optional)
- Abrupt start/stop (easing issue)
- Wrong transform-origin
- Desync between animated properties (opacity, transform, color)

### Frame-by-frame inspection

Chrome DevTools Animations panel. Reveals timing desync between coordinated properties invisible
at full speed.

### Test on real devices

For touch interactions (drawers, swipe), test on physical hardware. Connect via USB, visit local
dev server by IP, use Safari remote devtools. Simulator is acceptable but real hardware is
better for gesture testing.

---

## Review Checklist

| Issue                                  | Fix                                                                                       |
| -------------------------------------- | ----------------------------------------------------------------------------------------- |
| `transition: all`                      | Specify exact properties: `transition: transform 200ms ease-out`                          |
| `scale(0)` entry animation             | Start from `scale(0.95)` with `opacity: 0`                                                |
| `ease-in` on entering element or long animation (≥ 150 ms) | Switch to `ease-out` or custom curve; `ease-in` is acceptable only on quick exits (< 150 ms) |
| `transform-origin: center` on popover  | Set to trigger location or use Radix/Base UI CSS variable (modals exempt — keep centered) |
| Delayed repeated keyboard action       | Remove delay; keep focus and feedback immediate                                                                 |
| Repeated action feels slow             | Shorten or remove transition; measure the whole interaction                                                                      |
| Hover animation without media query    | Add `@media (hover: hover) and (pointer: fine)`                                           |
| Keyframes on rapidly-triggered element | Use CSS transitions for interruptibility                                                  |
| Framer Motion `x`/`y` under load       | Predetermined motion that must survive main-thread load → CSS or WAAPI (`element.animate(...)`); keep individual props for gesture-driven per-axis motion. Verify acceleration claims against the installed version's docs |
| Exit distracts from the next task      | Reduce exit travel/duration when that resolves the distraction                                 |
| Introductory sequence needs hierarchy  | Consider a bounded stagger; simultaneous appearance is valid                                                |
