#!/usr/bin/env python3
"""
Resolve Agent Pipeline Runner
Orchestrates the complete Future Factories multimodal pipeline
"""

import argparse
import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional

import httpx
from google.cloud import storage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")

class PipelineOrchestrator:
    def __init__(self):
        self.project_id = PROJECT_ID
        self.region = REGION
        self.service_urls = {}
        
    async def get_service_urls(self):
        """Get Cloud Run service URLs"""
        try:
            import subprocess
            
            services = ["data-ingester", "historical-processor", "fusion-engine", "ai-planner"]
            
            for service in services:
                result = subprocess.run([
                    "gcloud", "run", "services", "describe", service,
                    "--region", self.region,
                    "--format", "value(status.url)"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.service_urls[service] = result.stdout.strip()
                    logger.info(f"Found {service}: {self.service_urls[service]}")
                else:
                    logger.error(f"Failed to get URL for {service}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to get service URLs: {e}")
            return False
    
    async def process_historical_data(self):
        """Process historical analog data to build baselines"""
        logger.info("Processing historical data to build baselines...")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.service_urls['historical-processor']}/process",
                    json={
                        "files": [
                            "R01_Data.xlsx", "R02_Data.xlsx", "R03_Data.xlsx", "R04_Data.xlsx",
                            "Conveyor_Signals.csv", "FFCellSafetyManagement.xlsx", "FFCell_CycleManagement.xlsx"
                        ],
                        "force_refresh": True
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Historical processing complete:")
                    logger.info(f"   Extracted {result.get('extracted_baselines', 0)} baselines")
                    logger.info(f"   Safety incidents: {result.get('safety_incidents', 0)}")
                    logger.info(f"   Total cycles: {result.get('total_cycles', 0)}")
                    return True
                else:
                    logger.error(f"Historical processing failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Historical processing error: {e}")
            return False
    
    async def ingest_multimodal_data(self):
        """Ingest multimodal real-time data"""
        logger.info("📥 Ingesting multimodal real-time data...")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.service_urls['data-ingester']}/ingest",
                    json={
                        "json_files": ["data_31000.json", "data_32000.json"],
                        "session_id": f"ff-demo-{int(time.time())}"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Data ingestion complete:")
                    logger.info(f"   Processed {result.get('processed_records', 0)} timestamped records")
                    logger.info(f"   Published {result.get('published_telemetry', 0)} telemetry messages")
                    logger.info(f"   Published {result.get('published_images', 0)} image references")
                    logger.info(f"   🆔 Session ID: {result.get('session_id', 'N/A')}")
                    return result
                else:
                    logger.error(f"Data ingestion failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Data ingestion error: {e}")
            return None
    
    async def check_fusion_status(self):
        """Check fusion engine status"""
        logger.info("Checking fusion engine status...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.service_urls['fusion-engine']}/status")
                
                if response.status_code == 200:
                    status = response.json()
                    logger.info(f"   Active sessions: {status.get('active_sessions', 0)}")
                    logger.info(f"   Active windows: {status.get('active_windows', 0)}")
                    return status
                else:
                    logger.error(f"Fusion status check failed: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Fusion status error: {e}")
            return None
    
    async def wait_for_pipeline_completion(self, max_wait_seconds=180):
        """Wait for pipeline to process data"""
        logger.info(f"⏳ Waiting for pipeline processing (max {max_wait_seconds}s)...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            status = await self.check_fusion_status()
            if status and status.get('active_windows', 0) == 0:
                logger.info("Pipeline processing complete")
                return True
            
            await asyncio.sleep(10)
        
        logger.warning("Pipeline processing timeout - may still be running")
        return False
    
    async def check_bigquery_results(self):
        """Check BigQuery for results"""
        logger.info("Checking BigQuery results...")
        
        try:
            from google.cloud import bigquery
            client = bigquery.Client()
            
            # Check historical baselines
            query = f"SELECT COUNT(*) as count FROM `{self.project_id}.resolve.historical_baselines`"
            job = client.query(query)
            results = job.result()
            
            for row in results:
                baseline_count = row.count
                logger.info(f"   Historical baselines: {baseline_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"BigQuery check failed: {e}")
            return False
    
    async def run_complete_pipeline(self):
        """Run the complete pipeline end-to-end"""
        logger.info("Starting complete Future Factories pipeline...")
        
        # Get service URLs
        if not await self.get_service_urls():
            logger.error("Failed to get service URLs")
            return False
        
        # Step 1: Process historical data
        if not await self.process_historical_data():
            logger.error("Historical processing failed")
            return False
        
        # Step 2: Ingest multimodal data
        ingestion_result = await self.ingest_multimodal_data()
        if not ingestion_result:
            logger.error("Data ingestion failed")
            return False
        
        # Step 3: Wait for pipeline completion
        await self.wait_for_pipeline_completion()
        
        # Step 4: Check results
        await self.check_bigquery_results()
        
        logger.info("Pipeline execution complete!")
        logger.info("")
        logger.info("Summary:")
        logger.info("   Historical baselines extracted from Excel files")
        logger.info("   Multimodal data ingested (JSON + images)")
        logger.info("   Data fused with time synchronization")
        logger.info("   AI analysis with historical context")
        logger.info("   Safety validation and action planning")
        logger.info("")
        logger.info("Check results:")
        logger.info(f"   • BigQuery: https://console.cloud.google.com/bigquery?project={self.project_id}")
        logger.info(f"   • Cloud Run logs: https://console.cloud.google.com/run?project={self.project_id}")
        logger.info(f"   • Pub/Sub topics: https://console.cloud.google.com/cloudpubsub?project={self.project_id}")
        
        return True

async def main():
    parser = argparse.ArgumentParser(description="Run Resolve Agent Pipeline")
    parser.add_argument("--historical", action="store_true", help="Process historical data only")
    parser.add_argument("--realtime", action="store_true", help="Process real-time data only")
    parser.add_argument("--complete", action="store_true", help="Run complete pipeline (default)")
    
    args = parser.parse_args()
    
    orchestrator = PipelineOrchestrator()
    
    if args.historical:
        await orchestrator.get_service_urls()
        await orchestrator.process_historical_data()
    elif args.realtime:
        await orchestrator.get_service_urls()
        await orchestrator.ingest_multimodal_data()
    else:
        await orchestrator.run_complete_pipeline()

if __name__ == "__main__":
    asyncio.run(main())
