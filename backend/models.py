from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .database import Base  # Changed: added dot before database
from datetime import datetime

class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    dosage = Column(String, nullable=False)
    frequency = Column(String, nullable=False)  # e.g., "Once a day", "Twice a day"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Nullable if ongoing
    is_active = Column(Boolean, default=True)
    notes = Column(String, nullable=True)

    reminders = relationship("Reminder", back_populates="medication", cascade="all, delete-orphan")
    logs = relationship("MedicationLog", back_populates="medication", cascade="all, delete-orphan")

class MedicationLog(Base):
    __tablename__ = "medication_logs"
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    taken_at = Column(DateTime, default=datetime.utcnow)
    was_taken = Column(Boolean, default=True)  # True if taken, False if missed
    notes = Column(String, nullable=True)
    medication = relationship("Medication", back_populates="logs")

class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    reminder_time = Column(Time, nullable=False)  # Time of day for the reminder
    is_sent = Column(Boolean, default=False)  # Whether the reminder has been sent
    medication = relationship("Medication", back_populates="reminders")