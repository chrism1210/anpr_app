from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import uvicorn
import asyncio
import logging
import os
import uuid
import io
import zipfile
import csv
import base64
from pathlib import Path

from database import SessionLocal, engine, Base
from models import (
    Hotlist, ANPRRead, DeviceSource, HotlistRevision, HotlistRepository
)
from schemas import (
    HotlistCreate, HotlistUpdate, HotlistResponse, ANPRReadCreate, ANPRReadResponse,
    BofHotlistRevisions, BofHotlistData, ExternalHotlistRevisions, DeviceSourceCreate,
    DeviceSourceResponse, GetHotlistRepoStatusRequest, GetHotlistStatusRequest,
    SetHotlistStatusRequest, GetHotlistUpdatesRequest, GetHotlistUpdatesRestrictSizeRequest,
    GetMultipleHotlistUpdatesRequest, GetMultipleHotlistUpdatesRestrictSizeRequest
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

# Helper functions for BOF hotlist synchronization
def get_or_create_hotlist_repository(db: Session) -> HotlistRepository:
    """Get or create the global hotlist repository"""
    repo = db.query(HotlistRepository).first()
    if not repo:
        repo = HotlistRepository(revision=1)
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return repo

def increment_hotlist_repository_revision(db: Session):
    """Increment the global hotlist repository revision"""
    repo = get_or_create_hotlist_repository(db)
    repo.revision += 1
    repo.updated_at = datetime.utcnow()
    db.commit()

def get_or_create_device_source(db: Session, source_id: str) -> DeviceSource:
    """Get or create a device source"""
    device = db.query(DeviceSource).filter(DeviceSource.source_id == source_id).first()
    if not device:
        device = DeviceSource(
            source_id=source_id,
            name=f"Device {source_id}",
            description=f"Auto-created device for source {source_id}"
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    return device

def get_or_create_hotlist_revision(db: Session, hotlist_id: int, device_source_id: int, hotlist_name: str) -> HotlistRevision:
    """Get or create a hotlist revision tracking entry"""
    revision = db.query(HotlistRevision).filter(
        HotlistRevision.hotlist_id == hotlist_id,
        HotlistRevision.device_source_id == device_source_id
    ).first()
    
    if not revision:
        # Get the current hotlist revision
        hotlist = db.query(Hotlist).filter(Hotlist.id == hotlist_id).first()
        revision = HotlistRevision(
            hotlist_id=hotlist_id,
            device_source_id=device_source_id,
            hotlist_name=hotlist_name,
            latest_revision=hotlist.revision if hotlist else 1,
            external_system_revision=-1
        )
        db.add(revision)
        db.commit()
        db.refresh(revision)
    
    return revision

def generate_hotlist_csv_data(hotlists: List[Hotlist]) -> str:
    """Generate CSV data for hotlists in BOF 16-column format"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    for hotlist in hotlists:
        # BOF 16-column format
        row = [
            hotlist.license_plate,           # VRM
            hotlist.vehicle_make or "",      # Vehicle Make
            hotlist.vehicle_model or "",     # Vehicle Model
            hotlist.vehicle_color or "",     # Vehicle Colour
            "STOP" if hotlist.priority == "high" else "SILENT",  # Action
            "",                              # Warning Markers
            hotlist.category.upper(),        # Reason
            "",                              # NIM (5x5x5) Code
            hotlist.description,             # Information/Action
            "",                              # Force & Area
            "",                              # Weed Date
            "",                              # PNC ID
            "Unclassified",                  # GPMS Marking
            "",                              # CAD Information
            "",                              # Spare 1
            ""                               # Spare 2
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

# API Routes - Hotlist Management
@app.post("/api/hotlists", response_model=HotlistResponse)
async def create_hotlist(hotlist: HotlistCreate, db: Session = Depends(get_db)):
    """Create a new hotlist entry"""
    db_hotlist = Hotlist(**hotlist.model_dump())
    db.add(db_hotlist)
    db.commit()
    db.refresh(db_hotlist)
    
    # Increment global repository revision
    increment_hotlist_repository_revision(db)
    
    return db_hotlist

@app.get("/api/hotlists", response_model=List[HotlistResponse])
async def get_hotlists(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all hotlist entries with optional search"""
    query = db.query(Hotlist)
    
    if search:
        query = query.filter(
            Hotlist.license_plate.ilike(f"%{search}%") |
            Hotlist.description.ilike(f"%{search}%") |
            Hotlist.category.ilike(f"%{search}%")
        )
    
    hotlists = query.offset(skip).limit(limit).all()
    return hotlists

@app.get("/api/hotlists/{hotlist_id}", response_model=HotlistResponse)
async def get_hotlist(hotlist_id: int, db: Session = Depends(get_db)):
    """Get a specific hotlist entry"""
    hotlist = db.query(Hotlist).filter(Hotlist.id == hotlist_id).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist entry not found")
    return hotlist

@app.put("/api/hotlists/{hotlist_id}", response_model=HotlistResponse)
async def update_hotlist(hotlist_id: int, hotlist_update: HotlistUpdate, db: Session = Depends(get_db)):
    """Update a hotlist entry"""
    hotlist = db.query(Hotlist).filter(Hotlist.id == hotlist_id).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist entry not found")
    
    update_data = hotlist_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hotlist, field, value)
    
    # Increment the hotlist revision
    hotlist.revision += 1
    hotlist.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(hotlist)
    
    # Increment global repository revision
    increment_hotlist_repository_revision(db)
    
    return hotlist

@app.delete("/api/hotlists/{hotlist_id}")
async def delete_hotlist(hotlist_id: int, db: Session = Depends(get_db)):
    """Delete a hotlist entry"""
    hotlist = db.query(Hotlist).filter(Hotlist.id == hotlist_id).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist entry not found")
    
    db.delete(hotlist)
    db.commit()
    
    # Increment global repository revision
    increment_hotlist_repository_revision(db)
    
    return {"message": "Hotlist entry deleted successfully"}

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
    license_plate: str = Form(...),
    camera_id: str = Form(...),
    location: str = Form(...),
    confidence: int = Form(0),
    direction: Optional[str] = Form(None),
    speed: Optional[int] = Form(None),
    lane: Optional[int] = Form(None),
    timestamp: Optional[str] = Form(None),
    plate_image: Optional[UploadFile] = File(None),
    context_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Enhanced ANPR read ingestion with binary image support
    Accepts multipart form data with optional image files
    """
    
    # Parse timestamp if provided
    parsed_timestamp = None
    if timestamp:
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            parsed_timestamp = datetime.utcnow()
    else:
        parsed_timestamp = datetime.utcnow()
    
    # Create ANPR read record
    db_anpr_read = ANPRRead(
        license_plate=license_plate,
        camera_id=camera_id,
        location=location,
        confidence=confidence,
        direction=direction,
        speed=speed,
        lane=lane,
        timestamp=parsed_timestamp
    )
    
    # Check if this plate is on any hotlist
    hotlist_match = db.query(Hotlist).filter(Hotlist.license_plate == license_plate).first()
    if hotlist_match:
        db_anpr_read.hotlist_match = True
        db_anpr_read.hotlist_id = hotlist_match.id
    
    # Save images to filesystem and update database record
    plate_image_path = None
    context_image_path = None
    
    if plate_image:
        try:
            # Generate unique filename for plate image
            file_extension = plate_image.filename.split('.')[-1] if '.' in plate_image.filename else 'jpg'
            unique_filename = f"plate_{uuid.uuid4()}.{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            # Save the file
            with open(file_path, "wb") as buffer:
                content = await plate_image.read()
                buffer.write(content)
            
            plate_image_path = str(file_path)
            db_anpr_read.plate_image_path = plate_image_path
            
        except Exception as e:
            logger.error(f"Error saving plate image: {e}")
    
    if context_image:
        try:
            # Generate unique filename for context image
            file_extension = context_image.filename.split('.')[-1] if '.' in context_image.filename else 'jpg'
            unique_filename = f"context_{uuid.uuid4()}.{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            # Save the file
            with open(file_path, "wb") as buffer:
                content = await context_image.read()
                buffer.write(content)
            
            context_image_path = str(file_path)
            db_anpr_read.context_image_path = context_image_path
            
        except Exception as e:
            logger.error(f"Error saving context image: {e}")
    
    db.add(db_anpr_read)
    db.commit()
    db.refresh(db_anpr_read)
    
    return ANPRReadResponse.model_validate(db_anpr_read)

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
    repo = get_or_create_hotlist_repository(db)
    
    # If the revision number provided is the same as current, return -1 (no changes)
    if revisionnumber == repo.revision:
        return -1
    
    # Otherwise return the current revision
    return repo.revision

@app.get("/bof/services/UpdateHotlistsService/getHotlistStatus")
async def get_hotlist_status(
    sourceID: str,
    db: Session = Depends(get_db)
) -> List[BofHotlistRevisions]:
    """
    BOF: Get hotlist status for a specific source
    Returns array of BofHotlistRevisions for all hotlists allocated to this source
    """
    # Get or create the device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get all active hotlists
    hotlists = db.query(Hotlist).filter(Hotlist.is_active == True).all()
    
    result = []
    for hotlist in hotlists:
        # Create hotlist name from license plate for simplicity
        hotlist_name = f"hotlist_{hotlist.license_plate}"
        
        # Get or create revision tracking
        revision = get_or_create_hotlist_revision(db, hotlist.id, device_source.id, hotlist_name)
        
        # Update latest revision from hotlist
        revision.latest_revision = hotlist.revision
        db.commit()
        
        result.append(BofHotlistRevisions(
            hotlist_name=hotlist_name,
            latest_revision=hotlist.revision,
            external_system_revision=revision.external_system_revision,
            is_allocated=revision.is_allocated
        ))
    
    return result

@app.post("/bof/services/UpdateHotlistsService/setHotlistStatus")
async def set_hotlist_status(
    sourceID: str,
    hotlistsAndRevisions: List[ExternalHotlistRevisions],
    db: Session = Depends(get_db)
):
    """
    BOF: Set hotlist status for a specific source
    Updates the external system revision for each hotlist
    """
    # Get or create the device source
    device_source = get_or_create_device_source(db, sourceID)
    
    for hotlist_revision in hotlistsAndRevisions:
        # Find the hotlist by name (extract license plate from name)
        hotlist_name = hotlist_revision.hotlist_name
        license_plate = hotlist_name.replace("hotlist_", "")
        
        hotlist = db.query(Hotlist).filter(Hotlist.license_plate == license_plate).first()
        if hotlist:
            # Update the revision tracking
            revision = get_or_create_hotlist_revision(db, hotlist.id, device_source.id, hotlist_name)
            revision.external_system_revision = hotlist_revision.current_revision
            db.commit()
    
    return {"status": "success"}

@app.get("/bof/services/UpdateHotlistsService/getHotlistUpdates")
async def get_hotlist_updates(
    sourceID: str,
    hotlistname: str,
    db: Session = Depends(get_db)
) -> BofHotlistData:
    """
    BOF: Get hotlist updates for a specific hotlist
    Returns BofHotlistData with ZIP file containing updates
    """
    # Extract license plate from hotlist name
    license_plate = hotlistname.replace("hotlist_", "")
    
    # Get the hotlist
    hotlist = db.query(Hotlist).filter(Hotlist.license_plate == license_plate).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist not found")
    
    # Get device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get or create revision tracking
    revision = get_or_create_hotlist_revision(db, hotlist.id, device_source.id, hotlistname)
    
    # Generate CSV data for the hotlist
    csv_data = generate_hotlist_csv_data([hotlist])
    
    # Create ZIP file with hotlist data
    zip_data = create_hotlist_zip(hotlistname, sourceID, csv_data)
    
    # Encode binary data as base64 for JSON response
    zip_data_b64 = base64.b64encode(zip_data).decode('utf-8')
    
    return BofHotlistData(
        hotlist_name=hotlistname,
        latest_revision=hotlist.revision,
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
    BOF: Get hotlist updates with size restriction
    Returns BofHotlistData with ZIP file containing updates or too_big flag
    """
    # Extract license plate from hotlist name
    license_plate = hotlistname.replace("hotlist_", "")
    
    # Get the hotlist
    hotlist = db.query(Hotlist).filter(Hotlist.license_plate == license_plate).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist not found")
    
    # Get device source
    device_source = get_or_create_device_source(db, sourceID)
    
    # Get or create revision tracking
    revision = get_or_create_hotlist_revision(db, hotlist.id, device_source.id, hotlistname)
    
    # Generate CSV data for the hotlist
    csv_data = generate_hotlist_csv_data([hotlist])
    
    # Create ZIP file with hotlist data
    zip_data = create_hotlist_zip(hotlistname, sourceID, csv_data)
    
    # Check if ZIP file is too big
    if len(zip_data) > size:
        return BofHotlistData(
            hotlist_name=hotlistname,
            latest_revision=hotlist.revision,
            hotlist_deltas=None,
            is_file_too_big=True
        )
    
    # Encode binary data as base64 for JSON response
    zip_data_b64 = base64.b64encode(zip_data).decode('utf-8')
    
    return BofHotlistData(
        hotlist_name=hotlistname,
        latest_revision=hotlist.revision,
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