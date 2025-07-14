from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Hotlist(Base):
    __tablename__ = "hotlists"
    
    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String(20), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # e.g., "stolen", "wanted", "bolo"
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Additional fields for more context
    vehicle_make = Column(String(50), nullable=True)
    vehicle_model = Column(String(50), nullable=True)
    vehicle_color = Column(String(30), nullable=True)
    vehicle_year = Column(Integer, nullable=True)
    owner_name = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationship to ANPR reads
    anpr_reads = relationship("ANPRRead", back_populates="hotlist")

class ANPRRead(Base):
    __tablename__ = "anpr_reads"
    
    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String(20), index=True, nullable=False)
    camera_id = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Integer, default=0)  # 0-100
    
    # Image data (optional)
    image_path = Column(String(500), nullable=True)
    plate_image_path = Column(String(500), nullable=True)  # Path to plate crop image
    context_image_path = Column(String(500), nullable=True)  # Path to context image
    
    # Hotlist matching
    hotlist_match = Column(Boolean, default=False)
    hotlist_id = Column(Integer, ForeignKey("hotlists.id"), nullable=True)
    
    # Additional metadata
    direction = Column(String(20), nullable=True)  # "north", "south", "east", "west"
    speed = Column(Integer, nullable=True)  # if available from camera
    lane = Column(Integer, nullable=True)
    
    # Relationship to hotlist
    hotlist = relationship("Hotlist", back_populates="anpr_reads")

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)  # camera_id, api, system, etc.
    user_id = Column(String(100), nullable=True) 