"""
Safety Reviewer Agent - Quality Assurance
=========================================
Critiques and validates other agent outputs.
Acts as a final safety checkpoint before responses reach users.

Key responsibilities:
1. Content safety review
2. PII leak detection
3. Medical disclaimer verification
4. Response quality assessment
5. Retry recommendations
"""

from typing import Dict, List, Optional
from .base import BaseAgent, AgentInput, AgentOutput
from ..core.guardrails import SafetyFlag, ContentFilterResult, ValidationResult


class SafetyReviewResult:
    """Result of safety review"""
    def __init__(
        self,
        is_safe: bool,
        issues: List[Dict],
        recommendations: List[str],
        severity: str = "info"
    ):
        self.is_safe = is_safe
        self.issues = issues
        self.recommendations = recommendations
        self.severity = severity


class SafetyReviewerAgent(BaseAgent):
    """
    Agent that reviews and critiques other agent outputs.
    
    This is a CRITICAL safety layer that:
    - Reviews content for dangerous advice
    - Detects PII leaks
    - Ensures medical disclaimers are present
    - Validates response quality
    - Provides retry feedback
    
    Usage:
        reviewer = SafetyReviewerAgent()
        review = await reviewer.review_response(
            original_question,
            ai_response,
            context={'intent': 'interaction_check'}
        )
        if not review.is_safe:
            # Regenerate with feedback
    """
    
    name = "safety_reviewer"
    description = "Reviews AI outputs for safety and quality"
    
    # Required disclaimers by intent
    REQUIRED_DISCLAIMERS = {
        'medication_info': [
            'consult', 'doctor', 'healthcare', 'provider',
            'not medical advice', 'informational'
        ],
        'interaction_check': [
            'consult', 'doctor', 'pharmacist', 'healthcare',
            'not a substitute', 'professional advice'
        ],
        'dosage_question': [
            'consult', 'doctor', 'prescription', 'prescribed',
            'do not change', 'without consulting'
        ],
        'side_effects': [
            'consult', 'doctor', 'healthcare', 'severe',
            'seek medical', 'professional'
        ]
    }
    
    # Quality thresholds
    MIN_LENGTH_BY_INTENT = {
        'medication_info': 100,
        'interaction_check': 150,
        'dosage_question': 100,
        'side_effects': 120,
        'emergency': 50,
        'general_chat': 20
    }
    
    def __init__(self, strict_mode: bool = True, **kwargs):
        """
        Args:
            strict_mode: If True, enforces stricter safety standards
            **kwargs: Passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.strict_mode = strict_mode
        self.review_count = 0
        self.block_count = 0
    
    async def review_response(
        self,
        original_question: str,
        ai_response: str,
        context: Optional[Dict] = None
    ) -> SafetyReviewResult:
        """
        Review an AI-generated response for safety issues.
        
        Args:
            original_question: The user's original question
            ai_response: The AI-generated response
            context: Additional context (intent, user_meds, etc.)
            
        Returns:
            SafetyReviewResult with assessment and recommendations
        """
        self.review_count += 1
        context = context or {}
        intent = context.get('intent', 'general')
        
        issues = []
        recommendations = []
        
        # Check 1: Content Filter
        filter_result = self.content_filter.check_response(ai_response, context)
        if not filter_result.is_safe:
            issues.append({
                'type': 'dangerous_content',
                'categories': filter_result.blocked_categories,
                'severity': 'critical'
            })
            recommendations.append("RESPONSE BLOCKED: Contains dangerous medical advice")
            recommendations.append("Action: Return safe fallback response")
            
            self.block_count += 1
            
            return SafetyReviewResult(
                is_safe=False,
                issues=issues,
                recommendations=recommendations,
                severity="critical"
            )
        
        # Check 2: PII Leak Detection
        pii_result = self.pii_detector.detect(ai_response)
        if pii_result.contains_phi:
            issues.append({
                'type': 'pii_leak',
                'phi_types': pii_result.phi_types,
                'severity': 'high'
            })
            recommendations.append("PII detected in response - redact before sending")
        
        # Check 3: Medical Disclaimer Check
        disclaimer_check = self._check_medical_disclaimer(ai_response, intent)
        if not disclaimer_check['has_disclaimer']:
            if intent in self.REQUIRED_DISCLAIMERS:
                issues.append({
                    'type': 'missing_disclaimer',
                    'severity': 'high' if self.strict_mode else 'medium'
                })
                recommendations.append(f"Add medical disclaimer for {intent} responses")
        
        # Check 4: Response Quality
        quality_check = self._check_response_quality(ai_response, intent)
        if quality_check['issues']:
            issues.extend(quality_check['issues'])
            recommendations.extend(quality_check['recommendations'])
        
        # Check 5: Consistency with Question
        consistency_check = self._check_consistency(
            original_question, ai_response, intent
        )
        if not consistency_check['is_consistent']:
            issues.append({
                'type': 'inconsistent_response',
                'severity': 'medium'
            })
            recommendations.append(consistency_check['recommendation'])
        
        # Determine overall safety
        critical_issues = [i for i in issues if i.get('severity') == 'critical']
        high_issues = [i for i in issues if i.get('severity') == 'high']
        
        is_safe = len(critical_issues) == 0
        if self.strict_mode and high_issues:
            is_safe = False
        
        severity = "info"
        if critical_issues:
            severity = "critical"
        elif high_issues:
            severity = "high"
        elif issues:
            severity = "medium"
        
        return SafetyReviewResult(
            is_safe=is_safe,
            issues=issues,
            recommendations=recommendations,
            severity=severity
        )
    
    async def _process(self, input_data: AgentInput) -> AgentOutput:
        """
        Main agent interface - processes review requests.
        Input query should contain the response to review.
        """
        # Parse input - expects JSON with response and context
        try:
            import json
            review_request = json.loads(input_data.query)
            
            response_to_review = review_request.get('response', '')
            original_question = review_request.get('original_question', '')
            context = review_request.get('context', {})
            
            review = await self.review_response(
                original_question,
                response_to_review,
                context
            )
            
            return AgentOutput(
                success=True,
                response=json.dumps({
                    'is_safe': review.is_safe,
                    'issues': review.issues,
                    'recommendations': review.recommendations,
                    'severity': review.severity
                }),
                metadata={
                    'is_safe': review.is_safe,
                    'issue_count': len(review.issues),
                    'severity': review.severity,
                    'intent': 'safety_review'
                },
                safety_flags=[
                    SafetyFlag(
                        level=review.severity if review.severity in ['info', 'warning', 'critical', 'emergency'] else 'warning',
                        category='other',
                        message=f"Safety review found {len(review.issues)} issues",
                        action_required=not review.is_safe
                    )
                ] if review.issues else [],
                confidence=1.0 if review.is_safe else 0.5
            )
            
        except Exception as e:
            return AgentOutput(
                success=False,
                response=f"Review failed: {str(e)}",
                metadata={'error': str(e), 'intent': 'safety_review'}
            )
    
    def _check_medical_disclaimer(self, response: str, intent: str) -> Dict:
        """Check if response has appropriate medical disclaimer"""
        response_lower = response.lower()
        
        # General disclaimer phrases
        disclaimer_phrases = [
            'consult your doctor',
            'consult your healthcare provider',
            'consult your physician',
            'talk to your doctor',
            'speak with your doctor',
            'contact your doctor',
            'not medical advice',
            'not a substitute for professional',
            'informational purposes only'
        ]
        
        has_general = any(phrase in response_lower for phrase in disclaimer_phrases)
        
        # Intent-specific checks
        if intent in self.REQUIRED_DISCLAIMERS:
            required = self.REQUIRED_DISCLAIMERS[intent]
            has_specific = any(phrase in response_lower for phrase in required)
        else:
            has_specific = True  # No specific requirements
        
        return {
            'has_disclaimer': has_general or has_specific,
            'has_general': has_general,
            'has_specific': has_specific
        }
    
    def _check_response_quality(self, response: str, intent: str) -> Dict:
        """Check response quality metrics"""
        issues = []
        recommendations = []
        
        # Length check
        min_length = self.MIN_LENGTH_BY_INTENT.get(intent, 50)
        if len(response) < min_length:
            issues.append({
                'type': 'too_short',
                'severity': 'medium',
                'details': f'Response is {len(response)} chars, minimum {min_length}'
            })
            recommendations.append(f"Expand response to at least {min_length} characters")
        
        # Structure check
        if intent in ['interaction_check', 'side_effects']:
            if '**' not in response and '*' not in response:
                issues.append({
                    'type': 'poor_formatting',
                    'severity': 'low',
                    'details': 'Response lacks formatting for readability'
                })
                recommendations.append("Add markdown formatting (bold, bullets) for readability")
        
        # Redundancy check
        if response.count('.') < 2 and len(response) > 100:
            issues.append({
                'type': 'run_on_sentence',
                'severity': 'low',
                'details': 'Response may be difficult to read'
            })
            recommendations.append("Break into shorter sentences")
        
        return {'issues': issues, 'recommendations': recommendations}
    
    def _check_consistency(
        self,
        question: str,
        response: str,
        intent: str
    ) -> Dict:
        """Check if response is consistent with question"""
        question_lower = question.lower()
        response_lower = response.lower()
        
        # Check if response addresses the question
        # Extract key terms from question
        question_words = set(question_lower.split())
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                     'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                     'through', 'during', 'before', 'after', 'above', 'below',
                     'between', 'under', 'and', 'but', 'or', 'yet', 'so'}
        
        key_terms = question_words - stop_words
        
        # Check if key terms appear in response
        if key_terms:
            matches = sum(1 for term in key_terms if term in response_lower)
            match_ratio = matches / len(key_terms)
            
            if match_ratio < 0.3:
                return {
                    'is_consistent': False,
                    'recommendation': 'Response may not address the specific question asked'
                }
        
        return {'is_consistent': True, 'recommendation': ''}
    
    def get_stats(self) -> Dict:
        """Get reviewer statistics"""
        base_stats = super().get_stats()
        base_stats.update({
            'reviews_conducted': self.review_count,
            'responses_blocked': self.block_count,
            'block_rate': self.block_count / max(self.review_count, 1),
            'strict_mode': self.strict_mode
        })
        return base_stats
