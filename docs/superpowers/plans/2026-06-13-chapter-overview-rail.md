# Chapter Overview Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a quiet, sticky course-overview rail to the homepage so readers can see all published chapters at a glance and jump to any of them.

**Architecture:** Wrap the homepage chapter list in a two-column grid (方案 A): Hero/Footer stay full-width; a new `ChapterRail.astro` occupies a sticky left column on `lg+`, and collapses to a sticky top "课程目录" bar + tap-to-open dropdown below `lg`. Rail data is derived in `index.astro` (published chapters only, same source as the cards) and passed in as a prop. Scrollspy (IntersectionObserver) + smooth-scroll anchors drive the active state. The rail is visually low-emphasis: no border/background, muted text, with the only accent being a 1px gold tick on the active item.

**Tech Stack:** Astro (static), Tailwind CSS v4, vanilla TS in `<script>` (no test runner — verification is `npm run build` + dev-server visual checks). `html { scroll-behavior: smooth }` is already global.

**Verification model:** This is a static-site UI change with no unit-test harness. Each task verifies via `npm run build` (must pass) and, where behavior is visual/interactive, a `npm run dev` manual check with explicit expected observations. Commit after each task.

---

## File Structure

- **Create:** `src/components/ChapterRail.astro` — owns rail markup (desktop nav + mobile bar/dropdown), the `RailSection`/`RailItem` prop shape, and the scrollspy/smooth-scroll/toggle script. One responsibility: course navigation UI.
- **Modify:** `src/pages/index.astro` — widen container to `max-w-6xl`; build the `railSections` data; wrap section list in the two-column grid; render `<ChapterRail>`; add `sec-*`/`ch-*` anchors + `scroll-mt-24`.
- **Unchanged:** `src/styles/global.css` — all rail styling lives in the component's scoped `<style>` block (active tick, mobile bar, focus, reduced-motion). The global `html { scroll-behavior: smooth }` already present is reused, and overridden for reduced-motion via `:global(html)` from the component.
- **Unchanged:** `ChapterCard.astro`, `Header.astro`, `Footer.astro`, `SectionHeading.astro` (anchor added via a wrapping element in `index.astro`, not by changing the component), `scripts/chapters.json`.

---

## Task Overview (skeleton — code filled in below)

- **Task 1: Derive `railSections` data in `index.astro`**
  Compute the published-only, grouped section→chapters structure (`{id, title}` per item) and widen container. No layout change yet; verify build + that data is correct.

- **Task 2: Add anchors + `scroll-mt-24` to sections and cards**
  Put `id="sec-<section>"` on each `<section>` wrapper and `id="ch-<id>"` on a wrapper around each card; add `scroll-mt-24` so smooth-scroll targets aren't clipped. Verify anchors resolve.

- **Task 3: Create `ChapterRail.astro` — desktop rail markup + quiet styles (no JS yet)**
  Static `<nav>` with sections/chapters as real anchor links, muted styling, `hidden lg:block`. Verify it renders and links jump (via global smooth-scroll).

- **Task 4: Wrap homepage in two-column grid; mount the rail**
  Add `lg:grid lg:grid-cols-[210px_minmax(0,1fr)]` wrapper around rail + content. Verify desktop two-column layout; content column not narrower than before; Hero/Footer full-width.

- **Task 5: Add scrollspy + active-state JS to the rail**
  IntersectionObserver sets `aria-current`/active class on the nearest card's rail item; auto-scroll active item into rail view. Verify highlight tracks scroll.

- **Task 6: Add mobile bar + dropdown (markup, styles, toggle JS)**
  `lg:hidden` sticky "课程目录" bar showing current section; tap toggles a disclosure panel reusing the same items; tap item/✕/outside closes + scrolls. Verify on narrow viewport.

- **Task 7: a11y + reduced-motion + final build/visual pass**
  `aria-label`/`aria-current`/`aria-expanded`/`aria-controls`, Esc-to-close, focus-visible states, `prefers-reduced-motion`. Final `npm run build` + responsive walkthrough against acceptance criteria.

---

## Detailed Tasks

> **Note for the implementer:** In `src/pages/index.astro`, every chapter — *including* 准备篇 — already renders a `ChapterCard` inside the `grid md:grid-cols-2` block (lines ~164-178). The 准备篇 skills-promo block (lines ~117-160) is only an alternate *heading*; the cards still render below it. So `ch-<id>` card anchors are uniform across all sections — there is no special-case anchor for 准备篇.

### Task 1: Derive `railSections` data and widen container

**Files:**
- Modify: `src/pages/index.astro` (frontmatter ~lines 10-19; `<main>` ~line 35)

- [ ] **Step 1: Add `railSections` derivation to the frontmatter**

In `src/pages/index.astro`, find this existing block:

```js
const sections = ['准备篇', '认知篇', '核心篇', '进阶篇', '实战篇'] as const;
const grouped = sections.map(section => ({
  section,
  chapters: sorted.filter(ch => ch.data.section === section),
}));
```

Add directly below it:

```js
// Rail navigation data: published chapters only, sections with >=1 published chapter.
// Same source as the cards, so rail items always have a matching card anchor (ch-<id>).
const railSections = grouped
  .map(({ section, chapters }) => ({
    section,
    items: chapters
      .filter(ch => ch.data.published)
      .map(ch => ({ id: ch.id, title: ch.data.title })),
  }))
  .filter(group => group.items.length > 0);
```

- [ ] **Step 2: Widen the main container**

Change line ~35 from:

```astro
  <main class="max-w-5xl mx-auto px-6">
```

to:

```astro
  <main class="max-w-6xl mx-auto px-6">
```

- [ ] **Step 3: Verify build passes and data is correct**

Run: `npm run build`
Expected: build succeeds, no errors.

Then sanity-check the derived data shape (run from repo root):

```bash
node -e 'const d=require("./scripts/chapters.json");const secs=["准备篇","认知篇","核心篇","进阶篇","实战篇"];const g=secs.map(s=>({section:s,items:Object.entries(d).filter(([,c])=>c.section===s&&c.published).map(([id])=>id)})).filter(x=>x.items.length);console.log(JSON.stringify(g.map(x=>({section:x.section,n:x.items.length})),null,0));'
```

Expected output (实战篇 absent, 4 groups):
`[{"section":"准备篇","n":2},{"section":"认知篇","n":2},{"section":"核心篇","n":4},{"section":"进阶篇","n":2}]`

- [ ] **Step 4: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat: derive railSections data and widen homepage container"
```

---

### Task 2: Add anchors and scroll-margin to sections and cards

**Files:**
- Modify: `src/pages/index.astro` (per-section `<section>` ~line 116; card grid ~lines 164-178)

- [ ] **Step 1: Add a section anchor id**

Find the per-section opening tag (~line 116):

```astro
        <section class="mb-12">
```

Change it to (interpolating the section name as a stable anchor, with scroll offset):

```astro
        <section id={`sec-${section}`} class="mb-12 scroll-mt-24">
```

- [ ] **Step 2: Wrap each card with a `ch-<id>` anchor**

Find the card grid map (~lines 164-178):

```astro
          <div class="grid md:grid-cols-2 gap-5">
          {chapters.map(ch => (
            <ChapterCard
              id={ch.id}
              title={ch.data.title}
              chapter={ch.data.chapter}
              section={ch.data.section}
              description={ch.data.description}
              published={ch.data.published}
              slides={ch.data.slides}
              bilibili={ch.data.bilibili}
              xhs={ch.data.xhs}
            />
          ))}
        </div>
```

Wrap the `<ChapterCard>` in an anchor `<div>` (keeps each card a direct grid item):

```astro
          <div class="grid md:grid-cols-2 gap-5">
          {chapters.map(ch => (
            <div id={`ch-${ch.id}`} class="scroll-mt-24">
              <ChapterCard
                id={ch.id}
                title={ch.data.title}
                chapter={ch.data.chapter}
                section={ch.data.section}
                description={ch.data.description}
                published={ch.data.published}
                slides={ch.data.slides}
                bilibili={ch.data.bilibili}
                xhs={ch.data.xhs}
              />
            </div>
          ))}
        </div>
```

- [ ] **Step 3: Verify build + anchors resolve**

Run: `npm run build`
Expected: build succeeds.

Run: `npm run dev`, open the printed URL, then in the browser address bar append `#ch-ch03-virtual-filesystem` and press Enter.
Expected: page smooth-scrolls to the ch03 card, and the card sits ~6rem below the top (not flush against it) thanks to `scroll-mt-24`. Also try `#sec-核心篇` → scrolls to the 核心篇 heading.

- [ ] **Step 4: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat: add sec/ch scroll anchors to homepage sections and cards"
```

---

### Task 3: Create `ChapterRail.astro` — desktop rail markup + quiet styles (no JS yet)

**Files:**
- Create: `src/components/ChapterRail.astro`
- Modify: `src/pages/index.astro` (import + render, temporary placement — final placement in Task 4)

- [ ] **Step 1: Create the component with desktop-only markup**

Create `src/components/ChapterRail.astro`:

```astro
---
interface RailItem {
  id: string;
  title: string;
}
interface RailSection {
  section: string;
  items: RailItem[];
}
interface Props {
  sections: RailSection[];
}

const { sections } = Astro.props;
const base = import.meta.env.BASE_URL;
---

{/* Desktop rail: quiet, sticky, lg+ only. Mobile bar/dropdown added in Task 6. */}
<nav class="chapter-rail hidden lg:block sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto" aria-label="课程目录">
  <p class="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-muted/35 mb-3">目录</p>
  {sections.map(group => (
    <div class="mb-4 last:mb-0">
      <p class="text-[11px] tracking-wide text-ink-muted/55 mb-1.5">{group.section}</p>
      <ul class="space-y-0.5">
        {group.items.map(item => (
          <li>
            <a
              href={`${base}/#ch-${item.id}`}
              data-rail-target={`ch-${item.id}`}
              class="rail-link block truncate py-1 pl-3 text-[13px] leading-snug text-ink-muted/55 hover:text-ink transition-colors"
            >{item.title}</a>
          </li>
        ))}
      </ul>
    </div>
  ))}
</nav>

<style>
  /* Active item (set by scrollspy JS in Task 5): firm the text + a single 1px gold tick.
     This is the only color in the rail. No background, no bold gold text. */
  .rail-link {
    border-left: 1px solid transparent;
    margin-left: -1px; /* keep text aligned whether or not the tick shows */
  }
  .rail-link.is-active {
    color: var(--color-ink);
    border-left-color: var(--color-gold-light);
  }
</style>
```

Note: `href` uses `/#ch-...` (not bare `#ch-...`) so it also works as a real link from the built site; the global `scroll-behavior: smooth` animates the jump even before Task 5's JS exists. The `data-rail-target` attribute is the hook the scrollspy script uses in Task 5.

- [ ] **Step 2: Temporarily render it to verify in isolation**

In `src/pages/index.astro`, add the import alongside the other component imports (~line 6):

```astro
import ChapterRail from '../components/ChapterRail.astro';
```

Then, temporarily, place it right after `<main ...>` opens (~line 35), BEFORE the Hero — this is throwaway placement just to see it render; Task 4 moves it into the grid:

```astro
  <main class="max-w-6xl mx-auto px-6">
    <ChapterRail sections={railSections} />
```

- [ ] **Step 3: Verify build + render + quiet styling + link jump**

Run: `npm run build`
Expected: build succeeds.

Run: `npm run dev`, open the URL on a wide (≥1024px) window.
Expected:
- A column of soft grey text appears at the top-left of `<main>`: a faint "目录" label, then section names (准备篇/认知篇/核心篇/进阶篇) each with their chapter titles below, all in light muted grey — no borders, no background, no number badges, no icons.
- Hovering a chapter title darkens it to near-black (`text-ink`); no background box appears.
- Clicking a chapter title smooth-scrolls down to that chapter's card.

- [ ] **Step 4: Commit**

```bash
git add src/components/ChapterRail.astro src/pages/index.astro
git commit -m "feat: add ChapterRail component with quiet desktop markup"
```

---

### Task 4: Wrap homepage in two-column grid; mount the rail

**Files:**
- Modify: `src/pages/index.astro` (remove temp placement from Task 3; wrap section list in grid)

- [ ] **Step 1: Remove the temporary rail placement**

Delete the throwaway `<ChapterRail sections={railSections} />` line added in Task 3 Step 2 (the one right after `<main>`).

- [ ] **Step 2: Wrap the section list in a two-column grid with the rail in column 1**

The Hero `<section>` (~lines 37-110) stays exactly where it is, full-width, directly inside `<main>`. Immediately AFTER the Hero `</section>` and BEFORE the `{grouped.map(...)}` block, open the grid wrapper. The structure becomes:

```astro
    </section>   <!-- end Hero -->

    <div class="lg:grid lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-10 lg:items-start">
      <ChapterRail sections={railSections} />
      <div class="min-w-0">
        {grouped.map(({ section, chapters }) => {
          /* ...existing section-rendering code, UNCHANGED... */
        })}
      </div>
    </div>
```

Concretely: insert `<div class="lg:grid lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-10 lg:items-start">` + `<ChapterRail sections={railSections} />` + `<div class="min-w-0">` right after the Hero closes, and add the two matching closing `</div>` tags right after the `{grouped.map(...)}` expression ends (before `</main>`). Do not change anything inside the map callback.

`lg:items-start` ensures the sticky rail measures against the grid row top; `min-w-0` on the content column prevents long card content from blowing out the grid track.

- [ ] **Step 3: Verify desktop two-column layout**

Run: `npm run build`
Expected: build succeeds.

Run: `npm run dev`, wide window (≥1024px).
Expected:
- Hero is still full-width and centered (NOT squeezed into a column).
- Below the Hero: the quiet rail sits in a ~210px left column; the chapter cards render in the right column, still two-up (`md:grid-cols-2`).
- The content column is not visibly narrower than before (container is now `max-w-6xl`, and the rail occupies the added width).
- Scrolling down: the rail stays pinned (`sticky top-24`) while cards scroll.

Resize the window below 1024px.
Expected: the grid collapses to a single column, the rail disappears (`hidden lg:block`), and the page looks like the original (cards stack as before). Mobile nav comes in Task 6.

- [ ] **Step 4: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat: two-column homepage grid with sticky chapter rail"
```

---

### Task 5: Add scrollspy + active-state JS to the rail

**Files:**
- Modify: `src/components/ChapterRail.astro` (append a `<script>` block)

- [ ] **Step 1: Add the scrollspy script**

Append this `<script>` to the END of `src/components/ChapterRail.astro` (after the `<style>` block). Astro bundles and scopes component scripts; this runs on the homepage where the rail exists.

```astro
<script>
  // Scrollspy: highlight the rail item whose card is nearest the top of the viewport.
  // Rail links carry data-rail-target="ch-<id>"; cards have id="ch-<id>".
  function initChapterRail() {
    const links = Array.from(
      document.querySelectorAll<HTMLAnchorElement>('.chapter-rail .rail-link[data-rail-target]')
    );
    if (links.length === 0) return;

    const linkByTarget = new Map<string, HTMLAnchorElement>();
    for (const link of links) {
      const t = link.dataset.railTarget;
      if (t) linkByTarget.set(t, link);
    }

    const cards = links
      .map((l) => document.getElementById(l.dataset.railTarget!))
      .filter((el): el is HTMLElement => el !== null);
    if (cards.length === 0) return;

    let activeId = '';
    const setActive = (id: string) => {
      if (id === activeId) return;
      activeId = id;
      for (const link of links) {
        const on = link.dataset.railTarget === id;
        link.classList.toggle('is-active', on);
        if (on) {
          link.setAttribute('aria-current', 'true');
          // Keep the active item visible if the rail itself scrolled.
          link.scrollIntoView({ block: 'nearest' });
        } else {
          link.removeAttribute('aria-current');
        }
      }
    };

    // Track which cards are currently intersecting; pick the topmost one.
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        // Choose the visible card highest on the page (smallest top offset).
        let topId = '';
        let topY = Infinity;
        for (const id of visible) {
          const el = document.getElementById(id);
          if (!el) continue;
          const y = el.getBoundingClientRect().top;
          if (y < topY) {
            topY = y;
            topId = id;
          }
        }
        if (topId) setActive(topId);
      },
      // Bias the active band toward the upper part of the viewport so the
      // highlight changes as a card reaches the top, reducing boundary jitter.
      { rootMargin: '-20% 0px -70% 0px', threshold: 0 }
    );

    for (const card of cards) observer.observe(card);
  }

  initChapterRail();
  // Re-init after Astro view transitions / client navigations, if ever enabled.
  document.addEventListener('astro:page-load', initChapterRail);
</script>
```

- [ ] **Step 2: Verify the active highlight tracks scrolling**

Run: `npm run build`
Expected: build succeeds (TypeScript in the script compiles).

Run: `npm run dev`, wide window. Slowly scroll from top to bottom.
Expected:
- As each chapter card reaches roughly the upper-third of the viewport, its rail item becomes active: text firms to near-black AND a thin gold vertical tick appears on its left edge. Exactly one item is active at a time.
- The previously active item reverts to muted grey with no tick.
- Clicking a rail item scrolls to that card and that item becomes active.
- No console errors.

- [ ] **Step 3: Commit**

```bash
git add src/components/ChapterRail.astro
git commit -m "feat: scrollspy active-state for chapter rail"
```

---

### Task 6: Add mobile bar + dropdown (markup, styles, toggle JS)

**Files:**
- Modify: `src/components/ChapterRail.astro` (add mobile markup before the desktop `<nav>`; extend `<style>` and `<script>`)

- [ ] **Step 1: Add the mobile bar + dropdown markup**

In `src/components/ChapterRail.astro`, directly BEFORE the desktop `<nav class="chapter-rail ...">`, add this `lg:hidden` block. It reuses the same `sections` data.

```astro
{/* Mobile/tablet (<lg): sticky bar + tap-to-open dropdown. */}
<div class="chapter-rail-mobile lg:hidden" data-rail-mobile>
  <button
    type="button"
    class="chapter-rail-mobile__bar"
    aria-expanded="false"
    aria-controls="chapter-rail-panel"
    data-rail-toggle
  >
    <span class="inline-flex items-center gap-2">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
      <span class="text-sm font-medium">课程目录</span>
    </span>
    <span class="text-xs text-ink-muted/60" data-rail-current></span>
  </button>
  <div id="chapter-rail-panel" class="chapter-rail-mobile__panel" hidden>
    {sections.map(group => (
      <div class="mb-3 last:mb-0">
        <p class="text-[11px] tracking-wide text-ink-muted/55 mb-1">{group.section}</p>
        <ul class="space-y-0.5">
          {group.items.map(item => (
            <li>
              <a
                href={`${base}/#ch-${item.id}`}
                data-rail-target={`ch-${item.id}`}
                class="rail-link block truncate py-1.5 pl-3 text-[13px] text-ink-muted/70 hover:text-ink transition-colors"
              >{item.title}</a>
            </li>
          ))}
        </ul>
      </div>
    ))}
  </div>
</div>
```

- [ ] **Step 2: Add mobile styles**

Add these rules inside the component's `<style>` block (alongside the `.rail-link` rules):

```css
.chapter-rail-mobile {
  position: sticky;
  top: 0;
  z-index: 30;
  margin: 0 -1.5rem 1.5rem; /* bleed to viewport edges (counteract main px-6) */
  background: var(--color-paper);
  border-bottom: 1px solid var(--color-gold-pale);
}
.chapter-rail-mobile__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.75rem 1.5rem;
  color: var(--color-ink);
  background: transparent;
  border: none;
  cursor: pointer;
}
.chapter-rail-mobile__panel {
  max-height: 60vh;
  overflow-y: auto;
  padding: 0.5rem 1.5rem 1rem;
  border-top: 1px solid var(--color-gold-pale);
}
```

Note: the mobile panel reuses `.rail-link` / `.is-active` from Task 3's style block, so the active tick works there too.

- [ ] **Step 3: Extend the script to drive the bar + toggle**

In the component `<script>`, inside `initChapterRail()`, BEFORE the final `}` of the function, add toggle + current-section wiring. Add this block after the `observer` setup (after the `for (const card of cards) observer.observe(card);` line):

```javascript
    // --- Mobile bar: toggle panel + reflect current section ---
    const mobile = document.querySelector<HTMLElement>('[data-rail-mobile]');
    const toggle = document.querySelector<HTMLButtonElement>('[data-rail-toggle]');
    const panel = document.getElementById('chapter-rail-panel');
    const currentLabel = document.querySelector<HTMLElement>('[data-rail-current]');

    const closePanel = () => {
      if (!toggle || !panel) return;
      toggle.setAttribute('aria-expanded', 'false');
      panel.hidden = true;
    };
    const openPanel = () => {
      if (!toggle || !panel) return;
      toggle.setAttribute('aria-expanded', 'true');
      panel.hidden = false;
    };

    if (toggle && panel) {
      toggle.addEventListener('click', () => {
        if (panel.hidden) openPanel();
        else closePanel();
      });
      // Tap an item: close, then let the anchor scroll happen.
      panel.querySelectorAll('a[data-rail-target]').forEach((a) =>
        a.addEventListener('click', () => closePanel())
      );
      // Tap outside closes.
      document.addEventListener('click', (e) => {
        if (!mobile) return;
        if (!panel.hidden && !mobile.contains(e.target as Node)) closePanel();
      });
      // Esc closes.
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !panel.hidden) closePanel();
      });
    }

    // Reflect the active card's SECTION name in the mobile bar.
    const sectionOfTarget = new Map<string, string>();
    document.querySelectorAll<HTMLElement>('[data-rail-mobile] [data-rail-target]').forEach((a) => {
      const group = a.closest('div');
      const label = group?.querySelector('p')?.textContent?.trim();
      const t = (a as HTMLElement).dataset.railTarget;
      if (label && t) sectionOfTarget.set(t, label);
    });
```

Then, INSIDE the existing `setActive` function, after the `activeId = id;` line, add the current-label update:

```javascript
      if (currentLabel) {
        const label = sectionOfTarget.get(id);
        if (label) currentLabel.textContent = label;
      }
```

(`currentLabel` and `sectionOfTarget` are declared below `setActive` in source order, but `setActive` only runs from observer/click callbacks that fire after init completes, so the closure references resolve fine. If the implementer prefers, hoist the two `const`s above `setActive` — functionally identical.)

- [ ] **Step 4: Verify on a narrow viewport**

Run: `npm run build`
Expected: build succeeds.

Run: `npm run dev`. Open the URL and narrow the window to <1024px (or use device toolbar at ~390px).
Expected:
- The desktop rail is gone. A sticky "☰ 课程目录" bar sits at the top of the content area and stays pinned as you scroll past the Hero.
- The right side of the bar shows the current section name (e.g. "核心篇") and updates as you scroll.
- Tapping the bar opens a panel listing all sections + chapters; `aria-expanded` flips to `true`.
- Tapping a chapter closes the panel and scrolls to that card.
- Tapping outside the bar/panel, or pressing Esc, closes the panel.
- No console errors.

- [ ] **Step 5: Commit**

```bash
git add src/components/ChapterRail.astro
git commit -m "feat: mobile chapter-rail bar and dropdown panel"
```

---

### Task 7: a11y, reduced-motion, and final acceptance pass

**Files:**
- Modify: `src/components/ChapterRail.astro` (focus-visible + reduced-motion styles)

- [ ] **Step 1: Add focus-visible and reduced-motion styles**

The idle rail text is intentionally faint (`/55`), so keyboard focus must be clearly visible. Add to the component `<style>` block:

```css
.rail-link:focus-visible {
  outline: none;
  color: var(--color-ink);
  border-left-color: var(--color-gold);
  background: var(--color-gold-pale);
  border-radius: 2px;
}

@media (prefers-reduced-motion: reduce) {
  /* The global `html { scroll-behavior: smooth }` is overridden for users
     who prefer reduced motion; rail jumps become instant. */
  :global(html) {
    scroll-behavior: auto;
  }
}
```

- [ ] **Step 2: Verify keyboard a11y and reduced-motion**

Run: `npm run build`
Expected: build succeeds.

Run: `npm run dev`, wide window.
Expected:
- Press Tab repeatedly to move focus into the rail. Each focused chapter link shows a clear gold-pale highlight + gold tick (not just faint grey). Pressing Enter on a focused link jumps to that card.
- The mobile toggle button is reachable by keyboard; Enter opens/closes the panel; Esc closes it.
- Inspect the rail `<nav>`: it has `aria-label="课程目录"`; the active link has `aria-current="true"`; the mobile toggle has `aria-expanded` reflecting state and `aria-controls="chapter-rail-panel"`.

Then enable "Reduce motion" (OS setting or DevTools → Rendering → Emulate `prefers-reduced-motion: reduce`) and click a rail link.
Expected: the jump is instant (no smooth animation).

- [ ] **Step 3: Final acceptance pass against the spec**

Walk through every acceptance criterion from the design spec (`docs/superpowers/specs/2026-06-13-chapter-overview-rail-design.md` §9):

1. Desktop ≥lg: Hero full-width (not squeezed); quiet rail left + cards right; content column not narrower than before. ✅ check visually.
2. Scrollspy highlight = text darken + 1px gold tick only; no background block, no gold text on idle. ✅
3. Click rail item → smooth-scroll to card; card not clipped under any sticky element (`scroll-mt-24`). ✅
4. Rail lists published chapters only; 实战篇 absent; every rail item maps to a real card (no dead anchors). ✅ — confirm by clicking each.
5. Mobile <lg: left rail hidden; sticky "课程目录" bar + dropdown works. ✅
6. JS disabled: rail links still jump. ✅ — in DevTools, disable JS, reload, click a rail link; it should still navigate to the `#ch-...` anchor (instant, no scrollspy).
7. `npm run build` passes; image-path / assets checks unaffected (no content/ or public/ changes). ✅
8. No new color system; gold only in existing places + the 1px active tick + focus ring. ✅

Run the build one final time:

Run: `npm run build`
Expected: build succeeds with no errors or warnings related to the new component.

- [ ] **Step 4: Commit**

```bash
git add src/components/ChapterRail.astro
git commit -m "feat: chapter-rail focus-visible and reduced-motion a11y"
```

---

## Notes for the implementer

- **No test runner exists** in this repo — do not invent one or add Vitest/Jest. Verification is `npm run build` + the dev-server visual checks described per task.
- **`scroll-mt-24`** = `scroll-margin-top: 6rem`. The site Header is NOT sticky on desktop, so 6rem is generous headroom; on mobile it also clears the sticky 课程目录 bar (~3rem) comfortably.
- **Tailwind v4 arbitrary values** like `lg:grid-cols-[210px_minmax(0,1fr)]` and `max-h-[calc(100vh-7rem)]` are supported by the `@tailwindcss/vite` plugin in use — no config change needed.
- **Do not modify** `ChapterCard.astro`, `Header.astro`, `Footer.astro`, `SectionHeading.astro`, or `scripts/chapters.json`. All anchors are added via wrapper elements in `index.astro`.
- **Branch:** work continues on `feat/chapter-overview-rail` (already created; the spec commit lives there).
- After all tasks: open a PR against `main`. The CI `check-image-paths` workflow only triggers on `content/**/*.md`, which this PR does not touch, so it won't run; `verify-assets` may run on push.

