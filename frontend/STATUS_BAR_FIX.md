# Status Bar Bug — Root Cause & Fix

## What the user saw
The mock iOS status bar (showing time + 📶📡🔋) was invisible or clipped at the top of the browser on every page load and refresh.

---

## Attempts that didn't work

### 1. Removing `<br>` tags and fixing `top: 20px`
The HTML had two `<br>` tags inside a flex container — they don't work as line breaks in flexbox, they become zero-size flex items that push the real content (time, emojis) out of the bar's bounds. `top: 20px` also offset the bar incorrectly.

**Fixed:** removed `<br>` tags, changed `top: 20px` → `top: 0`, changed `align-items: flex-end` → `align-items: center`.

**Result:** still invisible. Reason: height was still broken.

---

### 2. Status bar had zero height in the browser
The height was set to `var(--safe-top)` which used `env(safe-area-inset-top, 44px)`.

The fallback `44px` only applies when `env()` is **not supported at all**. In Chrome desktop, `env()` IS supported but returns `0` (no notch). So the status bar had **0px height**.

**Fixed:** changed height to `max(44px, env(safe-area-inset-top, 44px))`.

**Result:** height now 44px, but still getting clipped. Browser cache also showed old padding values.

---

### 3. Header overlapping the status bar (`--safe-top` = 0 everywhere)
`.app-container` had `padding-top: var(--safe-top)` and `.ios-header` had `top: var(--safe-top)` — both resolving to `0` in the browser. So the header sat at `top: 0`, directly on top of the status bar.

**Fixed:** hardcoded `--safe-top: 44px` in `:root` instead of using `env()`. This cascaded correctly to both `app-container` padding and `ios-header` sticky position.

**Result:** layout correct on initial load, but still disappearing on refresh.

---

### 4. Scroll restoration on refresh
Chrome restores scroll position on refresh. If the page was scrolled even slightly, the restored scroll position made the sticky header jump, making the status bar appear to vanish.

**Fixed:** added to `app.js`:
```js
if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
}
window.scrollTo(0, 0);
```

**Result:** refresh now lands at top. But status bar content still clipped at the very top edge.

---

## The actual root cause

`body { overflow-x: hidden }` in Chrome creates a **scroll container** on the body element. This is a known Chrome behaviour — when the body is a scroll container, `position: fixed` children get clipped at the body's scroll container boundary (the top edge of the viewport), causing the top portion of fixed elements to be cut off.

**Final fix:** changed `overflow-x: hidden` → `overflow-x: clip` on `body`.

```css
body {
    overflow-x: clip; /* not hidden — clip doesn't create a scroll container */
}
```

`overflow-x: clip` prevents horizontal overflow without creating a scroll container, so `position: fixed` elements are no longer clipped.

---

## Summary of all changes made

| File | Change |
|------|--------|
| `frontend/index.html` | Removed two `<br>` tags inside `.status-bar` |
| `frontend/style.css` | `top: 20px` → `top: 0` on `.status-bar` |
| `frontend/style.css` | `height: var(--safe-top)` → `height: 44px` on `.status-bar` |
| `frontend/style.css` | `align-items: flex-end` → `align-items: center` on `.status-bar` |
| `frontend/style.css` | `--safe-top: env(safe-area-inset-top, 44px)` → `--safe-top: 44px` |
| `frontend/style.css` | `overflow-x: hidden` → `overflow-x: clip` on `body` ← **the real fix** |
| `frontend/app.js` | Disabled scroll restoration, force scroll to top on load |
