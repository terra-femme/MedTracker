"""
Guardrails Module - Safety First!
=================================
Provides safety controls for all AI operations:
- Schema validation (enforce structured outputs)
- PII detection (HIPAA compliance)
- Content filtering (block dangerous advice)
- Input/output validators
"""

from .schemas import (
    MedicationRecommendation,
    InteractionSeverity,
    InteractionCheckResult,
    SafetyFlag,
    IntentClassification,
)
from .pii_detector import PIIDetector, PHIDetectionResult
from .content_filter import MedicalContentFilter, ContentFilterResult
from .validators import ResponseValidator, ValidationResult

__all__ = [
    # Schemas
    'MedicationRecommendation',
    'InteractionSeverity',
    'InteractionCheckResult',
    'SafetyFlag',
    'IntentClassification',
    # PII
    'PIIDetector',
    'PHIDetectionResult',
    # Content
    'MedicalContentFilter',
    'ContentFilterResult',
    # Validators
    'ResponseValidator',
    'ValidationResult',
]
