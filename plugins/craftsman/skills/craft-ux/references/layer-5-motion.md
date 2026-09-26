# Layer 5 — Motion & Accessibility

Motion should make an interface responsive, legible, and alive. It is part of the interaction
design, not a substitute for color, hierarchy, or well-built components. The brief and interaction
frequency determine how expressive it should be. A missing animation is not inherently a defect.

## Audit and design method

1. Inspect the product, existing motion, audience, and project rules. Identify which interactions
   repeat frequently and which moments introduce or explain something.
2. Observe actual state changes: hover/press, menus, dialogs, selection, loading, reordering, and
   navigation. Look for missing feedback, disorienting jumps, delayed actions, or distracting motion.
   A conditional render without `AnimatePresence` is only a search lead, not a finding.
3. Choose the smallest treatment that solves the observed problem. A static change can be correct.
   Reuse the installed motion system or CSS; do not add a library for one fade.
4. Test repeated use, rapid interruption/reversal, keyboard, touch, and reduced motion. Inspect both
   ends and the transition; good endpoint contrast can still fail during an uncoordinated theme fade.
5. Report concrete findings using `review-protocol.md`, or the canonical craft-audit format when
   running under craft-audit. State the affected interaction and observed consequence. No separate
   approval gate is needed for routine audit choices within the user's requested scope.

Use these references as optional lenses, not impersonated endorsements or universal style rules:

- `motion/emil-craft.md`: frequency, responsiveness, interruptibility, gestures.
- `motion/jakub-polish.md`: optical alignment, surface depth, subtle transitions.
- `motion/jhey-experimental.md`: expressive CSS for a fitting creative/marketing brief.
- `motion/fluid-gestures.md`: velocity, projection, rubberbanding, interruptible springs.
- `layer-1-tokens.md`: shared duration/easing tokens.

## Make the site feel alive

| Moment | Useful treatment | Acceptance check |
| --- | --- | --- |
| Hover/focus | Clear edge, color, underline, or subtle depth change | Works without moving the target; keyboard focus is immediate and visible |
| Press | Immediate color/depth change; slight scale where suitable | Confirms input without shrinking small controls or delaying the action |
| Menu/dialog | Short fade or small origin-aware movement | Focus is correct; rapid open/close works; no unreadable blur is required |
| Selection | Persistent selected cue; optional traveling indicator | State is clear even with motion off; repeated navigation stays fast |
| Loading/result | Stable layout, clear pending feedback, smooth replacement if useful | No artificial delay, duplicate content, or missing completion message |
| Card expansion/reorder | Spatial continuity through layout/transform motion | Text is not distorted; scroll/focus remain sensible; animation can reverse |
| Marketing introduction | A coordinated reveal or product demonstration | It serves the story, does not gate reading, and has a static alternative |

For ordinary controls, roughly 100–180 ms feedback and 150–250 ms small entries are useful
starting points; larger surfaces may need 200–350 ms. Distance, frequency, device, and existing
motion tokens decide. Frequent actions may be instantaneous. A deliberate product demonstration
can be longer. Do not infer quality from a fixed duration ceiling.

Use `ease-out` for a responsive arrival, a suitable ease-in-out for on-screen movement, and a
spring where continuity under interruption matters. Standard CSS easing is valid. Tune a custom
curve only when it improves the actual motion. Exits often benefit from less travel and a shorter
duration; they need not always differ. Blur, bounce, stagger, and scale are optional techniques.

For a premium marketing site, one carefully composed entrance and tactile controls can be enough.
Do not add perpetual card loops, scroll hijacking, parallax, or magnetic pointers by default.
For an expressive brief, use them selectively with usable touch and reduced-motion alternatives.

## Implementation and performance

| Need | Usually sufficient |
| --- | --- |
| Hover/press/color or class-driven state | CSS transition with explicit properties |
| Entry on mount | CSS animation or `@starting-style` where supported |
| Programmatic animation without a new library | WAAPI (`element.animate`) |
| Interruptible springs, shared layout, gestures | The project's Motion/animation library |

- Prefer transform and opacity for movement. Small color/border transitions are reasonable even
  though they repaint. Layout-property animation can be costly; use transform-based layout motion
  when practical and profile genuine size animations rather than declaring every accordion invalid.
- Avoid per-frame React state for pointer/scroll progress. Use motion values, refs, or a suitable
  native animation. An event listener alone is not a bug; expensive work and repeated layout reads
  and writes are. Use observers or scroll timelines when they fit and verify browser support.
- Gradient position/size, shadows, filters, and clipping are not automatically compositor-only.
  For large effects, prefer a pre-rendered layer animated with transform/opacity and measure paint.
- Set `will-change` only for a measured problem on a small set of elements, and remove it when no
  longer useful. Do not assume it guarantees acceleration.
- Clean up listeners, observers, animation handles, and library contexts. Stop invisible loops.
- Keep essential content visible if scripting or an entry observer fails. Respect native scrolling.
- Test under representative load. Describe device/performance evidence accurately; desktop
  screenshots are not proof of smoothness on a phone.

[Browser animation guidance](https://web.dev/articles/animations-guide) explains the distinction
between layout, paint, and compositing. Verify library-specific behavior against the installed
version before making acceleration claims.

## Severity follows the consequence

- **Critical:** motion hides or blocks a primary task, focus is lost/invisible, or a serious
  accessibility failure prevents use. Follow the shared prioritization rules for actual impact.
- **Important:** distracting or janky transitions, delayed repeated actions, unreadable transition
  states, ignored reduced-motion preference, or missing feedback that leaves the user uncertain.
- **Opportunity:** an optional expressive treatment or minor optical refinement outside the brief.

No missing blur, built-in easing, instant keyboard action, or absence of an exit animation is a
failure by itself. On a requested polish task, a visible failure against the brief belongs in scope.

## Reduced-motion pattern

Author a usable static state first and add decorative movement under `no-preference`. For example:

```css
.dialog-panel { opacity: 1; transform: none; }
@media (prefers-reduced-motion: no-preference) {
  .dialog-panel[data-entering] { animation: panel-in 180ms ease-out; }
  @keyframes panel-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: none; }
  }
}
```

For JS animation, branch on the preference too; CSS cannot disable every JS-driven effect. Keep
state feedback and meaningful progress available when movement is removed. A short fade may be
appropriate, but an immediate update is valid. Test initial render and changes in the preference.
Do not depend on animation completion events to perform essential application actions.

---

## Accessibility Floor

Every interface must clear these requirements regardless of motion choices. Treat each item as a
hard requirement, not a stretch goal.

### prefers-reduced-motion

`prefers-reduced-motion` is a first-class branch, not an afterthought. Every animation must have
an explicit reduced-motion path:

- Start from the usable static pattern above; enable movement under `no-preference`.
- In JavaScript animation libraries (Framer Motion, GSAP), read the media query directly and skip
  or instant-complete transitions: `const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches`
- CSS media-query rules alone cannot stop every JS-driven animation; use the library's
  preference hook or a subscribed media query as well.
- Functional motion (loading spinners, progress indicators, state transitions) must provide an
  instant or opacity-only alternative when reduced motion is active, not just disappear.
- Under reduced motion, replace slides/springs/parallax with an immediate update or short opacity
  cross-fade; remove elastic overshoot and retain clear feedback.
- Avoid slow looping oscillations near 0.2 Hz (one cycle per ~5 s) and abrupt brightness jumps —
  ease dark↔light theme changes where a transition is used at all.

### Retrofitting existing motion

Inventory CSS animations/transitions and JS timelines, then add scoped reduced-motion rules to the
affected components. Ensure the scoped override wins the cascade: match the original selector's
specificity and place it later, or use scoped `!important` where necessary. Verify the computed
result. Preserve static transforms/filters the design needs; reset only entrance/movement effects.
Set an explicitly usable final appearance when removing an entrance; simply
canceling an animation can otherwise leave content hidden. For example, adapt these selectors to
the actual component classes:

```css
@media (prefers-reduced-motion: reduce) {
  .marketing-reveal {
    animation: none;
    transition: none;
    opacity: 1;
    transform: none;
    filter: none;
  }
  html { scroll-behavior: auto; }
}
```

Handle loading/progress with a clear static status, and cancel or instant-complete JS timelines
through their own APIs. Keep essential actions independent of completion callbacks. Avoid an
unexamined global near-zero-duration override: it can alter callbacks and leave final states
wrong. Test the actual affected components under the preference.

### Related preference media queries

Two siblings of reduced-motion that translucent/high-polish UI must also honor:

- **`prefers-reduced-transparency: reduce`** — make translucent surfaces frostier or solid:
  raise background opacity, drop the `backdrop-filter` blur.
- **`prefers-contrast: more`** — near-solid backgrounds with a defined, contrasting border.

```css
@media (prefers-reduced-transparency: reduce) {
  .toolbar { background: white; backdrop-filter: none; }
}
@media (prefers-contrast: more) {
  .card { background: var(--surface); border: 1px solid var(--border-strong); }
}
```

### Focus-visible states

- Every interactive element — buttons, links, inputs, custom controls — must expose a visible
  `:focus-visible` ring. Do not suppress the browser default without replacing it.
- The focus indicator must have at least 3:1 contrast against the adjacent background (WCAG 2.2
  criterion 1.4.11 for author-styled indicators). Keep focused controls from being entirely
  obscured by sticky headers or overlays (2.4.11).
- Never use `outline: none` or `outline: 0` without an explicit replacement focus style.
- Custom components (dropdown triggers, combobox options, dialog close buttons) must receive focus
  and show the ring; invisible focus is a critical failure.

### Keyboard navigation completeness

- All interactive functionality must be reachable and operable by keyboard alone.
- Tab order must follow visual reading order; avoid positive `tabindex` values.
- Modals and drawers must trap focus within themselves while open and restore focus to the trigger
  on close.
- Custom widgets (sliders, date pickers, tab panels) must implement the ARIA authoring patterns
  (arrow key navigation, Home/End, Escape to dismiss).
- Dropdown menus must close on Escape and return focus to the trigger.

### WCAG AA contrast minimum

- Normal text (< 18 pt / < 14 pt bold): minimum 4.5:1 against its background.
- Large text (≥ 18 pt / ≥ 14 pt bold): minimum 3:1.
- UI components and state indicators (borders, icons that convey meaning): minimum 3:1.
- Placeholder text must meet the applicable text contrast ratio. Inactive controls are exempt,
  but disabled text should still
  be visually distinguishable from active text through means other than color alone.
- Check contrast at design-token level, not just in isolation — layered surfaces (card on
  sidebar on background) compound contrast loss.

### ARIA live regions

Use announcements for important status updates that otherwise occur outside the user's focus.
Native semantics, focus management, and widget state may already communicate a change; announcing
every dynamic region duplicates speech and makes an interface noisy.

**When to use `aria-live`:**

- Task-relevant status outside focus, such as save results, cart totals, or connection failures;
  batch frequent updates such as streaming text rather than announcing every token
- Prefer `role="status"` (polite) or `role="alert"` (assertive) over bare `aria-live` —
  they carry implied semantics and are more widely supported

**`role="status"` (polite):**

```html
<!-- Polite: waits for the user to finish their current interaction -->
<div role="status" aria-live="polite" aria-atomic="true">
  3 items in cart
</div>
```

Use for: success confirmations, save indicators, count updates, background-sync messages.

**`role="alert"` (assertive):**

```html
<!-- Assertive: interrupts immediately — use only for errors or urgent info -->
<div role="alert" aria-live="assertive" aria-atomic="true">
  Error: Could not save your changes. Please try again.
</div>
```

Use for: form errors, network failures, security warnings. Never use for non-urgent updates —
assertive interrupts the screen reader mid-sentence.

**`aria-atomic`:**

- `aria-atomic="true"` — the entire region is re-announced when any part changes. Use when the
  full message must be heard together ("3 items in cart" not just "3").
- `aria-atomic="false"` (default) — only the changed nodes are announced. Use for streaming
  text or append-only logs where announcing the delta is sufficient.

**`aria-live="off"` for decorative updates:**

Animated counters, progress bars that update frequently, and other decorative live regions
should use `aria-live="off"` (or no live region at all) to prevent announcement spam. Only
announce when the value has semantic importance to the user's task.

**Pattern — React live region:**

```tsx
// Place the live region in the DOM on initial render; update its text content only
function StatusAnnouncer({ message }: { message: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"  // visually hidden but announced
    >
      {message}
    </div>
  );
}
```

Keep live regions present in the DOM from initial render — injecting them dynamically at the
moment of announcement is unreliable across screen readers.

---

### JavaScript reduced-motion branch

The pattern for any animation authored in JavaScript:

```ts
const prefersReduced =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Example: skip enter animation entirely
const variants = prefersReduced
  ? { hidden: { opacity: 1 }, visible: { opacity: 1, transition: { duration: 0 } } }
  : {
      hidden: { opacity: 0, y: 6 },
      visible: { opacity: 1, y: 0 },
    };
```

This is an initial preference snapshot. In reactive UI, use the installed library's reduced-motion
hook or subscribe to media-query changes, with SSR-safe initialization. Author and test both branches.
