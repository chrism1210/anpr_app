from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, BigInteger, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class HotlistGroup(Base):
    __tablename__ = "hotlist_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # BOF-specific fields for revision tracking
    revision = Column(BigInteger, default=1)  # Revision number for this hotlist group
    
    # Relationships
    vehicles = relationship("Hotlist", back_populates="hotlist_group")
    hotlist_revisions = relationship("HotlistRevision", back_populates="hotlist_group")

class Hotlist(Base):
    __tablename__ = "hotlists"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # UK ANPR Regulation 109 - 16 Fields
    # 1. VRM (Vehicle Registration Mark)
    license_plate = Column(String(10), index=True, nullable=False)
    
    # 2. Vehicle Make
    vehicle_make = Column(String(50))
    
    # 3. Vehicle Model
    vehicle_model = Column(String(50))
    
    # 4. Vehicle Colour
    vehicle_color = Column(String(30))
    
    # 5. Action (derived from group priority - STOP/SILENT)
    # This will be calculated dynamically in the CSV export
    
    # 6. Warning Markers
    warning_markers = Column(String(100))
    
    # 7. Reason (category - will be derived from group)
    # This will be calculated dynamically in the CSV export
    
    # 8. NIM (5x5x5) Code
    nim_code = Column(String(20))
    
    # 9. Information/Action
    intelligence_information = Column(Text)
    
    # 10. Force & Area
    force_area = Column(String(50))
    
    # 11. Weed Date
    weed_date = Column(Date)
    
    # 12. PNC ID
    pnc_id = Column(String(50))
    
    # 13. GPMS Marking
    gpms_marking = Column(String(20), default="Unclassified")
    
    # 14. CAD Information
    cad_information = Column(String(200))
    
    # 15. Operational Instructions (Spare 1)
    operational_instructions = Column(Text)
    
    # 16. Source Reference (Spare 2)
    source_reference = Column(String(100))
    
    # System fields
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
    """Track device sources for BOF integration"""
    __tablename__ = "device_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(200))
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