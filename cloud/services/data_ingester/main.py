#!/usr/bin/env python3
"""
Data Ingester Service
Reads Future Factories multimodal data from GCS, validates schemas, publishes to Pub/Sub
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from google.cloud import storage, pubsub_v1
import jsonschema
from pydantic import BaseModel

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/data_ingester.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Ingester", version="2.0")

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
GCS_BUCKET = os.getenv("GCS_BUCKET", f"{PROJECT_ID}-resolve-binaries")
MULTIMODAL_PATH = "datasets/future-factories/multimodal-2024-data/Batch 1"

# Initialize clients
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()

# Pub/Sub topics
TELEMETRY_TOPIC = f"projects/{PROJECT_ID}/topics/telemetry.v1"
IMAGES_TOPIC = f"projects/{PROJECT_ID}/topics/images.v1"

class SensorReading(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    sensor_values: Dict[str, Any]
    image_refs: List[str]

class ProcessingRequest(BaseModel):
    json_files: List[str] = ["data_31000.json", "data_32000.json"]
    session_id: Optional[str] = None

def validate_sensor_data(sensor_values: Dict[str, Any]) -> bool:
    """Validate sensor data against expected schema"""
    required_fields = [
        "Q_VFD1_Temperature", "Q_VFD2_Temperature", "Q_VFD3_Temperature", "Q_VFD4_Temperature",
        "M_Conv1_Speed_mmps", "M_Conv2_Speed_mmps", "M_Conv3_Speed_mmps", "M_Conv4_Speed_mmps",
        "I_SafetyDoor1_Status", "I_SafetyDoor2_Status", "Q_Cell_CycleCount"
    ]
    
    for field in required_fields:
        if field not in sensor_values:
            logger.warning(f"Missing required sensor field: {field}")
            return False
    
    # Validate temperature ranges
    for i in range(1, 5):
        temp_field = f"Q_VFD{i}_Temperature"
        temp = sensor_values.get(temp_field, 0)
        if not (0 <= temp <= 150):  # Reasonable temperature range
            logger.warning(f"Temperature out of range for {temp_field}: {temp}")
            return False
    
    return True

def read_multimodal_data(json_file: str) -> Dict[str, Any]:
    """Read multimodal JSON data from GCS"""
    try:
        bucket = storage_client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{MULTIMODAL_PATH}/{json_file}")
        data = json.loads(blob.download_as_text())
        logger.info(f"Read {len(data)} timestamped records from {json_file}")
        return data
    except Exception as e:
        logger.error(f"Failed to read {json_file}: {e}")
        raise

def publish_telemetry(sensor_reading: SensorReading) -> str:
    """Publish sensor data to telemetry topic"""
    try:
        telemetry_record = {
            "timestamp": sensor_reading.timestamp,
            "session_id": sensor_reading.session_id,
            "trace_id": sensor_reading.trace_id,
            "features": {
                # Temperature readings
                "vfd_temperatures": [
                    sensor_reading.sensor_values.get(f"Q_VFD{i}_Temperature", 0) for i in range(1, 5)
                ],
                # Conveyor speeds
                "conveyor_speeds": [
                    sensor_reading.sensor_values.get(f"M_Conv{i}_Speed_mmps", 0) for i in range(1, 5)
                ],
                # Robot data
                "robot_grippers": {
                    f"r0{i}": {
                        "position": sensor_reading.sensor_values.get(f"I_R0{i}_Gripper_Pot", 0),
                        "load": sensor_reading.sensor_values.get(f"I_R0{i}_Gripper_Load", 0)
                    } for i in range(1, 5)
                },
                "robot_joints": {
                    "r01": {
                        "shoulder": sensor_reading.sensor_values.get("M_R01_SJointAngle_Degree", 0),
                        "elbow": sensor_reading.sensor_values.get("M_R01_LJointAngle_Degree", 0),
                        "wrist": sensor_reading.sensor_values.get("M_R01_UJointAngle_Degree", 0)
                    }
                },
                # Safety
                "safety_doors": {
                    "door1": sensor_reading.sensor_values.get("I_SafetyDoor1_Status", True),
                    "door2": sensor_reading.sensor_values.get("I_SafetyDoor2_Status", True)
                },
                "cycle_count": sensor_reading.sensor_values.get("Q_Cell_CycleCount", 0),
                # Raw data for reference
                "raw_sensor_data": sensor_reading.sensor_values
            }
        }
        
        # Publish to Pub/Sub
        message_data = json.dumps(telemetry_record).encode("utf-8")
        future = publisher.publish(TELEMETRY_TOPIC, message_data)
        message_id = future.result()
        
        logger.info(f"Published telemetry for {sensor_reading.timestamp} - Message ID: {message_id}")
        return message_id
        
    except Exception as e:
        logger.error(f"Failed to publish telemetry: {e}")
        raise

def publish_image_metadata(sensor_reading: SensorReading) -> List[str]:
    """Publish image metadata to images topic"""
    message_ids = []
    
    try:
        for i, image_ref in enumerate(sensor_reading.image_refs):
            # Convert image reference to GCS path
            gcs_path = f"gs://{GCS_BUCKET}/{MULTIMODAL_PATH}/{image_ref.replace('Dataset/', '')}"
            
            image_record = {
                "timestamp": sensor_reading.timestamp,
                "session_id": sensor_reading.session_id,
                "trace_id": sensor_reading.trace_id,
                "image_uri": gcs_path,
                "camera_id": f"camera_{i}",
                "image_type": "manufacturing_cell",
                "original_ref": image_ref
            }
            
            message_data = json.dumps(image_record).encode("utf-8")
            future = publisher.publish(IMAGES_TOPIC, message_data)
            message_id = future.result()
            message_ids.append(message_id)
            
        logger.info(f"Published {len(message_ids)} image records for {sensor_reading.timestamp}")
        return message_ids
        
    except Exception as e:
        logger.error(f"Failed to publish image metadata: {e}")
        raise

@app.post("/ingest")
async def ingest_data(request: ProcessingRequest):
    """Ingest multimodal data from GCS and publish to Pub/Sub topics"""
    
    session_id = request.session_id or f"ff-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    processed_records = 0
    published_telemetry = 0
    published_images = 0
    
    logger.info(f"Starting data ingestion for session {session_id}")
    
    try:
        for json_file in request.json_files:
            logger.info(f"Processing {json_file}...")
            
            # Read multimodal data
            data = read_multimodal_data(json_file)
            
            # Process each timestamped record
            for timestamp, record_data in data.items():
                trace_id = str(uuid.uuid4())
                
                sensor_values = record_data.get("Sensor_values", {})
                image_refs = record_data.get("Images", [])
                
                # Validate sensor data
                if not validate_sensor_data(sensor_values):
                    logger.warning(f"Skipping record {timestamp} - validation failed")
                    continue
                
                # Create sensor reading
                sensor_reading = SensorReading(
                    timestamp=timestamp,
                    session_id=session_id,
                    trace_id=trace_id,
                    sensor_values=sensor_values,
                    image_refs=image_refs
                )
                
                # Publish telemetry data
                telemetry_msg_id = publish_telemetry(sensor_reading)
                published_telemetry += 1
                
                # Publish image metadata
                if image_refs:
                    image_msg_ids = publish_image_metadata(sensor_reading)
                    published_images += len(image_msg_ids)
                
                processed_records += 1
                
                # Production rate limiting to prevent overwhelming downstream services
                if processed_records >= 100:
                    logger.info("Rate limit reached - processed 100 records per batch")
                    break
            
            if processed_records >= 100:
                break
        
        result = {
            "session_id": session_id,
            "processed_records": processed_records,
            "published_telemetry": published_telemetry,
            "published_images": published_images,
            "status": "success"
        }
        
        logger.info(f"Ingestion complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "data_ingester", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
