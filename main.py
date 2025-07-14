from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse
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
from pathlib import Path

from database import SessionLocal, engine, Base
from models import Hotlist, ANPRRead
from schemas import HotlistCreate, HotlistUpdate, HotlistResponse, ANPRReadCreate, ANPRReadResponse

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

# Frontend Routes
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
    
    update_data = hotlist_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hotlist, field, value)
    
    db.commit()
    db.refresh(hotlist)
    return hotlist

@app.delete("/api/hotlists/{hotlist_id}")
async def delete_hotlist(hotlist_id: int, db: Session = Depends(get_db)):
    """Delete a hotlist entry"""
    hotlist = db.query(Hotlist).filter(Hotlist.id == hotlist_id).first()
    if not hotlist:
        raise HTTPException(status_code=404, detail="Hotlist entry not found")
    
    db.delete(hotlist)
    db.commit()
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
    
    if plate_image and plate_image.size > 0:
        # Generate unique filename
        file_extension = Path(plate_image.filename).suffix if plate_image.filename else '.jpg'
        filename = f"plate_{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await plate_image.read()
            buffer.write(content)
        
        plate_image_path = f"/static/uploads/{filename}"
        logger.info(f"Saved plate image: {plate_image_path} ({len(content)} bytes)")
    
    if context_image and context_image.size > 0:
        # Generate unique filename  
        file_extension = Path(context_image.filename).suffix if context_image.filename else '.jpg'
        filename = f"context_{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await context_image.read()
            buffer.write(content)
        
        context_image_path = f"/static/uploads/{filename}"
        logger.info(f"Saved context image: {context_image_path} ({len(content)} bytes)")
    
    # Update database record with image paths
    if plate_image_path:
        db_anpr_read.plate_image_path = plate_image_path
    if context_image_path:
        db_anpr_read.context_image_path = context_image_path
    
    # Save to database
    db.add(db_anpr_read)
    db.commit()
    db.refresh(db_anpr_read)
    
    # Convert to response model
    anpr_response = ANPRReadResponse.model_validate(db_anpr_read)
    
    # Process images for BOF integration if provided
    plate_image_data = None
    context_image_data = None
    
    if plate_image and plate_image.size > 0:
        # Re-read the file for BOF integration
        await plate_image.seek(0)
        plate_image_data = await plate_image.read()
    
    if context_image and context_image.size > 0:
        # Re-read the file for BOF integration
        await context_image.seek(0)
        context_image_data = await context_image.read()
    
    # Process through BOF integration with images
    return anpr_response

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
    """Get a specific ANPR read"""
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

# Sample hotlist sync endpoint for demonstration
@app.get("/anpr/hotlists/sync")
async def sample_hotlist_sync():
    """Sample hotlist sync endpoint that returns demo data"""
    return {
        "hotlists": [
            {
                "license_plate": "ABC123",
                "description": "Stolen vehicle from Manchester",
                "category": "stolen",
                "priority": "high",
                "vehicle_make": "Ford",
                "vehicle_model": "Focus",
                "vehicle_color": "Blue"
            },
            {
                "license_plate": "XYZ789",
                "description": "Wanted in connection with robbery",
                "category": "wanted",
                "priority": "high",
                "vehicle_make": "BMW",
                "vehicle_model": "X5",
                "vehicle_color": "Black"
            },
            {
                "license_plate": "TEST456",
                "description": "Vehicle of interest - surveillance",
                "category": "surveillance",
                "priority": "medium",
                "vehicle_make": "Toyota",
                "vehicle_model": "Camry",
                "vehicle_color": "Silver"
            }
        ]
    }

# API Routes - System Status
@app.get("/anpr/connectivity")
async def get_connectivity():
    """Get connectivity status for dashboard display"""
    return {"status": "disconnected", "message": "No integrations configured"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 