# T-014 — Move Platform-Specific Time Formatting to Pure Python
**Date:** 2026-03-18
**File:** `backend/agents/schedule_agent.py`
**Status:** Resolved

---

## The Problem

`schedule_agent.py` was formatting reminder times using Python's `strftime` with a platform-specific flag:

```python
import platform
time_format = "%#I:%M %p" if platform.system() == 'Windows' else "%-I:%M %p"
display_time = reminder_time.strftime(time_format).lower().lstrip('0')
```

This appeared in two places:
- `_create_scheduled_dose()` — sets `display_time` on each scheduled dose
- `format_schedule()` — formats `now_window.start` and `now_window.end`

The flags `%#I` (Windows) and `%-I` (Linux/macOS) both mean "12-hour hour without leading zero". They are not part of the C standard — they are OS extensions. Python's `strftime` passes them directly to the OS's C library. The result:

| Platform | Flag | Behavior |
|----------|------|----------|
| Windows  | `%#I` | Works — removes leading zero |
| Linux / macOS | `%-I` | Works — removes leading zero |
| Windows with `%-I` | `%-I` | `ValueError` or literal `%-I` in output |
| Linux with `%#I` | `%#I` | `ValueError` or literal `%#I` in output |

The app ran correctly in development (Windows) but would silently break the schedule view on any Linux deployment — every dose time would either error out or display as a raw format string like `%#I:00 AM`.

The `.lstrip('0')` call at the end was a secondary workaround: even with the correct flag, some Python versions on some platforms still zero-pad, so `lstrip('0')` was stripping it after the fact. This made the code harder to reason about: the format string was supposed to not zero-pad, but `.lstrip('0')` existed in case it did anyway.

---

## Why This Is in the Backend at All

The schedule API sends `scheduled_time` as a pre-formatted human-readable string:

```json
{
  "scheduled_time": "9:00 am",
  "now_window": {
    "start": "8:30 am",
    "end": "9:30 am"
  }
}
```

The frontend uses `dose.scheduled_time` directly as display text — it never receives a raw `time` object and has no formatting to do. This means the backend is responsible for the string shape, and any formatting bug in Python becomes a display bug in the UI.

The correct long-term fix would be to send times as ISO strings (`"09:00"`) and let the frontend format them with JavaScript's `Intl.DateTimeFormat`. That approach was not taken here because it would require changes to the frontend rendering layer. Instead the backend formatter was made platform-safe without changing the wire format.

---

## The Fix

A module-level helper `_fmt_time` replaces both strftime calls:

```python
def _fmt_time(t: time) -> str:
    """Format a time object as '9:00 am' / '12:30 pm'.

    Pure-Python replacement for strftime('%#I:%M %p') [Windows] /
    strftime('%-I:%M %p') [Linux]. Both flags are platform-specific;
    this version works identically on Windows, Linux, and macOS.
    """
    hour = t.hour % 12 or 12  # 0 -> 12 (midnight), 13 -> 1, etc.
    ampm = "am" if t.hour < 12 else "pm"
    return f"{hour}:{t.minute:02d} {ampm}"
```

The `% 12 or 12` expression handles the two edge cases in one step:
- `time(0, 0)`: `0 % 12 = 0`, `0 or 12 = 12` → "12:00 am" (midnight)
- `time(12, 0)`: `12 % 12 = 0`, `0 or 12 = 12` → "12:00 pm" (noon)
- `time(13, 0)`: `13 % 12 = 1`, `1 or 12 = 1` → "1:00 pm"

The `:02d` format on `t.minute` zero-pads minutes (e.g., `9:05 am`), which is correct — only the hour should be unpadded.

---

## Call Sites Replaced

**Before — `_create_scheduled_dose()`:**
```python
# Format display time (cross-platform)
import platform
time_format = "%#I:%M %p" if platform.system() == 'Windows' else "%-I:%M %p"
display_time = reminder_time.strftime(time_format).lower().lstrip('0')
```

**After:**
```python
display_time = _fmt_time(reminder_time)
```

---

**Before — `format_schedule()`:**
```python
# Format times cross-platform (Windows uses %#I, Unix uses %-I)
import platform
time_format = "%#I:%M %p" if platform.system() == 'Windows' else "%-I:%M %p"

return {
    "date": schedule.date.isoformat(),
    "now_window": {
        "start": schedule.now_window_start.strftime(time_format).lower().lstrip('0'),
        "end": schedule.now_window_end.strftime(time_format).lower().lstrip('0')
    },
    ...
}
```

**After:**
```python
return {
    "date": schedule.date.isoformat(),
    "now_window": {
        "start": _fmt_time(schedule.now_window_start),
        "end": _fmt_time(schedule.now_window_end),
    },
    ...
}
```

---

## Verified Output

```
time(0, 0)   -> '12:00 am'   (midnight)
time(9, 0)   -> '9:00 am'
time(9, 30)  -> '9:30 am'
time(12, 0)  -> '12:00 pm'   (noon)
time(13, 30) -> '1:30 pm'
time(21, 0)  -> '9:00 pm'
time(23, 59) -> '11:59 pm'
```

Output is identical to what `%#I:%M %p` / `%-I:%M %p` produced on their respective platforms. No change to the wire format seen by the frontend.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/agents/schedule_agent.py` | Added `_fmt_time()` module-level helper; removed both `import platform` statements and both `strftime` platform conditionals |
