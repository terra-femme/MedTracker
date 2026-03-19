"""
Medication Knowledge Service - Enhanced Version with OpenFDA
Fetches real medication data from RxNorm API AND OpenFDA API

NEW IN THIS VERSION:
- OpenFDA integration for:
  - Indications (what the drug is for)
  - Side Effects (adverse reactions)
  - Drug Interactions (what not to mix with)
  - Warnings

HEALTH-TECH LEARNING:
OpenFDA is the official FDA API that provides drug label data.
This is the SAME information you see on the package insert!
Using official FDA data means:
- No hallucination risk (unlike LLMs)
- Legally defensible information
- Authoritative medical source
- Perfect for health-tech applications

API Documentation:
- RxNorm: https://lhncbc.nlm.nih.gov/RxNav/APIs/
- OpenFDA: https://open.fda.gov/apis/drug/label/
"""

import requests
from typing import List, Dict, Optional
import json
import re


class MedicationKnowledgeBase:
    """
    This class talks to RxNorm API AND OpenFDA API to get real medication information
    Think of it as your "medical textbook" that the chatbot can reference
    """
    
    def __init__(self):
        # RxNorm API endpoint (FREE, no key needed!)
        self.base_url = "https://rxnav.nlm.nih.gov/REST"
        
        # OpenFDA API endpoint (FREE, no key needed!)
        self.openfda_url = "https://api.fda.gov/drug/label.json"
        
        # Cache for common lookups (reduces API calls)
        self._cache = {}
        
        # DEBUG flag - set to True to see API responses
        self.debug = False
    
    # =========================================================================
    # OPENFDA METHODS - NEW! For indications, side effects, interactions
    # =========================================================================
    
    def get_drug_info_from_fda(self, drug_name: str) -> Dict:
        """
        🏥 MAIN METHOD: Get comprehensive drug information from OpenFDA
        
        This queries the FDA's drug label database to get:
        - What the drug is for (indications)
        - Side effects (adverse reactions)
        - Drug interactions (what NOT to mix with)
        - Warnings
        
        HEALTH-TECH NOTE:
        This returns OFFICIAL FDA data from drug labels.
        Much safer than using an LLM which might hallucinate!
        
        Args:
            drug_name: Name of the drug (e.g., "lisinopril", "metformin")
            
        Returns:
            Dictionary with drug information or error
            
        Example:
            >>> kb.get_drug_info_from_fda("lisinopril")
            {
                'success': True,
                'drug_name': 'lisinopril',
                'indications': 'Treatment of hypertension...',
                'side_effects': ['dizziness', 'cough', ...],
                'interactions': 'Do not use with potassium supplements...',
                'warnings': '...'
            }
        """
        if not drug_name or len(drug_name) < 2:
            return {
                'success': False,
                'error': 'Drug name too short',
                'drug_name': drug_name
            }
        
        # Check cache first (saves API calls!)
        cache_key = f"fda_info_{drug_name.lower()}"
        if cache_key in self._cache:
            if self.debug:
                print(f"📦 [CACHE HIT] Returning cached FDA info for: {drug_name}")
            return self._cache[cache_key]
        
        if self.debug:
            print(f"🔍 [OpenFDA] Searching for drug: {drug_name}")
        
        try:
            # Try searching by generic name first (most reliable)
            # URL encode the drug name for safety
            clean_name = drug_name.strip().lower()
            
            # OpenFDA query - search generic_name OR brand_name
            # The + is "OR" in OpenFDA query syntax
            search_query = f'openfda.generic_name:"{clean_name}"+openfda.brand_name:"{clean_name}"'
            
            url = f"{self.openfda_url}?search={search_query}&limit=1"
            
            if self.debug:
                print(f"🌐 [OpenFDA] Query URL: {url}")
            
            response = requests.get(url, timeout=10)
            
            if self.debug:
                print(f"📡 [OpenFDA] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    label = results[0]  # Get the first (best) match
                    
                    # Extract the information we need
                    result = self._parse_fda_label(label, drug_name)
                    
                    # Cache the result
                    self._cache[cache_key] = result
                    
                    if self.debug:
                        print(f"✅ [OpenFDA] Found info for: {drug_name}")
                        print(f"   Indications: {result.get('indications', 'N/A')[:100]}...")
                    
                    return result
                else:
                    if self.debug:
                        print(f"⚠️ [OpenFDA] No results for: {drug_name}")
                    
                    return {
                        'success': False,
                        'error': 'No FDA label data found for this medication',
                        'drug_name': drug_name
                    }
            
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Medication not found in FDA database',
                    'drug_name': drug_name
                }
            else:
                return {
                    'success': False,
                    'error': f'FDA API error: {response.status_code}',
                    'drug_name': drug_name
                }
                
        except requests.exceptions.Timeout:
            if self.debug:
                print(f"⏰ [OpenFDA] Timeout for: {drug_name}")
            return {
                'success': False,
                'error': 'FDA API timeout - try again',
                'drug_name': drug_name
            }
        except Exception as e:
            if self.debug:
                print(f"❌ [OpenFDA] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'drug_name': drug_name
            }
    
    def _parse_fda_label(self, label: Dict, drug_name: str) -> Dict:
        """
        Parse the FDA drug label data into a clean format
        
        The FDA label has many fields - we extract the most useful ones:
        - indications_and_usage: What it's for
        - adverse_reactions: Side effects
        - drug_interactions: What not to mix with
        - warnings: Important warnings
        - dosage_and_administration: How to take it
        
        HEALTH-TECH NOTE:
        FDA labels are TEXT-HEAVY. We clean them up for better display.
        """
        
        def clean_text(text_list: List[str]) -> str:
            """Clean and join FDA text (often comes as a list)"""
            if not text_list:
                return None
            
            # Join if it's a list
            if isinstance(text_list, list):
                text = ' '.join(text_list)
            else:
                text = str(text_list)
            
            # Clean up common FDA formatting issues
            text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
            text = text.strip()
            
            # Truncate if too long (for display)
            if len(text) > 2000:
                text = text[:2000] + '...'
            
            return text
        
        def extract_side_effects(adverse_reactions: str) -> List[str]:
            """
            Extract individual side effects from adverse reactions text
            
            FDA adverse reactions are usually paragraphs - we try to pull out
            the actual side effect names for a cleaner list.
            """
            if not adverse_reactions:
                return []
            
            # Common side effects keywords to look for
            # These are medically accurate terms from FDA labels
            common_effects = [
                'headache', 'dizziness', 'nausea', 'fatigue', 'diarrhea',
                'constipation', 'vomiting', 'abdominal pain', 'rash',
                'insomnia', 'drowsiness', 'dry mouth', 'cough', 'weakness',
                'muscle pain', 'back pain', 'joint pain', 'fever', 'chills',
                'itching', 'swelling', 'weight gain', 'weight loss',
                'decreased appetite', 'increased appetite', 'anxiety',
                'depression', 'confusion', 'blurred vision', 'chest pain',
                'shortness of breath', 'palpitations', 'edema', 'hypotension',
                'hypertension', 'tachycardia', 'bradycardia', 'arrhythmia',
                'hyperglycemia', 'hypoglycemia', 'hypokalemia', 'hyperkalemia',
                'anemia', 'neutropenia', 'thrombocytopenia', 'infection',
                'upper respiratory infection', 'urinary tract infection',
                'nasopharyngitis', 'pharyngitis', 'bronchitis', 'sinusitis',
                'peripheral edema', 'liver enzyme elevation', 'renal impairment'
            ]
            
            found_effects = []
            text_lower = adverse_reactions.lower()
            
            for effect in common_effects:
                if effect in text_lower:
                    found_effects.append(effect.title())
            
            # Limit to top 10 most relevant
            return found_effects[:10] if found_effects else ['See full label for details']
        
        # Extract each section
        indications = clean_text(label.get('indications_and_usage'))
        adverse_reactions_raw = clean_text(label.get('adverse_reactions'))
        interactions = clean_text(label.get('drug_interactions'))
        warnings = clean_text(label.get('warnings'))
        warnings_precautions = clean_text(label.get('warnings_and_precautions'))
        dosage = clean_text(label.get('dosage_and_administration'))
        
        # Get brand name if available
        openfda = label.get('openfda', {})
        brand_names = openfda.get('brand_name', [])
        generic_names = openfda.get('generic_name', [])
        
        # Combine warnings
        all_warnings = warnings or warnings_precautions
        
        # Extract side effects list
        side_effects_list = extract_side_effects(adverse_reactions_raw)
        
        # Create a short summary of indications (first sentence or two)
        indications_short = None
        if indications:
            # Get first 500 characters or first two sentences
            sentences = indications.split('.')
            if len(sentences) >= 2:
                indications_short = sentences[0] + '.' + sentences[1] + '.'
            else:
                indications_short = indications[:500]
        
        return {
            'success': True,
            'drug_name': drug_name,
            'brand_names': brand_names[:3] if brand_names else [],  # Top 3 brand names
            'generic_names': generic_names[:2] if generic_names else [],
            
            # Main fields for auto-fill
            'indications': indications_short,  # Short version for form
            'indications_full': indications,   # Full version for details
            
            'side_effects': side_effects_list,  # Clean list
            'side_effects_raw': adverse_reactions_raw,  # Full text
            
            'interactions': interactions,
            'interactions_summary': self._summarize_interactions(interactions),
            
            'warnings': all_warnings,
            'dosage_info': dosage,
            
            # Metadata
            'source': 'OpenFDA Drug Label Database',
            'disclaimer': 'This information is from FDA drug labels. Always consult your healthcare provider.'
        }
    
    def _summarize_interactions(self, interactions_text: str) -> List[str]:
        """
        Extract key drug interaction warnings
        
        Drug interactions text is usually very long. We extract the
        main drug classes/names that should be avoided.
        """
        if not interactions_text:
            return []
        
        # Common drug classes and medications that frequently interact
        # These are medically accurate categories
        interaction_keywords = [
            'NSAID', 'nsaids', 'aspirin', 'ibuprofen', 'naproxen',
            'ACE inhibitor', 'ARB', 'diuretic', 'potassium',
            'lithium', 'warfarin', 'anticoagulant', 'blood thinner',
            'MAO inhibitor', 'MAOI', 'antidepressant', 'SSRI',
            'CYP3A4', 'CYP2D6', 'grapefruit', 'alcohol',
            'insulin', 'metformin', 'sulfonylurea',
            'beta blocker', 'calcium channel blocker',
            'statin', 'digoxin', 'phenytoin', 'carbamazepine',
            'rifampin', 'ketoconazole', 'erythromycin',
            'St. John\'s Wort', 'antacid', 'proton pump inhibitor'
        ]
        
        found_interactions = []
        text_lower = interactions_text.lower()
        
        for keyword in interaction_keywords:
            if keyword.lower() in text_lower:
                found_interactions.append(keyword)
        
        return found_interactions[:8]  # Top 8 most relevant
    
    def get_quick_drug_summary(self, drug_name: str) -> Dict:
        """
        🚀 QUICK METHOD: Get just the essentials for form auto-fill
        
        This is optimized for the add medication form:
        - taken_for: What condition it treats (short)
        - common_side_effects: List of 5 most common
        - do_not_mix_with: Key interactions
        
        Perfect for auto-filling the form without overwhelming the user!
        """
        full_info = self.get_drug_info_from_fda(drug_name)
        
        if not full_info.get('success'):
            return full_info
        
        return {
            'success': True,
            'drug_name': drug_name,
            'taken_for': full_info.get('indications', 'Consult your healthcare provider'),
            'common_side_effects': full_info.get('side_effects', [])[:5],
            'do_not_mix_with': full_info.get('interactions_summary', []),
            'important_warning': full_info.get('warnings', '')[:300] if full_info.get('warnings') else None,
            'source': 'FDA Drug Label Database'
        }
    
    # =========================================================================
    # AUTOCOMPLETE / SPELL-CHECK METHODS (EXISTING)
    # =========================================================================
    
    def get_spelling_suggestions(self, query: str) -> List[str]:
        """
        Get spelling suggestions for a drug name
        
        RxNorm's spell-check is trained on medication names, so it understands:
        - "asprin" -> "aspirin"
        - "lisinipril" -> "lisinopril"  
        - "metforman" -> "metformin"
        
        This is CRITICAL for elderly users who may mistype!
        
        Example:
            >>> kb.get_spelling_suggestions("lisinipril")
            ["lisinopril"]
        """
        if not query or len(query) < 2:
            return []
        
        try:
            url = f"{self.base_url}/spellingsuggestions.json?name={query}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                suggestion_group = data.get('suggestionGroup', {})
                suggestion_list = suggestion_group.get('suggestionList', {})
                suggestions = suggestion_list.get('suggestion', [])
                
                # Return up to 10 suggestions
                return suggestions[:10] if suggestions else []
            
            return []
            
        except Exception as e:
            print(f"Spelling suggestion error: {e}")
            return []
    
    def get_approximate_matches(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Get drug names that approximately match the query
        Uses RxNorm's approximate term matching (fuzzy search)
        
        Returns list of dicts with name and rxcui
        
        Example:
            >>> kb.get_approximate_matches("lisino")
            [{"name": "Lisinopril", "rxcui": "104377"}, ...]
        """
        if not query or len(query) < 2:
            return []
        
        try:
            # Use the approximateTerm endpoint for fuzzy matching
            url = f"{self.base_url}/approximateTerm.json?term={query}&maxEntries={limit}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                candidates = data.get('approximateGroup', {}).get('candidate', [])
                
                results = []
                seen_names = set()  # Avoid duplicates
                
                for candidate in candidates:
                    name = candidate.get('name', '')
                    rxcui = candidate.get('rxcui', '')
                    
                    # Normalize name for comparison
                    name_lower = name.lower()
                    
                    if name_lower not in seen_names and name:
                        seen_names.add(name_lower)
                        results.append({
                            'name': name,
                            'rxcui': rxcui,
                            'score': float(candidate.get('score', 0))
                        })
                
                # Sort by score (higher is better match)
                results.sort(key=lambda x: x.get('score', 0), reverse=True)
                return results[:limit]
            
            return []
            
        except Exception as e:
            print(f"Approximate match error: {e}")
            return []
    
    def _is_valid_medication(self, name: str) -> bool:
        """
        Filter out non-medication items from RxNorm results
        
        Returns False for:
        - Medical devices (contact lens, bandages, etc.)
        - Lab tests and procedures
        - Supply items
        - Weird codes
        """
        if not name:
            return False
            
        name_lower = name.lower()
        
        # Skip patterns that indicate non-medications (be more specific)
        skip_patterns = [
            # Medical devices and supplies (specific matches)
            'contact lens', 'bandage', 'syringe', 'needle', 'catheter',
            'dressing', 'gauze', 'tape', 'wrap', 'pad pack', 'pack of',
            # Lab and diagnostic (avoid filtering drugs with 'test' in name like Testosterone)
            'lab test', 'blood panel', 'assay kit', 'culture medium', 'screening kit',
            # Dental/vision supplies
            'dental appliance', 'denture adhesive', 'orthodontic band',
            # Equipment
            'infusion device', 'insulin pump', 'glucose meter', 'bp monitor',
            # Codes and unspecified
            '-tk', '{', '}', '[unspecified]', '[discontinued]',
            # Non-drug items
            'irrigation solution', 'flush solution', 'cleanser',
        ]
        
        for pattern in skip_patterns:
            if pattern in name_lower:
                return False
        
        # Must look like a drug name (contains letters, not just codes)
        # Valid drugs should have at least 3 letters
        letters = ''.join(c for c in name if c.isalpha())
        if len(letters) < 3:
            return False
            
        return True
    
    def _score_medication(self, name: str) -> int:
        """
        Score a medication name to prioritize common/brand name drugs
        Higher score = better match for autocomplete
        """
        score = 0
        name_lower = name.lower()
        
        # Prefer brand names and common drugs (simpler names)
        # Brand names are usually shorter and simpler
        words = name.split()
        
        # Prefer 1-3 word names (brand names like "Advil", "Tylenol")
        if len(words) <= 3:
            score += 10
        
        # Slightly prefer names with strength info (indicates specific drug product)
        if any(unit in name for unit in ['MG', 'MCG', 'G ', 'ML', '%']):
            score += 5
            
        # Prefer common drug forms
        preferred_forms = ['tablet', 'capsule', 'injection', 'solution']
        for form in preferred_forms:
            if form in name_lower:
                score += 3
                break
        
        # Deprioritize very long names (often obscure or specific formulations)
        if len(name) > 60:
            score -= 10
            
        return score
    
    def autocomplete(self, query: str, limit: int = 8) -> List[Dict]:
        """
        MAIN AUTOCOMPLETE METHOD
        Combines spelling suggestions and approximate matching for best results
        Filters out non-medications and prioritizes common drugs
        
        Returns list of drug suggestions with:
        - name: Drug name
        - rxcui: RxNorm ID
        - display: Formatted string for UI
        - base_name: Just the drug name without strength/form
        - strength: Optional strength info
        - form: Optional form info (tablet, capsule, etc.)
        
        Example:
            >>> kb.autocomplete("adv")
            [
                {"name": "Advil", "rxcui": "5640", ...},
                {"name": "Advil 200 MG Oral Tablet", "rxcui": "202642", ...},
            ]
        """
        if not query or len(query) < 2:
            return []
        
        try:
            results = []
            seen_base_names = set()  # Track base drug names to avoid duplicates
            filtered_count = 0
            
            # Strategy 1: Try approximate term matching first
            approx_results = self.get_approximate_matches(query, limit * 3)

            for item in approx_results:
                name = item.get('name', '')

                # Skip invalid/non-medication items
                if not self._is_valid_medication(name):
                    filtered_count += 1
                    continue

                # Parse the name
                parsed = self._parse_drug_name(name)
                base_name = parsed.get('base_name', name)
                base_name_lower = base_name.lower()

                # Skip if we already have this base drug (avoid duplicate strengths)
                if base_name_lower in seen_base_names:
                    continue

                seen_base_names.add(base_name_lower)

                results.append({
                    'name': name,
                    'rxcui': item.get('rxcui', ''),
                    'display': name,
                    'base_name': base_name,
                    'strength': parsed.get('strength'),
                    'strength_value': parsed.get('strength_value'),
                    'strength_unit': parsed.get('strength_unit'),
                    'form': parsed.get('form'),
                    'score': self._score_medication(name) + item.get('score', 0)
                })

            # Sort by combined score (KB score + RxNorm score)
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # Strategy 2: If few results, try spelling suggestions
            if len(results) < 3:
                spelling_suggestions = self.get_spelling_suggestions(query)
                
                for suggestion in spelling_suggestions[:5]:
                    suggestion_lower = suggestion.lower()
                    
                    if suggestion_lower not in seen_base_names:
                        seen_base_names.add(suggestion_lower)
                        
                        # Get RxCUI for this suggestion
                        rxcui = self._get_rxcui(suggestion)
                        
                        results.append({
                            'name': suggestion,
                            'rxcui': rxcui or '',
                            'display': f"{suggestion} (suggested spelling)",
                            'base_name': suggestion,
                            'strength': None,
                            'strength_value': None,
                            'strength_unit': None,
                            'form': None,
                            'is_spelling_suggestion': True,
                            'score': 100
                        })

            return results[:limit]
            
        except Exception as e:
            print(f"Autocomplete error: {e}")
            return []
    
    def _parse_drug_name(self, name: str) -> Dict:
        """
        Parse a drug name to extract components
        
        Example:
            "Lisinopril 10 MG Oral Tablet" -> 
            {
                "base_name": "Lisinopril",
                "strength": "10 MG",
                "strength_value": 10.0,
                "strength_unit": "MG",
                "form": "Oral Tablet"
            }
        """
        result = {
            'base_name': name,
            'strength': None,
            'strength_value': None,
            'strength_unit': None,
            'form': None
        }
        
        # Common strength units
        strength_pattern = r'(\d+\.?\d*)\s*(MG|MCG|G|ML|MEQ|UNIT|IU|%)'
        
        # Common forms
        forms = [
            'Oral Tablet', 'Tablet', 'Oral Capsule', 'Capsule',
            'Oral Solution', 'Solution', 'Oral Suspension', 'Suspension',
            'Injectable', 'Injection', 'Topical Cream', 'Cream',
            'Topical Ointment', 'Ointment', 'Topical Gel', 'Gel',
            'Transdermal Patch', 'Patch', 'Nasal Spray', 'Spray',
            'Ophthalmic Solution', 'Eye Drops', 'Otic Solution', 'Ear Drops',
            'Inhaler', 'Nebulizer Solution', 'Suppository', 'Powder'
        ]
        
        # Extract strength
        strength_match = re.search(strength_pattern, name, re.IGNORECASE)
        if strength_match:
            result['strength_value'] = float(strength_match.group(1))
            result['strength_unit'] = strength_match.group(2).upper()
            result['strength'] = f"{strength_match.group(1)} {strength_match.group(2).upper()}"
        
        # Extract form
        name_upper = name.upper()
        for form in forms:
            if form.upper() in name_upper:
                result['form'] = form
                break
        
        # Extract base name (first word(s) before numbers)
        base_match = re.match(r'^([A-Za-z\-]+(?:\s+[A-Za-z\-]+)?)', name)
        if base_match:
            result['base_name'] = base_match.group(1).strip()
        
        return result
    
    def get_drug_details(self, rxcui: str) -> Dict:
        """
        Get detailed information about a drug by its RxCUI
        
        Returns structured information including:
        - Name
        - Strength
        - Form
        - Route of administration
        - Active ingredients
        """
        if not rxcui:
            return {'success': False, 'error': 'No RxCUI provided'}
        
        try:
            # Get properties
            url = f"{self.base_url}/rxcui/{rxcui}/properties.json"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                properties = data.get('properties', {})
                
                name = properties.get('name', '')
                parsed = self._parse_drug_name(name)
                
                return {
                    'success': True,
                    'rxcui': rxcui,
                    'name': name,
                    'base_name': parsed.get('base_name'),
                    'strength': parsed.get('strength'),
                    'strength_value': parsed.get('strength_value'),
                    'strength_unit': parsed.get('strength_unit'),
                    'form': parsed.get('form'),
                    'synonym': properties.get('synonym', ''),
                    'tty': properties.get('tty', '')  # Term type
                }
            
            return {'success': False, 'error': 'Drug not found'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # ORIGINAL METHODS (kept for RAG chatbot compatibility)
    # =========================================================================
    
    def search_drug(self, drug_name: str) -> Dict:
        """
        Search for a drug by name
        Example: search_drug("aspirin") returns info about aspirin
        """
        try:
            url = f"{self.base_url}/drugs.json?name={drug_name}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'drug_name': drug_name
                }
            else:
                return {
                    'success': False,
                    'error': 'Drug not found',
                    'drug_name': drug_name
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'drug_name': drug_name
            }
    
    def get_drug_interactions(self, drug_name: str) -> Dict:
        """
        Check what other drugs this medication interacts with
        VERY IMPORTANT for patient safety!
        """
        try:
            rxcui = self._get_rxcui(drug_name)
            
            if not rxcui:
                return {
                    'success': False,
                    'error': 'Could not find drug ID',
                    'drug_name': drug_name
                }
            
            url = f"{self.base_url}/interaction/interaction.json?rxcui={rxcui}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'drug_name': drug_name,
                    'rxcui': rxcui
                }
            else:
                return {
                    'success': False,
                    'error': 'No interaction data available',
                    'drug_name': drug_name
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'drug_name': drug_name
            }
    
    def get_drug_properties(self, drug_name: str) -> Dict:
        """
        Get detailed properties of a drug
        """
        try:
            rxcui = self._get_rxcui(drug_name)
            
            if not rxcui:
                return {
                    'success': False,
                    'error': 'Could not find drug',
                    'drug_name': drug_name
                }
            
            url = f"{self.base_url}/rxcui/{rxcui}/properties.json"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'drug_name': drug_name,
                    'rxcui': rxcui
                }
            else:
                return {
                    'success': False,
                    'error': 'No property data available',
                    'drug_name': drug_name
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'drug_name': drug_name
            }
    
    def _get_rxcui(self, drug_name: str) -> Optional[str]:
        """
        Helper function: Get RxCUI (drug ID) from drug name
        RxCUI is like a "social security number" for drugs
        """
        # Check cache first
        cache_key = f"rxcui_{drug_name.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            url = f"{self.base_url}/rxcui.json?name={drug_name}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                id_group = data.get('idGroup', {})
                rxcui_list = id_group.get('rxnormId', [])
                
                if rxcui_list:
                    rxcui = rxcui_list[0]
                    self._cache[cache_key] = rxcui  # Cache it
                    return rxcui
                    
            return None
            
        except:
            return None
    
    def format_for_rag(self, drug_info: Dict) -> str:
        """
        Convert drug data into text for vector database
        """
        if not drug_info.get('success'):
            return f"No information available for {drug_info.get('drug_name', 'unknown drug')}"
        
        drug_name = drug_info.get('drug_name', 'Unknown')
        description_parts = [f"Medication: {drug_name}"]
        data = drug_info.get('data', {})
        
        formatted_text = "\n".join(description_parts)
        formatted_text += f"\n\nRaw Data: {json.dumps(data, indent=2)}"
        
        return formatted_text


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_openfda():
    """
    Test the OpenFDA integration
    """
    kb = MedicationKnowledgeBase()
    kb.debug = True  # Enable debug output
    
    print("=" * 70)
    print("🏥 TESTING OPENFDA DRUG INFORMATION")
    print("=" * 70)
    
    test_drugs = [
        "lisinopril",    # Blood pressure medication
        "metformin",     # Diabetes medication
        "atorvastatin",  # Cholesterol medication
        "omeprazole",    # Acid reflux medication
        "sertraline",    # Antidepressant
    ]
    
    for drug in test_drugs:
        print(f"\n{'='*60}")
        print(f"💊 Testing: {drug.upper()}")
        print("=" * 60)
        
        # Get quick summary (for form auto-fill)
        summary = kb.get_quick_drug_summary(drug)
        
        if summary.get('success'):
            print(f"\n📋 TAKEN FOR:")
            print(f"   {summary.get('taken_for', 'N/A')[:200]}...")
            
            print(f"\n⚠️ COMMON SIDE EFFECTS:")
            for effect in summary.get('common_side_effects', []):
                print(f"   • {effect}")
            
            print(f"\n🚫 DO NOT MIX WITH:")
            for interaction in summary.get('do_not_mix_with', []):
                print(f"   • {interaction}")
            
            if summary.get('important_warning'):
                print(f"\n⚠️ WARNING:")
                print(f"   {summary.get('important_warning')[:200]}...")
        else:
            print(f"   ❌ Error: {summary.get('error')}")
    
    print("\n" + "=" * 70)
    print("✅ OpenFDA test complete!")
    print("=" * 70)


def test_autocomplete():
    """
    Test the autocomplete functionality
    """
    kb = MedicationKnowledgeBase()
    
    print("=" * 60)
    print("TESTING MEDICATION AUTOCOMPLETE")
    print("=" * 60)
    
    test_queries = [
        "lisin",           # Should find Lisinopril
        "metfor",          # Should find Metformin
        "asprin",          # Misspelled - should suggest Aspirin
        "lisinipril",      # Misspelled - should correct
        "ator",            # Should find Atorvastatin
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        results = kb.autocomplete(query, limit=5)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result['name']}")
                if result.get('strength'):
                    print(f"     Strength: {result['strength']}")
                if result.get('form'):
                    print(f"     Form: {result['form']}")
                if result.get('rxcui'):
                    print(f"     RxCUI: {result['rxcui']}")
        else:
            print("  No results found")
    
    print("\n" + "=" * 60)
    print("TESTING SPELLING SUGGESTIONS")
    print("=" * 60)
    
    misspellings = ["asprin", "lisinipril", "metforman", "amlodipeen"]
    
    for word in misspellings:
        print(f"\n❌ Misspelled: '{word}'")
        suggestions = kb.get_spelling_suggestions(word)
        if suggestions:
            print(f"   ✅ Suggestions: {', '.join(suggestions[:3])}")
        else:
            print("   No suggestions found")


if __name__ == "__main__":
    # Run both tests
    test_openfda()
    print("\n\n")
    test_autocomplete()