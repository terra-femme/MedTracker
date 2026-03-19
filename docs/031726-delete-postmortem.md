# Delete Bug — Full Postmortem
**Date:** 2026-03-17
**Bugs fixed:** B-2 (permanent delete broken), B-3 (sw.js 404), accidental data wipe, browser JS cache
**Status:** Resolved

---

## What the user reported

> "The delete button still archives, which is fine, but even when it is archived and I press delete it still is not deleted. It stays on the screen and I can even restore it. The green banner for deletion even appears but no true deletion happens."

Two separate problems were happening at once:

1. The delete button was calling the wrong API URL (no `?permanent=true`)
2. The browser was running a cached version of `app.js` from weeks ago, so even after the code was fixed, the fix never reached the browser

---

## Problem 1 — `?permanent=true` was never sent

### What the backend expected

```
DELETE /medications/3?permanent=true   →  hard delete (removes from DB)
DELETE /medications/3                  →  soft delete / archive (sets is_active=False)
```

The backend router (`medications.py`) has a `permanent: bool = False` query parameter. If it is not present in the URL, it defaults to `False` and the medication is just archived.

### What the frontend was actually sending

```javascript
// OLD — no permanent param, always archives
deleteMedication: (id) => authFetch(`/medications/${id}`, {
    method: 'DELETE'
}).then(r => r.json()),
```

The `deleteMedication` JS function called `API.deleteMedication(id)` with no second argument, and the API method built a URL with no query string. Every delete was silently becoming an archive.

### The fix

```javascript
// NEW — passes permanent=true when requested
deleteMedication: (id, permanent = false) => {
    const url = `/medications/${id}${permanent ? '?permanent=true' : ''}`;
    return authFetch(url, { method: 'DELETE' }).then(r => r.json());
},
```

And the caller:

```javascript
// Before
await API.deleteMedication(id);

// After
await API.deleteMedication(id, true);
```

---

## Problem 2 — Browser JS cache: the fix that wasn't

### What happened

After fixing the JS, the browser still ran the old code. A hard refresh (Ctrl+Shift+R) did not help. To confirm the browser was running old code, this was typed in the DevTools console:

```javascript
API.deleteMedication.toString()
```

The output was the old function — no `permanent` parameter, no `?permanent=true`. The fix was in the file on disk but the browser had no idea.

### Why this happens

When a browser loads a file like `/static/app.js`, it stores a copy in its local cache. On subsequent visits it checks: "do I already have this?" — and if yes, it serves the cached copy without asking the server. This is called **browser caching** and it normally makes websites load faster.

The problem: the browser identifies files by their URL. `/static/app.js` today looks identical to `/static/app.js` last week. The browser has no way to know the contents changed unless:

- The server sends a `Cache-Control: no-cache` header (telling the browser to always revalidate), or
- The URL changes

The FastAPI `StaticFiles` mount does not set `Cache-Control` headers by default, so the browser cached `app.js` aggressively.

Even `Ctrl+Shift+R` (hard refresh) does not always clear a strongly-cached file. It forces a network request for the HTML page itself, but linked resources like JS files may still be served from disk cache depending on the browser version and cache headers.

### The fix — cache-busting via version query string

The URL was changed in `index.html`:

```html
<!-- Before -->
<script src="/static/app.js"></script>

<!-- After -->
<script src="/static/app.js?v=2"></script>
```

The `?v=2` is meaningless to the server — FastAPI ignores it and serves the same file. But to the browser, `/static/app.js?v=2` is a completely different URL from `/static/app.js`. It has nothing cached for that URL, so it fetches fresh.

**Every time you change `app.js` and need the browser to pick it up immediately, increment this number.** `?v=2` → `?v=3` → `?v=4`, etc. This is called a **cache-bust**.

### How to know you're running the new JS

Open DevTools (F12) → Console tab → type:

```javascript
API.deleteMedication.toString()
```

If the output shows `permanent = false` in the function signature, the new JS is loaded. If it shows the old one-liner with just `(id) =>`, you're still on the cache. Increment the version and refresh.

---

## Problem 3 — Accidental data wipe of active medications

### What happened

Once the new JS loaded, the delete button worked. But active medications disappeared alongside the archived test entries the user intended to delete.

### Root cause: Delete button was visible on active medications

`loadMedications()` renders **all** medications — both active and archived — in one list. The Delete (trash) button was rendered on every card, regardless of whether the medication was active or archived.

Active medication card buttons: **Edit · Archive · Delete**
Archived medication card buttons: **Edit · Restore · Delete**

The user expected the flow to be:
```
Active → Archive → then Delete
```

But the UI allowed:
```
Active → Delete directly (permanent, no going back)
```

When the delete button finally worked with the new JS, the user likely clicked it on active medications while testing, confirmed both dialogs, and the medications were permanently removed from the database.

### Why the data was unrecoverable

`MedicationAgent.delete(permanent=True)` does three things in order:

```python
# 1. Delete all dose logs for this medication
self.db.query(MedicationLog).filter(
    MedicationLog.medication_id == medication_id
).delete()

# 2. Delete all reminders for this medication
self.db.query(Reminder).filter(
    Reminder.medication_id == medication_id
).delete()

# 3. Delete the medication itself
self.db.delete(med)
self.db.commit()
```

No soft delete, no recycle bin, no backup. Once committed to SQLite, the rows are gone. Without a database backup or Alembic migration history, there is no recovery path.

### The fix — gate permanent delete behind archive

The Delete button is now hidden on active medications entirely:

```javascript
// Before — delete button on every card
<button onclick="deleteMedication(${med.id})">...</button>

// After — delete button only appears on archived medications
${!med.is_active ? `
<button onclick="deleteMedication(${med.id})">...</button>
` : ''}
```

The enforced flow is now:

```
Active medication
    ↓ Archive button
Archived medication  (Restore button available — reversible)
    ↓ Delete button
Permanently deleted  (irreversible)
```

A user can no longer accidentally wipe an active medication in one step.

---

## How to prevent this class of problem in the future

### 1. Always cache-bust after JS changes

When you edit `app.js` or `style.css` and need users (or yourself) to get the new version immediately, increment the version string in `index.html`:

```html
<script src="/static/app.js?v=4"></script>
<link rel="stylesheet" href="/static/style.css?v=4">
```

If you're deploying to production later, a build tool (Webpack, Vite) will do this automatically by hashing file contents. For now, manual version bumping is the correct approach.

### 2. Verify which JS is running before debugging

Any time a fix doesn't seem to work, check the actual loaded code before spending time on the logic:

```javascript
// Check a specific function
API.deleteMedication.toString()

// Check any function
someFunction.toString()
```

If the output doesn't match your source file, it's a cache problem, not a logic problem.

### 3. Irreversible operations need a two-step UI gate

Any operation that permanently destroys data should require the user to pass through a reversible intermediate state first. In this app:

- Archive = reversible (Restore button available)
- Delete = irreversible (no recovery)

Making delete only available from the archived state means a user always has one chance to reconsider before the data is gone.

### 4. Consider adding Alembic + DB backups (T-009)

The medications that were wiped today were test data, so no real loss. But when real patient data is involved, the absence of database backups is a serious risk. T-009 (Add Alembic) is on the task list and will give you a migration history. Pairing that with a daily SQLite backup (even just copying `medtracker.db` to a timestamped file) would allow recovery from accidental deletes.

```bash
# Simple daily backup — add to a cron job or Task Scheduler
copy medtracker.db backups\medtracker_%date:~-4,4%%date:~-10,2%%date:~-7,2%.db
```

---

## Summary of all changes made this session

| File | Change | Why |
|------|--------|-----|
| `frontend/app.js` | `API.deleteMedication` now accepts `permanent` param and appends `?permanent=true` to URL | Fix was never being sent to backend |
| `frontend/app.js` | `deleteMedication()` passes `true` to `API.deleteMedication` | Same |
| `frontend/app.js` | `clearAllData()` passes `true` to `API.deleteMedication` | Consistency — clear all should also permanently delete |
| `frontend/app.js` | Delete button hidden on active medications | Prevent accidental wipe of active data |
| `frontend/index.html` | `app.js?v=2` → `app.js?v=3` (incremented twice) | Force browser to load new JS, bypassing cache |
| `backend/agents/schedule_agent.py` | `taken_med_ids` replaced with `taken_logs_by_med` (list per medication) | AM/PM dose collision fix (B-1) |
| `backend/main.py` | Added `/sw.js` route serving `frontend/sw.js` | Fix 404 on service worker (B-3) |
| `frontend/app.js` | SW registered from `/sw.js` not `/static/sw.js` | Required for correct scope on push notifications |
| `backend/main.py` | Lifespan wrapped in `try/finally` with `scheduler.pause()` before shutdown | Prevent `RuntimeError: cannot schedule new futures after interpreter shutdown` freeze |
