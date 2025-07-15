from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, BigInteger, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class HotlistGroup(Base):
    __tablename__ = "hotlist_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # e.g., "stolen", "wanted", "bolo"
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # BOF-specific fields for revision tracking
    revision = Column(BigInteger, default=1)  # Revision number for this hotlist group
    
    # Relationships
    vehicles = relationship("Hotlist", back_populates="hotlist_group")
    hotlist_revisions = relationship("HotlistRevision", back_populates="hotlist_group")

class Hotlist(Base):
    __tablename__ = "hotlists"
    
    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, index=True, nullable=False)  # VRM
    
    # Basic vehicle information
    vehicle_make = Column(String)
    vehicle_model = Column(String) 
    vehicle_color = Column(String)
    
    # Extended ANPR-compliant vehicle details
    vin_number = Column(String)  # Vehicle Identification Number
    engine_number = Column(String)
    engine_capacity = Column(Integer)  # Engine capacity in cc
    fuel_type = Column(String)  # Petrol, Diesel, Electric, Hybrid, etc.
    body_type = Column(String)  # Saloon, Hatchback, Estate, etc.
    
    # Registration information
    date_of_first_registration = Column(Date)
    date_of_first_uk_registration = Column(Date) 
    vehicle_manufactured_date = Column(Date)
    
    # ANPR-specific operational fields
    warning_markers = Column(String)  # Warning markers for the vehicle
    nim_code = Column(String)  # NIM (5x5x5) Code
    force_area = Column(String)  # Police force/area identifier
    weed_date = Column(Date)  # Date when record should be reviewed/removed
    pnc_id = Column(String)  # Police National Computer ID
    gpms_marking = Column(String, default="Unclassified")  # GPMS classification
    cad_information = Column(String)  # Command and Control information
    
    # Additional operational data
    theft_marker = Column(Boolean, default=False)  # Vehicle stolen marker
    scrap_marker = Column(Boolean, default=False)  # Vehicle scrapped marker
    export_marker = Column(Boolean, default=False)  # Vehicle exported marker
    
    # Extended description and intelligence
    intelligence_information = Column(Text)  # Additional intelligence
    operational_instructions = Column(Text)  # Specific operational instructions
    vehicle_features = Column(String)  # Distinctive features
    
    # Audit and tracking
    source_reference = Column(String)  # Source of the intelligence
    authorizing_officer = Column(String)  # Officer authorizing the entry
    review_date = Column(Date)  # Date for next review
    
    # Existing fields
    hotlist_group_id = Column(Integer, ForeignKey("hotlist_groups.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    revision = Column(BigInteger, default=1)
    
    # Relationship
    hotlist_group = relationship("HotlistGroup", back_populates="vehicles")
    anpr_reads = relationship("ANPRRead", back_populates="hotlist")

class ANPRRead(Base):
    __tablename__ = "anpr_reads"
    
    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String(20), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Integer, default=0)  # 0-100
    direction = Column(String(20), nullable=True)  # e.g., "North", "South"
    speed = Column(Integer, nullable=True)  # Speed in km/h
    lane = Column(Integer, nullable=True)  # Lane number
    
    # Image paths
    plate_image_path = Column(String(500), nullable=True)
    context_image_path = Column(String(500), nullable=True)
    
    # Hotlist matching
    hotlist_match = Column(Boolean, default=False)
    hotlist_id = Column(Integer, ForeignKey("hotlists.id"), nullable=True)
    
    # Relationships
    hotlist = relationship("Hotlist", back_populates="anpr_reads")

class DeviceSource(Base):
    """Track device sources that sync hotlists"""
    __tablename__ = "device_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(10), unique=True, index=True, nullable=False)  # BOF sourceID
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    hotlist_revisions = relationship("HotlistRevision", back_populates="device_source")

class HotlistRevision(Base):
    """Track hotlist revisions for each device source"""
    __tablename__ = "hotlist_revisions"
    
    id = Column(Integer, primary_key=True, index=True)
    hotlist_group_id = Column(Integer, ForeignKey("hotlist_groups.id"), nullable=False)
    device_source_id = Column(Integer, ForeignKey("device_sources.id"), nullable=False)
    hotlist_name = Column(String(100), nullable=False)  # Name of the hotlist
    latest_revision = Column(BigInteger, nullable=False)  # Latest revision available
    external_system_revision = Column(BigInteger, default=-1)  # Revision device thinks it has
    is_allocated = Column(Boolean, default=True)  # Whether this hotlist is allocated to this device
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    hotlist_group = relationship("HotlistGroup", back_populates="hotlist_revisions")
    device_source = relationship("DeviceSource", back_populates="hotlist_revisions")

class HotlistRepository(Base):
    """Track the global hotlist repository revision"""
    __tablename__ = "hotlist_repository"
    
    id = Column(Integer, primary_key=True, index=True)
    revision = Column(BigInteger, default=1)  # Global repository revision
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)  # camera_id, api, system, etc.
    user_id = Column(String(100), nullable=True) 