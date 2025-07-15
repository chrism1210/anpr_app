from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from typing import Optional, List

# Hotlist Group Schemas
class HotlistGroupBase(BaseModel):
    name: str = Field(..., max_length=100, description="Name of the hotlist")
    is_active: bool = Field(True, description="Whether this hotlist is active")

class VehicleBase(BaseModel):
    """UK ANPR Regulation 109 compliant vehicle schema - 16 fields"""
    
    # 1. VRM (Vehicle Registration Mark) - Required
    license_plate: str = Field(..., max_length=10, description="Vehicle Registration Mark (VRM)")
    
    # 2. Vehicle Make
    vehicle_make: Optional[str] = Field(None, max_length=50, description="Vehicle manufacturer")
    
    # 3. Vehicle Model
    vehicle_model: Optional[str] = Field(None, max_length=50, description="Vehicle model")
    
    # 4. Vehicle Colour
    vehicle_color: Optional[str] = Field(None, max_length=30, description="Vehicle colour")
    
    # 5. Action - calculated dynamically from group settings
    
    # 6. Warning Markers
    warning_markers: Optional[str] = Field(None, max_length=100, description="Warning markers for the vehicle")
    
    # 7. Reason - calculated dynamically from group settings
    
    # 8. NIM (5x5x5) Code
    nim_code: Optional[str] = Field(None, max_length=20, description="NIM (5x5x5) Code")
    
    # 9. Information/Action
    intelligence_information: Optional[str] = Field(None, description="Intelligence information and action required")
    
    # 10. Force & Area
    force_area: Optional[str] = Field(None, max_length=50, description="Police force/area identifier")
    
    # 11. Weed Date
    weed_date: Optional[date] = Field(None, description="Date when record should be reviewed/removed")
    
    # 12. PNC ID
    pnc_id: Optional[str] = Field(None, max_length=50, description="Police National Computer ID")
    
    # 13. GPMS Marking
    gpms_marking: Optional[str] = Field("Unclassified", max_length=20, description="GPMS classification")
    
    # 14. CAD Information
    cad_information: Optional[str] = Field(None, max_length=200, description="Command and Control information")
    
    # 15. Operational Instructions (Spare 1)
    operational_instructions: Optional[str] = Field(None, description="Specific operational instructions")
    
    # 16. Source Reference (Spare 2)
    source_reference: Optional[str] = Field(None, max_length=100, description="Source of the intelligence")

class VehicleCreate(VehicleBase):
    pass

class VehicleCreateWithGroup(VehicleBase):
    """Vehicle creation schema that includes group assignment"""
    pass

class VehicleResponse(VehicleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class HotlistGroupCreate(HotlistGroupBase):
    vehicles: List[VehicleCreate] = Field(default_factory=list, description="List of vehicles in this hotlist")

class HotlistGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    vehicles: Optional[List[VehicleCreate]] = None

class HotlistGroupResponse(HotlistGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    revision: int
    vehicles: List[VehicleResponse] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)

# ANPR Read Schemas
class ANPRReadBase(BaseModel):
    license_plate: str = Field(..., max_length=20, description="Detected license plate")
    camera_id: str = Field(..., max_length=50, description="Camera identifier")
    location: str = Field(..., max_length=200, description="Camera location")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")
    confidence: int = Field(0, ge=0, le=100, description="Detection confidence percentage")
    direction: Optional[str] = Field(None, max_length=20, description="Vehicle direction")
    speed: Optional[int] = Field(None, ge=0, description="Vehicle speed in km/h")
    lane: Optional[int] = Field(None, ge=1, description="Lane number")
    plate_image_path: Optional[str] = Field(None, max_length=500, description="Path to plate image")
    context_image_path: Optional[str] = Field(None, max_length=500, description="Path to context image")
    hotlist_match: bool = Field(False, description="Whether this read matched a hotlist")
    hotlist_id: Optional[int] = Field(None, description="ID of matched hotlist entry")

class ANPRReadCreate(ANPRReadBase):
    pass

class ANPRReadResponse(ANPRReadBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# System Stats Schema
class SystemStats(BaseModel):
    total_hotlists: int = Field(..., description="Total number of active hotlist entries")
    total_anpr_reads: int = Field(..., description="Total number of ANPR reads")
    hotlist_matches: int = Field(..., description="Number of hotlist matches")
    system_status: str = Field(..., description="System operational status")

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

class BofRepoStatusResponse(BaseModel):
    """BOF repository status response"""
    source_id: str = Field(..., description="Source identifier")
    revision_number: int = Field(..., description="Current revision number")
    hotlists: List[BofHotlistRevisions] = Field(default_factory=list, description="Available hotlists")

class BofHotlistStatusResponse(BaseModel):
    """BOF hotlist status response for a specific device"""
    source_id: str = Field(..., description="Source identifier")
    hotlists: List[BofHotlistRevisions] = Field(default_factory=list, description="Hotlist status for this device")

class BofCaptureResponse(BaseModel):
    """Response for BOF capture operations"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    read_id: Optional[int] = Field(None, description="Created ANPR read ID")

# BOF Capture/Input schemas
class BofSendCaptureRequest(BaseModel):
    """BOF sendCapture request with full capture details"""
    vrm: str = Field(..., description="Vehicle Registration Mark (license plate)")
    feedID: int = Field(..., description="Feed identifier")
    sourceID: int = Field(..., description="Source identifier")
    cameraID: int = Field(..., description="Camera identifier")
    plateImage: Optional[str] = Field(None, description="Base64 encoded plate image")
    overviewImage: Optional[str] = Field(None, description="Base64 encoded overview image")
    captureDate: str = Field(..., description="Capture date in ISO format")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")
    cameraPresetPosition: Optional[int] = Field(None, description="Camera preset position")
    cameraPan: Optional[str] = Field(None, description="Camera pan position")
    cameraTilt: Optional[str] = Field(None, description="Camera tilt position")
    cameraZoom: Optional[str] = Field(None, description="Camera zoom level")
    confidencePercentage: Optional[int] = Field(None, description="Recognition confidence percentage")
    motionTowardCamera: Optional[bool] = Field(None, description="Whether motion is toward camera")

class BofSendCompactCaptureRequest(BaseModel):
    """BOF sendCompactCapture request with pipe-delimited capture data"""
    capture: str = Field(..., description="Pipe-delimited capture data string")

class BofSendCompoundCaptureRequest(BaseModel):
    """BOF sendCompoundCapture request with multiple compact captures"""
    captures: List[str] = Field(..., max_items=50, description="List of pipe-delimited capture strings (max 50)")

# Configuration schemas
class ANPRConfiguration(BaseModel):
    """ANPR system configuration"""
    camera_locations: List[str] = Field(default_factory=list, description="Configured camera locations")
    system_status: str = Field("operational", description="System status")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last configuration update")

class ConnectivityStatus(BaseModel):
    """System connectivity status"""
    status: str = Field(..., description="Connectivity status")
    message: str = Field(..., description="Status message")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last connectivity check")

class BofAddBinaryCaptureDataRequest(BaseModel):
    """BOF addBinaryCaptureData request for sending binary image data"""
    captureGUID: str = Field(..., description="Unique identifier for the capture")
    imageType: str = Field(..., description="Type of image (P for plate, C for context)")
    binaryData: str = Field(..., description="Base64 encoded binary image data") 