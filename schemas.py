from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

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
    created_by: Optional[str] = Field(None, max_length=100)
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
    revision: int
    
    model_config = ConfigDict(from_attributes=True)

# ANPR Read Schemas
class ANPRReadBase(BaseModel):
    license_plate: str = Field(..., max_length=20, description="Detected license plate")
    camera_id: str = Field(..., max_length=50, description="Camera identifier")
    location: str = Field(..., max_length=200, description="Camera location")
    confidence: int = Field(0, ge=0, le=100, description="Detection confidence percentage")
    direction: Optional[str] = Field(None, max_length=20, description="Vehicle direction")
    speed: Optional[int] = Field(None, ge=0, description="Vehicle speed in km/h")
    lane: Optional[int] = Field(None, ge=1, description="Lane number")

class ANPRReadCreate(ANPRReadBase):
    pass

class ANPRReadResponse(ANPRReadBase):
    id: int
    timestamp: datetime
    plate_image_path: Optional[str] = None
    context_image_path: Optional[str] = None
    hotlist_match: bool
    hotlist_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

# BOF-specific schemas for hotlist synchronization
class BofHotlistRevisions(BaseModel):
    """BOF hotlist revision information for a specific hotlist"""
    hotlist_name: str = Field(..., description="Name of the hotlist")
    latest_revision: int = Field(..., description="Latest revision number available")
    external_system_revision: int = Field(-1, description="Revision the external system has")
    is_allocated: bool = Field(True, description="Whether this hotlist is allocated to this device")

class BofHotlistData(BaseModel):
    """BOF hotlist data with updates"""
    hotlist_name: str = Field(..., description="Name of the hotlist")
    latest_revision: int = Field(..., description="Latest revision number")
    hotlist_deltas: Optional[str] = Field(None, description="Base64 encoded ZIP file containing hotlist updates")
    is_file_too_big: bool = Field(False, description="Whether the update file is too big")

class ExternalHotlistRevisions(BaseModel):
    """External hotlist revision information sent by devices"""
    hotlist_name: str = Field(..., description="Name of the hotlist")
    current_revision: int = Field(..., description="Current revision the device has")

class DeviceSourceCreate(BaseModel):
    source_id: str = Field(..., max_length=10, description="BOF source identifier")
    name: str = Field(..., max_length=100, description="Device name")
    description: Optional[str] = Field(None, description="Device description")
    is_active: bool = Field(True, description="Whether the device is active")

class DeviceSourceResponse(BaseModel):
    id: int
    source_id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class HotlistRevisionResponse(BaseModel):
    id: int
    hotlist_id: int
    device_source_id: int
    hotlist_name: str
    latest_revision: int
    external_system_revision: int
    is_allocated: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# BOF Web Service Request/Response schemas
class GetHotlistRepoStatusRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    revision_number: int = Field(..., description="Current revision held by the camera group")

class GetHotlistStatusRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")

class SetHotlistStatusRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    hotlists_and_revisions: List[ExternalHotlistRevisions] = Field(..., description="Array of hotlist revisions")

class GetHotlistUpdatesRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    hotlist_name: str = Field(..., description="Name of the hotlist to update")

class GetHotlistUpdatesRestrictSizeRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    hotlist_name: str = Field(..., description="Name of the hotlist to update")
    size: int = Field(..., description="Maximum size of the update to receive")

class GetMultipleHotlistUpdatesRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    hotlist_names: List[str] = Field(..., description="Names of hotlists to update")

class GetMultipleHotlistUpdatesRestrictSizeRequest(BaseModel):
    source_id: str = Field(..., description="Source ID for the camera group")
    hotlist_names: List[str] = Field(..., description="Names of hotlists to update")
    size: int = Field(..., description="Maximum size of each update to receive")

# Statistics Schema
class StatsResponse(BaseModel):
    total_hotlists: int
    total_reads: int
    hotlist_matches: int
    match_rate: float 