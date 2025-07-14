"""
Third-party API integrations for ANPR system
BOF (British Optical Foundation) Protocol Implementation
"""

import json
import requests
import httpx
from datetime import datetime
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
import base64
import logging
from sqlalchemy.orm import Session
from models import ANPRRead, Hotlist
from schemas import ANPRReadResponse

logger = logging.getLogger(__name__)

class BOFConfig:
    """Configuration for BOF Management Server connection"""
    def __init__(self):
        self.host_name: Optional[str] = None
        self.host_ip: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.feed_identifier: Optional[str] = None
        self.source_identifier: Optional[str] = None
        self.camera_identifier: int = 1  # Always defaulted to 1
        self.enabled: bool = False

class HotlistSyncManager:
    """Simple hotlist synchronization manager"""
    
    def __init__(self, sync_url: str = None, api_key: str = None):
        self.sync_url = sync_url or "http://localhost:8000/anpr/hotlists/sync"
        self.api_key = api_key
        self.client = httpx.AsyncClient()
    
    async def sync_hotlists(self, db: Session) -> bool:
        """
        Sync hotlists from external source
        Can be configured to pull from various sources (REST API, file, etc.)
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            response = await self.client.get(
                f"{self.sync_url}",
                headers=headers
            )
            
            if response.status_code == 200:
                hotlists_data = response.json()
                
                # Process each hotlist
                for hotlist_data in hotlists_data.get('hotlists', []):
                    # Check if hotlist exists
                    existing = db.query(Hotlist).filter(
                        Hotlist.license_plate == hotlist_data['license_plate']
                    ).first()
                    
                    if not existing:
                        # Create new hotlist entry
                        hotlist = Hotlist(
                            license_plate=hotlist_data['license_plate'],
                            description=hotlist_data.get('description', ''),
                            category=hotlist_data.get('category', 'general'),
                            priority=hotlist_data.get('priority', 'medium'),
                            vehicle_make=hotlist_data.get('vehicle_make'),
                            vehicle_model=hotlist_data.get('vehicle_model'),
                            vehicle_color=hotlist_data.get('vehicle_color'),
                            created_at=datetime.now()
                        )
                        db.add(hotlist)
                
                db.commit()
                logger.info(f"Successfully synced {len(hotlists_data.get('hotlists', []))} hotlists")
                return True
                
        except Exception as e:
            logger.error(f"Hotlist sync failed: {str(e)}")
            return False
        
        return False

class BOFIntegration:
    """
    BOF (British Optical Foundation) Web Services Integration
    Implements sendCompactCapture and addBinaryCaptureData operations
    """
    
    def __init__(self, config: BOFConfig):
        self.config = config
        self.client = httpx.AsyncClient()
    
    async def send_compact_capture(self, anpr_read: ANPRReadResponse) -> bool:
        """
        Send ANPR read as compact capture (textual data)
        BOF sendCompactCapture operation
        """
        if not self.config.enabled:
            return True
            
        try:
            compact_string = self._build_compact_capture_string(anpr_read)
            
            # SOAP envelope for BOF sendCompactCapture
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:bof="http://bof.homeoffice.gov.uk/anpr">
    <soap:Header/>
    <soap:Body>
        <bof:sendCompactCapture>
            <bof:username>{self.config.username}</bof:username>
            <bof:password>{self.config.password}</bof:password>
            <bof:feedIdentifier>{self.config.feed_identifier}</bof:feedIdentifier>
            <bof:sourceIdentifier>{self.config.source_identifier}</bof:sourceIdentifier>
            <bof:cameraIdentifier>{self.config.camera_identifier}</bof:cameraIdentifier>
            <bof:compactCapture>{compact_string}</bof:compactCapture>
        </bof:sendCompactCapture>
    </soap:Body>
</soap:Envelope>"""

            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "sendCompactCapture"
            }
            
            response = await self.client.post(
                f"http://{self.config.host_ip}/bof/services/AnprService",
                data=soap_body,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent compact capture for plate: {anpr_read.license_plate}")
                return True
            else:
                logger.error(f"BOF sendCompactCapture failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"BOF sendCompactCapture error: {str(e)}")
            return False
    
    async def add_binary_capture_data(self, anpr_read: ANPRReadResponse, 
                                    image_data: bytes, data_type: str) -> bool:
        """
        Send binary image data (plate crop or context image)
        BOF addBinaryCaptureData operation
        
        Args:
            anpr_read: The ANPR read data
            image_data: Binary image data
            data_type: "plate" or "context"
        """
        if not self.config.enabled:
            return True
            
        try:
            # Encode image data
            encoded_data = base64.b64encode(image_data).decode('utf-8')
            
            # SOAP envelope for BOF addBinaryCaptureData
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:bof="http://bof.homeoffice.gov.uk/anpr">
    <soap:Header/>
    <soap:Body>
        <bof:addBinaryCaptureData>
            <bof:username>{self.config.username}</bof:username>
            <bof:password>{self.config.password}</bof:password>
            <bof:feedIdentifier>{self.config.feed_identifier}</bof:feedIdentifier>
            <bof:sourceIdentifier>{self.config.source_identifier}</bof:sourceIdentifier>
            <bof:cameraIdentifier>{self.config.camera_identifier}</bof:cameraIdentifier>
            <bof:plateNumber>{anpr_read.license_plate}</bof:plateNumber>
            <bof:captureDateTime>{anpr_read.timestamp.isoformat()}</bof:captureDateTime>
            <bof:dataType>{data_type}</bof:dataType>
            <bof:binaryData>{encoded_data}</bof:binaryData>
        </bof:addBinaryCaptureData>
    </soap:Body>
</soap:Envelope>"""

            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "addBinaryCaptureData"
            }
            
            response = await self.client.post(
                f"http://{self.config.host_ip}/bof/services/AnprService",
                data=soap_body,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent {data_type} image for plate: {anpr_read.license_plate}")
                return True
            else:
                logger.error(f"BOF addBinaryCaptureData failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"BOF addBinaryCaptureData error: {str(e)}")
            return False
    
    def _build_compact_capture_string(self, anpr_read: ANPRReadResponse) -> str:
        """
        Build compact capture string format for BOF
        Format: PlateNumber,DateTime,Location,Confidence,etc.
        """
        return f"{anpr_read.license_plate},{anpr_read.timestamp.isoformat()},{anpr_read.location},{anpr_read.confidence},{anpr_read.camera_id}"

class ANPRIntegrationManager:
    """Simplified integration manager for BOF-only operations"""
    
    def __init__(self):
        self.bof_config = BOFConfig()
        self.bof_integration = None
        self.hotlist_sync = HotlistSyncManager()
    
    async def initialize(self, bof_host: str, bof_username: str, bof_password: str, 
                        feed_id: str, source_id: str, hotlist_sync_url: str = None):
        """Initialize BOF integration"""
        self.bof_config.host_ip = bof_host
        self.bof_config.username = bof_username
        self.bof_config.password = bof_password
        self.bof_config.feed_identifier = feed_id
        self.bof_config.source_identifier = source_id
        self.bof_config.enabled = True
        
        self.bof_integration = BOFIntegration(self.bof_config)
        
        if hotlist_sync_url:
            self.hotlist_sync = HotlistSyncManager(hotlist_sync_url)
        
        logger.info("BOF integration initialized successfully")
    
    async def process_anpr_read(self, anpr_read: ANPRReadResponse, 
                              plate_image: bytes = None, context_image: bytes = None) -> bool:
        """
        Process ANPR read through BOF integration
        """
        if not self.bof_integration:
            logger.warning("BOF integration not initialized")
            return False
        
        success = True
        
        try:
            # Send compact capture (textual data)
            if not await self.bof_integration.send_compact_capture(anpr_read):
                success = False
            
            # Send plate image if available
            if plate_image and success:
                if not await self.bof_integration.add_binary_capture_data(anpr_read, plate_image, "plate"):
                    success = False
            
            # Send context image if available
            if context_image and success:
                if not await self.bof_integration.add_binary_capture_data(anpr_read, context_image, "context"):
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing ANPR read: {str(e)}")
            return False
    
    async def sync_hotlists(self, db: Session) -> bool:
        """Sync hotlists from configured source"""
        return await self.hotlist_sync.sync_hotlists(db)
    
    def get_connectivity_status(self) -> Dict[str, Any]:
        """Get current connectivity status"""
        return {
            "bof_enabled": self.bof_config.enabled,
            "bof_host": self.bof_config.host_ip,
            "bof_configured": bool(self.bof_config.host_ip and self.bof_config.username),
            "hotlist_sync_url": self.hotlist_sync.sync_url,
            "last_sync": datetime.now().isoformat()
        }

# Global integration manager instance
integration_manager = ANPRIntegrationManager() 