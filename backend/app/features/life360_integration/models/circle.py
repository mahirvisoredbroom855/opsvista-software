from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class Life360Circle(Base):
    __tablename__ = "life360_circles"
    
    # Primary key - our internal ID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Life360's circle ID (from their API)
    circle_id = Column(String, unique=True, nullable=False)
    
    # Human-readable name
    circle_name = Column(String, nullable=False)
    
    # Enable/disable tracking
    is_active = Column(Boolean, default=True)
    
    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())