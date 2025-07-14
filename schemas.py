from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional

# Hotlist Schemas
class HotlistBase(BaseModel):
    license_plate: str = Field(..., max_length=20, description="Vehicle license plate number")
    description: str = Field(..., description="Description of why this vehicle is on the hotlist")
    category: str = Field(..., max_length=50, description="Category (stolen, wanted, bolo, etc.)")
    priority: str = Field("medium", description="Priority level (low, medium, high, critical)")
    created_by: str = Field(..., max_length=100, description="User who created this entry")
    is_active: bool = Field(True, description="Whether this hotlist entry is active")
    expiry_date: Optional[datetime] = Field(None, description="When this hotlist entry expires")
    
    # Vehicle details
    vehicle_make: Optional[str] = Field(None, max_length=50)
    vehicle_model: Optional[str] = Field(None, max_length=50)
    vehicle_color: Optional[str] = Field(None, max_length=30)
    vehicle_year: Optional[int] = Field(None, ge=1900, le=2030)
    owner_name: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None

class HotlistCreate(HotlistBase):
    pass

class HotlistUpdate(BaseModel):
    license_plate: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = None
    is_active: Optional[bool] = None
    expiry_date: Optional[datetime] = None
    vehicle_make: Optional[str] = Field(None, max_length=50)
    vehicle_model: Optional[str] = Field(None, max_length=50)
    vehicle_color: Optional[str] = Field(None, max_length=30)
    vehicle_year: Optional[int] = Field(None, ge=1900, le=2030)
    owner_name: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None

class HotlistResponse(HotlistBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# ANPR Read Schemas
class ANPRReadBase(BaseModel):
    license_plate: str = Field(..., max_length=20, description="Detected license plate")
    camera_id: str = Field(..., max_length=50, description="Camera identifier")
    location: str = Field(..., max_length=200, description="Camera location")
    confidence: int = Field(0, ge=0, le=100, description="Detection confidence (0-100)")
    image_path: Optional[str] = Field(None, max_length=500, description="Path to captured image")
    direction: Optional[str] = Field(None, max_length=20, description="Vehicle direction")
    speed: Optional[int] = Field(None, ge=0, description="Vehicle speed if available")
    lane: Optional[int] = Field(None, ge=1, description="Lane number")

class ANPRReadCreate(ANPRReadBase):
    timestamp: Optional[datetime] = Field(None, description="Read timestamp (defaults to now)")

class ANPRReadResponse(ANPRReadBase):
    id: int
    timestamp: datetime
    hotlist_match: bool
    hotlist_id: Optional[int] = None
    plate_image_path: Optional[str] = None
    context_image_path: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Statistics Schema
class StatsResponse(BaseModel):
    total_hotlists: int
    total_reads: int
    hotlist_matches: int
    match_rate: float 