"""
Content Filter - Medical Safety
===============================
Blocks dangerous medical advice and content.
Health-Tech Rule: AI must never suggest harmful actions!
"""

from typing import List, Dict, Set
from pydantic import BaseModel, Field
from enum import Enum


class ContentFilterResult(BaseModel):
    """Result of content filtering"""
    is_safe: bool = Field(..., description="Whether content is safe")
    blocked_categories: List[str] = Field(default_factory=list, description="Categories that triggered block")
    reason: str = Field(..., description="Human-readable explanation")
    severity: str = Field(default="info", description="Severity of the issue")


class DangerousCategory(Enum):
    """Categories of dangerous medical content"""
    SELF_HARM = "self_harm"
    SUICIDE = "suicide"
    PRESCRIPTION_CHANGE = "prescription_change"
    UNQUALIFIED_DIAGNOSIS = "unqualified_diagnosis"
    EXPIRED_MEDICATION = "expired_medication"
    DOSAGE_INCREASE = "dosage_increase"
    STOP_MEDICATION = "stop_medication"
    CRUSH_EXTENDED_RELEASE = "crush_extended_release"
    OFF_LABEL_USE = "off_label_use"
    EMERGENCY_DELAY = "emergency_delay"


class MedicalContentFilter:
    """
    Filters dangerous medical content from AI responses.
    
    This is a CRITICAL safety layer that prevents the AI from:
    - Encouraging self-harm
    - Suggesting prescription changes without doctor
    - Making unqualified diagnoses
    - Recommending expired medications
    - Suggesting dangerous medication modifications
    """
    
    # Dangerous patterns organized by category
    DANGEROUS_PATTERNS: Dict[DangerousCategory, List[str]] = {
        DangerousCategory.SELF_HARM: [
            'hurt yourself', 'harm yourself', 'damage yourself',
            'cut yourself', 'injure yourself'
        ],
        DangerousCategory.SUICIDE: [
            'kill yourself', 'end your life', 'suicide', 'kill myself',
            'end my life', 'not worth living', 'better off dead'
        ],
        DangerousCategory.PRESCRIPTION_CHANGE: [
            'increase your dose', 'decrease your dose', 'change your dose',
            'take more than prescribed', 'take less than prescribed',
            'double the dose', 'triple the dose', 'half the dose'
        ],
        DangerousCategory.UNQUALIFIED_DIAGNOSIS: [
            'you have cancer', 'you are diabetic', 'you have diabetes',
            'you have heart disease', 'you have', 'diagnosis:',
            'you are diagnosed with', 'you suffer from'
        ],
        DangerousCategory.EXPIRED_MEDICATION: [
            'expired medication', 'expired pills', 'past expiration',
            'old pills', 'expired drugs', 'take expired'
        ],
        DangerousCategory.DOSAGE_INCREASE: [
            'take more', 'increase to', 'go up to', 'higher dose',
            'stronger dose', 'maximum dose'
        ],
        DangerousCategory.STOP_MEDICATION: [
            'stop taking', 'quit taking', 'discontinue', "don't take",
            'stop your medication', 'quit your medication', 'stop cold turkey'
        ],
        DangerousCategory.CRUSH_EXTENDED_RELEASE: [
            'crush the tablet', 'crush the pill', 'break the tablet',
            'chew the tablet', 'crush extended', 'crush time-release'
        ],
        DangerousCategory.OFF_LABEL_USE: [
            'use it for', 'take it for', 'works for', 'good for',
            'helps with weight loss', 'helps with sleep', 'recreational use'
        ],
        DangerousCategory.EMERGENCY_DELAY: [
            'wait and see', 'see how you feel', 'wait it out',
            'give it time', "don't call 911", 'not an emergency',
            'probably fine', 'just wait'
        ],
    }
    
    # Required safety elements for different response types
    REQUIRED_ELEMENTS: Dict[str, List[str]] = {
        'medical_advice': [
            'consult', 'doctor', 'physician', 'healthcare provider',
            'pharmacist', 'medical professional', 'healthcare'
        ],
        'interaction_warning': [
            'interaction', 'doctor', 'pharmacist', 'consult'
        ],
        'side_effects': [
            'side effects', 'may experience', 'common side effects'
        ]
    }
    
    def __init__(self):
        self.blocked_count = 0
        self.category_counts: Dict[str, int] = {cat.value: 0 for cat in DangerousCategory}
    
    def check_input(self, text: str) -> ContentFilterResult:
        """
        Check user input for concerning content.
        Used to detect potential emergencies or misuse.
        """
        text_lower = text.lower()
        blocked = []
        
        # Check for emergency keywords
        emergency_keywords = [
            'overdose', 'took too many', 'too many pills', 'unconscious',
            "can't breathe", 'chest pain', 'heart attack', 'stroke',
            'suicide', 'kill myself', 'dying', 'emergency', '911'
        ]
        
        has_emergency = any(kw in text_lower for kw in emergency_keywords)
        
        if has_emergency:
            return ContentFilterResult(
                is_safe=False,
                blocked_categories=['emergency_detected'],
                reason="Emergency keywords detected - requires immediate human attention",
                severity="critical"
            )
        
        return ContentFilterResult(
            is_safe=True,
            blocked_categories=[],
            reason="Input appears safe",
            severity="info"
        )
    
    def check_response(
        self, 
        response: str, 
        context: Dict = None
    ) -> ContentFilterResult:
        """
        Check AI response for dangerous content.
        
        Args:
            response: The AI-generated response
            context: Additional context (intent, user_meds, etc.)
            
        Returns:
            ContentFilterResult with safety assessment
        """
        context = context or {}
        response_lower = response.lower()
        blocked_categories = []
        
        # Check each dangerous category
        for category, patterns in self.DANGEROUS_PATTERNS.items():
            for pattern in patterns:
                if pattern in response_lower:
                    blocked_categories.append(category.value)
                    self.category_counts[category.value] += 1
                    break  # Only count once per category
        
        # Determine severity
        severity = "info"
        if blocked_categories:
            critical_cats = ['suicide', 'self_harm', 'emergency_delay', 'crush_extended_release']
            if any(cat in critical_cats for cat in blocked_categories):
                severity = "critical"
            else:
                severity = "high"
            
            self.blocked_count += 1
            
            return ContentFilterResult(
                is_safe=False,
                blocked_categories=blocked_categories,
                reason=f"Response blocked due to dangerous content: {', '.join(blocked_categories)}",
                severity=severity
            )
        
        # Check for missing required elements based on intent
        intent = context.get('intent', '')
        if intent in self.REQUIRED_ELEMENTS:
            required = self.REQUIRED_ELEMENTS[intent]
            has_required = any(elem in response_lower for elem in required)
            
            if not has_required:
                return ContentFilterResult(
                    is_safe=False,
                    blocked_categories=['missing_required_elements'],
                    reason=f"Response missing required safety elements for {intent}",
                    severity="medium"
                )
        
        return ContentFilterResult(
            is_safe=True,
            blocked_categories=[],
            reason="Response passed safety checks",
            severity="info"
        )
    
    def get_stats(self) -> Dict:
        """Get filtering statistics"""
        return {
            'total_blocked': self.blocked_count,
            'category_breakdown': self.category_counts
        }


# Singleton instance
_content_filter = None

def get_content_filter() -> MedicalContentFilter:
    """Get singleton content filter"""
    global _content_filter
    if _content_filter is None:
        _content_filter = MedicalContentFilter()
    return _content_filter
