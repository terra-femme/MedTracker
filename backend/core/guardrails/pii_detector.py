"""
PII Detector - HIPAA Compliance
===============================
Detects and redacts Protected Health Information (PHI).
Health-Tech Critical: Never log PHI!
"""

import re
from typing import List, Dict, Set
from pydantic import BaseModel, Field


class PHIDetectionResult(BaseModel):
    """Result of PHI detection"""
    contains_phi: bool = Field(..., description="Whether PHI was detected")
    phi_types: List[str] = Field(default_factory=list, description="Types of PHI found")
    redacted_text: str = Field(..., description="Text with PHI redacted")
    original_preview: str = Field(..., description="First 50 chars of original (for debugging)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")


class PIIDetector:
    """
    HIPAA-compliant PHI detector.
    
    Detects:
    - SSNs
    - Phone numbers
    - Email addresses
    - Medical record numbers
    - Credit card numbers
    - Dates of birth (common formats)
    """
    
    # Regex patterns for common PHI
    PATTERNS: Dict[str, str] = {
        'ssn': r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
        'phone': r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'mrn': r'\b(MRN|mrn|Medical Record|Account|Acct)[:\s#]*\d{6,10}\b',
        'credit_card': r'\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b',
        'dob_slash': r'\b\d{1,2}[/-]\d{1,2}[/-](19|20)?\d{2}\b',
        'dob_written': r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s,]+\d{1,2}[a-z]{0,2}[\s,]+(19|20)?\d{2}\b',
    }
    
    # Keywords that suggest medical context (increases confidence)
    MEDICAL_CONTEXT: Set[str] = {
        'patient', 'doctor', 'hospital', 'clinic', 'medical', 'health',
        'prescription', 'diagnosis', 'treatment', 'medication', 'drug',
        'allergy', 'symptom', 'condition', 'disease', 'surgery'
    }
    
    def __init__(self):
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }
    
    def detect(self, text: str) -> PHIDetectionResult:
        """
        Detect PHI in text and return redacted version.
        
        Args:
            text: Text to scan for PHI
            
        Returns:
            PHIDetectionResult with detection details and redacted text
        """
        if not text:
            return PHIDetectionResult(
                contains_phi=False,
                phi_types=[],
                redacted_text="",
                original_preview="",
                confidence=0.0
            )
        
        found_types: List[str] = []
        redacted = text
        
        # Check each pattern
        for phi_type, pattern in self._compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                found_types.append(phi_type)
                # Replace with redaction marker
                redacted = pattern.sub(f'[REDACTED-{phi_type.upper()}]', redacted)
        
        # Calculate confidence based on medical context
        confidence = self._calculate_confidence(text, found_types)
        
        return PHIDetectionResult(
            contains_phi=len(found_types) > 0,
            phi_types=found_types,
            redacted_text=redacted,
            original_preview=text[:50] + "..." if len(text) > 50 else text,
            confidence=confidence
        )
    
    def contains_phi(self, text: str) -> bool:
        """Quick check if text contains any PHI"""
        return self.detect(text).contains_phi
    
    def sanitize_for_logging(self, text: str, max_length: int = 200) -> str:
        """
        Redact PHI and truncate for safe logging.
        ALWAYS use this before logging any user input!
        
        Args:
            text: Text to sanitize
            max_length: Maximum length for log entry
            
        Returns:
            Safe text suitable for logging
        """
        result = text
        # Aggressive redaction - replace ALL patterns with generic [REDACTED]
        for pattern in self._compiled_patterns.values():
            result = pattern.sub('[REDACTED]', result)
        
        # Truncate
        if len(result) > max_length:
            result = result[:max_length] + "..."
        
        return result
    
    def _calculate_confidence(self, text: str, found_types: List[str]) -> float:
        """Calculate confidence score based on findings and context"""
        if not found_types:
            return 0.0
        
        # Base confidence from number of PHI types found
        base_confidence = min(0.3 + (len(found_types) * 0.2), 0.8)
        
        # Boost if medical context keywords present
        text_lower = text.lower()
        has_medical_context = any(keyword in text_lower for keyword in self.MEDICAL_CONTEXT)
        
        if has_medical_context:
            base_confidence = min(base_confidence + 0.15, 1.0)
        
        return base_confidence


# Singleton instance for reuse
_pii_detector = None

def get_pii_detector() -> PIIDetector:
    """Get singleton PII detector instance"""
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector


# Convenience functions
def detect_phi(text: str) -> PHIDetectionResult:
    """Quick function to detect PHI"""
    return get_pii_detector().detect(text)

def contains_phi(text: str) -> bool:
    """Quick check for PHI"""
    return get_pii_detector().contains_phi(text)

def sanitize_for_logs(text: str) -> str:
    """Sanitize text for logging"""
    return get_pii_detector().sanitize_for_logging(text)
