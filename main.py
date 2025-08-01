from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from pathlib import Path
import logging
import io
import csv
import base64
import uuid
import zipfile
from datetime import datetime
import uvicorn

from database import SessionLocal, engine
from models import Base, Hotlist, ANPRRead, HotlistGroup, DeviceSource, HotlistRevision
from schemas import (
    HotlistGroupCreate, HotlistGroupUpdate, HotlistGroupResponse,
    VehicleCreate, VehicleResponse,
    ANPRReadCreate, ANPRReadResponse, SystemStats,
    BofHotlistRevisions, BofHotlistData, BofRepoStatusResponse, BofHotlistStatusResponse, BofCaptureResponse,
    BofSendCaptureRequest, BofSendCompactCaptureRequest, BofSendCompoundCaptureRequest,
    BofAddBinaryCaptureDataRequest, ANPRConfiguration, ConnectivityStatus
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="ANPR Management System",
    description="Automatic Number Plate Recognition system for vehicle hotlist management and camera integration",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions for BOF hotlist operations
def get_or_create_device_source(db: Session, source_id: str) -> DeviceSource:
    """Get or create a device source for BOF integration"""
    device = db.query(DeviceSource).filter(DeviceSource.source_id == source_id).first()
    if not device:
        device = DeviceSource(
            source_id=source_id,
            description=f"Auto-created device for source {source_id}"
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    return device

def get_or_create_hotlist_revision(db: Session, hotlist_group_id: int, device_source_id: int, hotlist_name: str) -> HotlistRevision:
    """Get or create a hotlist revision tracking entry"""
    revision = db.query(HotlistRevision).filter(
        HotlistRevision.hotlist_group_id == hotlist_group_id,
        HotlistRevision.device_source_id == device_source_id
    ).first()
    
    if not revision:
        # Get the current hotlist group revision (use the highest revision from its hotlists)
        latest_hotlist_revision = db.query(Hotlist).filter(
            Hotlist.hotlist_group_id == hotlist_group_id,
            Hotlist.is_active == True
        ).order_by(Hotlist.revision.desc()).first()
        
        revision = HotlistRevision(
            hotlist_group_id=hotlist_group_id,
            device_source_id=device_source_id,
            hotlist_name=hotlist_name,
            latest_revision=latest_hotlist_revision.revision if latest_hotlist_revision else 1,
            external_system_revision=-1
        )
        db.add(revision)
        db.commit()
        db.refresh(revision)
    
    return revision

def generate_hotlist_csv_data(hotlists: List[Hotlist]) -> str:
    """Generate CSV data for hotlists in BOF 16-column format compliant with UK ANPR Regulation 109"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    for hotlist in hotlists:
        # BOF 16-column format with UK ANPR Regulation 109 fields
        row = [
            hotlist.license_plate,                                              # 1. VRM
            hotlist.vehicle_make or "",                                        # 2. Vehicle Make
            hotlist.vehicle_model or "",                                       # 3. Vehicle Model  
            hotlist.vehicle_color or "",                                       # 4. Vehicle Colour
            "SILENT",                                                          # 5. Action (default SILENT)
            hotlist.warning_markers or "",                                     # 6. Warning Markers
            "",                                                                # 7. Reason (empty)
            hotlist.nim_code or "",                                           # 8. NIM (5x5x5) Code
            hotlist.intelligence_information or "",                           # 9. Information/Action
            hotlist.force_area or "",                                         # 10. Force & Area
            hotlist.weed_date.strftime("%d/%m/%Y") if hotlist.weed_date else "", # 11. Weed Date
            hotlist.pnc_id or "",                                             # 12. PNC ID
            hotlist.gpms_marking or "Unclassified",                          # 13. GPMS Marking
            hotlist.cad_information or "",                                    # 14. CAD Information
            hotlist.operational_instructions or "",                           # 15. Operational Instructions (Spare 1)
            hotlist.source_reference or ""                                    # 16. Source Reference (Spare 2)
        ]
        writer.writerow(row)
    
    return output.getvalue()

def create_hotlist_zip(hotlist_name: str, source_id: str, csv_data: str, operation: str = "R") -> bytes:
    """Create a ZIP file containing hotlist data"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        filename = f"{source_id}_{hotlist_name}_{operation}.dat"
        # Ensure CSV data is properly encoded as UTF-8
        csv_bytes = csv_data.encode('utf-8')
        zip_file.writestr(filename, csv_bytes)
    
    zip_buffer.seek(0)
    return zip_buffer.read()

# Web UI Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/hotlists", response_class=HTMLResponse)
async def hotlists_page(request: Request):
    """Hotlists management page"""
    return templates.TemplateResponse("hotlists.html", {"request": request})

@app.get("/anpr-reads", response_class=HTMLResponse)
async def anpr_reads_page(request: Request):
    """ANPR reads monitoring page"""
    return templates.TemplateResponse("anpr_reads.html", {"request": request})

# API Routes - Hotlist Groups (New structured hotlists)
@app.post("/api/hotlist-groups", response_model=HotlistGroupResponse)
async def create_hotlist_group(hotlist_group: HotlistGroupCreate, db: Session = Depends(get_db)):
    """Create a new hotlist group with multiple vehicles"""
    print(f"DEBUG: Starting to create hotlist group: {hotlist_group.name}")
    
    # Create the hotlist group with only the simplified fields
    db_hotlist_group = HotlistGroup(
        name=hotlist_group.name,
        is_active=hotlist_group.is_active
    )
    print(f"DEBUG: Created HotlistGroup object")
    
    db.add(db_hotlist_group)
    print(f"DEBUG: Added to session")
    
    db.commit()
    print(f"DEBUG: Committed hotlist group")
    
    db.refresh(db_hotlist_group)
    print(f"DEBUG: Refreshed, ID: {db_hotlist_group.id}")
    
    # Add vehicles to the group
    print(f"DEBUG: Adding {len(hotlist_group.vehicles)} vehicles")
    for i, vehicle_data in enumerate(hotlist_group.vehicles):
        print(f"DEBUG: Creating vehicle {i+1}: {vehicle_data.license_plate}")
        
        # Get all vehicle data and filter out None values
        vehicle_dict = vehicle_data.model_dump(exclude_none=True)
        
        # Create vehicle with all provided fields
        db_vehicle = Hotlist(
            hotlist_group_id=db_hotlist_group.id,
            **vehicle_dict
        )
        print(f"DEBUG: Created Hotlist object for vehicle {i+1}")
        
        db.add(db_vehicle)
        print(f"DEBUG: Added vehicle {i+1} to session")
    
    db.commit()
    db.refresh(db_hotlist_group)
    
    # Revision tracking is simplified - no global repository revision needed
    
    return db_hotlist_group

@app.get("/api/hotlist-groups", response_model=List[HotlistGroupResponse])
async def get_hotlist_groups(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all hotlist groups with optional search"""
    query = db.query(HotlistGroup)
    
    if search:
        query = query.filter(
            HotlistGroup.name.ilike(f"%{search}%")
        )
    
    hotlist_groups = query.offset(skip).limit(limit).all()
    return hotlist_groups

@app.get("/api/hotlist-groups/{group_id}", response_model=HotlistGroupResponse)
async def get_hotlist_group(group_id: int, db: Session = Depends(get_db)):
    """Get a specific hotlist group by ID"""
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.id == group_id).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    return hotlist_group

@app.put("/api/hotlist-groups/{group_id}", response_model=HotlistGroupResponse)
async def update_hotlist_group(group_id: int, hotlist_group_update: HotlistGroupUpdate, db: Session = Depends(get_db)):
    """Update a hotlist group"""
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.id == group_id).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    
    update_data = hotlist_group_update.model_dump(exclude_unset=True)
    
    # Handle vehicles update separately
    if 'vehicles' in update_data:
        vehicles_data = update_data.pop('vehicles')
        
        # Delete existing vehicles
        db.query(Hotlist).filter(Hotlist.hotlist_group_id == group_id).delete()
        
        # Add new vehicles
        for vehicle_data in vehicles_data:
            db_vehicle = Hotlist(
                hotlist_group_id=group_id,
                **vehicle_data
            )
            db.add(db_vehicle)
    
    # Update group fields
    for field, value in update_data.items():
        setattr(hotlist_group, field, value)
    
    # Increment the hotlist group revision
    hotlist_group.revision += 1
    hotlist_group.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(hotlist_group)
    
    # Revision tracking is simplified - no global repository revision needed
    
    return hotlist_group

@app.delete("/api/hotlist-groups/{group_id}")
async def delete_hotlist_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a hotlist group and all its vehicles"""
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.id == group_id).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    
    # Delete all vehicles in the group
    db.query(Hotlist).filter(Hotlist.hotlist_group_id == group_id).delete()
    
    # Delete the group
    db.delete(hotlist_group)
    db.commit()
    
    # Revision tracking is simplified - no global repository revision needed
    
    return {"message": "Hotlist group deleted successfully"}

# CSV Upload endpoint for hotlist groups
@app.post("/api/hotlist-groups/{group_id}/upload-csv")
async def upload_csv_to_hotlist(
    group_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a CSV file of vehicles to a hotlist group"""
    # Check if hotlist group exists
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.id == group_id).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(content_str))
        vehicles_added = 0;
        
        for row in csv_reader:
            # Clean up the row data
            vehicle_data = {}
            for key, value in row.items():
                if value and value.strip():  # Only include non-empty values
                    # Map common field variations
                    key_lower = key.lower().strip()
                    if key_lower in ['license_plate', 'licence_plate', 'vrm', 'plate']:
                        vehicle_data['license_plate'] = value.strip()
                    elif key_lower in ['vehicle_make', 'make']:
                        vehicle_data['vehicle_make'] = value.strip()
                    elif key_lower in ['vehicle_model', 'model']:
                        vehicle_data['vehicle_model'] = value.strip()
                    elif key_lower in ['vehicle_color', 'vehicle_colour', 'color', 'colour']:
                        vehicle_data['vehicle_color'] = value.strip()
                    elif key_lower in ['fuel_type', 'fuel']:
                        vehicle_data['fuel_type'] = value.strip()
                    elif key_lower in ['body_type', 'body']:
                        vehicle_data['body_type'] = value.strip()
                    elif key_lower in ['vin_number', 'vin']:
                        vehicle_data['vin_number'] = value.strip()
                    elif key_lower in ['warning_markers', 'warnings']:
                        vehicle_data['warning_markers'] = value.strip()
                    elif key_lower in ['intelligence_information', 'intelligence', 'info']:
                        vehicle_data['intelligence_information'] = value.strip()
                    elif key_lower in ['force_area', 'force']:
                        vehicle_data['force_area'] = value.strip()
            
            # License plate is required
            if 'license_plate' not in vehicle_data:
                continue
                
            # Create the vehicle
            db_vehicle = Hotlist(
                hotlist_group_id=group_id,
                **vehicle_data
            )
            db.add(db_vehicle)
            vehicles_added += 1
        
        # Commit all vehicles
        db.commit()
        
        # Revision tracking is simplified - no global repository revision needed
        
        return {
            "message": f"Successfully uploaded {vehicles_added} vehicles to hotlist group '{hotlist_group.name}'",
            "vehicles_added": vehicles_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {str(e)}")

# API Routes - ANPR Reads
@app.post("/anpr/reads", response_model=ANPRReadResponse)
async def ingest_anpr_read(anpr_read: ANPRReadCreate, db: Session = Depends(get_db)):
    """Ingest ANPR read record from camera and process through BOF protocol"""
    db_anpr_read = ANPRRead(**anpr_read.model_dump())
    
    # Check if this plate is on any hotlist
    hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == anpr_read.license_plate).first()
    if hotlist_match:
        db_anpr_read.hotlist_match = True
        db_anpr_read.hotlist_id = hotlist_match.id
    
    db.add(db_anpr_read)
    db.commit()
    db.refresh(db_anpr_read)
    
    # Convert to response model
    anpr_response = ANPRReadResponse.model_validate(db_anpr_read)
    
    return anpr_response

@app.post("/anpr/reads/with-images", response_model=ANPRReadResponse)
async def ingest_anpr_read_with_images(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Enhanced ANPR read ingestion with binary image support
    Accepts multipart form data with optional image files
    """
    # This endpoint can be simplified or removed if not needed
    raise HTTPException(status_code=501, detail="Endpoint not implemented")

@app.get("/anpr/reads", response_model=List[ANPRReadResponse])
async def get_anpr_reads(
    skip: int = 0, 
    limit: int = 100, 
    hotlist_only: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get ANPR reads with optional filtering"""
    query = db.query(ANPRRead)
    
    if hotlist_only:
        query = query.filter(ANPRRead.hotlist_match == True)
    
    if search:
        query = query.filter(
            ANPRRead.license_plate.ilike(f"%{search}%") |
            ANPRRead.camera_id.ilike(f"%{search}%") |
            ANPRRead.location.ilike(f"%{search}%")
        )
    
    anpr_reads = query.order_by(ANPRRead.timestamp.desc()).offset(skip).limit(limit).all()
    return anpr_reads

@app.get("/anpr/reads/{read_id}", response_model=ANPRReadResponse)
async def get_anpr_read(read_id: int, db: Session = Depends(get_db)):
    """Get a specific ANPR read by ID"""
    anpr_read = db.query(ANPRRead).filter(ANPRRead.id == read_id).first()
    if not anpr_read:
        raise HTTPException(status_code=404, detail="ANPR read not found")
    return anpr_read

# API Routes - Statistics
@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics for dashboard"""
    total_hotlists = db.query(Hotlist).count()
    total_reads = db.query(ANPRRead).count()
    hotlist_matches = db.query(ANPRRead).filter(ANPRRead.hotlist_match == True).count()
    
    return {
        "total_hotlists": total_hotlists,
        "total_reads": total_reads,
        "hotlist_matches": hotlist_matches,
        "match_rate": (hotlist_matches / total_reads * 100) if total_reads > 0 else 0
    }

# BOF Hotlist Synchronization Endpoints
@app.get("/bof/services/UpdateHotlistsService/getHotlistRepoStatus")
async def get_hotlist_repo_status(
    sourceID: str,
    revisionnumber: int,
    db: Session = Depends(get_db)
):
    """
    BOF: Get the latest revision number of the hotlist repository
    Returns the current revision or -1 if no changes since last update
    """
    # This function is no longer needed as revision tracking is simplified
    return -1

@app.get("/bof/services/UpdateHotlistsService/getHotlistStatus")
async def get_hotlist_status(
    sourceID: str,
    db: Session = Depends(get_db)
) -> List[BofHotlistRevisions]:
    """
    BOF: Get hotlist status for a specific source
    Returns array of BofHotlistRevisions for all hotlist groups allocated to this source
    """
    # Get or create the device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get all active hotlist groups
    hotlist_groups = db.query(HotlistGroup).filter(HotlistGroup.is_active == True).all()
    
    result = []
    for group in hotlist_groups:
        # Use the actual group name for hotlist sync
        hotlist_name = group.name
        
        # Get or create revision tracking for this group
        revision = get_or_create_hotlist_revision(db, group.id, device_source.id, hotlist_name)
        
        # Update latest revision from group
        revision.latest_revision = group.revision
        db.commit();
        
        result.append(BofHotlistRevisions(
            hotlist_name=hotlist_name,
            latest_revision=group.revision,
            external_system_revision=revision.external_system_revision,
            is_allocated=revision.is_allocated
        ))
    
    return result

@app.post("/bof/services/UpdateHotlistsService/setHotlistStatus")
async def set_hotlist_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    BOF: Set hotlist status for a specific source
    Simplified implementation for BOF compatibility
    """
    # For now, return a simple success response
    return {"status": "success", "message": "Hotlist status updated"}

# BOF Hotlist Updates Endpoints
@app.get("/bof/services/UpdateHotlistsService/getHotlistUpdates")
async def get_hotlist_updates(
    sourceID: str,
    hotlistname: str,
    db: Session = Depends(get_db)
) -> BofHotlistData:
    """
    BOF: Get hotlist updates for a specific hotlist group
    Returns BofHotlistData with ZIP file containing all vehicles in the group
    """
    # Find the hotlist group by name
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.name == hotlistname).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    
    # Get device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get or create revision tracking for this group
    revision = get_or_create_hotlist_revision(db, hotlist_group.id, device_source.id, hotlistname)
    
    # Get all active vehicles in this group
    vehicles = db.query(Hotlist).filter(
        Hotlist.hotlist_group_id == hotlist_group.id,
        Hotlist.is_active == True
    ).all()
    
    # Generate CSV data for all vehicles in the group
    csv_data = generate_hotlist_csv_data(vehicles)
    
    # Create ZIP file with hotlist data
    zip_data = create_hotlist_zip(hotlistname, sourceID, csv_data)
    
    # Encode binary data as base64 for JSON response
    zip_data_b64 = base64.b64encode(zip_data).decode('utf-8')
    
    return BofHotlistData(
        hotlist_name=hotlistname,
        latest_revision=hotlist_group.revision,
        hotlist_deltas=zip_data_b64,
        is_file_too_big=False
    )

@app.get("/bof/services/UpdateHotlistsService/getHotlistUpdatesRestrictSize")
async def get_hotlist_updates_restrict_size(
    sourceID: str,
    hotlistname: str,
    size: int,
    db: Session = Depends(get_db)
) -> BofHotlistData:
    """
    BOF: Get hotlist updates with size restriction for a specific hotlist group
    Returns BofHotlistData with ZIP file containing updates or too_big flag
    """
    # Find the hotlist group by name
    hotlist_group = db.query(HotlistGroup).filter(HotlistGroup.name == hotlistname).first()
    if not hotlist_group:
        raise HTTPException(status_code=404, detail="Hotlist group not found")
    
    # Get device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get or create revision tracking for this group
    revision = get_or_create_hotlist_revision(db, hotlist_group.id, device_source.id, hotlistname)
    
    # Get all active vehicles in this group
    vehicles = db.query(Hotlist).filter(
        Hotlist.hotlist_group_id == hotlist_group.id,
        Hotlist.is_active == True
    ).all()
    
    # Generate CSV data for all vehicles in the group
    csv_data = generate_hotlist_csv_data(vehicles)
    
    # Create ZIP file with hotlist data
    zip_data = create_hotlist_zip(hotlistname, sourceID, csv_data)
    
    # Check if ZIP file is too big
    if len(zip_data) > size:
        return BofHotlistData(
            hotlist_name=hotlistname,
            latest_revision=hotlist_group.revision,
            hotlist_deltas=None,
            is_file_too_big=True
        )
    
    # Encode binary data as base64 for JSON response
    zip_data_b64 = base64.b64encode(zip_data).decode('utf-8')
    
    return BofHotlistData(
        hotlist_name=hotlistname,
        latest_revision=hotlist_group.revision,
        hotlist_deltas=zip_data_b64,
        is_file_too_big=False
    )

@app.get("/bof/services/UpdateHotlistsService/getMultipleHotlistUpdates")
async def get_multiple_hotlist_updates(
    sourceid: str,
    hotlistnames: List[str],
    db: Session = Depends(get_db)
) -> List[BofHotlistData]:
    """
    BOF: Get updates for multiple hotlists
    Returns array of BofHotlistData objects
    """
    results = []
    
    for hotlist_name in hotlistnames:
        try:
            result = await get_hotlist_updates(sourceid, hotlist_name, db)
            results.append(result)
        except HTTPException:
            # Skip hotlists that don't exist
            continue
    
    return results

@app.get("/bof/services/UpdateHotlistsService/getMultipleHotlistUpdatesRestrictSize")
async def get_multiple_hotlist_updates_restrict_size(
    sourceid: str,
    hotlistnames: List[str],
    size: int,
    db: Session = Depends(get_db)
) -> List[BofHotlistData]:
    """
    BOF: Get updates for multiple hotlists with size restriction
    Returns array of BofHotlistData objects with size limits
    """
    results = []
    
    for hotlist_name in hotlistnames:
        try:
            result = await get_hotlist_updates_restrict_size(sourceid, hotlist_name, size, db)
            results.append(result)
        except HTTPException:
            # Skip hotlists that don't exist
            continue
    
    return results

# BOF Capture/Input Endpoints
@app.post("/bof/services/InputCaptureWebService/sendCapture", response_model=BofCaptureResponse)
async def bof_send_capture(
    request: BofSendCaptureRequest,
    db: Session = Depends(get_db)
):
    """
    BOF: Send complete capture record to BOF system
    Creates an ANPR read from the full capture data with image support
    """
    try:
        # Parse capture date
        capture_time = datetime.fromisoformat(request.captureDate.replace('Z', '+00:00'))
        
        # Create ANPR read record
        anpr_read = ANPRRead(
            license_plate=request.vrm,
            camera_id=str(request.cameraID),
            location=f"Feed:{request.feedID}, Source:{request.sourceID}, Camera:{request.cameraID}",
            timestamp=capture_time,
            confidence=request.confidencePercentage or 0,
            direction=None,
            speed=None,
            lane=None
        )
        
        # Check for hotlist match
        hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == request.vrm).first()
        if hotlist_match:
            anpr_read.hotlist_match = True
            anpr_read.hotlist_id = hotlist_match.id
        
        # Save to database first to get the ID
        db.add(anpr_read)
        db.commit()
        db.refresh(anpr_read)
        
        # Process plate image if provided
        if request.plateImage:
            try:
                # Decode base64 image
                image_data = base64.b64decode(request.plateImage)
                
                # Generate filename
                filename = f"plate_{uuid.uuid4()}.jpg"
                filepath = UPLOAD_DIR / filename
                
                # Save image
                with open(filepath, "wb") as f:
                    f.write(image_data)
                
                # Update ANPR read with image path
                anpr_read.plate_image_path = str(filepath)
                
                logger.info(f"BOF sendCapture: Saved plate image for plate {request.vrm}")
                
            except Exception as e:
                logger.error(f"Error processing plate image: {str(e)}")
        
        # Process overview image if provided
        if request.overviewImage:
            try:
                # Decode base64 image
                image_data = base64.b64decode(request.overviewImage)
                
                # Generate filename
                filename = f"context_{uuid.uuid4()}.jpg"
                filepath = UPLOAD_DIR / filename
                
                # Save image
                with open(filepath, "wb") as f:
                    f.write(image_data)
                
                # Update ANPR read with context image path
                anpr_read.context_image_path = str(filepath)
                
                logger.info(f"BOF sendCapture: Saved overview image for plate {request.vrm}")
                
            except Exception as e:
                logger.error(f"Error processing overview image: {str(e)}")
        
        # Update database with image paths
        db.commit()
        
        logger.info(f"BOF sendCapture: Created ANPR read for plate {request.vrm}")
        
        return BofCaptureResponse(
            success=True,
            message=f"Capture processed successfully for plate {request.vrm}",
            read_id=anpr_read.id
        )
        
    except Exception as e:
        logger.error(f"BOF sendCapture error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing capture: {str(e)}")

@app.post("/bof/services/InputCaptureWebService/sendCompactCapture", response_model=BofCaptureResponse)
async def bof_send_compact_capture(
    request: BofSendCompactCaptureRequest,
    db: Session = Depends(get_db)
):
    """
    BOF: Send compact (pipe-delimited) capture record
    Format: signature | username | vrm | feedID | sourceID | cameraID | captureDate | latitude | longitude | cameraPresetPosition | cameraPan | cameraTilt | cameraZoom | confidencePercentage | motionTowardCamera
    """
    try:
        # Parse the pipe-delimited capture string
        parts = request.capture.split('|')
        if len(parts) < 7:
            raise HTTPException(status_code=400, detail="Invalid compact capture format")
        
        # Extract required fields
        signature = parts[0].strip()
        username = parts[1].strip()
        vrm = parts[2].strip()
        feed_id = int(parts[3].strip())
        source_id = int(parts[4].strip())
        camera_id = int(parts[5].strip())
        capture_date = parts[6].strip()
        
        # Parse optional fields
        latitude = float(parts[7].strip()) if len(parts) > 7 and parts[7].strip() else None
        longitude = float(parts[8].strip()) if len(parts) > 8 and parts[8].strip() else None
        camera_preset = int(parts[9].strip()) if len(parts) > 9 and parts[9].strip() else None
        camera_pan = parts[10].strip() if len(parts) > 10 else None
        camera_tilt = parts[11].strip() if len(parts) > 11 else None
        camera_zoom = parts[12].strip() if len(parts) > 12 else None
        confidence = int(parts[13].strip()) if len(parts) > 13 and parts[13].strip() else 0
        motion_toward_camera = parts[14].strip().lower() == 'true' if len(parts) > 14 else None
        
        # Parse capture date
        capture_time = datetime.fromisoformat(capture_date.replace('Z', '+00:00'))
        
        # Create ANPR read record
        anpr_read = ANPRRead(
            license_plate=vrm,
            camera_id=str(camera_id),
            location=f"Feed:{feed_id}, Source:{source_id}, Camera:{camera_id}",
            timestamp=capture_time,
            confidence=confidence,
            direction=None,
            speed=None,
            lane=None
        )
        
        # Check for hotlist match
        hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == vrm).first()
        if hotlist_match:
            anpr_read.hotlist_match = True
            anpr_read.hotlist_id = hotlist_match.id
        
        # Save to database
        db.add(anpr_read)
        db.commit()
        db.refresh(anpr_read)
        
        logger.info(f"BOF sendCompactCapture: Created ANPR read for plate {vrm}")
        
        return BofCaptureResponse(
            success=True,
            message=f"Compact capture processed successfully for plate {vrm}",
            read_id=anpr_read.id
        )
        
    except ValueError as e:
        logger.error(f"BOF sendCompactCapture parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error parsing compact capture: {str(e)}")
    except Exception as e:
        logger.error(f"BOF sendCompactCapture error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing compact capture: {str(e)}")

@app.post("/bof/services/InputCaptureWebService/sendCompoundCapture", response_model=BofCaptureResponse)
async def bof_send_compound_capture(
    request: BofSendCompoundCaptureRequest,
    db: Session = Depends(get_db)
):
    """
    BOF: Send multiple compact capture records in a single request
    Maximum 50 captures per request
    """
    try:
        if len(request.captures) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 captures per request")
        
        created_reads = []
        
        for capture_string in request.captures:
            # Parse the pipe-delimited capture string
            parts = capture_string.split('|')
            if len(parts) < 7:
                logger.warning(f"Skipping invalid compact capture format: {capture_string}")
                continue
            
            # Extract required fields
            signature = parts[0].strip()
            username = parts[1].strip()
            vrm = parts[2].strip()
            feed_id = int(parts[3].strip())
            source_id = int(parts[4].strip())
            camera_id = int(parts[5].strip())
            capture_date = parts[6].strip()
            
            # Parse optional fields
            confidence = int(parts[13].strip()) if len(parts) > 13 and parts[13].strip() else 0
            
            # Parse capture date
            capture_time = datetime.fromisoformat(capture_date.replace('Z', '+00:00'))
            
            # Create ANPR read record
            anpr_read = ANPRRead(
                license_plate=vrm,
                camera_id=str(camera_id),
                location=f"Feed:{feed_id}, Source:{source_id}, Camera:{camera_id}",
                timestamp=capture_time,
                confidence=confidence,
                direction=None,
                speed=None,
                lane=None
            )
            
            # Check for hotlist match
            hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == vrm).first()
            if hotlist_match:
                anpr_read.hotlist_match = True
                anpr_read.hotlist_id = hotlist_match.id
            
            # Save to database
            db.add(anpr_read)
            created_reads.append(anpr_read)
        
        # Commit all at once
        db.commit()
        
        logger.info(f"BOF sendCompoundCapture: Created {len(created_reads)} ANPR reads")
        
        return BofCaptureResponse(
            success=True,
            message=f"Compound capture processed successfully. Created {len(created_reads)} reads",
            read_id=None
        )
        
    except Exception as e:
        logger.error(f"BOF sendCompoundCapture error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing compound capture: {str(e)}")

@app.post("/bof/services/InputBinaryDataWebService/addBinaryCaptureData", response_model=BofCaptureResponse)
async def bof_add_binary_capture_data(
    request: BofAddBinaryCaptureDataRequest,
    db: Session = Depends(get_db)
):
    """
    BOF: Add binary image data to a previously sent capture record
    Supports plate (P) and context (C) image types
    """
    try:
        # Parse capture time
        capture_time = datetime.fromisoformat(request.captureTime.replace('Z', '+00:00'))
        
        # Find existing ANPR read that matches this capture
        anpr_read = db.query(ANPRRead).filter(
            ANPRRead.license_plate == request.vrm,
            ANPRRead.camera_id == str(request.cameraIdentifier),
            ANPRRead.timestamp == capture_time
        ).first()
        
        if not anpr_read:
            # Create new ANPR read if it doesn't exist
            anpr_read = ANPRRead(
                license_plate=request.vrm,
                camera_id=str(request.cameraIdentifier),
                location=f"Feed:{request.feedIdentifier}, Source:{request.sourceIdentifier}, Camera:{request.cameraIdentifier}",
                timestamp=capture_time,
                confidence=0,
                direction=None,
                speed=None,
                lane=None
            )
            
            # Check for hotlist match
            hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == request.vrm).first()
            if hotlist_match:
                anpr_read.hotlist_match = True
                anpr_read.hotlist_id = hotlist_match.id
            
            db.add(anpr_read)
            db.commit()
            db.refresh(anpr_read)
        
        # Save binary image data to filesystem
        if request.binaryImage:
            try:
                # Decode base64 image
                image_data = base64.b64decode(request.binaryImage)
                
                # Generate filename
                image_extension = "jpg"  # Default to JPG
                if request.binaryDataType == "P":
                    filename = f"plate_{uuid.uuid4()}.{image_extension}"
                    filepath = UPLOAD_DIR / filename
                    
                    # Save image
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    
                    # Update ANPR read with image path
                    anpr_read.plate_image_path = str(filepath)
                    
                elif request.binaryDataType == "C":
                    filename = f"context_{uuid.uuid4()}.{image_extension}"
                    filepath = UPLOAD_DIR / filename
                    
                    # Save image
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    
                    # Update ANPR read with context image path
                    anpr_read.context_image_path = str(filepath)
                
                db.commit()
                
                logger.info(f"BOF addBinaryCaptureData: Saved {request.binaryDataType} image for plate {request.vrm}")
                
            except Exception as e:
                logger.error(f"Error saving binary image: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error saving binary image: {str(e)}")
        
        return BofCaptureResponse(
            success=True,
            message=f"Binary capture data processed successfully for plate {request.vrm}",
            read_id=anpr_read.id
        )
        
    except Exception as e:
        logger.error(f"BOF addBinaryCaptureData error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing binary capture data: {str(e)}")

# Helper function to parse compact capture strings
def parse_compact_capture(capture_string: str) -> dict:
    """Parse a pipe-delimited compact capture string into a dictionary"""
    parts = capture_string.split('|')
    if len(parts) < 7:
        raise ValueError("Invalid compact capture format")
    
    return {
        "signature": parts[0].strip(),
        "username": parts[1].strip(),
        "vrm": parts[2].strip(),
        "feed_id": int(parts[3].strip()),
        "source_id": int(parts[4].strip()),
        "camera_id": int(parts[5].strip()),
        "capture_date": parts[6].strip(),
        "latitude": float(parts[7].strip()) if len(parts) > 7 and parts[7].strip() else None,
        "longitude": float(parts[8].strip()) if len(parts) > 8 and parts[8].strip() else None,
        "camera_preset": int(parts[9].strip()) if len(parts) > 9 and parts[9].strip() else None,
        "camera_pan": parts[10].strip() if len(parts) > 10 else None,
        "camera_tilt": parts[11].strip() if len(parts) > 11 else None,
        "camera_zoom": parts[12].strip() if len(parts) > 12 else None,
        "confidence": int(parts[13].strip()) if len(parts) > 13 and parts[13].strip() else 0,
        "motion_toward_camera": parts[14].strip().lower() == 'true' if len(parts) > 14 else None
    }

# Sample connectivity check endpoint
@app.get("/anpr/connectivity")
async def get_connectivity_status():
    """Get connectivity status for dashboard"""
    # This is a placeholder - would normally check actual connectivity
    return {
        "status": "connected",
        "last_sync": datetime.utcnow().isoformat(),
        "devices_connected": 1
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)