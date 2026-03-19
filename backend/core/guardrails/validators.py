"""
Response Validators - Output Quality
====================================
Validates AI outputs against quality and safety standards.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ValidationError
import json


class ValidationResult(BaseModel):
    """Result of validation check"""
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="Non-critical issues")
    corrected_output: Optional[str] = Field(None, description="Suggested correction if applicable")


class ResponseValidator:
    """
    Validates AI responses for quality and safety.
    
    Checks:
    - Response is not empty
    - Response is not too short (likely an error)
    - Response contains required elements
    - Response doesn't contain forbidden patterns
    - JSON responses are valid (if applicable)
    """
    
    # Minimum response lengths by intent
    MIN_LENGTHS: Dict[str, int] = {
        'medication_info': 50,
        'interaction_check': 80,
        'dosage_question': 60,
        'side_effects': 70,
        'emergency': 20,  # Can be short for emergency
        'general_chat': 10
    }
    
    # Required phrases by intent (safety-critical)
    REQUIRED_PHRASES: Dict[str, List[str]] = {
        'interaction_check': [
            'doctor', 'pharmacist', 'healthcare', 'consult'
        ],
        'side_effects': [
            'side effects', 'may', 'common'
        ],
        'medication_info': [
            'medication', 'medicine', 'drug'
        ]
    }
    
    # Forbidden patterns (red flags)
    FORBIDDEN_PATTERNS: List[str] = [
        'i am an ai',  # AI shouldn't remind user unnecessarily
        'as an ai', 
        'language model',
        'training data',
        'i cannot help with that',  # Without explanation
    ]
    
    def __init__(self):
        self.validation_count = 0
        self.failure_count = 0
        self.failure_reasons: Dict[str, int] = {}
    
    def validate_response(
        self,
        response: str,
        intent: str = 'general',
        expected_schema: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate an AI response.
        
        Args:
            response: The AI-generated response
            intent: Classification of the original query
            expected_schema: Optional Pydantic model to validate against
            
        Returns:
            ValidationResult with pass/fail status and any issues
        """
        self.validation_count += 1
        errors = []
        warnings = []
        
        # Check 1: Not empty
        if not response or not response.strip():
            errors.append("Response is empty")
            self._record_failure("empty_response")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        response_stripped = response.strip()
        
        # Check 2: Minimum length
        min_length = self.MIN_LENGTHS.get(intent, 20)
        if len(response_stripped) < min_length:
            errors.append(f"Response too short ({len(response_stripped)} chars, min {min_length})")
            self._record_failure("too_short")
        
        # Check 3: Required phrases for intent
        if intent in self.REQUIRED_PHRASES:
            response_lower = response_stripped.lower()
            required = self.REQUIRED_PHRASES[intent]
            missing = [p for p in required if p not in response_lower]
            
            if missing:
                # This is a warning, not error, for some intents
                if intent == 'interaction_check':
                    errors.append(f"Missing required safety phrases: {missing}")
                    self._record_failure("missing_phrases")
                else:
                    warnings.append(f"Missing recommended phrases: {missing}")
        
        # Check 4: Forbidden patterns
        response_lower = response_stripped.lower()
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in response_lower:
                warnings.append(f"Contains forbidden pattern: '{pattern}'")
        
        # Check 5: Schema validation (if provided)
        if expected_schema:
            try:
                # Try to parse as JSON and validate
                if isinstance(response_stripped, str):
                    try:
                        data = json.loads(response_stripped)
                    except json.JSONDecodeError:
                        errors.append("Response is not valid JSON as expected")
                        self._record_failure("invalid_json")
                        data = None
                    
                    if data:
                        expected_schema(**data)
            except ValidationError as e:
                errors.append(f"Schema validation failed: {e}")
                self._record_failure("schema_validation")
        
        # Check 6: Medical disclaimer check (for non-emergency medical content)
        if intent in ['medication_info', 'interaction_check', 'dosage_question', 'side_effects']:
            disclaimer_phrases = [
                'consult', 'doctor', 'physician', 'healthcare provider',
                'pharmacist', 'medical professional', 'not medical advice',
                'healthcare'
            ]
            has_disclaimer = any(p in response_lower for p in disclaimer_phrases)
            
            if not has_disclaimer:
                errors.append("Missing medical disclaimer - must mention consulting healthcare provider")
                self._record_failure("missing_disclaimer")
        
        is_valid = len(errors) == 0
        if not is_valid:
            self.failure_count += 1
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def validate_json_response(
        self,
        response: str,
        schema_model: Any
    ) -> ValidationResult:
        """
        Validate that a response is valid JSON matching a schema.
        
        Args:
            response: JSON string to validate
            schema_model: Pydantic model class
            
        Returns:
            ValidationResult
        """
        errors = []
        
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Invalid JSON: {e}"],
                warnings=[]
            )
        
        try:
            validated = schema_model(**data)
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                corrected_output=validated.model_dump_json()
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Schema validation failed: {e}"],
                warnings=[]
            )
    
    def _record_failure(self, reason: str):
        """Track failure reason"""
        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1
    
    def get_stats(self) -> Dict:
        """Get validation statistics"""
        return {
            'total_validated': self.validation_count,
            'failed': self.failure_count,
            'pass_rate': (self.validation_count - self.failure_count) / max(self.validation_count, 1),
            'failure_breakdown': self.failure_reasons
        }


# Singleton instance
_validator = None

def get_validator() -> ResponseValidator:
    """Get singleton validator"""
    global _validator
    if _validator is None:
        _validator = ResponseValidator()
    return _validator
