#!/usr/bin/env python3
"""
AI Planner Service
Enhanced multimodal AI planning using Gemini with historical context from Future Factories data
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from google.cloud import storage, pubsub_v1, bigquery
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from pydantic import BaseModel
import httpx

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/ai_planner.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Planner", version="2.0")

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
GCS_BUCKET = "your-project-id-resolve-binaries"
SAFETY_API_URL = os.getenv("SAFETY_API_URL", "http://localhost:8083")

# Initialize clients
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
bigquery_client = bigquery.Client()
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Initialize Gemini model
gemini_model = GenerativeModel("gemini-2.5-flash-lite")

# Pub/Sub topics
ACTIONS_TOPIC = f"projects/{PROJECT_ID}/topics/actions.v1"

class FusedRecord(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    telemetry_data: Dict[str, Any]
    image_uris: List[str]
    historical_context: Optional[Dict[str, Any]] = None

class ActionPlan(BaseModel):
    plan_id: str
    session_id: str
    trace_id: str
    reasoning: str
    confidence: float
    actions: List[Dict[str, Any]]
    historical_analysis: Optional[Dict[str, Any]] = None

class PlanningRequest(BaseModel):
    fused_record: FusedRecord

def get_historical_baselines(components: List[str]) -> Dict[str, Any]:
    """Get historical baselines for components from BigQuery"""
    try:
        # Query historical baselines
        components_str = "', '".join(components)
        query = f"""
        SELECT component, metric, mean, std, percentile_95, sample_count
        FROM `{PROJECT_ID}.resolve.historical_baselines`
        WHERE component IN ('{components_str}')
        ORDER BY component, metric
        """
        
        query_job = bigquery_client.query(query)
        results = query_job.result()
        
        baselines = {}
        for row in results:
            component = row.component
            if component not in baselines:
                baselines[component] = {}
            
            baselines[component][row.metric] = {
                "mean": row.mean,
                "std": row.std,
                "percentile_95": row.percentile_95,
                "sample_count": row.sample_count
            }
        
        logger.info(f"Retrieved baselines for {len(baselines)} components")
        return baselines
        
    except Exception as e:
        logger.error(f"Failed to get historical baselines: {e}")
        return {}

def analyze_deviations(current_data: Dict[str, Any], baselines: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze current readings against historical baselines"""
    deviations = {}
    
    try:
        # Analyze VFD temperatures
        vfd_temps = current_data.get("features", {}).get("vfd_temperatures", [])
        for i, temp in enumerate(vfd_temps, 1):
            robot_component = f"r0{i}"
            if robot_component in baselines:
                for metric, baseline in baselines[robot_component].items():
                    if "temperature" in metric.lower():
                        deviation = abs(temp - baseline["mean"]) / baseline["std"] if baseline["std"] > 0 else 0
                        deviations[f"vfd{i}_temperature"] = {
                            "current": temp,
                            "baseline_mean": baseline["mean"],
                            "baseline_std": baseline["std"],
                            "deviation_score": deviation,
                            "status": "critical" if deviation > 3 else "warning" if deviation > 2 else "normal"
                        }
        
        # Analyze conveyor speeds
        conveyor_speeds = current_data.get("features", {}).get("conveyor_speeds", [])
        if "conveyor_system" in baselines:
            for i, speed in enumerate(conveyor_speeds, 1):
                for metric, baseline in baselines["conveyor_system"].items():
                    if f"conv{i}" in metric.lower() or "speed" in metric.lower():
                        deviation = abs(speed - baseline["mean"]) / baseline["std"] if baseline["std"] > 0 else 0
                        deviations[f"conv{i}_speed"] = {
                            "current": speed,
                            "baseline_mean": baseline["mean"],
                            "baseline_std": baseline["std"],
                            "deviation_score": deviation,
                            "status": "critical" if deviation > 3 else "warning" if deviation > 2 else "normal"
                        }
        
        logger.info(f"Analyzed {len(deviations)} metrics for deviations")
        return deviations
        
    except Exception as e:
        logger.error(f"Failed to analyze deviations: {e}")
        return {}

def download_image_for_analysis(image_uri: str) -> Optional[Part]:
    """Download image from GCS for Gemini analysis"""
    try:
        # Parse GCS URI
        if not image_uri.startswith("gs://"):
            return None
        
        # Extract bucket and path
        uri_parts = image_uri.replace("gs://", "").split("/", 1)
        bucket_name = uri_parts[0]
        blob_path = uri_parts[1]
        
        # Download image
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        image_data = blob.download_as_bytes()
        
        # Create image part for Gemini
        image_part = Part.from_data(mime_type="image/png", data=image_data)
        return image_part
        
    except Exception as e:
        logger.error(f"Failed to download image {image_uri}: {e}")
        return None

def generate_enhanced_prompt(fused_record: FusedRecord, deviations: Dict[str, Any]) -> str:
    """Generate enhanced prompt with historical context"""
    
    telemetry = fused_record.telemetry_data.get("features", {})
    
    prompt = f"""
You are an expert AI system analyzing a Future Factories manufacturing cell with historical context.

CURRENT SITUATION (Timestamp: {fused_record.timestamp}):

REAL-TIME SENSOR DATA:
- VFD Temperatures: {telemetry.get('vfd_temperatures', [])}°C
- Conveyor Speeds: {telemetry.get('conveyor_speeds', [])} mm/s
- Robot Grippers: {json.dumps(telemetry.get('robot_grippers', {}), indent=2)}
- Robot Joints: {json.dumps(telemetry.get('robot_joints', {}), indent=2)}
- Safety Doors: {telemetry.get('safety_doors', {})}
- Cycle Count: {telemetry.get('cycle_count', 0)}

HISTORICAL ANALYSIS:
"""

    # Add deviation analysis
    if deviations:
        prompt += "\nDEVIATIONS FROM HISTORICAL BASELINES:\n"
        for metric, deviation in deviations.items():
            status = deviation['status'].upper()
            prompt += f"- {metric}: {deviation['current']:.1f} (baseline: {deviation['baseline_mean']:.1f} ± {deviation['baseline_std']:.1f}) - {status}\n"
    else:
        prompt += "\n- All readings within normal historical ranges\n"
    
    prompt += f"""

SYNCHRONIZED IMAGES: Manufacturing cell with robots and conveyors (provided separately)

ANALYSIS TASKS:
1. **Historical Context**: Compare current readings to historical baselines
2. **Multimodal Correlation**: Does the visual state match sensor readings and historical patterns?
3. **Anomaly Detection**: Identify deviations from normal operational patterns
4. **Predictive Assessment**: Based on historical trends, what issues might develop?
5. **Action Recommendations**: What actions should be taken based on current + historical analysis?

AVAILABLE ACTIONS:
- emergency_stop: Immediate halt (for critical issues)
- reduce_speed: Slow down operations (for warnings)
- alert_maintenance: Schedule maintenance (for developing issues)
- log_incident: Record for analysis (for monitoring)

Provide analysis in JSON format:
{{
    "historical_context": {{
        "deviations_detected": ["list of significant deviations"],
        "trend_analysis": "overall trend assessment",
        "predictive_outlook": "what might happen next"
    }},
    "multimodal_analysis": {{
        "visual_sensor_correlation": "how image matches sensor data",
        "anomalies_detected": ["visual or sensor anomalies"],
        "manufacturing_state": "current operation state"
    }},
    "risk_assessment": {{
        "current_risk_level": "low/medium/high/critical",
        "risk_factors": ["specific risk factors identified"],
        "time_to_potential_failure": "estimate if applicable"
    }},
    "action_plan": [
        {{
            "action": "action_name",
            "priority": "low/medium/high/critical",
            "reasoning": "why this action is needed",
            "parameters": {{"key": "value"}}
        }}
    ],
    "confidence": 0.85
}}
"""
    
    return prompt

async def call_safety_api(actions: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Call safety API to validate actions"""
    try:
        async with httpx.AsyncClient() as client:
            safety_request = {
                "actions": actions,
                "context": context
            }
            
            response = await client.post(
                f"{SAFETY_API_URL}/validate",
                json=safety_request,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json().get("validated_actions", [])
            else:
                logger.error(f"Safety API returned {response.status_code}: {response.text}")
                return []
                
    except Exception as e:
        logger.error(f"Failed to call safety API: {e}")
        return []

@app.post("/plan")
async def create_action_plan(request: PlanningRequest, background_tasks: BackgroundTasks):
    """Create enhanced action plan using multimodal AI with historical context"""
    
    logger.info(f"Creating action plan for trace {request.fused_record.trace_id}")
    
    try:
        # Get historical baselines
        components = ["r01", "r02", "r03", "r04", "conveyor_system"]
        baselines = get_historical_baselines(components)
        
        # Analyze deviations
        deviations = analyze_deviations(request.fused_record.telemetry_data, baselines)
        
        # Download images for analysis
        image_parts = []
        for image_uri in request.fused_record.image_uris[:2]:  # Limit to 2 images for cost
            image_part = download_image_for_analysis(image_uri)
            if image_part:
                image_parts.append(image_part)
        
        # Generate enhanced prompt
        prompt = generate_enhanced_prompt(request.fused_record, deviations)
        
        # Call Gemini with multimodal input
        logger.info("Calling Gemini 2.5 Flash-Lite for enhanced multimodal analysis...")
        
        content_parts = [prompt] + image_parts
        response = gemini_model.generate_content(content_parts)
        
        # Parse response
        try:
            response_text = response.text
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            analysis = json.loads(response_text)
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from Gemini, creating structured response")
            analysis = {
                "historical_context": {"deviations_detected": list(deviations.keys())},
                "multimodal_analysis": {"raw_response": response.text},
                "risk_assessment": {"current_risk_level": "medium"},
                "action_plan": [{"action": "log_incident", "priority": "medium", "reasoning": "Analysis completed", "parameters": {}}],
                "confidence": 0.7
            }
        
        # Extract actions for safety validation
        proposed_actions = analysis.get("action_plan", [])
        
        # Validate actions with safety API
        safety_context = {
            "telemetry": request.fused_record.telemetry_data,
            "deviations": deviations,
            "session_id": request.fused_record.session_id
        }
        
        validated_actions = await call_safety_api(proposed_actions, safety_context)
        
        # Create action plan
        action_plan = ActionPlan(
            plan_id=f"plan-{request.fused_record.trace_id}",
            session_id=request.fused_record.session_id,
            trace_id=request.fused_record.trace_id,
            reasoning=analysis.get("risk_assessment", {}).get("risk_factors", ["Analysis completed"])[0],
            confidence=analysis.get("confidence", 0.8),
            actions=validated_actions,
            historical_analysis={
                "deviations": deviations,
                "baselines_used": len(baselines),
                "analysis": analysis
            }
        )
        
        # Publish to actions topic
        background_tasks.add_task(publish_action_plan, action_plan)
        
        logger.info(f"Created action plan {action_plan.plan_id} with {len(validated_actions)} validated actions")
        
        return {
            "plan_id": action_plan.plan_id,
            "actions": action_plan.actions,
            "reasoning": action_plan.reasoning,
            "confidence": action_plan.confidence,
            "historical_context": action_plan.historical_analysis,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Failed to create action plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def publish_action_plan(action_plan: ActionPlan):
    """Publish action plan to Pub/Sub"""
    try:
        message_data = action_plan.model_dump_json().encode("utf-8")
        future = publisher.publish(ACTIONS_TOPIC, message_data)
        message_id = future.result()
        logger.info(f"Published action plan {action_plan.plan_id} - Message ID: {message_id}")
    except Exception as e:
        logger.error(f"Failed to publish action plan: {e}")

@app.post("/webhook/fused")
async def webhook_fused_record(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint for receiving fused records from Pub/Sub"""
    try:
        # Parse Pub/Sub message
        body = await request.body()
        pubsub_message = json.loads(body.decode())
        
        if 'message' in pubsub_message:
            # Decode the base64 message data
            import base64
            message_data = json.loads(base64.b64decode(pubsub_message['message']['data']).decode())
            
            # Convert to PlanningRequest format
            planning_request = PlanningRequest(fused_record=FusedRecord(**message_data))
            
            # Process the fused record
            logger.info(f"Webhook received fused record for trace {planning_request.fused_record.trace_id}")
            result = await create_action_plan(planning_request, background_tasks)
            
            return {"status": "processed", "trace_id": planning_request.fused_record.trace_id}
        else:
            logger.warning("Received invalid Pub/Sub message format")
            return {"status": "error", "message": "Invalid Pub/Sub format"}
            
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "ai_planner", 
        "version": "2.0",
        "timestamp": datetime.now().isoformat(),
        "project_id": PROJECT_ID,
        "region": LOCATION
    }
    
    try:
        # Check Vertex AI connectivity
        test_model = GenerativeModel("gemini-2.5-flash-lite")
        health_status["vertex_ai"] = "connected"
        
        # Check BigQuery connectivity
        query = f"SELECT 1 as test FROM `{PROJECT_ID}.resolve.historical_baselines` LIMIT 1"
        job = bigquery_client.query(query)
        results = list(job.result())
        health_status["bigquery"] = "connected"
        
        # Check GCS connectivity
        bucket = storage_client.bucket("your-project-id-resolve-binaries")
        blob_count = len(list(bucket.list_blobs(max_results=1)))
        health_status["gcs"] = "connected"
        
    except Exception as e:
        logger.warning(f"Health check warning: {e}")
        health_status["status"] = "degraded"
        health_status["warning"] = str(e)
    
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
