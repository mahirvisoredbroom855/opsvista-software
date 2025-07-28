from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from decimal import Decimal

class LocationBase(BaseModel):
    """Base schema for location data"""
    circle_id: str
    member_id: str  # Life360's member ID
    member_name: Optional[str] = None
    user_id: Optional[UUID] = None  # Link to auth.users table
    
    # GPS coordinates
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    accuracy: Optional[int] = Field(None, ge=0)
    
    # Location context
    place_name: Optional[str] = None
    address: Optional[str] = None
    
    # Movement data
    speed: Optional[Decimal] = Field(None, ge=0)
    is_driving: Optional[bool] = None
    battery_level: Optional[int] = Field(None, ge=0, le=100)
    
    # When the location was recorded (from Life360)
    timestamp: Optional[datetime] = None

class LocationCreate(LocationBase):
    """Schema for creating new location records"""
    raw_data: Optional[Dict[str, Any]] = None

class LocationResponse(LocationBase):
    """Schema for API responses with full location data"""
    id: UUID  # Our internal UUID
    ingestion_time: datetime  # When we stored the data
    processing_status: str = 'pending'
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class LocationUpdate(BaseModel):
    """Schema for updating location processing status"""
    processing_status: Optional[str] = None
    error_message: Optional[str] = None
    user_id: Optional[UUID] = None  # For linking to users