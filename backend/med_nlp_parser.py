"""
Medication Tracker - Natural Language Processing Module
This helps the app understand natural language when users add medications
"""

import re
from typing import Dict, Optional

class MedicationNLPParser:
    """
    This class is like a translator - it takes human sentences
    and figures out medication details from them
    """
    
    def __init__(self):
        # These are patterns we look for in the text
        # Think of them like "clue words" that help us understand
        
        # Frequency patterns (how often to take it)
        self.frequency_patterns = {
            'once daily': 'once daily',
            'once a day': 'once daily',
            'daily': 'once daily',
            'twice daily': 'twice daily',
            'twice a day': 'twice daily',
            '2 times a day': 'twice daily',
            '2 times daily': 'twice daily',
            'three times daily': '3 times daily',
            'three times a day': '3 times daily',
            '3 times a day': '3 times daily',
            'every morning': 'every morning',
            'every night': 'every night',
            'at bedtime': 'at bedtime',
            'before bed': 'at bedtime',
            'as needed': 'as needed',
            'when needed': 'as needed',
            'every 4 hours': 'every 4 hours',
            'every 6 hours': 'every 6 hours',
            'every 8 hours': 'every 8 hours',
            'every 12 hours': 'every 12 hours',
        }
        
        # Common dosage units
        self.dosage_units = ['mg', 'mcg', 'g', 'ml', 'iu', 'units', 
                            'tablet', 'tablets', 'capsule', 'capsules',
                            'pill', 'pills', 'puff', 'puffs', 'drop', 'drops']
    
    def parse_medication_input(self, text: str) -> Dict:
        """
        Takes a sentence like "Add aspirin 500mg twice daily"
        Returns a dictionary with: name, dosage, frequency, notes
        
        Think of this like a detective finding clues in a sentence!
        """
        # Make text lowercase for easier matching
        text_lower = text.lower()
        
        result = {
            'name': None,
            'dosage': None,
            'frequency': None,
            'notes': None
        }
        
        # Step 1: Extract any additional notes FIRST (so we can remove them)
        result['notes'] = self._extract_notes(text_lower)
        
        # Step 2: Find the frequency (how often) BEFORE name
        result['frequency'] = self._extract_frequency(text_lower)
        
        # Step 3: Find the dosage (how much)
        result['dosage'] = self._extract_dosage(text_lower)
        
        # Step 4: Find the medication name (after removing other parts)
        result['name'] = self._extract_medication_name(text_lower, result['dosage'], result['frequency'])
        
        return result
    
    def _extract_frequency(self, text: str) -> Optional[str]:
        """
        Looks for frequency clues in the text
        Like: "twice daily", "every morning", "as needed"
        
        IMPORTANT: Check longer patterns first to avoid partial matches!
        """
        # Sort patterns by length (longest first) to avoid partial matches
        # For example, check "twice daily" before checking "daily"
        sorted_patterns = sorted(self.frequency_patterns.items(), 
                                key=lambda x: len(x[0]), 
                                reverse=True)
        
        for pattern, frequency in sorted_patterns:
            if pattern in text:
                return frequency
        
        # If no pattern found, return default
        return "as directed"
    
    def _extract_dosage(self, text: str) -> Optional[str]:
        """
        Looks for dosage information
        Like: "500mg", "2 tablets", "1000 IU"
        """
        # Look for patterns like "500mg", "2 tablets", "1000 iu"
        # \d+ means "one or more digits"
        # \s* means "zero or more spaces"
        for unit in self.dosage_units:
            # Pattern looks for: number + optional space + unit
            pattern = r'(\d+\.?\d*\s*' + unit + r's?)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Try to find just a number with common units
        dosage_pattern = r'(\d+\.?\d*\s*(?:mg|mcg|g|ml|iu|units?))'
        match = re.search(dosage_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_medication_name(self, text: str, dosage: str, frequency: str) -> Optional[str]:
        """
        Finds the medication name by removing other parts
        This is like finding the main subject of the sentence
        """
        # Start with a copy of the text
        working_text = text
        
        # Remove common action words
        working_text = re.sub(r'\b(add|take|remind me to take|using?|my)\b', '', working_text, flags=re.IGNORECASE)
        
        # Remove dosage if found
        if dosage:
            working_text = working_text.replace(dosage.lower(), '')
        
        # Remove ALL frequency patterns from the text, not just the matched one
        # This is important because "twice daily" might have been in the original text
        # CRITICAL FIX: Sort patterns by length (longest first) before removing!
        # This ensures "twice daily" is removed BEFORE "daily" is checked
        sorted_patterns = sorted(self.frequency_patterns.keys(), key=len, reverse=True)
        for pattern in sorted_patterns:
            if pattern in working_text:
                working_text = working_text.replace(pattern, '')
                break  # Stop after first match to avoid removing too much
        
        # Also remove the standardized frequency result (as a backup)
        if frequency and frequency != "as directed":
            working_text = working_text.replace(frequency.lower(), '')
        
        # Remove extra whitespace and get the remaining text
        name = ' '.join(working_text.split()).strip()
        
        # Remove leading/trailing punctuation
        name = name.strip('.,!?')
        
        # Take the first few words as the medication name
        words = name.split()
        if len(words) > 0:
            # Usually medication name is 1-2 words, but let's be smart about it
            # If we only have 1 word, use it
            # If we have 2-3 words, use first 2
            # If we have more, use first 3 (in case of multi-word drug names)
            if len(words) == 1:
                return words[0]
            elif len(words) <= 3:
                return ' '.join(words[:2])
            else:
                return ' '.join(words[:3])
        
        return None
    
    def _extract_notes(self, text: str) -> Optional[str]:
        """
        Finds additional notes like "with food" or "on empty stomach"
        """
        note_keywords = [
            'with food',
            'without food',
            'on empty stomach',
            'with water',
            'before meals',
            'after meals',
            'in the morning',
            'at night',
            'with breakfast',
            'with dinner'
        ]
        
        found_notes = []
        for keyword in note_keywords:
            if keyword in text:
                found_notes.append(keyword)
        
        if found_notes:
            return ', '.join(found_notes)
        
        return None


# Test function to show how it works (locally)
def test_parser():
    """
    This function shows examples of the parser working
    Run this to see what it does!
    """
    parser = MedicationNLPParser()
    
    test_sentences = [
        "Add aspirin 500mg twice daily",
        "Take vitamin D 1000 IU every morning",
        "Remind me to use my inhaler 2 puffs as needed",
        "Add metformin 850mg three times a day with food",
        "Take blood pressure medication 10mg once daily"
    ]
    
    print("=" * 60)
    print("TESTING MEDICATION NLP PARSER")
    print("=" * 60)
    
    for sentence in test_sentences:
        print(f"\nInput: '{sentence}'")
        result = parser.parse_medication_input(sentence)
        print(f"  -> Name: {result['name']}")
        print(f"  -> Dosage: {result['dosage']}")
        print(f"  -> Frequency: {result['frequency']}")
        print(f"  -> Notes: {result['notes']}")


# Run the test if this file is run directly
if __name__ == "__main__":
    test_parser()