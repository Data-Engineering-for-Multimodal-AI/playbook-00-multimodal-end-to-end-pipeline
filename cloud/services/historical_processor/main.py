#!/usr/bin/env python3
"""
Historical Processor Service
Processes Future Factories analog/historical data (Excel files) to build baselines and patterns
"""

import json
import logging
import os
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from google.cloud import storage, bigquery
import pandas as pd
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/historical_processor.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Historical Processor", version="2.0")

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
GCS_BUCKET = os.getenv("GCS_BUCKET", f"{PROJECT_ID}-resolve-binaries")
ANALOG_PATH = "datasets/future-factories/analog-2024-08-13/Analog"

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

class HistoricalBaseline(BaseModel):
    component: str
    metric: str
    mean: float
    std: float
    min_value: float
    max_value: float
    percentile_95: float
    sample_count: int
    last_updated: str

class ProcessingRequest(BaseModel):
    files: List[str] = [
        "R01_Data.xlsx", "R02_Data.xlsx", "R03_Data.xlsx", "R04_Data.xlsx",
        "Conveyor_Signals.csv", "FFCellSafetyManagement.xlsx", "FFCell_CycleManagement.xlsx"
    ]
    force_refresh: bool = False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def read_excel_from_gcs(file_path: str) -> pd.DataFrame:
    """Read Excel file from GCS into pandas DataFrame"""
    try:
        bucket = storage_client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{ANALOG_PATH}/{file_path}")
        
        # Download as bytes
        file_content = blob.download_as_bytes()
        
        # Read Excel file
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
        else:  # CSV
            df = pd.read_csv(io.BytesIO(file_content))
        
        logger.info(f"Read {len(df)} rows from {file_path}")
        return df
        
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        raise

def process_robot_data(robot_file: str) -> List[HistoricalBaseline]:
    """Process robot historical data to extract baselines"""
    baselines = []
    
    try:
        df = read_excel_from_gcs(robot_file)
        robot_id = robot_file.replace("_Data.xlsx", "").lower()
        
        # Process numerical columns
        numerical_cols = df.select_dtypes(include=['float64', 'int64']).columns
        
        for col in numerical_cols:
            if df[col].notna().sum() > 10:  # Need at least 10 data points
                baseline = HistoricalBaseline(
                    component=robot_id,
                    metric=col.lower().replace(" ", "_"),
                    mean=float(df[col].mean()),
                    std=float(df[col].std()),
                    min_value=float(df[col].min()),
                    max_value=float(df[col].max()),
                    percentile_95=float(df[col].quantile(0.95)),
                    sample_count=int(df[col].notna().sum()),
                    last_updated=datetime.now().isoformat()
                )
                baselines.append(baseline)
        
        logger.info(f"Extracted {len(baselines)} baselines from {robot_file}")
        return baselines
        
    except Exception as e:
        logger.error(f"Failed to process {robot_file}: {e}")
        return []

def process_conveyor_data(conveyor_file: str) -> List[HistoricalBaseline]:
    """Process conveyor historical data"""
    baselines = []
    
    try:
        # Note: The CSV is actually an Excel file based on our earlier analysis
        df = read_excel_from_gcs(conveyor_file)
        
        # Process numerical columns
        numerical_cols = df.select_dtypes(include=['float64', 'int64']).columns
        
        for col in numerical_cols:
            if df[col].notna().sum() > 10:
                baseline = HistoricalBaseline(
                    component="conveyor_system",
                    metric=col.lower().replace(" ", "_"),
                    mean=float(df[col].mean()),
                    std=float(df[col].std()),
                    min_value=float(df[col].min()),
                    max_value=float(df[col].max()),
                    percentile_95=float(df[col].quantile(0.95)),
                    sample_count=int(df[col].notna().sum()),
                    last_updated=datetime.now().isoformat()
                )
                baselines.append(baseline)
        
        logger.info(f"Extracted {len(baselines)} conveyor baselines")
        return baselines
        
    except Exception as e:
        logger.error(f"Failed to process conveyor data: {e}")
        return []

def process_safety_data(safety_file: str) -> Dict[str, Any]:
    """Process safety management data"""
    try:
        df = read_excel_from_gcs(safety_file)
        
        # Extract safety patterns
        safety_summary = {
            "total_incidents": len(df),
            "incident_types": df.get('Incident_Type', pd.Series()).value_counts().to_dict() if 'Incident_Type' in df.columns else {},
            "severity_distribution": df.get('Severity', pd.Series()).value_counts().to_dict() if 'Severity' in df.columns else {},
            "components_affected": df.get('Component', pd.Series()).value_counts().to_dict() if 'Component' in df.columns else {},
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info(f"Processed safety data: {len(df)} incidents")
        return safety_summary
        
    except Exception as e:
        logger.error(f"Failed to process safety data: {e}")
        return {}

def process_cycle_data(cycle_file: str) -> Dict[str, Any]:
    """Process cycle management data"""
    try:
        df = read_excel_from_gcs(cycle_file)
        
        # Extract cycle patterns
        cycle_summary = {
            "total_cycles": len(df),
            "average_cycle_time": float(df.get('Cycle_Time', pd.Series()).mean()) if 'Cycle_Time' in df.columns else 0,
            "cycle_efficiency": float(df.get('Efficiency', pd.Series()).mean()) if 'Efficiency' in df.columns else 0,
            "production_patterns": df.get('Shift', pd.Series()).value_counts().to_dict() if 'Shift' in df.columns else {},
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info(f"Processed cycle data: {len(df)} cycles")
        return cycle_summary
        
    except Exception as e:
        logger.error(f"Failed to process cycle data: {e}")
        return {}

def store_baselines_in_bigquery(baselines: List[HistoricalBaseline]) -> None:
    """Store historical baselines in BigQuery"""
    try:
        # Create dataset and table if they don't exist
        dataset_id = "resolve"
        table_id = "historical_baselines"
        
        dataset_ref = bigquery_client.dataset(dataset_id)
        table_ref = dataset_ref.table(table_id)
        
        # Define schema
        schema = [
            bigquery.SchemaField("component", "STRING"),
            bigquery.SchemaField("metric", "STRING"),
            bigquery.SchemaField("mean", "FLOAT"),
            bigquery.SchemaField("std", "FLOAT"),
            bigquery.SchemaField("min_value", "FLOAT"),
            bigquery.SchemaField("max_value", "FLOAT"),
            bigquery.SchemaField("percentile_95", "FLOAT"),
            bigquery.SchemaField("sample_count", "INTEGER"),
            bigquery.SchemaField("last_updated", "TIMESTAMP"),
        ]
        
        # Create table if it doesn't exist
        try:
            bigquery_client.get_table(table_ref)
        except:
            table = bigquery.Table(table_ref, schema=schema)
            bigquery_client.create_table(table)
            logger.info(f"Created table {dataset_id}.{table_id}")
        
        # Insert data
        rows_to_insert = []
        for baseline in baselines:
            rows_to_insert.append({
                "component": baseline.component,
                "metric": baseline.metric,
                "mean": baseline.mean,
                "std": baseline.std,
                "min_value": baseline.min_value,
                "max_value": baseline.max_value,
                "percentile_95": baseline.percentile_95,
                "sample_count": baseline.sample_count,
                "last_updated": baseline.last_updated,
            })
        
        errors = bigquery_client.insert_rows_json(table_ref, rows_to_insert)
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
        else:
            logger.info(f"Stored {len(rows_to_insert)} baselines in BigQuery")
            
    except Exception as e:
        logger.error(f"Failed to store baselines in BigQuery: {e}")
        raise

@app.post("/process")
async def process_historical_data(request: ProcessingRequest):
    """Process historical analog data and build baselines"""
    
    logger.info("Starting historical data processing...")
    
    all_baselines = []
    safety_data = {}
    cycle_data = {}
    
    try:
        for file_name in request.files:
            logger.info(f"Processing {file_name}...")
            
            if file_name.startswith("R0") and file_name.endswith("_Data.xlsx"):
                # Robot data
                baselines = process_robot_data(file_name)
                all_baselines.extend(baselines)
                
            elif file_name == "Conveyor_Signals.csv":
                # Conveyor data
                baselines = process_conveyor_data(file_name)
                all_baselines.extend(baselines)
                
            elif file_name == "FFCellSafetyManagement.xlsx":
                # Safety data
                safety_data = process_safety_data(file_name)
                
            elif file_name == "FFCell_CycleManagement.xlsx":
                # Cycle data
                cycle_data = process_cycle_data(file_name)
        
        # Store baselines in BigQuery
        if all_baselines:
            store_baselines_in_bigquery(all_baselines)
        
        result = {
            "processed_files": len(request.files),
            "extracted_baselines": len(all_baselines),
            "safety_incidents": safety_data.get("total_incidents", 0),
            "total_cycles": cycle_data.get("total_cycles", 0),
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Historical processing complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Historical processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/baselines/{component}")
async def get_baselines(component: str):
    """Get historical baselines for a component"""
    try:
        query = f"""
        SELECT * FROM `{PROJECT_ID}.resolve.historical_baselines`
        WHERE component = @component
        ORDER BY last_updated DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("component", "STRING", component)
            ]
        )
        
        query_job = bigquery_client.query(query, job_config=job_config)
        results = query_job.result()
        
        baselines = []
        for row in results:
            baselines.append(dict(row))
        
        return {"component": component, "baselines": baselines}
        
    except Exception as e:
        logger.error(f"Failed to get baselines for {component}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "historical_processor", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
