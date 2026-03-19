# Autocomplete Scoring System
**Date:** 2026-03-17
**File:** `backend/agents/autocomplete_agent.py`

---

## The Problem It Solves

When a user types "asp" into the add medication modal, the app queries RxNorm (the NIH drug database). RxNorm returns every drug it knows that matches "asp" — including aspirin, but also aspartate, asparaginase, and other obscure biochemical compounds. RxNorm has no opinion on which one a typical user is more likely looking for. Without our own ranking, whatever RxNorm happened to return first would show up first.

The scoring system exists to ensure **common, well-known medications always surface above obscure ones** for the same query.

---

## How It Works

Every result gets a **final score** calculated as:

```
final score = RxNorm's score + KB's score + our bonuses
```

Results are then **sorted descending** by final score. The highest score shows first in the dropdown.

---

## The Three Sources of Score

### 1. RxNorm's Score (external, not our number)

RxNorm returns a relevance float for every result — something like `14.46` or `8.2`. This is RxNorm's own internal measure of how closely a result matches your query. It is **not** on a 0–100 scale. There is no documented ceiling. It just means "higher = RxNorm thinks this matches better." In practice these numbers tend to fall between 5 and 20 for typical medication queries.

We cannot change this number. We just receive it.

### 2. KB's Score (our first layer, inside `medication_knowledge.py`)

Before results even reach the scoring bonuses, `MedicationKnowledgeBase._score_medication()` adds its own points to each result based on the drug name's structure:

| Rule | Points |
|------|--------|
| Name is 1–3 words (brand names like "Advil", "Tylenol") | +10 |
| Name contains a strength unit (MG, MCG, ML, %) | +5 |
| Name contains a common form (tablet, capsule, injection, solution) | +3 |
| Name is longer than 60 characters (obscure formulations) | -10 |

This score is **added to RxNorm's score** inside `kb.autocomplete()` and returned as a single combined `score` field. By the time a result reaches `AutocompleteAgent._process_results()`, the `score` already reflects both RxNorm's relevance and KB's structural opinion.

### 3. Our Bonuses (second layer, inside `autocomplete_agent.py`)

`_process_results()` then adds further bonuses on top of the combined KB+RxNorm score:

| Bonus | Points | Rule |
|-------|--------|------|
| Prefix match (longer name) | +50 | The query is the **beginning** of a longer drug name |
| Prefix match (exact) | +5 | The drug name **is** the query exactly |
| Common drug | +30 | The drug appears in our known medications list |

These numbers have no external meaning. They are not percentages. There is no scale. They are sized to be **large enough to reliably change sort order** given that RxNorm+KB scores are typically 5–30.

---

## Why These Specific Numbers

- Combined RxNorm + KB typical score range: **5–30**
- Prefix bonus of **+50** is larger than that max → a prefix match always beats a non-prefix match regardless of what RxNorm and KB thought
- Common drug bonus of **+30** on top of that → a known medication always beats an obscure one when both are prefix matches

Live test results for query "asp":

| Drug | RxNorm+KB score | Prefix bonus | Common drug bonus | Final score |
|------|----------------|--------------|-------------------|-------------|
| Aspirin | 0* | +50 | +30 | **90** |
| Aspartate | 16.5 | +50 | — | **66.5** |
| Aspartic Acid | 16.2 | +50 | — | **66.2** |

*Aspirin scored 0 from RxNorm+KB because it came from the common drugs fallback (see below), not a live RxNorm result. It still wins by 24 points.

Live test results for query "met":

| Drug | RxNorm+KB score | Prefix bonus | Common drug bonus | Final score |
|------|----------------|--------------|-------------------|-------------|
| metformin | 13.4 | +50 | +30 | **93.4** |
| Metoprolol | 0* | +50 | +30 | **90** |
| metformin hydrochloride | 3.1 | +50 | — | **53.1** |
| Met (exact match) | 21.5 | +5 | — | **26.5** |
| Actoplus Met | 11.7 | — | — | **21.7** |

---

## The Prefix Bonus: Longer vs Exact

There are two prefix cases and they're treated differently on purpose:

**Longer name** (`base.startswith(query) AND len(base) > len(query)`) → **+50**

The query is the beginning of a longer drug name. This is almost always a user typing the start of a medication name. "asp" → "aspirin", "met" → "metformin", "mec" → "meclizine".

**Exact match** (`base == query`) → **+5**

The drug name is exactly what the user typed. For very short queries like "met" or "iron", an exact match is more likely to be a supply item or generic compound than a medication. It still gets a small bonus (it did match), but not enough to beat a proper medication.

---

## The Common Drugs Fallback

There are two separate places the common drugs list is used:

**1. As a bonus** — any drug that passes through `_process_results` and whose name matches the list gets +30 added to its score.

**2. As a fallback** — if `kb.autocomplete()` returns fewer than 3 results after filtering, the agent scans the hardcoded list for drugs whose name starts with the query and injects them directly as suggestions with `score: 10` and `source: "common"`.

This fallback is important for cases like "tape" where the KB filter blocks all RxNorm results (because "tape" is a bad pattern for medical supplies). Tapentadol is not returned by RxNorm for the query "tape" but it is in the common drugs list, so it surfaces via the fallback.

---

## The "tape" Case — Why It's Special

Typing "tape" is a tricky case that required a deliberate decision:

RxNorm's approximate match for "tape" returns supply items like "TAPE", "Medicated Tape", "flurandrenolide Medicated Tape". `kb._is_valid_medication()` filters these out because `'tape'` is in its bad patterns list. After filtering, RxNorm returns nothing.

The tempting fix — removing "tape" from the bad patterns — was tried and immediately caused tape supply items to flood the results, pushing Tapentadol out entirely (since the common drugs fallback only runs when there are fewer than 3 results).

The correct solution: keep `'tape'` in the KB bad patterns, and rely on the common drugs fallback to surface Tapentadol. The result:

| Drug | Score | Source |
|------|-------|--------|
| Tapentadol | 10 | common (fallback) |

`source: "common"` means the result came from our hardcoded list, not a live RxNorm query. This is honest and intentional — Tapentadol is a well-known Schedule II opioid that will always be spelled the same way, so the hardcoded list is a reliable source for it.

**The lesson:** removing a filter to fix one case can break many others. The fallback mechanism exists precisely for drugs that would otherwise be blocked by filters designed to catch supply items.

---

## The Common Drugs List

This is a hardcoded list of ~80 well-known medications in `AutocompleteAgent.__init__`. Any drug on this list receives the +30 bonus when it comes through RxNorm, and is used as a fallback source when RxNorm returns nothing.

Current list:

```
# Pain relievers
Advil, Tylenol, Aspirin, Aleve, Motrin, Ibuprofen, Acetaminophen,
Naproxen, Excedrin, Midol

# Allergy / Cold
Benadryl, Claritin, Zyrtec, Allegra, Flonase, Sudafed,
Diphenhydramine, Loratadine, Cetirizine, Fexofenadine,
Mucinex, DayQuil, NyQuil, Theraflu

# Heart / Blood pressure
Lisinopril, Metoprolol, Amlodipine, Losartan, Hydrochlorothiazide,
Atorvastatin, Simvastatin, Warfarin, Xarelto, Eliquis

# Diabetes
Metformin, Insulin, Glipizide, Januvia, Trulicity

# Stomach / Digestive
Omeprazole, Prilosec, Nexium, Zantac, Pepcid,
Imodium, Pepto-Bismol, Tums, Rolaids, Dulcolax

# Antibiotics
Amoxicillin, Azithromycin, Ciprofloxacin, Doxycycline,
Keflex, Bactrim, Flagyl

# Mental health
Sertraline, Fluoxetine, Escitalopram, Bupropion, Venlafaxine,
Alprazolam, Lorazepam, Clonazepam, Trazodone

# Asthma / Breathing
Albuterol, Flovent, Advair, Singulair, Prednisone

# Thyroid
Levothyroxine, Synthroid

# Pain / Nerve
Gabapentin, Tramadol, Tapentadol, Cyclobenzaprine, Meloxicam

# Motion sickness / Nausea
Meclizine, Scopolamine, Ondansetron

# Vitamins / Supplements
Vitamin D, Vitamin B12, Iron, Calcium, Magnesium, Fish Oil, Multivitamin
```

To add a medication to this list, open `backend/agents/autocomplete_agent.py` and add the name to the `self._common_drugs` list in `__init__`. No other changes needed.

---

## This Applies to Every Query

The scoring is not specific to "tape" or "asp". It runs on every single autocomplete search. Those were just the queries that exposed the problem during testing. Any query that returns both a common medication and an obscure compound will benefit from this ranking.

---

## The Pipeline End to End

```
User types "met"
    ↓
kb.get_approximate_matches("met")        ← raw RxNorm results with RxNorm score
    ↓
kb._is_valid_medication()                ← filter out supplies, devices, non-drugs
    ↓
kb._score_medication()                   ← add structural score (name length, has strength, etc.)
    ↓
combined score = RxNorm + KB stored as "score" key
    ↓
kb.autocomplete() returns List[Dict]     ← pre-filtered, pre-scored, pre-deduplicated
    ↓
AutocompleteAgent._process_results()     ← adds prefix bonus (+50/+5) and common drug bonus (+60)
    ↓
sort descending by final score
    ↓
return top 6 to frontend
```

Common drugs are always injected as candidates before `_process_results` runs (not only for short queries). This ensures a well-known medication like Aspirin always competes in the sort even when RxNorm returns only brand variants for the same prefix.

If fewer than 3 suggestions remain after processing, the common drugs fallback injects hardcoded matches directly as `MedicationSuggestion` objects with `source: "common"` before the final sort.

---

## Scoring Values — 2026-03-18 Update

The common drug bonus was raised from **+30 to +60** after testing revealed that RxNorm brand variants (e.g., "Aspir-Low" for the query "aspir") were scoring ~117 (67 RxNorm + 50 prefix), which was enough to beat the common drug injection of Aspirin (~90 at +30). At +60, an injected common drug scores **10 + 50 + 60 = 120**, which beats typical brand variants (~117) while still losing to high-confidence RxNorm direct matches (e.g., ATORVASTATIN for "atorva" scores ~207).

The rule for calibrating these values: the common drug injection must beat the highest typical obscure brand variant score. As of 2026-03-18 that ceiling is ~117.

---

## Known Limitations

### 1. Strength and form never appear in the dropdown

**What the code does:** `_parse_drug_name()` in both the KB and the agent correctly extracts strength from names like "Atorvastatin 20 MG Oral Tablet". The parsing logic is not the problem.

**Why it still shows nothing:** The RxNorm `approximateTerm` endpoint returns *concept names* — ingredient and brand-name entries like "ATORVASTATIN" or "Aspirin". These are high-level identifiers, not specific drug products. Specific products (called SCD — Semantic Clinical Drug — in RxNorm terminology) have names like "Atorvastatin 20 MG Oral Tablet" and are a separate tier in the RxNorm data model.

The `approximateTerm` endpoint does not reliably return SCD entries for ingredient-level queries. When a user types "atorva", RxNorm returns the ingredient concept "ATORVASTATIN" — a name that contains no dosage string. The parser runs correctly, finds no "MG" pattern, and sets `strength: null`. This is accurate behavior given the input.

**Why it cannot be resolved without extra API calls:** To show strength in the dropdown, each matched ingredient concept would need a follow-up call to the RxNorm `getDrugs/{rxcui}` endpoint to retrieve its associated clinical products. For a 6-result autocomplete dropdown, that means 6 additional API calls per keypress. Given that the autocomplete fires on every keystroke, this would add significant latency and is not appropriate for a real-time dropdown.

**The correct place for strength:** Strength is fetched after the user *selects* a medication from the dropdown. The `selectMedication()` flow already handles this — it triggers an FDA/RxNorm lookup for the specific drug, which returns dosage-specific data.

**The `strengthHtml` div is correct to remain empty** for most autocomplete suggestions. It will only populate if a user types a specific enough query that RxNorm happens to return a clinical drug name directly (e.g., typing "lisinopril 10" might return "lisinopril 10 MG Oral Tablet").

---

### 2. Transposition typos do not trigger the "Did you mean?" spelling fallback

**What a transposition is:** The user types letters in the wrong order — "aspri" instead of "aspirin" (the i and r are swapped). This is distinct from an insertion ("aspierin"), deletion ("asprin"), or substitution ("asperon"), which spell checkers handle more reliably.

**Why the spelling fallback does not trigger:** The agent's spelling fallback runs when `len(suggestions) == 0`. For the query "aspri", RxNorm's approximate matching returns "Astri-UC" — a real topical product whose name happens to match the fuzzy query. Because Astri-UC passes `_is_valid_medication()` and there are 3 results, the fallback threshold is never reached.

Even if the threshold were reached, `kb.get_spelling_suggestions("aspri")` returns `[]`. RxNorm's spelling API corrects insertion/deletion errors but does not model transpositions. Tested live: "aspri" → `[]`, "asprin" → `[]`, "zithrmax" → `["zithromax"]`.

**Why "aspri" is also not caught by common drug injection:** The injection checks `drug.lower().startswith(query_lower)`. For query "aspri":

```
"aspirin".startswith("aspri")  →  False
```

"aspri" is not a prefix of "aspirin" — the letters appear in a different order. The injection correctly does not match.

**What does work:** Normal typing ("aspir", "aspirin", "aspi") all surface Aspirin via the common drug injection and prefix bonus. Only transpositions — which are statistically rare and difficult to detect without edit-distance computation — fall through.

**What a fix would require:** A local fuzzy matcher (e.g., `difflib.get_close_matches` or Levenshtein distance) run against the common drugs list whenever no prefix match exists. This is a self-contained Python feature with no external API calls and would catch the "aspri" case. It is not currently implemented because the scope of the autocomplete was to fix ranking and surfacing, not to build a spell checker.

---

### 3. Score normalization (pre-existing)

The +50 and +60 bonus values are absolute numbers calibrated against the observed RxNorm score range of 5–30 (rising to ~100 for very direct matches). If RxNorm changes its scoring model or returns significantly higher scores, the prefix bonus could stop being decisive. The proper long-term fix is to normalize RxNorm's score to a 0–1 range before adding bonuses, making all weights percentage-based. This is not currently implemented.
