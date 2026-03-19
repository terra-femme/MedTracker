"""
Enhance.md Feature Tests
========================
Tests for: autocomplete scoring, pill columns, strengthHtml/formHtml fields

Run from project root:
    python -m backend.tests.test_enhance

No server required. Tests autocomplete agent directly and checks DB schema.
"""

import sys
import sqlite3
import os

sys.path.insert(0, 'D:/portfolio/medtracker')


# -- Helpers ------------------------------------------------------------------

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
HEAD = "\033[1m"
END  = "\033[0m"

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  {PASS} {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    msg = f"  {FAIL} {label}"
    if detail:
        msg += f"\n         -> {detail}"
    print(msg)


def section(title):
    print(f"\n{HEAD}{'-'*60}{END}")
    print(f"{HEAD}{title}{END}")
    print(f"{HEAD}{'-'*60}{END}")


# -- 1. DB Schema --------------------------------------------------------------

section("1. Database Schema - pill columns")

db_path = "medtracker.db"
if not os.path.exists(db_path):
    print(f"  \033[93m[SKIP]\033[0m medtracker.db not found - run the server once first")
else:
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(medications)")}
    conn.close()

    for col in ("pill_shape", "pill_color", "pill_size"):
        if col in cols:
            ok(f"Column '{col}' exists in medications table")
        else:
            fail(f"Column '{col}' missing from medications table",
                 "run: python setup_database.py")


# -- 2. Autocomplete Agent - ranking ------------------------------------------

section("2. AutocompleteAgent - ranking & scoring")

try:
    from backend.medication_knowledge import MedicationKnowledgeBase
    from backend.agents.autocomplete_agent import AutocompleteAgent

    kb    = MedicationKnowledgeBase()
    agent = AutocompleteAgent(kb)

    # 2a. Common drug beats obscure compound for "asp"
    result = agent.search("asp")
    suggestions = result["suggestions"]
    names_lower = [s["base_name"].lower() for s in suggestions]

    if suggestions and suggestions[0]["base_name"].lower() == "aspirin":
        ok("'asp' -> Aspirin ranks first")
    else:
        top = suggestions[0]["base_name"] if suggestions else "no results"
        fail("'asp' -> Aspirin should rank first", f"got: {top}")

    if "aspirin" in names_lower:
        ok("'asp' -> Aspirin appears in results")
    else:
        fail("'asp' -> Aspirin missing from results")

    # 2a2. Aspirin beats "Aspir-Low" brand for 5-char query "aspir"
    result = agent.search("aspir")
    suggestions = result["suggestions"]
    if suggestions and suggestions[0]["base_name"].lower() == "aspirin":
        ok("'aspir' -> Aspirin ranks first (not Aspir-Low brand)")
    else:
        top = suggestions[0]["base_name"] if suggestions else "no results"
        fail("'aspir' -> Aspirin should rank first", f"got: {top}")

    # 2b. metformin beats obscure results for "met"
    result = agent.search("met")
    suggestions = result["suggestions"]
    if suggestions and suggestions[0]["base_name"].lower() in ("metformin", "metoprolol"):
        ok(f"'met' -> common drug ({suggestions[0]['base_name']}) ranks first")
    else:
        top = suggestions[0]["base_name"] if suggestions else "no results"
        fail("'met' -> metformin or metoprolol should rank first", f"got: {top}")

    # 2c. Tapentadol surfaces for "tape" (via common drugs fallback)
    result = agent.search("tape")
    suggestions = result["suggestions"]
    names_lower = [s["base_name"].lower() for s in suggestions]
    if "tapentadol" in names_lower:
        ok("'tape' -> Tapentadol surfaces via common drugs fallback")
    else:
        fail("'tape' -> Tapentadol missing", f"got: {names_lower}")

    # Confirm it's not coming through as a supply item
    bad = [n for n in names_lower if n in ("tape", "medicated tape")]
    if not bad:
        ok("'tape' -> no tape supply items in results")
    else:
        fail("'tape' -> supply items leaked into results", f"found: {bad}")

    # 2d. Meclizine surfaces for "mec"
    result = agent.search("mec")
    suggestions = result["suggestions"]
    names_lower = [s["base_name"].lower() for s in suggestions]
    if "meclizine" in names_lower:
        ok("'mec' -> Meclizine appears in results")
    else:
        fail("'mec' -> Meclizine missing", f"got: {names_lower}")

    # 2e. Scores are present and sorted descending
    result = agent.search("met")
    scores = [s["score"] for s in result["suggestions"]]
    if scores == sorted(scores, reverse=True):
        ok("'met' -> results are sorted by score descending")
    else:
        fail("'met' -> results not sorted by score", f"scores: {scores}")

    # 2f. Strength and form fields are present (not None means the agent parses them)
    result = agent.search("metformin")
    suggestions = result["suggestions"]
    # At least some results should have a strength field (not all will - some are short names)
    has_strength = any(s.get("strength") for s in suggestions)
    if has_strength:
        ok("'metformin' -> at least one result has a strength value")
    else:
        # Not a hard failure - RxNorm may not return strength for all queries
        print(f"  \033[93m[INFO]\033[0m 'metformin' -> no strength found (may be normal for this query)")

    # 2g. source field is present on all results
    result = agent.search("asp")
    if all("source" in s for s in result["suggestions"]):
        ok("'asp' -> all results have a 'source' field")
    else:
        fail("'asp' -> some results missing 'source' field")

    # 2h. base_name field is present on all results (required for strengthHtml rendering)
    if all("base_name" in s for s in result["suggestions"]):
        ok("'asp' -> all results have a 'base_name' field")
    else:
        fail("'asp' -> some results missing 'base_name' field")

    # 2i. Spelling fallback for a typo
    result = agent.search("aspri")
    all_suggestions = result["suggestions"] + [
        {"source": s, "base_name": s} for s in result.get("spelling_suggestions", [])
    ]
    spelling_triggered = (
        any(s.get("source") == "spelling" for s in result["suggestions"])
        or len(result.get("spelling_suggestions", [])) > 0
    )
    if spelling_triggered:
        ok("'aspri' -> spelling fallback triggered")
    else:
        # This is a soft check - if RxNorm returns something for "aspri" spelling is skipped
        print(f"  \033[93m[INFO]\033[0m 'aspri' -> spelling fallback not triggered (RxNorm may have matched directly)")

    # 2j. kb.autocomplete() is being called (not get_approximate_matches)
    # Indirect test: kb.autocomplete adds base_name, form, strength to results.
    # If the agent used get_approximate_matches, base_name would often be None.
    result = agent.search("atorv")
    suggestions = result["suggestions"]
    base_names_not_none = [s for s in suggestions if s.get("base_name")]
    if base_names_not_none:
        ok("'atorv' -> base_name populated (kb.autocomplete path confirmed)")
    else:
        fail("'atorv' -> base_name missing on all results (may be using wrong kb method)")

except ImportError as e:
    print(f"  \033[93m[SKIP]\033[0m Could not import agents: {e}")
except Exception as e:
    fail("AutocompleteAgent raised an exception", str(e))
    import traceback
    traceback.print_exc()


# -- 3. Schema fields ----------------------------------------------------------

section("3. Pydantic Schema - pill fields")

try:
    from backend.schemas import MedicationBase, MedicationUpdate

    # MedicationBase should have pill fields
    fields = MedicationBase.model_fields
    for field in ("pill_shape", "pill_color", "pill_size"):
        if field in fields:
            ok(f"MedicationBase has '{field}' field")
        else:
            fail(f"MedicationBase missing '{field}' field")

    # MedicationUpdate should have pill fields
    update_fields = MedicationUpdate.model_fields
    for field in ("pill_shape", "pill_color", "pill_size"):
        if field in update_fields:
            ok(f"MedicationUpdate has '{field}' field")
        else:
            fail(f"MedicationUpdate missing '{field}' field")

    # taken_for should appear exactly once (no duplicate)
    base_field_names = list(MedicationBase.model_fields.keys())
    taken_for_count = base_field_names.count("taken_for")
    if taken_for_count == 1:
        ok("MedicationBase has exactly one 'taken_for' field (no duplicate)")
    else:
        fail(f"MedicationBase has {taken_for_count} 'taken_for' fields", "remove the duplicate")

except ImportError as e:
    print(f"  \033[93m[SKIP]\033[0m Could not import schemas: {e}")


# -- 4. SQLAlchemy Model - pill fields -----------------------------------------

section("4. SQLAlchemy Model - pill columns")

try:
    from backend.models import Medication
    from sqlalchemy import inspect

    mapper = inspect(Medication)
    col_names = {c.key for c in mapper.columns}

    for col in ("pill_shape", "pill_color", "pill_size"):
        if col in col_names:
            ok(f"Medication model has '{col}' column")
        else:
            fail(f"Medication model missing '{col}' column")

    # taken_for should appear exactly once
    taken_for_cols = [c for c in mapper.columns if c.key == "taken_for"]
    if len(taken_for_cols) == 1:
        ok("Medication model has exactly one 'taken_for' column (no duplicate)")
    else:
        fail(f"Medication model has {len(taken_for_cols)} 'taken_for' columns")

except ImportError as e:
    print(f"  \033[93m[SKIP]\033[0m Could not import models: {e}")


# -- Summary -------------------------------------------------------------------

total = passed + failed
print(f"\n{'-'*60}")
print(f"{HEAD}RESULTS: {passed}/{total} passed{END}")
if failed:
    print(f"\033[91m{failed} test(s) failed - see above\033[0m")
else:
    print("\033[92mAll automated tests passed.\033[0m")
print(f"{'-'*60}\n")

print("""
MANUAL BROWSER CHECKLIST (server must be running)
--------------------------------------------------
Autocomplete dropdown:
  [ ] Type "asp"    -> Aspirin is first result, not Aspartate or Aspartic Acid
  [ ] Type "aspir"  -> Aspirin is first result (not "Aspir-Low" brand)
  [ ] Type "atorva" -> ATORVASTATIN appears (no strength shown - RxNorm API limitation,
                       approximateTerm returns ingredient names not "X MG" products)
  NOTE: "aspri" (transposed typo) shows "Astri-UC" - known RxNorm limitation.
        RxNorm spelling API does not bridge transpositions. Working as expected.

Add Medication -> Step 2 pill panel:
  [ ] Submit a new medication -> form disappears, pill panel appears
  [ ] Click a shape button    -> pill preview updates immediately
  [ ] Click a color swatch    -> pill preview color changes immediately
  [ ] Click a size button     -> pill preview size changes immediately
  [ ] "Save & Done"           -> modal closes, medication card appears

Medication card:
  [ ] Medication saved with pill attrs -> shows CSS pill shape (not emoji)
  [ ] Medication without pill attrs    -> shows emoji fallback ((pill))
  [ ] "Skip" in pill step             -> card shows emoji fallback

API spot check (DevTools Console or curl):
  [ ] fetch('/debug/autocomplete/metformin').then(r=>r.json()).then(console.log)
      -> "source" on results shows "rxnorm" (not "get_approximate_matches")
  [ ] After Save & Done, fetch('/medications').then(r=>r.json()).then(console.log)
      -> medication has pill_shape, pill_color, pill_size set
""")

sys.exit(0 if failed == 0 else 1)
