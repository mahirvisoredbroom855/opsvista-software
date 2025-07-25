from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.supbase_client import Base
import uuid

class RawLocationFeed(Base):
    __tablename__ = "raw_location_feed"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Life360 system identifiers (keep these - needed for API calls)
    circle_id = Column(String, nullable=False)  
    member_id = Column(String, nullable=False)    # Life360's member ID
    member_name = Column(String)                  # "John Smith" from Life360
    
    # Link to YOUR user system (optional but powerful)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # GPS coordinates
    latitude = Column(Numeric(9, 6))
    longitude = Column(Numeric(9, 6))
    accuracy = Column(Integer)
    
    # Location context
    place_name = Column(String)
    address = Column(String)
    
    # Movement data
    speed = Column(Numeric(5, 2))
    is_driving = Column(Boolean)
    battery_level = Column(Integer)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True))
    ingestion_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # Raw data and processing
    raw_data = Column(JSONB)
    processing_status = Column(String, default='pending')
    error_message = Column(Text)
    
    # SQLAlchemy relationship (optional - makes queries easier)
    user = relationship("User", back_populates="location_data")