#!/usr/bin/env python3
"""
Production Deployment Tool for Resolve Agent Pipeline
Handles infrastructure deployment and service configuration
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('deployment.log')
    ]
)
logger = logging.getLogger(__name__)

class ProductionDeployer:
    """Production-grade deployment orchestrator"""
    
    def __init__(self, project_id: str, region: str = "us-central1"):
        self.project_id = project_id
        self.region = region
        self.services = {
            "data-ingester": {
                "source": "services/data_ingester",
                "memory": "1Gi",
                "cpu": "1",
                "min_instances": 0,
                "max_instances": 5,
                "timeout": 300
            },
            "historical-processor": {
                "source": "services/historical_processor",
                "memory": "2Gi", 
                "cpu": "2",
                "min_instances": 0,
                "max_instances": 3,
                "timeout": 600
            },
            "fusion-engine": {
                "source": "services/fusion_engine",
                "memory": "1Gi",
                "cpu": "1", 
                "min_instances": 1,
                "max_instances": 5,
                "timeout": 300
            },
            "ai-planner": {
                "source": "services/ai_planner",
                "memory": "2Gi",
                "cpu": "2",
                "min_instances": 0,
                "max_instances": 10,
                "timeout": 600
            }
        }
        self.service_urls = {}
        
    def validate_prerequisites(self) -> bool:
        """Validate deployment prerequisites"""
        logger.info("Validating deployment prerequisites...")
        
        try:
            # Check gcloud CLI
            result = subprocess.run(["gcloud", "version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("gcloud CLI not found or not configured")
                return False
            
            # Check terraform
            result = subprocess.run(["terraform", "version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("Terraform not found")
                return False
            
            # Check project access
            result = subprocess.run([
                "gcloud", "config", "get-value", "project"
            ], capture_output=True, text=True, timeout=10)
            
            current_project = result.stdout.strip()
            if current_project != self.project_id:
                logger.warning(f"Current project ({current_project}) != target project ({self.project_id})")
                logger.info(f"Setting project to {self.project_id}")
                subprocess.run(["gcloud", "config", "set", "project", self.project_id], 
                             check=True, timeout=10)
            
            # Validate service files exist
            for service_name, config in self.services.items():
                service_path = Path(config["source"])
                if not service_path.exists():
                    logger.error(f"Service directory not found: {service_path}")
                    return False
                
                main_py = service_path / "main.py"
                requirements_txt = service_path / "requirements.txt"
                
                if not main_py.exists():
                    logger.error(f"main.py not found in {service_path}")
                    return False
                    
                if not requirements_txt.exists():
                    logger.error(f"requirements.txt not found in {service_path}")
                    return False
            
            logger.info("✓ Prerequisites validation passed")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Command timeout during prerequisite validation")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed during prerequisite validation: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during prerequisite validation: {e}")
            return False
    
    def deploy_infrastructure(self) -> bool:
        """Deploy infrastructure using Terraform"""
        logger.info("Deploying infrastructure with Terraform...")
        
        try:
            terraform_dir = Path("infra/terraform")
            if not terraform_dir.exists():
                logger.error("Terraform directory not found")
                return False
            
            # Change to terraform directory
            original_cwd = os.getcwd()
            os.chdir(terraform_dir)
            
            try:
                # Initialize Terraform
                logger.info("Initializing Terraform...")
                result = subprocess.run([
                    "terraform", "init", "-input=false"
                ], check=True, capture_output=True, text=True, timeout=120)
                
                # Plan Terraform
                logger.info("Planning Terraform deployment...")
                result = subprocess.run([
                    "terraform", "plan",
                    f"-var=project_id={self.project_id}",
                    f"-var=region={self.region}",
                    "-input=false"
                ], check=True, capture_output=True, text=True, timeout=120)
                
                # Apply Terraform
                logger.info("Applying Terraform configuration...")
                result = subprocess.run([
                    "terraform", "apply", "-auto-approve",
                    f"-var=project_id={self.project_id}",
                    f"-var=region={self.region}",
                    "-input=false"
                ], check=True, capture_output=True, text=True, timeout=300)
                
                logger.info("✓ Infrastructure deployment completed")
                return True
                
            finally:
                os.chdir(original_cwd)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Terraform deployment failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Infrastructure deployment error: {e}")
            return False
    
    def configure_docker_auth(self) -> bool:
        """Configure Docker authentication for Google Cloud"""
        logger.info("Configuring Docker authentication...")
        
        try:
            subprocess.run([
                "gcloud", "auth", "configure-docker", "gcr.io", "--quiet"
            ], check=True, timeout=60)
            
            logger.info("✓ Docker authentication configured")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Docker authentication error: {e}")
            return False
    
    def deploy_cloud_run_service(self, service_name: str, config: Dict) -> bool:
        """Deploy a single Cloud Run service"""
        logger.info(f"Deploying {service_name}...")
        
        try:
            cmd = [
                "gcloud", "run", "deploy", service_name,
                "--source", config["source"],
                "--region", self.region,
                "--allow-unauthenticated",
                "--memory", config["memory"],
                "--cpu", config["cpu"],
                "--min-instances", str(config["min_instances"]),
                "--max-instances", str(config["max_instances"]),
                "--timeout", str(config["timeout"]),
                "--set-env-vars", f"GOOGLE_CLOUD_PROJECT={self.project_id}",
                "--quiet"
            ]
            
            # Add service-specific environment variables
            if service_name == "ai-planner":
                cmd[-2] += f",VERTEX_AI_LOCATION={self.region}"
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
            
            # Get service URL
            url_result = subprocess.run([
                "gcloud", "run", "services", "describe", service_name,
                "--region", self.region,
                "--format", "value(status.url)"
            ], check=True, capture_output=True, text=True, timeout=30)
            
            service_url = url_result.stdout.strip()
            self.service_urls[service_name] = service_url
            
            logger.info(f"✓ {service_name} deployed: {service_url}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to deploy {service_name}: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Service deployment error for {service_name}: {e}")
            return False
    
    def deploy_all_services(self) -> bool:
        """Deploy all Cloud Run services"""
        logger.info("Deploying Cloud Run services...")
        
        success_count = 0
        for service_name, config in self.services.items():
            if self.deploy_cloud_run_service(service_name, config):
                success_count += 1
            else:
                logger.error(f"Failed to deploy {service_name}")
        
        if success_count == len(self.services):
            logger.info(f"✓ All {success_count} services deployed successfully")
            return True
        else:
            logger.error(f"Only {success_count}/{len(self.services)} services deployed successfully")
            return False
    
    def create_pubsub_subscriptions(self) -> bool:
        """Create Pub/Sub push subscriptions"""
        logger.info("Creating Pub/Sub subscriptions...")
        
        if not self.service_urls:
            logger.error("No service URLs available for subscriptions")
            return False
        
        subscriptions = [
            {
                "name": "telemetry-fusion-sub",
                "topic": "telemetry.v1", 
                "endpoint": f"{self.service_urls['fusion-engine']}/webhook/telemetry"
            },
            {
                "name": "images-fusion-sub",
                "topic": "images.v1",
                "endpoint": f"{self.service_urls['fusion-engine']}/webhook/images"
            }
        ]
        
        # Only create planner subscription if we have both fusion and planner URLs
        if "ai-planner" in self.service_urls:
            subscriptions.append({
                "name": "fused-planner-sub", 
                "topic": "fused.v1",
                "endpoint": f"{self.service_urls['ai-planner']}/webhook/fused"
            })
        
        success_count = 0
        for sub in subscriptions:
            try:
                cmd = [
                    "gcloud", "pubsub", "subscriptions", "create", sub["name"],
                    "--topic", sub["topic"],
                    "--push-endpoint", sub["endpoint"],
                    "--quiet"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"✓ Created subscription: {sub['name']}")
                    success_count += 1
                elif "already exists" in result.stderr:
                    logger.info(f"✓ Subscription already exists: {sub['name']}")
                    success_count += 1
                else:
                    logger.error(f"Failed to create subscription {sub['name']}: {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Error creating subscription {sub['name']}: {e}")
        
        if success_count == len(subscriptions):
            logger.info(f"✓ All {success_count} subscriptions configured")
            return True
        else:
            logger.warning(f"Only {success_count}/{len(subscriptions)} subscriptions configured")
            return success_count > 0
    
    async def validate_deployment(self) -> bool:
        """Validate that all services are healthy"""
        logger.info("Validating deployment health...")
        
        healthy_services = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for service_name, url in self.service_urls.items():
                try:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        health_data = response.json()
                        logger.info(f"✓ {service_name} healthy: {health_data.get('status', 'unknown')}")
                        healthy_services += 1
                    else:
                        logger.error(f"✗ {service_name} unhealthy: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"✗ {service_name} health check failed: {e}")
        
        if healthy_services == len(self.service_urls):
            logger.info(f"✓ All {healthy_services} services are healthy")
            return True
        else:
            logger.warning(f"Only {healthy_services}/{len(self.service_urls)} services are healthy")
            return False
    
    def print_deployment_summary(self):
        """Print deployment summary"""
        print("\n" + "="*80)
        print("DEPLOYMENT COMPLETE")
        print("="*80)
        print(f"Project ID: {self.project_id}")
        print(f"Region: {self.region}")
        print(f"Services Deployed: {len(self.service_urls)}")
        print()
        print("Service URLs:")
        for service_name, url in self.service_urls.items():
            print(f"  {service_name:20} {url}")
        print()
        print("Next Steps:")
        print("  1. Process historical data: python run_pipeline.py --historical")
        print("  2. Run real-time pipeline: python run_pipeline.py --realtime")  
        print("  3. Run complete pipeline: python run_pipeline.py")
        print(f"  4. Check BigQuery: https://console.cloud.google.com/bigquery?project={self.project_id}")
        print(f"  5. View logs: https://console.cloud.google.com/run?project={self.project_id}")
        print("="*80)
    
    async def deploy(self) -> bool:
        """Execute complete deployment"""
        logger.info("Starting production deployment...")
        
        # Validate prerequisites
        if not self.validate_prerequisites():
            logger.error("Prerequisites validation failed")
            return False
        
        # Configure Docker authentication
        if not self.configure_docker_auth():
            logger.error("Docker authentication failed")
            return False
        
        # Deploy infrastructure
        if not self.deploy_infrastructure():
            logger.error("Infrastructure deployment failed")
            return False
        
        # Deploy services
        if not self.deploy_all_services():
            logger.error("Service deployment failed")
            return False
        
        # Create Pub/Sub subscriptions
        if not self.create_pubsub_subscriptions():
            logger.warning("Pub/Sub subscription creation had issues")
        
        # Validate deployment
        await asyncio.sleep(10)  # Give services time to start
        await self.validate_deployment()
        
        # Print summary
        self.print_deployment_summary()
        
        logger.info("Production deployment completed successfully")
        return True

async def main():
    """Main deployment entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy Resolve Agent Pipeline")
    parser.add_argument("--project-id", required=True, help="GCP Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    
    args = parser.parse_args()
    
    deployer = ProductionDeployer(args.project_id, args.region)
    
    try:
        success = await deployer.deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment failed with unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
