# Layer 4 — States

Every data-driven component declares what it shows while loading, when empty, on error, and when
disabled. These are designed up front, not retrofitted.

> **See also**
>
> - For underlying spacing/typography/motion-timing values → [`layer-1-tokens.md`](layer-1-tokens.md)
> - For layout primitive components (Stack, Inline, Grid, Box, Center) → [`layer-2-primitives.md`](layer-2-primitives.md)
> - For component-level patterns (forms, tables, modals, nav) → [`layer-3-components.md`](layer-3-components.md)
> - For common anti-patterns to avoid → [`anti-patterns.md`](anti-patterns.md)
> - For the **data-wiring side** of these states (when/how loading/error/empty are *produced* — query
>   states, suspense, error boundaries) → `craft-frontend` → `data-fetching.md`. This file owns the
>   *visual* treatment; craft-frontend owns the async plumbing that triggers it.

A component without all four states isn't finished.

---

## The Four States

Every component that fetches, reads, or depends on external data must handle:

1. **Loading** — data is in flight
2. **Empty** — data arrived but there is nothing to show
3. **Error** — data fetch failed or an operation was rejected
4. **Disabled** — the control exists but cannot be interacted with right now

Design all four alongside the happy path. Never treat them as post-launch polish.

---

## Loading States

### Skeleton vs. Spinner

- **Skeletons** for page-level and section-level loading. They communicate layout and reduce
  perceived wait time by giving the eye something to anchor to.
- **Spinners** only for inline actions: button submissions, single-field fetches, inline mutations.
  Never use a spinner for page-level loading — it provides no spatial preview and feels slower.

### Skeleton rules

- Skeleton screens **match content dimensions exactly**. Wrong dimensions cause layout shift on
  reveal, which is worse than no skeleton at all. Measure the real rendered content first.
- Pulse animation: `1.5 s` duration, ease-in-out. Faster feels jittery; slower feels broken.
- Background: `bg-muted` (or the equivalent surface-muted token). Don't use white — it disappears
  on light backgrounds.
- Repeat the skeleton's shape for each item in a list; don't show a single bar for a 10-row table.

```html
<!-- Skeleton: two lines of text content -->
<div class="animate-pulse space-y-2">
  <div class="h-4 bg-muted rounded w-3/4"></div>
  <div class="h-4 bg-muted rounded w-1/2"></div>
</div>

<!-- Skeleton: card with avatar + text -->
<div class="animate-pulse flex gap-3 p-4">
  <div class="h-10 w-10 bg-muted rounded-full shrink-0"></div>
  <div class="flex-1 space-y-2">
    <div class="h-4 bg-muted rounded w-1/2"></div>
    <div class="h-3 bg-muted rounded w-3/4"></div>
  </div>
</div>
```

### Progressive loading

Show what you have; stream the rest. Render cached or partial data immediately, fill in fresh data
as it arrives. Use framework Suspense boundaries to isolate loading regions — don't block the whole
page on a single slow fetch.

### Loading copy

Loading text ends with `…`: "Loading…", "Saving…", "Connecting…". Never "Please wait." (passive)
or bare "Loading" (truncated-feeling).

### Perceived performance

Respond immediately to the action, preserve useful content, and show honest pending/progress state.
Do not speed up a spinner to imply faster processing or add artificial delays. Respect reduced
motion and measure actual responsiveness separately from the visual treatment.

---

## Empty States

### Anatomy

Every empty state has four elements, in this order:

1. **Icon or illustration** — establishes the context at a glance. Use an icon for compact spaces;
   a spot illustration for full-page empties.
2. **Headline** — one sentence, specific to the context. "No messages yet" not "Nothing here."
3. **Description** — one or two sentences explaining why it's empty and what will change. Optional
   for very obvious cases.
4. **Primary CTA** — the single most useful action. This is the most important element; it turns a
   dead end into an onboarding surface. Optional secondary link for "learn more."

```jsx
<EmptyState
  icon={<InboxIcon />}
  title="No messages yet"
  description="When you receive messages, they'll appear here."
  action={<Button>Compose message</Button>}
/>
```

Never render bare "No data" or an empty container. Both are dead ends.

### Context matters

- **Dashboard empty state** (first-run): focus on setup. Guide the user toward their first action.
- **Filtered-list empty state** (no results): focus on the filter. Offer to clear or adjust it.
- **Search empty state**: confirm the query was understood, suggest relaxing constraints.

These are different experiences. Design them separately.

### Placement

Use `<Center minHeight="320px">` (or equivalent) to vertically center empty states in their
container — avoid floating them at the top of a large blank region.

---

## Error States

### Levels of error

| Scope       | Treatment                                         |
| ----------- | ------------------------------------------------- |
| Page-level  | Full error page with illustration + retry + home  |
| Section     | Inline error block within the section             |
| Field-level | Error message below the field with `role="alert"` |
| Toast       | Persistent toast (never auto-dismiss on errors)   |

### Error boundary placement

Place error boundaries at the route level as a minimum. Add finer-grained boundaries around
independently-fetching sections (sidebar, feed, widget) so one failure doesn't crash the whole
page. The boundary's fallback UI should match the shape of the section it replaces — don't show a
full-page error for a widget failure.

### Copy rules

- **Never expose** technical details, stack traces, error codes, or HTTP status numbers to users.
- **Include the fix or next step** in every error message. An error without a recovery path is
  incomplete design.
- **Be direct.** "Connection failed. Please try again." not "Oops! Something went wrong."
- **Active voice.** "We couldn't save your changes." not "Your changes could not be saved."
- **No exclamation marks.** Confidence, not theatrical alarm.

### Recovery actions

Every error state offers at least one of:

- **Retry** — re-attempts the failed operation
- **Go back** — returns to a known-good state
- **Contact support** — escape hatch for unrecoverable errors

Log the real error server-side with full context. Show only the human message client-side.

```jsx
<ErrorState
  title="Couldn't load your posts"
  description="Check your connection and try again."
  action={<Button onClick={retry}>Try again</Button>}
/>
```

---

## Disabled States

### Disabled vs. loading

These are different states and must look different:

- **Disabled** — the control cannot be used because a prerequisite isn't met (permissions,
  plan tier, incomplete form). It may never become available in this context.
- **Loading / pending** — the control triggered an async operation and is temporarily locked.
  It will become interactive again.

Never use a disabled-looking style to communicate "in progress." Use a spinner + `aria-busy` instead.

### Visual treatment

- Opacity: minimum `40%` (`opacity-40`). Below this, users may not notice the element at all;
  above it, the disabled state is ambiguous.
- Cursor: `cursor-not-allowed` on the element, `cursor-default` on the container that swallows
  pointer events.
- No hover state. No focus ring on the interactive element (but preserve focus management so
  keyboard users aren't stranded).
- Color contrast can drop below the standard WCAG ratio for disabled elements — but don't rely on
  low contrast alone. Combine with reduced opacity and `cursor-not-allowed`.

### Communicating why

Whenever a control is disabled, tell users why — either via a tooltip on hover/focus of the
wrapper, or via adjacent explanatory text. Silent disabled states are a usability failure.

> **Do not use the `title` attribute for this.** The `title` attribute is not announced on
> keyboard focus or touch — it is invisible to keyboard-only users and touch device users. Use a
> Radix Tooltip component or `aria-describedby` pointing to a visually-hidden element instead.

```tsx
{/* Option A: Radix Tooltip (preferred — keyboard and touch accessible) */}
<Tooltip.Provider>
  <Tooltip.Root>
    <Tooltip.Trigger asChild>
      {/* Non-disabled span receives focus so the tooltip can trigger */}
      <span className="inline-block cursor-not-allowed">
        <button disabled aria-disabled="true" className="opacity-40 cursor-not-allowed pointer-events-none">
          Export
        </button>
      </span>
    </Tooltip.Trigger>
    <Tooltip.Content>Upgrade to Pro to export</Tooltip.Content>
  </Tooltip.Root>
</Tooltip.Provider>

{/* Option B: aria-describedby with visually-hidden text */}
<div className="inline-block cursor-not-allowed">
  <button
    disabled
    aria-disabled="true"
    aria-describedby="export-hint"
    className="opacity-40 cursor-not-allowed"
  >
    Export
  </button>
  <span id="export-hint" className="sr-only">Upgrade to Pro to export</span>
</div>
```

### `aria-disabled` vs. `disabled`

- `disabled` removes the element from tab order and prevents all events. Use for form inputs.
- `aria-disabled="true"` keeps the element focusable and announces the state to screen readers,
  while JS suppresses the action. Prefer this for buttons in complex flows where keyboard users
  need to reach the element to understand the context.

---

## Optimistic Updates and Rollback

When a mutation is low-latency and high-confidence, apply the result immediately in the UI
before the server confirms — this is the optimistic update pattern. It makes the interface feel
instant and reduces perceived wait time.

**The three-state sequence:**

1. **Optimistic success** — apply the expected result immediately (update UI, mark item as
   saved). No spinner. No delay.
2. **Background mutation** — send the request to the server while the UI already shows success.
3. **On success: offer undo** — the delete already completed optimistically; give the user a
   window to undo the now-completed action. **On error: rollback** — revert the UI to the
   previous state and surface a persistent error toast so the user knows the mutation failed.

```tsx
// Undo after a completed delete requires a server-side restore/soft-delete endpoint
// (e.g. `api.restoreItem(id)`). If the backend hard-deletes with no restore path,
// don't offer Undo at all — use a confirm-before-delete step instead.
async function handleDelete(id: string) {
  // Capture state BEFORE the optimistic update so rollback/undo have something to restore
  const snapshot = items;
  const deletedItem = items.find(item => item.id === id);
  if (!deletedItem) return; // nothing to delete — guard before mutating state

  // 1. Optimistic: remove immediately
  setItems(prev => prev.filter(item => item.id !== id));

  try {
    // 2. Background mutation
    await deleteItem(id);

    // 3. Success: offer undo for the completed delete — Undo must reverse the server
    // state too, not just the local UI, or the UI is lying about what's persisted.
    toast("Item deleted.", {
      action: {
        label: "Undo",
        onClick: async () => {
          setItems(prev => [...prev, deletedItem]);
          await api.restoreItem(id); // reverses the server-side delete
        },
      },
      duration: 5000,
    });
  } catch {
    // 3. Error: rollback to the pre-delete snapshot
    setItems(snapshot);
    toast.error("Couldn't delete item.", {
      duration: Infinity,  // persist until dismissed
    });
  }
}
```

**Rules:**

- **Never silently fail.** A rollback without user notification leaves the UI lying about state.
  Always surface the error and offer a recovery path.
- **Undo action belongs on the success path** — the mutation already completed, so Undo must call
  a server-side restore/soft-delete endpoint, not just re-add the item to local state; restoring
  only the UI while the server stays deleted is a lying UI. If no restore endpoint exists, don't
  offer Undo — use confirm-before-delete instead. Offering Undo on the error path is a
  double-restore bug: the rollback already restored the item, so a second restore duplicates it.
- **Error toast must persist** — do not auto-dismiss error toasts. The user must acknowledge the
  failure before it disappears (use `duration: Infinity` or equivalent).
- **Reserve for low-risk mutations.** Use optimistic updates for deletes, toggles, and simple
  edits. Avoid for financial transactions, publish actions, or mutations the user cannot easily
  undo.
- **The data-wiring side** (query invalidation, cache updates, server state sync) lives in
  `craft-frontend` → `data-fetching.md`. This section owns the visual treatment — what the user
  sees during optimism, rollback, and recovery.

### Preemptive disabling anti-pattern

Do not disable submit buttons before the user has attempted submission. Let the user try; show
inline validation errors on submit. Preemptive disabling removes affordance and confuses users who
don't know which field is blocking them. Exception: a button that has no valid action at all
(e.g., "Export" when the list is empty).
