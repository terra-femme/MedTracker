"""
MedTracker - Pydantic Schemas (Data Validation)
Enhanced version with comprehensive medication details

WHAT ARE SCHEMAS?
-----------------
Think of schemas as "gatekeepers" - they check that data coming into your API 
is valid before it touches your database. If someone sends "abc" for a number 
field, the schema catches it.

HEALTH-TECH IMPORTANCE:
Invalid data in healthcare can be dangerous. A schema that validates 
"strength must be a positive number" prevents accidents like negative dosages.
"""

import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import List, Optional


# =============================================================================
# MEDICATION SCHEMAS
# =============================================================================

class MedicationBase(BaseModel):
    """
    Base schema with all medication fields
    Used for both creating and reading medications
    """
    # Core identity
    name: str = Field(..., min_length=1, max_length=200, example="Aspirin")
    rxcui: Optional[str] = Field(None, max_length=20, example="1191")  # RxNorm ID

    # Form & Strength
    form_type: Optional[str] = Field("Tablet", max_length=50, example="Tablet")
    strength: Optional[float] = Field(None, example=500, ge=0)  # ge=0 means >= 0
    strength_unit: Optional[str] = Field("mg", max_length=20, example="mg")
    method_of_intake: Optional[str] = Field("Orally", max_length=50, example="Orally")

    # Dosage (keep original for backward compatibility)
    dosage: str = Field(..., max_length=200, example="500mg")
    quantity: Optional[float] = Field(1.0, example=1.0, ge=0)
    quantity_unit: Optional[str] = Field("tablet(s)", max_length=50, example="tablet(s)")
    when_to_take: Optional[str] = Field("Any Time", max_length=50, example="Before Food")

    # Scheduling
    frequency: str = Field(..., max_length=100, example="Once daily")
    start_date: date = Field(..., example="2024-01-01")
    end_date: Optional[date] = Field(None, example="2024-12-31")
    is_long_term: Optional[bool] = Field(False, example=False)

    # Status & Notes
    is_active: bool = Field(True, example=True)
    notes: Optional[str] = Field(None, max_length=1000, example="Take with food")
    taken_for: Optional[str] = Field(None, max_length=200, example="High Blood Pressure")

    # Pill appearance (for visual identification on card)
    pill_shape: Optional[str] = Field(None, max_length=20, example="oval")
    pill_color: Optional[str] = Field(None, max_length=20, example="white")
    pill_size:  Optional[str] = Field(None, max_length=20, example="medium")

    @field_validator('form_type')
    @classmethod
    def validate_form_type(cls, v):
        """Validate form type is one of the allowed values"""
        allowed = [
            "Tablet", "Capsule", "Liquid", "Syrup", "Injection", 
            "Cream", "Ointment", "Gel", "Patch", "Drops", 
            "Inhaler", "Spray", "Powder", "Suppository", "Other"
        ]
        if v and v not in allowed:
            # Be lenient - just capitalize and accept
            v = v.capitalize()
        return v
    
    @field_validator('method_of_intake')
    @classmethod
    def validate_method(cls, v):
        """Validate intake method"""
        allowed = [
            "Orally", "Injection", "Topical", "Inhaled", 
            "Sublingual", "Rectal", "Nasal", "Ocular", "Otic", "Other"
        ]
        if v and v not in allowed:
            v = v.capitalize()
        return v
    
    @field_validator('when_to_take')
    @classmethod
    def validate_when(cls, v):
        """Validate timing relative to food"""
        allowed = [
            "Before Food", "After Food", "With Food",
            "Empty Stomach", "Any Time", "At Bedtime"
        ]
        if v and v not in allowed:
            v = "Any Time"
        return v

    @field_validator('notes', 'taken_for', mode='before')
    @classmethod
    def strip_html(cls, v):
        """Strip HTML tags from free-text fields to prevent XSS."""
        if v is None:
            return v
        return re.sub(r'<[^>]+>', '', str(v)).strip()


class MedicationCreate(MedicationBase):
    """
    Schema for creating a new medication
    Inherits all fields from MedicationBase
    """
    reminder_times: Optional[List[str]] = Field(None, example=["08:00", "20:00"])


class MedicationUpdate(BaseModel):
    """
    Schema for updating a medication
    All fields are optional since you might only update one field
    """
    name: Optional[str] = None
    rxcui: Optional[str] = None
    form_type: Optional[str] = None
    strength: Optional[float] = None
    strength_unit: Optional[str] = None
    method_of_intake: Optional[str] = None
    dosage: Optional[str] = None
    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    when_to_take: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_long_term: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    taken_for: Optional[str] = None
    pill_shape: Optional[str] = None
    pill_color: Optional[str] = None
    pill_size:  Optional[str] = None
    reminder_times: Optional[List[str]] = None  # For updating reminder times


class Medication(MedicationBase):
    """
    Schema for reading a medication (includes id)
    Used in API responses
    """
    id: int
    
    class Config:
        from_attributes = True  # Allows creating from SQLAlchemy model


# =============================================================================
# AUTOCOMPLETE SCHEMAS (NEW!)
# =============================================================================

class DrugSuggestion(BaseModel):
    """
    A single drug suggestion from RxNorm autocomplete
    """
    name: str = Field(..., example="Aspirin")
    rxcui: str = Field(..., example="1191")
    strength: Optional[str] = Field(None, example="325 mg")
    form: Optional[str] = Field(None, example="Tablet")


class AutocompleteResponse(BaseModel):
    """
    Response from medication autocomplete endpoint
    """
    query: str
    suggestions: List[DrugSuggestion]
    source: str = "RxNorm"


# =============================================================================
# OCR SCHEMAS (NEW!)
# =============================================================================

class OCRResult(BaseModel):
    """
    Result from OCR processing of medication image
    
    PRIVACY NOTE:
    The image itself is NEVER stored - only the extracted text/data is returned.
    """
    detected_name: Optional[str] = None
    detected_strength: Optional[str] = None
    detected_form: Optional[str] = None
    detected_instructions: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)  # 0-1 confidence score
    raw_text: Optional[str] = None  # Full OCR text for debugging
    
    class Config:
        json_schema_extra = {
            "example": {
                "detected_name": "Lisinopril",
                "detected_strength": "10 mg",
                "detected_form": "Tablet",
                "detected_instructions": "Take once daily",
                "confidence": 0.85,
                "raw_text": "LISINOPRIL 10MG TABLETS Take once daily with water"
            }
        }


# =============================================================================
# REMINDER SCHEMAS
# =============================================================================

class ReminderCreate(BaseModel):
    """Schema for creating a reminder"""
    medication_id: int
    reminder_time: str = Field(..., example="08:00:00")


class Reminder(BaseModel):
    """Schema for reading a reminder"""
    id: int
    medication_id: int
    reminder_time: str
    is_sent: bool
    is_active: bool = True
    
    class Config:
        from_attributes = True


# =============================================================================
# LOG SCHEMAS
# =============================================================================

class LogCreate(BaseModel):
    """Schema for creating a medication log"""
    medication_id: int
    was_taken: bool = True
    timestamp: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    taken_for: Optional[str] = Field(None, max_length=200)

    @field_validator('notes', 'taken_for', mode='before')
    @classmethod
    def strip_html(cls, v):
        """Strip HTML tags from free-text fields to prevent XSS."""
        if v is None:
            return v
        return re.sub(r'<[^>]+>', '', str(v)).strip()


class Log(BaseModel):
    """Schema for reading a medication log"""
    id: int
    medication_id: int
    taken_at: datetime
    was_taken: bool
    notes: Optional[str]
    taken_for: Optional[str]

    class Config:
        from_attributes = True


# =============================================================================
# PUSH NOTIFICATION SCHEMAS
# =============================================================================

# =============================================================================
# AUTH SCHEMAS
# =============================================================================

class UserCreate(BaseModel):
    """Schema for registering a new user account."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    password: str = Field(..., min_length=8, max_length=100)


class Token(BaseModel):
    """JWT token response returned on successful login."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Data encoded inside the JWT payload."""
    username: Optional[str] = None


# =============================================================================
# PUSH NOTIFICATION SCHEMAS
# =============================================================================

class PushSubscriptionKeys(BaseModel):
    """Browser-provided ECDH keys from PushSubscription.toJSON()"""
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    """Schema for storing a browser push subscription"""
    endpoint: str = Field(..., min_length=10, description="Push service endpoint URL")
    keys: PushSubscriptionKeys
