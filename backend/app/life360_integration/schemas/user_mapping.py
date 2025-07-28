from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class UserMappingBase(BaseModel):
    """Base schema for user-member mapping"""
    user_id: UUID
    life360_member_id: str
    life360_member_name: Optional[str] = None
    is_active: bool = True

class UserMappingCreate(UserMappingBase):
    """Schema for creating user-member mapping"""
    pass

class UserMappingUpdate(BaseModel):
    """Schema for updating user-member mapping"""
    life360_member_name: Optional[str] = None
    is_active: Optional[bool] = None

class UserMappingResponse(UserMappingBase):
    """Schema for API responses"""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True