from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class CircleBase(BaseModel):
    """Base schema for Life360 Circle data"""
    circle_id: str  # Life360's circle ID
    circle_name: str  # Human-readable name like "Smith Family"
    is_active: bool = True

class CircleCreate(CircleBase):
    """Schema for creating a new circle configuration"""
    pass

class CircleUpdate(BaseModel):
    """Schema for updating circle configuration"""
    circle_name: Optional[str] = None
    is_active: Optional[bool] = None

class CircleResponse(CircleBase):
    """Schema for API responses with full circle data"""
    id: UUID  # Our internal UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True