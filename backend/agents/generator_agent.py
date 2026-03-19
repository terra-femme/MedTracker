"""
Response Generator Agent - Output Creation
==========================================
Generates final responses to user questions.
Uses templates and LLM to create safe, helpful answers.
"""

from typing import Dict, List, Optional
from .base import BaseAgent, AgentInput, AgentOutput
from ..core.guardrails import SafetyFlag


class ResponseGeneratorAgent(BaseAgent):
    """
    Agent that generates responses to user questions.
    
    Features:
    - Intent-specific response templates
    - Medication context integration
    - Safety disclaimer injection
    - Fallback responses for errors
    """
    
    name = "response_generator"
    description = "Generates helpful responses to medication questions"
    
    # Response templates by intent
    TEMPLATES = {
        'emergency': """**THIS SOUNDS LIKE IT COULD BE AN EMERGENCY**

**If this is a medical emergency:**
Call 911 immediately (or your local emergency number)

**If you suspect an overdose:**
Poison Control: 1-800-222-1222 (US)

I am an AI assistant and cannot provide emergency medical care.
Do NOT wait for an AI response in an emergency!

---

If this is NOT an emergency and I misunderstood, please rephrase your question.""",

        'general_chat': """Hello! I'm your medication assistant. I can help you with:

- Information about your medications
- Drug interaction checks
- Dosage timing questions
- Side effect information

What would you like to know about your medications?"""
    }
    
    # Standard disclaimer to append
    STANDARD_DISCLAIMER = """

---

*I'm an AI assistant providing general information. For medical decisions, please consult your healthcare provider or pharmacist.*"""
    
    def __init__(self, llm_func=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_func = llm_func
    
    async def _process(self, input_data: AgentInput) -> AgentOutput:
        """
        Generate a response to the user's question.
        
        Strategy:
        1. Get intent from context
        2. Use template for simple intents
        3. Generate custom response for complex queries
        4. Add appropriate disclaimers
        """
        question = input_data.query
        context = input_data.context
        intent = context.get('intent', 'medication_info')
        
        # Step 1: Check for template responses
        if intent in self.TEMPLATES:
            return AgentOutput(
                success=True,
                response=self.TEMPLATES[intent],
                metadata={
                    'intent': intent,
                    'method': 'template',
                    'used_template': True
                },
                confidence=1.0
            )
        
        # Step 2: Build context for generation
        meds_context = self._format_medications(input_data.user_medications)
        allergies_context = self._format_allergies(input_data.allergies)
        
        # Step 3: Check if we have interaction data to include
        interaction_data = context.get('interactions')
        
        # Step 4: Generate response
        if self.llm_func:
            response = await self._generate_with_llm(
                question, intent, meds_context, allergies_context, interaction_data
            )
        else:
            response = self._generate_fallback(question, intent, interaction_data)
        
        # Step 5: Add disclaimer (unless emergency - already has warning)
        if intent != 'emergency':
            response = response + self.STANDARD_DISCLAIMER
        
        return AgentOutput(
            success=True,
            response=response,
            metadata={
                'intent': intent,
                'method': 'llm' if self.llm_func else 'fallback',
                'has_interaction_data': interaction_data is not None
            },
            confidence=0.85 if self.llm_func else 0.6
        )
    
    def _format_medications(self, medications: List[Dict]) -> str:
        """Format user medications for context"""
        if not medications:
            return "No medications on file."
        
        lines = ["Your current medications:"]
        for med in medications:
            name = med.get('name', 'Unknown')
            dosage = med.get('dosage', '')
            frequency = med.get('frequency', '')
            lines.append(f"- {name}: {dosage}, {frequency}")
        
        return "\n".join(lines)
    
    def _format_allergies(self, allergies: List[str]) -> str:
        """Format allergies for context"""
        if not allergies:
            return "No known drug allergies."
        
        return f"Allergies: {', '.join(allergies)}"
    
    async def _generate_with_llm(
        self,
        question: str,
        intent: str,
        meds_context: str,
        allergies_context: str,
        interaction_data: Optional[Dict]
    ) -> str:
        """Generate response using LLM"""
        
        # Build prompt based on intent
        base_prompt = f"""You are a helpful medication assistant. Answer the user's question accurately and safely.

USER CONTEXT:
{meds_context}

{allergies_context}
"""
        
        if interaction_data and interaction_data.get('interactions'):
            base_prompt += f"\nINTERACTION INFORMATION:\n{interaction_data}\n"
        
        intent_instructions = {
            'medication_info': """Provide clear, factual information about the medication.
Include: what it's used for, how it works, and key precautions.
Keep it concise but complete.""",
            
            'interaction_check': """Explain the interaction clearly.
Emphasize consulting healthcare provider for severe interactions.
Provide practical guidance on what to watch for.""",
            
            'dosage_question': """Explain dosing considerations.
DO NOT suggest changing prescribed doses.
Direct user to their prescriber for dose adjustments.""",
            
            'side_effects': """List common side effects and when to contact a doctor.
Distinguish between common/mild and serious side effects.
Be honest but not alarmist."""
        }
        
        instruction = intent_instructions.get(
            intent, 
            "Provide helpful, accurate information."
        )
        
        prompt = f"""{base_prompt}

QUESTION: {question}

INSTRUCTIONS: {instruction}

Respond in a helpful, clear manner. Be concise but thorough."""
        
        try:
            response = await self.llm_func(prompt)
            return response.strip()
        except Exception as e:
            # Fallback on LLM error
            return self._generate_fallback(question, intent, interaction_data)
    
    def _generate_fallback(
        self,
        question: str,
        intent: str,
        interaction_data: Optional[Dict]
    ) -> str:
        """Generate fallback response when LLM unavailable"""
        
        fallbacks = {
            'medication_info': """I don't have detailed information about that medication in my knowledge base.

For accurate, up-to-date information, please:
- Ask your pharmacist
- Check with your doctor
- Look up the medication on reliable sources like MedlinePlus or DailyMed

Would you like me to help you with something else about your current medications?""",

            'interaction_check': """I'm unable to check that specific interaction right now.

**Important:** Always consult your pharmacist or doctor before combining medications, especially:
- Blood thinners (warfarin, apixaban)
- Blood pressure medications
- Diabetes medications
- Any new supplements or over-the-counter drugs

Your pharmacist can do a comprehensive interaction check with your full medication list.""",

            'dosage_question': """I can't provide specific dosing advice.

**Please contact your prescriber** for:
- Dose adjustments
- Missed dose instructions
- Questions about your current regimen

Your prescription label and pharmacist are also good resources for dosing questions.""",

            'side_effects': """Common side effects vary by medication.

**Contact your doctor if you experience:**
- Severe or unusual symptoms
- Allergic reactions (rash, swelling, difficulty breathing)
- Side effects that don't go away
- New symptoms after starting a medication

Your medication leaflet lists known side effects. Read it carefully and discuss concerns with your healthcare provider."""
        }
        
        return fallbacks.get(
            intent, 
            "I'm not able to answer that question right now. Please consult your healthcare provider for medical advice."
        )
    
    async def generate_retry(
        self,
        original_input: AgentInput,
        previous_response: str,
        safety_feedback: List[str]
    ) -> AgentOutput:
        """
        Generate a new response incorporating safety feedback.
        Used when initial response fails safety review.
        """
        if not self.llm_func:
            # Without LLM, return safe generic response
            return AgentOutput(
                success=True,
                response="I'm unable to provide that specific information. For accurate medical guidance, please consult your healthcare provider or pharmacist." + self.STANDARD_DISCLAIMER,
                metadata={'retry': True, 'method': 'fallback'}
            )
        
        feedback_text = "\n".join(f"- {f}" for f in safety_feedback)
        
        prompt = f"""You are a medication assistant. Your previous response had safety issues.

ORIGINAL QUESTION: {original_input.query}

YOUR PREVIOUS RESPONSE: {previous_response}

SAFETY ISSUES TO FIX:
{feedback_text}

Please generate a new response that:
1. Addresses the user's question
2. Fixes all the safety issues above
3. Includes appropriate medical disclaimers
4. Is helpful but conservative in medical advice"""
        
        try:
            response = await self.llm_func(prompt)
            return AgentOutput(
                success=True,
                response=response + self.STANDARD_DISCLAIMER,
                metadata={'retry': True, 'method': 'llm_retry'}
            )
        except Exception as e:
            return AgentOutput(
                success=False,
                response="Error generating response. Please consult your healthcare provider.",
                metadata={'retry': True, 'error': str(e)}
            )
