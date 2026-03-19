"""
Interaction Checker Agent - Drug Safety
=======================================
Checks for drug-drug and drug-allergy interactions.
Uses both knowledge base rules and LLM analysis.
"""

import json
import re
from typing import Dict, List, Optional
from .base import BaseAgent, AgentInput, AgentOutput
from ..core.guardrails import (
    InteractionCheckResult, 
    InteractionSeverity,
    SafetyFlag
)


class InteractionCheckerAgent(BaseAgent):
    """
    Agent that checks for drug interactions.
    
    Checks:
    1. Drug-to-drug interactions
    2. Drug-to-allergy interactions
    3. Duplicate therapy
    
    Uses known interaction database first, then LLM for analysis.
    """
    
    name = "interaction_checker"
    description = "Checks for drug interactions and safety concerns"
    
    # Known dangerous interactions (simplified - use real database in production)
    KNOWN_INTERACTIONS = {
        ('warfarin', 'ibuprofen'): {
            'severity': InteractionSeverity.SEVERE,
            'mechanism': 'Increased bleeding risk - NSAIDs affect platelet function',
            'recommendation': 'Avoid combining. Consult doctor for alternative pain relief.'
        },
        ('warfarin', 'aspirin'): {
            'severity': InteractionSeverity.SEVERE,
            'mechanism': 'Increased bleeding risk',
            'recommendation': 'Use only if specifically prescribed together. Monitor closely.'
        },
        ('lisinopril', 'potassium'): {
            'severity': InteractionSeverity.MODERATE,
            'mechanism': 'Risk of hyperkalemia (high potassium)',
            'recommendation': 'Monitor potassium levels. Avoid potassium supplements.'
        },
        ('metformin', 'contrast dye'): {
            'severity': InteractionSeverity.MODERATE,
            'mechanism': 'Risk of lactic acidosis',
            'recommendation': 'May need to hold metformin before/after contrast imaging.'
        },
        ('simvastatin', 'clarithromycin'): {
            'severity': InteractionSeverity.SEVERE,
            'mechanism': 'Increased statin levels - risk of muscle damage',
            'recommendation': 'Avoid combination. Consider alternative antibiotic.'
        },
        ('amiodarone', 'warfarin'): {
            'severity': InteractionSeverity.SEVERE,
            'mechanism': 'Amiodarone increases warfarin effect',
            'recommendation': 'Requires significant warfarin dose reduction and monitoring.'
        }
    }
    
    # Allergy cross-reactivity patterns
    ALLERGY_PATTERNS = {
        'penicillin': ['amoxicillin', 'ampicillin', 'cephalexin', 'cefdinir'],
        'sulfa': ['sulfamethoxazole', 'furosemide', 'hydrochlorothiazide'],
        'nsaid': ['ibuprofen', 'naproxen', 'aspirin', 'diclofenac'],
    }
    
    def __init__(self, llm_func=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_func = llm_func
    
    async def _process(self, input_data: AgentInput) -> AgentOutput:
        """
        Check for drug interactions.
        
        Strategy:
        1. Extract mentioned drugs from query
        2. Check against user's current medications
        3. Check against user's allergies
        4. Check known interaction database
        5. Use LLM for additional analysis if needed
        """
        question = input_data.query.lower()
        user_meds = input_data.user_medications
        allergies = input_data.allergies
        
        interactions_found = []
        safety_flags = []
        
        # Step 1: Extract drugs mentioned in query
        mentioned_drugs = self._extract_drugs(question)
        
        # Step 2: Check interactions with user's medications
        for mentioned_drug in mentioned_drugs:
            for user_med in user_meds:
                user_drug_name = user_med.get('name', '').lower()
                
                interaction = self._check_pair(mentioned_drug, user_drug_name)
                if interaction:
                    interactions_found.append(interaction)
                    
                    if interaction['severity'] in [InteractionSeverity.SEVERE, InteractionSeverity.CONTRAINDICATED]:
                        safety_flags.append(SafetyFlag(
                            level="critical",
                            category="interaction",
                            message=f"Severe interaction: {mentioned_drug} + {user_drug_name}",
                            action_required=True
                        ))
        
        # Step 3: Check allergy concerns
        for mentioned_drug in mentioned_drugs:
            allergy_concerns = self._check_allergies(mentioned_drug, allergies)
            for concern in allergy_concerns:
                interactions_found.append(concern)
                safety_flags.append(SafetyFlag(
                    level="critical",
                    category="allergy",
                    message=f"Allergy concern: {concern['recommendation']}",
                    action_required=True
                ))
        
        # Step 4: Check for duplicate therapy
        duplicates = self._check_duplicates(mentioned_drugs, user_meds)
        if duplicates:
            interactions_found.extend(duplicates)
        
        # Step 5: LLM analysis if unclear or complex
        if self.llm_func and len(interactions_found) == 0:
            llm_analysis = await self._llm_analyze(
                question, user_meds, allergies
            )
            if llm_analysis.get('potential_interactions'):
                interactions_found.extend(llm_analysis['potential_interactions'])
        
        # Build response
        has_severe = any(
            i.get('severity') in [InteractionSeverity.SEVERE, InteractionSeverity.CONTRAINDICATED]
            for i in interactions_found
        )
        
        response_summary = self._format_interactions(interactions_found)
        
        return AgentOutput(
            success=True,
            response=response_summary,
            metadata={
                'interactions_found': len(interactions_found),
                'interactions': interactions_found,
                'mentioned_drugs': mentioned_drugs,
                'has_severe_interaction': has_severe,
                'intent': 'interaction_check'
            },
            safety_flags=safety_flags,
            confidence=0.9 if interactions_found else 0.7
        )
    
    def _extract_drugs(self, text: str) -> List[str]:
        """Extract drug names from text (simplified)"""
        # Common drug names for demo - use NLP in production
        common_drugs = [
            'warfarin', 'ibuprofen', 'aspirin', 'lisinopril', 'metformin',
            'atorvastatin', 'simvastatin', 'amoxicillin', 'azithromycin',
            'omeprazole', 'amlodipine', 'metoprolol', 'losartan',
            'gabapentin', 'levothyroxine', 'albuterol', 'fluticasone'
        ]
        
        found = []
        text_lower = text.lower()
        
        for drug in common_drugs:
            if drug in text_lower:
                found.append(drug)
        
        return found
    
    def _check_pair(self, drug_a: str, drug_b: str) -> Optional[Dict]:
        """Check if two drugs have a known interaction"""
        # Check both orderings
        pair = (drug_a, drug_b)
        reverse_pair = (drug_b, drug_a)
        
        if pair in self.KNOWN_INTERACTIONS:
            return {
                'drug_a': drug_a,
                'drug_b': drug_b,
                **self.KNOWN_INTERACTIONS[pair]
            }
        
        if reverse_pair in self.KNOWN_INTERACTIONS:
            return {
                'drug_a': drug_a,
                'drug_b': drug_b,
                **self.KNOWN_INTERACTIONS[reverse_pair]
            }
        
        return None
    
    def _check_allergies(self, drug: str, allergies: List[str]) -> List[Dict]:
        """Check if drug may trigger allergies"""
        concerns = []
        drug_lower = drug.lower()
        
        for allergy in allergies:
            allergy_lower = allergy.lower()
            
            # Direct match
            if allergy_lower in drug_lower:
                concerns.append({
                    'drug': drug,
                    'allergy': allergy,
                    'severity': InteractionSeverity.CONTRAINDICATED,
                    'mechanism': f'Patient allergic to {allergy}',
                    'recommendation': f'DO NOT TAKE - Patient has known allergy to {allergy}'
                })
            
            # Cross-reactivity
            for allergen_class, related_drugs in self.ALLERGY_PATTERNS.items():
                if allergen_class in allergy_lower:
                    if drug_lower in [d.lower() for d in related_drugs]:
                        concerns.append({
                            'drug': drug,
                            'allergy': allergy,
                            'severity': InteractionSeverity.SEVERE,
                            'mechanism': f'Cross-reactivity with {allergen_class} allergy',
                            'recommendation': f'Avoid - may trigger {allergen_class} allergy reaction'
                        })
        
        return concerns
    
    def _check_duplicates(
        self, 
        mentioned_drugs: List[str], 
        user_meds: List[Dict]
    ) -> List[Dict]:
        """Check for duplicate therapy"""
        duplicates = []
        
        # NSAID duplicates
        nsaids = ['ibuprofen', 'naproxen', 'aspirin', 'diclofenac']
        user_nsaids = [
            m for m in user_meds 
            if any(n in m.get('name', '').lower() for n in nsaids)
        ]
        mentioned_nsaids = [d for d in mentioned_drugs if d in nsaids]
        
        if user_nsaids and mentioned_nsaids:
            duplicates.append({
                'type': 'duplicate_therapy',
                'drug_class': 'NSAID',
                'current': [m['name'] for m in user_nsaids],
                'mentioned': mentioned_nsaids,
                'severity': InteractionSeverity.MODERATE,
                'recommendation': 'Avoid taking multiple NSAIDs together - increases bleeding and kidney risk'
            })
        
        # ACE inhibitor duplicates
        ace_inhibitors = ['lisinopril', 'enalapril', 'captopril']
        user_ace = [
            m for m in user_meds
            if any(a in m.get('name', '').lower() for a in ace_inhibitors)
        ]
        mentioned_ace = [d for d in mentioned_drugs if d in ace_inhibitors]
        
        if user_ace and mentioned_ace:
            duplicates.append({
                'type': 'duplicate_therapy',
                'drug_class': 'ACE inhibitor',
                'current': [m['name'] for m in user_ace],
                'mentioned': mentioned_ace,
                'severity': InteractionSeverity.CONTRAINDICATED,
                'recommendation': 'DO NOT combine ACE inhibitors - dangerous blood pressure drop'
            })
        
        return duplicates
    
    async def _llm_analyze(
        self, 
        question: str, 
        user_meds: List[Dict], 
        allergies: List[str]
    ) -> Dict:
        """Use LLM for additional interaction analysis"""
        if not self.llm_func:
            return {'potential_interactions': []}
        
        try:
            prompt = f"""Analyze this medication question for potential interactions.

Patient's current medications: {', '.join(m['name'] for m in user_meds)}
Patient's allergies: {', '.join(allergies)}

Question: {question}

If you identify any potential interactions, respond in this JSON format:
{{"potential_interactions": [{{"drug_a": "name", "drug_b": "name", "severity": "mild/moderate/severe", "recommendation": "what to do"}}]}}

If no interactions, respond: {{"potential_interactions": []}}"""
            
            response = await self.llm_func(prompt)
            
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {'potential_interactions': []}
            
        except Exception as e:
            return {'potential_interactions': [], 'error': str(e)}
    
    def _format_interactions(self, interactions: List[Dict]) -> str:
        """Format interactions for response"""
        if not interactions:
            return "No known interactions found. However, always consult your pharmacist or doctor before combining medications."
        
        parts = []
        
        # Group by severity
        severe = [i for i in interactions if i.get('severity') in [InteractionSeverity.SEVERE, InteractionSeverity.CONTRAINDICATED]]
        moderate = [i for i in interactions if i.get('severity') == InteractionSeverity.MODERATE]
        mild = [i for i in interactions if i.get('severity') == InteractionSeverity.MILD]
        
        if severe:
            parts.append("**⚠️ SEVERE INTERACTIONS DETECTED:**")
            for i in severe:
                parts.append(f"- {i.get('drug_a', 'Unknown')} + {i.get('drug_b', 'Unknown')}: {i.get('recommendation', '')}")
            parts.append("")
        
        if moderate:
            parts.append("**Moderate Interactions:**")
            for i in moderate:
                parts.append(f"- {i.get('drug_a', 'Unknown')} + {i.get('drug_b', 'Unknown')}: {i.get('recommendation', '')}")
            parts.append("")
        
        if mild:
            parts.append("Mild interactions noted - monitor for symptoms.")
        
        parts.append("**Please consult your healthcare provider before making any medication changes.**")
        
        return "\n".join(parts)
