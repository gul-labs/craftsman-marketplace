# Layer 2 — Primitives & Implementation

Layout primitives (Stack/Inline/Grid/Box) and the Tailwind/CVA mechanics every component sits on. Replaces raw flex/gap divs and ad-hoc class soup.

> **craft-ux tie-in:** Reuse existing primitives and styling conventions. In a small page without
> them, token-based CSS Grid/Flexbox is valid; introduce abstractions when repeated patterns warrant it.

> **See also**
>
> - Design tokens (spacing/typography/color/timing) → [layer-1-tokens.md](layer-1-tokens.md)
> - Component patterns (skeleton, error, empty state) → [layer-3-components.md](layer-3-components.md)
> - Motion craft and animation → [layer-5-motion.md](layer-5-motion.md)

---

## Contents

- [Layout Primitives](#layout-primitives)
  - [Stack](#stack)
  - [Inline](#inline)
  - [Grid](#grid)
  - [Box](#box)
  - [Center](#center)
  - [Content Handling](#content-handling)
- [Implementation: Tailwind & React](#implementation-tailwind--react)
  - [The `cn()` Helper](#the-cn-helper)
  - [Dynamic Class Names](#dynamic-class-names)
  - [Variants with CVA](#variants-with-cva)
  - [Mobile-First Responsive](#mobile-first-responsive)
  - [Viewport Height](#viewport-height)
  - [Grid over Flex Math](#grid-over-flex-math)
  - [Dark Mode](#dark-mode)
  - [Z-Index Discipline](#z-index-discipline)
  - [Dependency Verification](#dependency-verification)
  - [React Composition](#react-composition)
  - [Reduced Motion (React)](#reduced-motion-react)
  - [Hydration Safety](#hydration-safety)
  - [Internationalization](#internationalization)
  - [Touch and Mobile](#touch-and-mobile)
  - [Performance Building Blocks](#performance-building-blocks)
  - [Animation under Load](#animation-under-load)
  - [Implementation Anti-Patterns](#implementation-anti-patterns)
  - [Browser and Standards Compliance](#browser-and-standards-compliance)

---

## Layout Primitives

Five structural components enforce the spacing scale through the type system. At 50+ pages they eliminate drift that tokens alone cannot prevent — tokens exist but a developer can still write `space-y-5`. Primitives make invalid spacing impossible.

All primitives are thin wrappers (~15–25 lines each): className mapping, `as` prop for semantic HTML, ref forwarding, no internal state, no side effects. Keep abstraction overhead proportionate to the project.

**Where the project mandates these primitives:** use them instead of raw layout utilities in
domain components. Without that convention, consistent token-based layout utilities are valid.

---

### Stack

Vertical spacing between children. `spacing` prop mapped to the 4 px scale. Replaces raw `space-y-*`.

**Use for:** page sections, form fields, list items, card bodies.

---

### Inline

Horizontal layout with `gap`, `align`, `justify` props. Replaces raw `flex items-center gap-*`.

**Use for:** header rows, icon+text, tag groups, toolbars, breadcrumbs, action buttons.

---

### Grid

Responsive grid with named `preset` prop (`stats`, `cards`, `detail`, `images`, `form`) or custom `cols` + `gap`. Replaces raw `grid grid-cols-*`.

**Use for:** card grids, stat grids, detail layouts, media galleries.

---

### Box

Padding container with scale-locked `padding` prop. Replaces raw `p-*` on container divs.

**Use for:** card bodies, section wraps, dialog content, sidebar panels.

---

### Center

Center content on both axes with optional `minHeight`. Replaces raw `flex items-center justify-center`.

**Use for:** empty states, loading states, auth pages, error pages.

---

### Content Handling

Every text container handles the full range:

- Short text: don't break layout
- Average text: render cleanly
- Long text: truncate with `truncate`, `line-clamp-*`, or `break-words`
- Flex children that contain text need `min-w-0` to allow truncation
- Empty data: render an empty state, not broken UI

Use `text-wrap: balance` on headings to prevent orphans. Use `text-wrap: pretty` on body for better line breaks.

---

## Implementation: Tailwind & React

---

### The `cn()` Helper

Mandatory for conditional classes. Resolves Tailwind class collisions via `tailwind-merge`.

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Usage
<button className={cn(
  "px-4 py-2 rounded-md",
  variant === "primary" && "bg-primary text-primary-foreground",
  disabled && "opacity-50 cursor-not-allowed"
)} />
```

---

### Dynamic Class Names

Tailwind purges classes it cannot statically detect at build time.

```typescript
// ❌ BROKEN — purged at build
<div className={`bg-${color}-500`} />

// ✅ CORRECT — static object map
const colorMap = { blue: "bg-blue-500", red: "bg-red-500" };
<div className={colorMap[color]} />
```

---

### Variants with CVA

Use `class-variance-authority` for multi-variant components. Eliminates boolean prop explosion.

```typescript
import { cva, type VariantProps } from "class-variance-authority";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive-hover",
        outline: "border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-accent hover:text-accent-foreground",
      },
      size: {
        sm: "h-9 px-3 text-sm",
        default: "h-10 px-4 py-2",
        lg: "h-11 px-8 text-base",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;
```

The example assumes `primary-hover` and `destructive-hover` are mapped into the utility theme.
Use the existing system's equivalent roles; `starter-kits.md` provides measured example pairs.
Do not copy a class whose token is missing, or use an opacity hover without measuring the composed
text/fill pair. `accent` is a quiet interaction surface; it always travels with its foreground.

---

### Mobile-First Responsive

Base styles target mobile. Layer breakpoints upward.

```html
<div
  class="flex flex-col gap-4 p-4
            md:flex-row md:gap-8 md:p-6
            lg:p-8"
/>
```

| Breakpoint | px   |
| ---------- | ---- |
| `sm`       | 640  |
| `md`       | 768  |
| `lg`       | 1024 |
| `xl`       | 1280 |
| `2xl`      | 1536 |

---

### Viewport Height

**NEVER** `h-screen` — causes layout jumping on iOS Safari when the browser chrome shows/hides.

**ALWAYS** `min-h-[100dvh]` for full-height sections.

---

### Grid over Flex Math

**NEVER** `w-[calc(33%-1rem)]` or similar flexbox percentage math.

**ALWAYS** CSS Grid for multi-column layouts: `grid grid-cols-3 gap-6`.

---

### Dark Mode

Class-based toggle (add `dark` to `<html>`):

```html
<html class="dark">
  <div class="bg-background text-foreground" />
</html>
```

Semantic tokens flip automatically via the `.dark` variable block; `dark:` palette overrides in
domain code are a token violation.

| Requirement            | Implementation                                            |
| ---------------------- | --------------------------------------------------------- |
| Native controls match  | `color-scheme: dark` on `<html>`                          |
| Browser chrome matches | `<meta name="theme-color" content="#0a0a0a">`             |
| Verify coverage        | Every component, every state, every overlay in both modes |

---

### Z-Index Discipline

No arbitrary `z-[9999]` values. Define a token scale in your CSS variables:

```
--z-base:           0
--z-dropdown:    1000
--z-sticky:      1100
--z-fixed:       1200
--z-modal-back:  1300
--z-modal:       1400
--z-popover:     1500
--z-tooltip:     1600
--z-toast:       1700
```

---

### Dependency Verification

Before importing any third-party library:

1. Check `package.json` — if missing, emit the install command before writing code.
2. Check Tailwind major version. v3 and v4 have incompatible config syntax:

|                | Tailwind v3          | Tailwind v4                              |
| -------------- | -------------------- | ---------------------------------------- |
| PostCSS plugin | `tailwindcss`        | `@tailwindcss/postcss`                   |
| Config file    | `tailwind.config.ts` | CSS `@theme` block                       |
| Install        | `npm i tailwindcss`  | `npm i tailwindcss @tailwindcss/postcss` |

3. New dependency > 20 KB gzipped requires explicit justification.

---

### React Composition

Prefer compound components (Radix/Headless UI style) over prop-soup APIs:

```tsx
// ❌ prop soup
<Tabs defaultValue="a" items={[...]} onChange={...} />

// ✅ compound
<Tabs defaultValue="a">
  <TabsList>
    <TabsTrigger value="a">Tab A</TabsTrigger>
    <TabsTrigger value="b">Tab B</TabsTrigger>
  </TabsList>
  <TabsContent value="a">Content A</TabsContent>
  <TabsContent value="b">Content B</TabsContent>
</Tabs>
```

For state context sharing, boolean prop refactoring, and React 19 `use()` patterns → `craft-frontend` → `state.md` and `architecture.md`.

---

### Reduced Motion (React)

```tsx
import { useReducedMotion } from "framer-motion";

function AnimatedCard() {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduce ? 0 : 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.3 }}
    />
  );
}
```

For the CSS `@media (prefers-reduced-motion)` global reset and full motion craft → [layer-5-motion.md](layer-5-motion.md).

---

### Hydration Safety

| Scenario                              | Pattern                                                                     |
| ------------------------------------- | --------------------------------------------------------------------------- |
| Controlled input                      | Pair `value` with `onChange`; or use `defaultValue` for uncontrolled        |
| Date/time rendering                   | Render placeholder on server, real value after mount                        |
| `suppressHydrationWarning`            | Only on the specific node that legitimately diverges — not as a blanket fix |
| `Date.now()` / `Math.random()` in JSX | Always causes mismatch — move to effect or pass as prop                     |

Client-only mount pattern:

```tsx
"use client";
import { useEffect, useState } from "react";

function LocalTime({ date }: { date: Date }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <span aria-hidden>&nbsp;</span>;
  return <span>{new Intl.DateTimeFormat().format(date)}</span>;
}
```

---

### Internationalization

| Rule                 | Implementation                                                                   |
| -------------------- | -------------------------------------------------------------------------------- |
| Dates and times      | `Intl.DateTimeFormat` — never hardcoded format strings                           |
| Numbers and currency | `Intl.NumberFormat`                                                              |
| Language detection   | `Accept-Language` header or `navigator.languages` — never IP                     |
| Brand/code names     | `translate="no"` attribute                                                       |
| Pluralization        | ICU messages `{count, plural, one {# item} other {# items}}` — never hand-rolled |
| New keys             | Add to canonical English file first, then propagate                              |

---

### Touch and Mobile

| Rule                     | CSS / attribute                                             |
| ------------------------ | ----------------------------------------------------------- |
| Kill 300 ms tap delay    | `touch-action: manipulation` on interactive elements        |
| Tap highlight            | `-webkit-tap-highlight-color: transparent` (or brand color) |
| Scroll bleed from modals | `overscroll-behavior: contain` on drawer/sheet/modal        |
| Drag state               | Disable text selection; apply `inert` to non-target regions |
| Tap target size          | >= 44 x 44 px — see [layer-1-tokens.md](layer-1-tokens.md)  |

---

### Performance Building Blocks

| Concern                | Pattern                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------- |
| Heavy components       | `next/dynamic` with `{ ssr: false }` when client-only                              |
| Images                 | `next/image` with explicit `width`/`height`; `priority` above fold                 |
| Below-fold images      | `loading="lazy"`                                                                   |
| Server/client split    | Server Components by default; add `"use client"` only where interactivity requires |
| Streaming              | `<Suspense>` boundaries around data-dependent sections                             |
| Third-party origins    | `<link rel="preconnect">` for CDN/API domains                                      |
| Critical fonts         | `<link rel="preload" as="font" crossOrigin>` + `font-display: swap`                |
| Long lists             | Virtualize at > 50 items (TanStack Virtual or equivalent)                          |
| Layout reads in render | Batch with writes; never call `getBoundingClientRect` in render                    |
| Animatable properties  | Prefer `transform`/`opacity` for movement; small color/edge state transitions are valid                                                     |

---

### Animation under Load

For movement, prefer **compositor-friendly properties — `transform` and `opacity`** (Framer Motion's
`x`/`y`/`scale`/`opacity` shorthands compile down to these). Animating layout properties (`width`,
`height`, `top`, `margin`) can force layout and paint each frame; profile before declaring it the cause of jank.

But the property isn't the whole story: a **JS-driven** animation computes each frame on the main
thread via `requestAnimationFrame`, so it can still stutter when the main thread is blocked — no
matter which property it targets. Per Motion's current docs, the independent transform props
(`x`, `y`, `scale`) are CSS-variable-driven and exist for gesture/per-axis control — not
compositor-accelerated; animating the direct `transform` string is the accelerated path when
that's crucial. Verify against the installed version's docs before asserting either way — see
`motion/emil-craft.md` → Framer Motion.

Two mitigations when motion must survive a busy main thread:

- For simple, independent `transform`/`opacity` motion, prefer the browser's compositor — a CSS
  transition/keyframe or the Web Animations API runs off the main thread. (Whether Framer Motion
  offloads a given animation has changed across versions — verify against the installed
  version's docs rather than assuming; see `motion/emil-craft.md` → Framer Motion.)
- Keep perpetual animations off the React render path (next bullet).

Additional rules:

- Perpetual animations (carousels, spinners): isolate in their own `"use client"` leaf so they don't trigger parent re-renders.
- Grain/noise overlays: `position: fixed; pointer-events: none` pseudo-elements only — never on scrolling containers (GPU repaint cost).

For full animation craft and timing tokens → [layer-5-motion.md](layer-5-motion.md).

---

### Implementation Anti-Patterns

Quick reject list.

| Anti-pattern                                   | Fix                                  |
| ---------------------------------------------- | ------------------------------------ |
| `outline: none` without `:focus-visible`       | Add `:focus-visible` ring            |
| `<div onClick>`                                | `<button type="button">`             |
| Dynamic Tailwind classes `bg-${x}-500`         | Static object map                    |
| Animating layout props (width, height, margin) | Use `transform` only                 |
| `h-screen` for full-height                     | `min-h-[100dvh]`                     |
| Flex percentage math                           | CSS Grid                             |
| Arbitrary `z-[9999]`                           | Token scale                          |
| Importing without checking `package.json`      | Verify first, emit install command   |
| `user-scalable=no` / `maximum-scale=1`         | Remove — disables accessibility zoom |
| Disabled submit before first attempt           | Show errors on submit, not on load   |

---

### Browser and Standards Compliance

See `review-protocol.md` § Web-Interface Compliance for the full audit pass.
