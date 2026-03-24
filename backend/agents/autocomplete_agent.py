"""
AutocompleteAgent - Handles medication search with clear separation of concerns

Responsibilities:
1. Search RxNorm for medication suggestions
2. Filter and rank results
3. Return structured suggestions

Does NOT:
- Handle FDA lookups (that's VerifyAgent)
- Handle UI rendering (that's frontend)
- Handle spelling correction (that's a separate tool call)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MedicationSuggestion:
    """Structured suggestion for frontend"""
    name: str
    base_name: str
    rxcui: str
    strength: Optional[str]
    form: Optional[str]
    score: float
    source: str  # "rxnorm" or "spelling"


class AutocompleteAgent:
    """
    Agent that searches for medications and returns clean suggestions

    Usage:
        agent = AutocompleteAgent(knowledge_base)
        results = agent.search("advil", limit=5)
    """

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.logger = logging.getLogger(self.__class__.__name__)
        # Common brand names cache for short queries
        # These are used when RxNorm returns poor results for short queries
        self._common_drugs = [
            # Pain relievers
            "Advil", "Tylenol", "Aspirin", "Aleve", "Motrin", "Ibuprofen",
            "Acetaminophen", "Naproxen", "Excedrin", "Midol",
            # Allergy/Cold
            "Benadryl", "Claritin", "Zyrtec", "Allegra", "Flonase", "Sudafed",
            "Diphenhydramine", "Loratadine", "Cetirizine", "Fexofenadine",
            "Mucinex", "DayQuil", "NyQuil", "Theraflu",
            # Heart/Blood pressure
            "Lisinopril", "Metoprolol", "Amlodipine", "Losartan", "Hydrochlorothiazide",
            "Atorvastatin", "Simvastatin", "Warfarin", "Xarelto", "Eliquis",
            # Diabetes
            "Metformin", "Insulin", "Glipizide", "Januvia", "Trulicity",
            # Stomach/Digestive
            "Omeprazole", "Prilosec", "Nexium", "Zantac", "Pepcid",
            "Imodium", "Pepto-Bismol", "Tums", "Rolaids", "Dulcolax",
            # Antibiotics
            "Amoxicillin", "Azithromycin", "Ciprofloxacin", "Doxycycline",
            "Keflex", "Bactrim", "Flagyl",
            # Mental Health
            "Sertraline", "Fluoxetine", "Escitalopram", "Bupropion", "Venlafaxine",
            "Alprazolam", "Lorazepam", "Clonazepam", "Trazodone",
            # Asthma/Breathing
            "Albuterol", "Flovent", "Advair", "Singulair", "Prednisone",
            # Thyroid
            "Levothyroxine", "Synthroid",
            # Vitamins/Supplements
            "Vitamin D", "Vitamin B12", "Iron", "Calcium", "Magnesium",
            "Fish Oil", "Multivitamin",
            # Other common
            "Gabapentin", "Tramadol", "Tapentadol", "Cyclobenzaprine", "Meloxicam",
            "Meclizine", "Scopolamine", "Ondansetron"
        ]

    def search(self, query: str, limit: int = 6) -> Dict:
        """
        Main entry point: Search for medications

        Returns:
            {
                "query": str,
                "suggestions": List[MedicationSuggestion],
                "spelling_suggestions": List[str],
                "debug": {...}  # For troubleshooting
            }
        """
        self.logger.info(f"🔍 Search started for: '{query}'")

        if not query or len(query) < 2:
            return {"query": query, "suggestions": [], "spelling_suggestions": [], "debug": {"error": "Query too short"}}

        try:
            # Step 1: Get filtered, scored results from knowledge base
            raw_results = self.kb.autocomplete(query, limit)
            self.logger.debug(f"Autocomplete results: {len(raw_results)}")

            # Always inject common drugs as candidates so well-known medications
            # surface even when RxNorm returns only brand variants or obscure names.
            # Score of 10 keeps them below strong RxNorm direct matches but
            # the +50 prefix bonus + +60 common drug bonus gives them 120 total,
            # which beats obscure brand variants (~67+50=117).
            query_lower = query.lower()
            for drug in self._common_drugs:
                if drug.lower().startswith(query_lower):
                    raw_results.append({
                        "name": drug,
                        "rxcui": "",
                        "score": 10.0
                    })

            # Step 2: Filter and transform
            suggestions = self._process_results(raw_results, query)
            self.logger.info(f"Processed suggestions: {len(suggestions)}")

            # Step 3: If few/poor results, supplement with common drugs cache
            if len(suggestions) < 3:
                self.logger.info(f"Few suggestions ({len(suggestions)}), checking common drugs cache")
                query_lower = query.lower()
                existing_names = {s.base_name.lower() for s in suggestions}

                for drug in self._common_drugs:
                    if drug.lower().startswith(query_lower) and drug.lower() not in existing_names:
                        suggestions.append(MedicationSuggestion(
                            name=drug,
                            base_name=drug,
                            rxcui="",
                            strength=None,
                            form=None,
                            score=10.0,
                            source="common"
                        ))
                        if len(suggestions) >= 6:
                            break

            # Step 4: If still no suggestions, try spelling
            spelling_suggestions = []
            if len(suggestions) == 0:
                self.logger.info("No medication suggestions, trying spelling...")
                spelling_suggestions = self.kb.get_spelling_suggestions(query)[:5]
                self.logger.info(f"Spelling suggestions: {spelling_suggestions}")

                # Convert spelling suggestions to proper format
                for spelling in spelling_suggestions:
                    suggestions.append(MedicationSuggestion(
                        name=spelling,
                        base_name=spelling,
                        rxcui="",
                        strength=None,
                        form=None,
                        score=0,
                        source="spelling"
                    ))

            # Step 4: Build debug info
            debug = {
                "raw_count": len(raw_results),
                "filtered_count": len(suggestions),
                "first_raw": raw_results[0]["name"] if raw_results else None,
                "filter_applied": True
            }

            return {
                "query": query,
                "suggestions": [self._to_dict(s) for s in suggestions],
                "spelling_suggestions": spelling_suggestions,
                "debug": debug
            }

        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            return {
                "query": query,
                "suggestions": [],
                "spelling_suggestions": [],
                "debug": {"error": str(e)}
            }

    def _process_results(self, raw_results: List[Dict], query: str) -> List[MedicationSuggestion]:
        """Process, filter, and rank RxNorm results by relevance."""
        suggestions = []
        seen_base = set()
        query_lower = query.lower()
        common_lower = {d.lower() for d in self._common_drugs}

        for item in raw_results:
            name = item.get("name", "")

            if not self._is_valid(name):
                self.logger.debug(f"Filtered out (invalid): {name[:30]}...")
                continue

            # Use base_name/strength/form already parsed by the KB; only
            # fall back to local re-parsing if the KB didn't provide them.
            parsed = self._parse_drug_name(name)
            base_name = item.get("base_name") or parsed["base_name"]
            base = base_name.lower()

            if base in seen_base:
                continue
            seen_base.add(base)

            score = float(item.get("score", 0))

            # Prefix bonus: query extends into a longer drug name
            # e.g. "tape" → "tapentadol" (+50) beats "tape" supply item (+5)
            if base.startswith(query_lower):
                if len(base) > len(query_lower):
                    score += 50.0   # prefix match into a longer name — likely the drug
                else:
                    score += 5.0    # exact match to query — often a supply item for short queries

            # Common drug bonus: well-known medications always surface first.
            # +60 (not +30) so that an injected common drug (10+50+60=120) beats
            # obscure brand variants from RxNorm (typically ~67+50=117).
            if base in common_lower:
                score += 60.0

            suggestions.append(MedicationSuggestion(
                name=name,
                base_name=base_name,
                rxcui=item.get("rxcui", ""),
                strength=item.get("strength") or parsed.get("strength"),
                form=item.get("form") or parsed.get("form"),
                score=score,
                source="rxnorm"
            ))

        # Sort by final score so highest-relevance results always come first
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:6]

    def _is_valid(self, name: str) -> bool:
        """Check if this looks like a real medication"""
        if not name:
            return False

        n = name.lower()

        # Explicitly BAD patterns - medical supplies/devices
        bad_patterns = [
            # Supplies (be specific to avoid filtering real drug names)
            "contact lens", "bandage", "syringe", "needle", "dressing", "dress,",
            "gauze", "catheter", "drain", "pad pack", "pack of", "wrap",
            # Nutrition/food
            "nutrition", "formula", "feeding", "diet", "meal", "supl ",
            # Equipment
            "pump", "monitor", "device", "meter", "test ",
            # Non-drug items
            "solution for", "irrigation", "cleanser", "flush",
            # Hand sanitizer and hygiene products
            "hand sanitizer", "sanitizer", "alcohol 70", "alcohol 60", "meli hands",
            # Weird codes
            "-tk", "{", "}", "[unspecified]", "[discontinued]",
        ]

        for bad in bad_patterns:
            if bad in n:
                return False

        # Must look like a drug name (mostly letters, no excessive punctuation)
        letters = [c for c in name if c.isalpha()]
        if len(letters) < 3:
            return False

        # Good medications usually have proper names (not mostly numbers/symbols)
        # Check that at least 50% of characters are letters
        if len(letters) / len(name) < 0.5:
            return False

        return True

    def _parse_drug_name(self, name: str) -> Dict:
        """Extract base name, strength, form from RxNorm name"""
        import re

        result = {
            "base_name": name,
            "strength": None,
            "form": None
        }

        # Extract strength (e.g., "200 MG")
        strength_match = re.search(r'(\d+\.?\d*)\s*(MG|MCG|G|ML|%)', name, re.IGNORECASE)
        if strength_match:
            result["strength"] = f"{strength_match.group(1)} {strength_match.group(2).upper()}"

        # Extract form
        forms = ["Tablet", "Capsule", "Injection", "Solution", "Suspension"]
        for form in forms:
            if form.lower() in name.lower():
                result["form"] = form
                break

        # Extract base name (first 1-2 words before numbers)
        words = name.split()
        base_words = []
        for word in words:
            if any(c.isdigit() for c in word):
                break
            base_words.append(word)

        if base_words:
            result["base_name"] = " ".join(base_words[:2])

        return result

    def _to_dict(self, suggestion: MedicationSuggestion) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "name": suggestion.name,
            "base_name": suggestion.base_name,
            "rxcui": suggestion.rxcui,
            "strength": suggestion.strength,
            "form": suggestion.form,
            "score": suggestion.score,
            "source": suggestion.source
        }


# Quick test
if __name__ == "__main__":
    from backend.medication_knowledge import MedicationKnowledgeBase

    kb = MedicationKnowledgeBase()
    agent = AutocompleteAgent(kb)

    print("=" * 60)
    print("TESTING AUTOCOMPLETE AGENT")
    print("=" * 60)

    for query in ["advil", "aspirin", "metform", "lisino"]:
        print(f"\nQuery: '{query}'")
        result = agent.search(query)
        print(f"   Suggestions: {len(result['suggestions'])}")
        for s in result["suggestions"][:3]:
            print(f"   • {s['base_name']} ({s['strength'] or 'no strength'})")
        print(f"   Debug: {result['debug']}")
