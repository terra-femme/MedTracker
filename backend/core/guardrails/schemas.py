"""
Pydantic Schemas for Guardrails
===============================
Strict schemas for validating AI inputs and outputs.
Health-Tech Rule: Never trust AI output - validate it!
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from enum import Enum


class InteractionSeverity(str, Enum):
    """Standardized severity levels for drug interactions"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CONTRAINDICATED = "contraindicated"


class SafetyFlag(BaseModel):
    """Standardized safety alert format"""
    level: Literal["info", "warning", "critical", "emergency"] = Field(
        ...,
        description="Severity level of the safety concern"
    )
    category: Literal["interaction", "allergy", "dosage", "duplicate", "pii", "content", "other"] = Field(
        ...,
        description="Category of safety issue"
    )
    message: str = Field(
        ...,
        min_length=5,
        description="Human-readable description of the issue"
    )
    action_required: bool = Field(
        default=False,
        description="Whether user action is required"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "level": "critical",
                "category": "interaction",
                "message": "Warfarin and ibuprofen increase bleeding risk",
                "action_required": True
            }
        }


class MedicationRecommendation(BaseModel):
    """Strict schema for AI medication recommendations"""
    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Medication name"
    )
    dosage: str = Field(
        ...,
        pattern=r'^\d+\s*(mg|mcg|g|ml|units|IU|mcg/hr)$',
        description="Dosage with unit (e.g., '10 mg', '500 mcg')"
    )
    frequency: Literal[
        "once_daily", "twice_daily", "three_times_daily",
        "every_morning", "every_night", "as_needed", 
        "weekly", "monthly", "as_directed"
    ] = Field(
        ...,
        description="How often to take the medication"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings for this medication"
    )
    
    @field_validator('name')
    @classmethod
    def validate_medication_name(cls, v: str) -> str:
        """Ensure medication name is not empty and has reasonable content"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Medication name must be at least 2 characters")
        # Block obviously fake names
        blocked_terms = ['fake', 'test', 'dummy', 'example']
        if any(term in v.lower() for term in blocked_terms):
            raise ValueError(f"Medication name contains blocked term")
        return v


class InteractionCheckResult(BaseModel):
    """Schema for drug interaction analysis results"""
    drug_a: str = Field(..., min_length=2)
    drug_b: str = Field(..., min_length=2)
    severity: InteractionSeverity
    mechanism: Optional[str] = Field(
        None,
        description="Mechanism of interaction"
    )
    recommendation: str = Field(
        ...,
        min_length=10,
        description="What the patient should do"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Sources of this interaction data"
    )
    
    @field_validator('recommendation')
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        """Ensure recommendation includes proper medical guidance"""
        v_lower = v.lower()
        # Must mention consulting healthcare provider for severe interactions
        if 'severe' in v_lower or 'contraindicated' in v_lower:
            if 'doctor' not in v_lower and 'provider' not in v_lower and 'pharmacist' not in v_lower:
                raise ValueError("Severe interaction recommendations must mention consulting healthcare provider")
        return v


class IntentClassification(BaseModel):
    """Schema for intent classification output"""
    intent: Literal[
        'medication_info',
        'interaction_check',
        'dosage_question',
        'side_effects',
        'emergency',
        'general_chat',
        'unknown'
    ] = Field(..., description="Classified intent")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0-1"
    )
    reasoning: str = Field(
        ...,
        min_length=5,
        description="Why this intent was chosen"
    )
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Flag low confidence classifications"""
        if v < 0.3:
            # Don't fail, but this is suspicious
            pass
        return v


class AgentHealthStatus(BaseModel):
    """Health check status for an agent"""
    agent_name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    last_check: str
    response_time_ms: float
    error_rate_24h: float
    details: Optional[dict] = None
