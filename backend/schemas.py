from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class MedicationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, example="Aspirin")
    dosage: str = Field(..., example="100mg")
    frequency: str = Field(..., example="Once a day(AM)")
    start_date: datetime = Field(..., example="2023-01-01")
    end_date: Optional[datetime] = Field(None, example="2023-12-31")
    is_active: bool = Field(True, example=True)
    notes: Optional[str] = Field(None, example="Take with food")

class MedicationCreate(MedicationBase):
    pass

class MedicationUpdate(MedicationBase):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class Medication(MedicationBase):
    id: int
    start_date: datetime
    end_date: Optional[datetime]
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True # replaces orm_mode = True in Pydantic v2


