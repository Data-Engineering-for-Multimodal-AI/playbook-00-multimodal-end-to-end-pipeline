#!/usr/bin/env python3
"""
Fusion Engine Service
Combines telemetry and image data with late-arrival handling
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

from fastapi import FastAPI, Request
from google.cloud import pubsub_v1
from pydantic import BaseModel
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fusion Engine", version="2.0")

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
FUSION_WINDOW_SECONDS = int(os.getenv("FUSION_WINDOW_SECONDS", "30"))

# Initialize clients
publisher = pubsub_v1.PublisherClient()

# Pub/Sub topics
FUSED_TOPIC = f"projects/{PROJECT_ID}/topics/fused.v1"

# In-memory fusion state (use Redis/Datastore for production)
fusion_windows = defaultdict(dict)  # {session_id: {trace_id: data}}

class TelemetryMessage(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    features: Dict[str, Any]

class ImageMessage(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    image_uri: str
    camera_id: str

class FusedRecord(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    telemetry_data: Dict[str, Any]
    image_uris: List[str]
    fusion_metadata: Dict[str, Any]

def should_fuse_now(session_id: str, trace_id: str) -> bool:
    """Determine if we should fuse the current data"""
    if session_id not in fusion_windows:
        return False
    
    window = fusion_windows[session_id].get(trace_id, {})
    
    # Fuse if we have both telemetry and images
    has_telemetry = "telemetry" in window
    # Wait for every camera's image (the dataset has two per reading); fusing on the first dropped the second
    has_images = len(window.get("images", [])) >= int(os.getenv("IMAGES_PER_READING", "2"))
    
    return has_telemetry and has_images

def create_fused_record(session_id: str, trace_id: str) -> Optional[FusedRecord]:
    """Create fused record from available data"""
    try:
        if session_id not in fusion_windows:
            return None
        
        window = fusion_windows[session_id].get(trace_id, {})
        if not window:
            return None
        
        telemetry_data = window.get("telemetry", {})
        images = window.get("images", [])
        
        fused_record = FusedRecord(
            timestamp=telemetry_data.get("timestamp", datetime.now().isoformat()),
            session_id=session_id,
            trace_id=trace_id,
            telemetry_data=telemetry_data,
            image_uris=[img["image_uri"] for img in images],
            fusion_metadata={
                "images_count": len(images),
                "fusion_time": datetime.now().isoformat(),
                "window_size_seconds": FUSION_WINDOW_SECONDS
            }
        )
        
        # Clean up the window
        del fusion_windows[session_id][trace_id]
        if not fusion_windows[session_id]:
            del fusion_windows[session_id]
        
        return fused_record
        
    except Exception as e:
        logger.error(f"Failed to create fused record: {e}")
        return None

async def publish_fused_record(fused_record: FusedRecord):
    """Publish fused record to downstream services"""
    try:
        message_data = fused_record.model_dump_json().encode("utf-8")
        future = publisher.publish(FUSED_TOPIC, message_data)
        message_id = future.result()
        
        logger.info(f"Published fused record {fused_record.trace_id} - Message ID: {message_id}")
        
    except Exception as e:
        logger.error(f"Failed to publish fused record: {e}")

@app.post("/webhook/telemetry")
async def handle_telemetry(request: Request):
    """Handle incoming telemetry data from Pub/Sub"""
    try:
        # Parse Pub/Sub message
        body = await request.body()
        envelope = json.loads(body)
        message_data = envelope.get("message", {}).get("data", "")
        
        # Decode message
        import base64
        decoded_data = base64.b64decode(message_data).decode("utf-8")
        telemetry = json.loads(decoded_data)
        
        session_id = telemetry["session_id"]
        trace_id = telemetry["trace_id"]
        
        # Store in fusion window
        if session_id not in fusion_windows:
            fusion_windows[session_id] = {}
        if trace_id not in fusion_windows[session_id]:
            fusion_windows[session_id][trace_id] = {}
        
        fusion_windows[session_id][trace_id]["telemetry"] = telemetry
        
        logger.info(f"Received telemetry for {trace_id}")
        
        # Check if we can fuse now
        if should_fuse_now(session_id, trace_id):
            fused_record = create_fused_record(session_id, trace_id)
            if fused_record:
                await publish_fused_record(fused_record)
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Failed to handle telemetry: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/webhook/images")
async def handle_images(request: Request):
    """Handle incoming image metadata from Pub/Sub"""
    try:
        # Parse Pub/Sub message
        body = await request.body()
        envelope = json.loads(body)
        message_data = envelope.get("message", {}).get("data", "")
        
        # Decode message
        import base64
        decoded_data = base64.b64decode(message_data).decode("utf-8")
        image_data = json.loads(decoded_data)
        
        session_id = image_data["session_id"]
        trace_id = image_data["trace_id"]
        
        # Store in fusion window
        if session_id not in fusion_windows:
            fusion_windows[session_id] = {}
        if trace_id not in fusion_windows[session_id]:
            fusion_windows[session_id][trace_id] = {}
        if "images" not in fusion_windows[session_id][trace_id]:
            fusion_windows[session_id][trace_id]["images"] = []
        
        fusion_windows[session_id][trace_id]["images"].append(image_data)
        
        logger.info(f"Received image metadata for {trace_id} ({image_data['camera_id']})")
        
        # Check if we can fuse now
        if should_fuse_now(session_id, trace_id):
            fused_record = create_fused_record(session_id, trace_id)
            if fused_record:
                await publish_fused_record(fused_record)
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Failed to handle image metadata: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/status")
async def get_fusion_status():
    """Get current fusion engine status"""
    active_sessions = len(fusion_windows)
    total_windows = sum(len(windows) for windows in fusion_windows.values())
    
    return {
        "active_sessions": active_sessions,
        "active_windows": total_windows,
        "fusion_window_seconds": FUSION_WINDOW_SECONDS,
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "fusion_engine", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
