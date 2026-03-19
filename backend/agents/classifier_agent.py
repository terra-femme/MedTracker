"""
Classifier Agent - Intent Detection
===================================
Classifies user questions into intent categories.
Fast, rule-based classification with LLM fallback.
"""

from typing import Dict, List
from .base import BaseAgent, AgentInput, AgentOutput
from ..core.guardrails import IntentClassification, SafetyFlag


class ClassifierAgent(BaseAgent):
    """
    Agent that classifies user intent.
    
    Intent categories:
    - medication_info: General questions about medications
    - interaction_check: Drug interaction questions
    - dosage_question: Dosing/timing questions
    - side_effects: Side effect questions
    - emergency: Urgent medical situations
    - general_chat: Casual conversation
    - unknown: Could not classify
    
    Uses fast keyword matching first, then LLM if needed.
    """
    
    name = "classifier"
    description = "Classifies user questions into intent categories"
    
    # Emergency keywords - always check these first
    EMERGENCY_KEYWORDS = [
        'overdose', 'too many', "can't breathe", 'chest pain',
        'unconscious', 'suicide', 'kill myself', 'emergency', 
        'dying', '911', 'poison control', 'took too much',
        'not breathing', 'severe allergic', 'anaphylaxis'
    ]
    
    # Intent keywords for fast classification
    INTENT_KEYWORDS = {
        'interaction_check': [
            'interaction', 'mix', 'combine', 'with', 'together',
            'take with', 'drink with', 'eat with', 'and',
            'can i take', 'safe to take'
        ],
        'dosage_question': [
            'dose', 'dosage', 'how much', 'how many', 'when to take',
            'how often', 'timing', 'schedule', 'missed dose',
            'double dose', 'skip', 'hours between'
        ],
        'side_effects': [
            'side effect', 'adverse', 'reaction', 'symptom',
            'feel sick', 'nausea', 'dizzy', 'headache',
            'rash', 'itching', 'swelling', 'tired'
        ],
        'medication_info': [
            'what is', 'how does', 'purpose', 'used for',
            'treat', 'medication', 'medicine', 'drug',
            'generic', 'brand name'
        ],
        'general_chat': [
            'hello', 'hi', 'hey', 'help', 'thank', 'thanks',
            'bye', 'goodbye', 'how are you'
        ]
    }
    
    def __init__(self, llm_func=None, **kwargs):
        """
        Args:
            llm_func: Optional async function for LLM classification
            **kwargs: Passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.llm_func = llm_func  # Optional LLM for complex cases
    
    async def _process(self, input_data: AgentInput) -> AgentOutput:
        """
        Classify the user's question.
        
        Strategy:
        1. Check for emergency keywords (fast path)
        2. Check keyword patterns for each intent
        3. If unclear, use LLM (if available)
        4. Default to unknown if still unclear
        """
        question = input_data.query.lower()
        
        # Step 1: Emergency check (highest priority)
        if self._check_emergency(question):
            return AgentOutput(
                success=True,
                response="emergency",
                metadata={
                    'classification': 'emergency',
                    'confidence': 1.0,
                    'method': 'keyword',
                    'intent': 'emergency'
                },
                safety_flags=[SafetyFlag(
                    level="emergency",
                    category="content",
                    message="Emergency keywords detected in user query",
                    action_required=True
                )],
                confidence=1.0
            )
        
        # Step 2: Keyword-based classification
        intent_scores = self._score_by_keywords(question)
        
        # Get highest scoring intent
        best_intent = max(intent_scores, key=intent_scores.get)
        best_score = intent_scores[best_intent]
        
        # Step 3: If confident, return result
        if best_score >= 0.5:
            confidence = min(best_score, 0.95)  # Cap at 0.95 for keyword method
            
            return AgentOutput(
                success=True,
                response=best_intent,
                metadata={
                    'classification': best_intent,
                    'confidence': confidence,
                    'method': 'keyword',
                    'scores': intent_scores,
                    'intent': best_intent
                },
                confidence=confidence
            )
        
        # Step 4: Try LLM if available and score is unclear
        if self.llm_func and best_score < 0.5:
            llm_result = await self._llm_classify(input_data.query)
            return AgentOutput(
                success=True,
                response=llm_result['intent'],
                metadata={
                    'classification': llm_result['intent'],
                    'confidence': llm_result['confidence'],
                    'method': 'llm',
                    'reasoning': llm_result['reasoning'],
                    'intent': llm_result['intent']
                },
                confidence=llm_result['confidence']
            )
        
        # Step 5: Default to unknown
        return AgentOutput(
            success=True,
            response="unknown",
            metadata={
                'classification': 'unknown',
                'confidence': 0.3,
                'method': 'default',
                'scores': intent_scores,
                'intent': 'unknown'
            },
            confidence=0.3
        )
    
    def _check_emergency(self, question: str) -> bool:
        """Check if question contains emergency keywords"""
        return any(keyword in question for keyword in self.EMERGENCY_KEYWORDS)
    
    def _score_by_keywords(self, question: str) -> Dict[str, float]:
        """
        Score each intent based on keyword matches.
        Returns dict of intent -> score (0-1)
        """
        scores = {intent: 0.0 for intent in self.INTENT_KEYWORDS.keys()}
        scores['unknown'] = 0.1  # Base score for unknown
        
        words = set(question.split())
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            matches = 0
            for keyword in keywords:
                if keyword in question:
                    # Multi-word keywords score higher
                    if ' ' in keyword:
                        matches += 2
                    else:
                        matches += 1
            
            # Normalize by number of keywords
            if keywords:
                scores[intent] = min(matches / (len(keywords) * 0.3), 1.0)
        
        return scores
    
    async def _llm_classify(self, question: str) -> Dict:
        """
        Use LLM for classification when keywords are unclear.
        This is a mock implementation - replace with actual LLM call.
        """
        if self.llm_func:
            try:
                prompt = f"""Classify this medication question into exactly one category:

Categories:
- medication_info: General questions about what a drug does
- interaction_check: Questions about combining drugs
- dosage_question: Questions about how much/when to take
- side_effects: Questions about adverse effects
- emergency: Urgent medical situations
- general_chat: Casual conversation

Question: "{question}"

Respond ONLY with the category name:"""
                
                # Call LLM (async)
                response = await self.llm_func(prompt)
                intent = response.strip().lower()
                
                # Validate intent
                valid_intents = list(self.INTENT_KEYWORDS.keys()) + ['emergency', 'unknown']
                if intent not in valid_intents:
                    intent = 'unknown'
                
                return {
                    'intent': intent,
                    'confidence': 0.8,
                    'reasoning': 'LLM classification'
                }
            except Exception as e:
                # Fallback on LLM error
                return {
                    'intent': 'unknown',
                    'confidence': 0.0,
                    'reasoning': f'LLM error: {e}'
                }
        
        # No LLM available
        return {
            'intent': 'unknown',
            'confidence': 0.0,
            'reasoning': 'No LLM available'
        }
    
    def get_supported_intents(self) -> List[str]:
        """Return list of supported intent categories"""
        return list(self.INTENT_KEYWORDS.keys()) + ['emergency', 'unknown']
