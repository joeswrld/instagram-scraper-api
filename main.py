"""
Instagram Scraper API - Main FastAPI Application
Production-ready public Instagram data scraper with local storage
"""
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import scraper modules (defined below)
from scraper import InstagramScraper
from storage import StorageManager
from job_manager import JobManager, JobStatus

# Initialize FastAPI
app = FastAPI(
    title="Instagram Scraper API",
    description="Production-ready API for scraping public Instagram data",
    version="1.0.0"
)

# Configure CORS - Allow requests from web browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Configuration
API_KEYS = set(os.getenv("API_KEYS", "dev-key-12345").split(","))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(exist_ok=True)

# Global instances
storage_manager = StorageManager(DATA_DIR)
job_manager = JobManager()
scraper = InstagramScraper(storage_manager)


# Models
class ScrapeType(str, Enum):
    POST = "post"
    PROFILE = "profile"
    HASHTAG = "hashtag"
    PLACE = "place"


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    ZIP = "zip"


class ScrapeRequest(BaseModel):
    urls: List[str]
    scrape_type: ScrapeType = ScrapeType.POST
    export_format: ExportFormat = ExportFormat.JSON
    include_media: bool = True
    include_comments: bool = True


class ScrapeResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    progress: Dict[str, Any]
    error: Optional[str] = None


# Authentication
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Endpoints
@app.get("/")
async def root():
    return {
        "service": "Instagram Scraper API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.post("/scrape", response_model=ScrapeResponse, dependencies=[Depends(verify_api_key)])
async def create_scrape_job(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new scraping job
    """
    try:
        # Generate job ID
        job_id = hashlib.md5(
            f"{datetime.now().isoformat()}{request.urls}".encode()
        ).hexdigest()[:16]
        
        # Create job
        job = job_manager.create_job(
            job_id=job_id,
            urls=request.urls,
            scrape_type=request.scrape_type,
            export_format=request.export_format,
            include_media=request.include_media,
            include_comments=request.include_comments
        )
        
        # Start scraping in background
        background_tasks.add_task(
            run_scrape_job,
            job_id=job_id,
            config=request.dict()
        )
        
        logger.info(f"Created scrape job: {job_id}")
        
        return ScrapeResponse(
            job_id=job_id,
            status=job.status.value,
            message=f"Scrape job created successfully. Processing {len(request.urls)} URL(s)"
        )
    
    except Exception as e:
        logger.error(f"Error creating scrape job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape/{job_id}", response_model=JobStatusResponse, dependencies=[Depends(verify_api_key)])
async def get_job_status(job_id: str):
    """
    Get the status of a scraping job
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        progress={
            "total": job.total_items,
            "completed": job.completed_items,
            "failed": job.failed_items,
            "percentage": (job.completed_items / job.total_items * 100) if job.total_items > 0 else 0
        },
        error=job.error
    )


@app.get("/scrape/{job_id}/results", dependencies=[Depends(verify_api_key)])
async def get_job_results(job_id: str, format: ExportFormat = ExportFormat.JSON):
    """
    Get the results of a completed scraping job
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status.value}"
        )
    
    try:
        # Get results based on format
        if format == ExportFormat.JSON:
            results = storage_manager.get_job_results(job_id, "json")
            return JSONResponse(content=results)
        
        elif format == ExportFormat.CSV:
            csv_path = storage_manager.get_job_results(job_id, "csv")
            return FileResponse(
                path=csv_path,
                media_type="text/csv",
                filename=f"{job_id}_results.csv"
            )
        
        elif format == ExportFormat.ZIP:
            zip_path = storage_manager.create_export_bundle(job_id)
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=f"{job_id}_export.zip"
            )
    
    except Exception as e:
        logger.error(f"Error retrieving results for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs", dependencies=[Depends(verify_api_key)])
async def list_jobs(status: Optional[JobStatus] = None, limit: int = 50):
    """
    List all scraping jobs with optional status filter
    """
    jobs = job_manager.list_jobs(status=status, limit=limit)
    
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "total_items": job.total_items,
                "completed_items": job.completed_items
            }
            for job in jobs
        ]
    }


@app.delete("/scrape/{job_id}", dependencies=[Depends(verify_api_key)])
async def delete_job(job_id: str):
    """
    Delete a job and its associated data
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Delete job data
        storage_manager.delete_job_data(job_id)
        
        # Remove job from manager
        job_manager.delete_job(job_id)
        
        return {"message": f"Job {job_id} deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task
async def run_scrape_job(job_id: str, config: Dict[str, Any]):
    """
    Execute scraping job in background
    """
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting scrape job: {job_id}")
        
        # Run scraper
        await scraper.scrape_batch(
            job_id=job_id,
            urls=config['urls'],
            scrape_type=config['scrape_type'],
            include_media=config['include_media'],
            include_comments=config['include_comments'],
            callback=lambda completed, total: job_manager.update_progress(
                job_id, completed, total
            )
        )
        
        # Export results
        storage_manager.export_results(job_id, config['export_format'])
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED)
        logger.info(f"Completed scrape job: {job_id}")
    
    except Exception as e:
        logger.error(f"Error in scrape job {job_id}: {str(e)}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)