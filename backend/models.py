"""
MedTracker - Database Models
Enhanced version with comprehensive medication details

WHY THESE FIELDS MATTER IN HEALTH-TECH:
---------------------------------------
1. form_type: Different forms (tablet vs liquid) have different administration methods
2. strength + strength_unit: Critical for dosage accuracy - wrong unit = potential harm
3. method_of_intake: Affects absorption rate and patient safety
4. when_to_take: Drug-food interactions can affect efficacy (e.g., take with food)
5. taken_for: Helps identify drug-condition interactions
6. rxcui: RxNorm's unique ID - enables interoperability with other healthcare systems
"""

from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Boolean, DateTime, Float
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime, timezone


class Medication(Base):
    """
    Enhanced Medication Model
    
    HEALTH-TECH PRIVACY NOTE:
    All data stored locally in SQLite. No cloud sync by default.
    For HIPAA compliance in production, you'd add:
    - Encryption at rest
    - Audit logging for all access
    - Role-based access control
    """
    __tablename__ = "medications"

    # === Core Identity Fields ===
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)  # Drug name (autocompleted from RxNorm)
    rxcui = Column(String, nullable=True)  # RxNorm Concept Unique Identifier
    
    # === Form & Strength (New!) ===
    # Example: "Tablet", "Capsule", "Liquid", "Injection", "Cream", "Patch"
    form_type = Column(String, nullable=True, default="Tablet")
    
    # Strength split into value + unit for better data handling
    # Example: strength=50, strength_unit="mg" -> "50 mg"
    strength = Column(Float, nullable=True)  # The numeric value (50, 100, 500, etc.)
    strength_unit = Column(String, nullable=True, default="mg")  # mg, mcg, ml, IU, etc.
    
    # Method of intake: How the medication enters the body
    # Example: "Orally", "Injection", "Topical", "Inhaled", "Sublingual"
    method_of_intake = Column(String, nullable=True, default="Orally")
    
    # === Dosage Details (Enhanced!) ===
    # Keep original 'dosage' for backward compatibility, but add structured fields
    dosage = Column(String, nullable=False)  # Original field: "500mg" or "2 tablets"
    
    # Quantity per dose: How many pills/ml to take each time
    quantity = Column(Float, nullable=True, default=1.0)  # e.g., 1, 2, 0.5
    quantity_unit = Column(String, nullable=True, default="tablet(s)")  # tablets, ml, puffs
    
    # When to take relative to food
    # Example: "Before Food", "After Food", "With Food", "Empty Stomach", "Any Time"
    when_to_take = Column(String, nullable=True, default="Any Time")
    
    # === Scheduling ===
    frequency = Column(String, nullable=False)  # "Once daily", "Twice daily", etc.
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Nullable if ongoing
    is_long_term = Column(Boolean, default=False)  # Checkbox for chronic medications
    
    # === Status & Notes ===
    is_active = Column(Boolean, default=True)
    notes = Column(String, nullable=True)  # Free-form instructions
    taken_for = Column(String, nullable=True)  # What condition this medication treats

    # === Pill Identification ===
    pill_shape = Column(String, nullable=True)  # oval, round, capsule, rectangle, diamond
    pill_color = Column(String, nullable=True)  # white, yellow, pink, blue, orange, red, green, purple, brown, gray
    pill_size  = Column(String, nullable=True)  # small, medium, large

    # === Ownership ===
    # Nullable during development (no Alembic yet). Will become NOT NULL after T-009.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # === Relationships ===
    reminders = relationship("Reminder", back_populates="medication", cascade="all, delete-orphan")
    logs = relationship("MedicationLog", back_populates="medication")
    
    def get_full_dosage_string(self):
        """
        Helper method to generate human-readable dosage string
        Example output: "50 mg Tablet - Take 1 tablet(s) Orally, Before Food"
        """
        parts = []
        
        if self.strength and self.strength_unit:
            parts.append(f"{self.strength} {self.strength_unit}")
        
        if self.form_type:
            parts.append(self.form_type)
        
        if self.quantity and self.quantity_unit:
            parts.append(f"- Take {self.quantity} {self.quantity_unit}")
        
        if self.method_of_intake:
            parts.append(self.method_of_intake)
        
        if self.when_to_take and self.when_to_take != "Any Time":
            parts.append(f", {self.when_to_take}")
        
        return " ".join(parts) if parts else self.dosage


class MedicationLog(Base):
    """
    Log of when medication was taken or missed
    
    HEALTH-TECH TIP: 
    This data is GOLD for adherence analytics. 
    Patterns here can predict hospital readmissions!
    """
    __tablename__ = "medication_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    taken_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    was_taken = Column(Boolean, default=True)  # True if taken, False if missed
    notes = Column(String, nullable=True)
    
    # Optional: Track which reminder triggered this log
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=True)
    
    medication = relationship("Medication", back_populates="logs")


class Reminder(Base):
    """
    Scheduled reminders for medications
    """
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    reminder_time = Column(Time, nullable=False)  # Time of day for the reminder
    is_sent = Column(Boolean, default=False)  # Whether a push notification was sent today (reset at midnight)
    is_active = Column(Boolean, default=True)  # Can disable without deleting

    medication = relationship("Medication", back_populates="reminders")


class User(Base):
    """
    Application user account.
    Medications, logs, and reminders will be scoped to a user once T-004 is complete.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PushSubscription(Base):
    """
    Browser Web Push subscription objects.
    One row per browser/device that has opted in to push notifications.
    Endpoint is unique — re-subscribing the same browser updates the existing row.
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, unique=True, nullable=False, index=True)
    p256dh_key = Column(String, nullable=False)   # Browser's public key
    auth_key = Column(String, nullable=False)      # Auth secret
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc))
    is_active = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
