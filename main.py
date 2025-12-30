"""
Instagram Scraper API - Main FastAPI Application - FIXED
"""

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from scraper import InstagramScraper
from storage import StorageManager
from job_manager import JobManager, JobStatus
from usage_tracker import UsageTracker, PricingTiers

app = FastAPI(
    title="Instagram Scraper API",
    description="Production-ready API for scraping public Instagram data with usage-based billing",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEYS = set(os.getenv("API_KEYS", "dev-key-12345").split(","))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(exist_ok=True)

storage_manager = StorageManager(DATA_DIR)
job_manager = JobManager()
scraper = InstagramScraper(storage_manager)
usage_tracker = UsageTracker(DATA_DIR)

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
    estimated_cost: Optional[float] = None
    pricing_info: Optional[Dict[str, Any]] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    progress: Dict[str, Any]
    error: Optional[str] = None
    cost_info: Optional[Dict[str, Any]] = None

class AccountCreateRequest(BaseModel):
    email: str
    api_keys: List[str]
    pricing_tier: str = "professional"
    spending_limit: Optional[float] = None

class PricingEstimateRequest(BaseModel):
    num_posts: int
    include_comments: bool = False
    include_media: bool = False

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    if user_account and not user_account.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    return x_api_key

@app.get("/")
async def root():
    return {
        "service": "Instagram Scraper API",
        "version": "1.0.0",
        "status": "operational",
        "billing": "usage-based",
        "pricing_tiers": list(PricingTiers.TIERS.keys())
    }

@app.post("/scrape", response_model=ScrapeResponse)
async def create_scrape_job(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Depends(verify_api_key)
):
    try:
        user_account = usage_tracker.get_user_from_api_key(x_api_key)
        
        estimated_cost = 0.0
        if user_account:
            cost_breakdown = PricingTiers.calculate_cost(
                num_posts=len(request.urls),
                tier=user_account.pricing_tier,
                include_comments=request.include_comments,
                include_media=request.include_media,
                current_month_posts=user_account.current_month_posts
            )
            estimated_cost = cost_breakdown["overage"]
            
            if user_account.spending_limit:
                projected_cost = user_account.current_month_cost + cost_breakdown["overage"]
                if projected_cost > user_account.spending_limit:
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "error": "Spending limit would be exceeded",
                            "current_spending": user_account.current_month_cost,
                            "spending_limit": user_account.spending_limit,
                            "estimated_job_cost": cost_breakdown["overage"],
                            "projected_total": projected_cost
                        }
                    )
        
        job_id = hashlib.md5(
            f"{datetime.now().isoformat()}{request.urls}".encode()
        ).hexdigest()[:16]
        
        storage_manager.init_job_storage(job_id, request.export_format.value)
        
        job = job_manager.create_job(
            job_id=job_id,
            urls=request.urls,
            scrape_type=request.scrape_type,
            export_format=request.export_format,
            include_media=request.include_media,
            include_comments=request.include_comments
        )
        
        background_tasks.add_task(
            run_scrape_job,
            job_id=job_id,
            config=request.dict(),
            api_key=x_api_key
        )
        
        logger.info(f"Created scrape job: {job_id} (estimated cost: ${estimated_cost:.4f})")
        
        pricing_info = None
        if user_account:
            pricing_info = {
                "tier": user_account.pricing_tier,
                "base_rate": PricingTiers.TIERS[user_account.pricing_tier]["base_price"],
                "estimated_cost": estimated_cost,
                "current_month_spending": user_account.current_month_cost,
                "spending_limit": user_account.spending_limit
            }
        
        return ScrapeResponse(
            job_id=job_id,
            status=job.status.value,
            message=f"Scrape job created successfully. Processing {len(request.urls)} URL(s).",
            estimated_cost=estimated_cost,
            pricing_info=pricing_info
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scrape job: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scrape/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, x_api_key: str = Depends(verify_api_key)):
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    cost_info = None
    if job.status == JobStatus.COMPLETED:
        user_account = usage_tracker.get_user_from_api_key(x_api_key)
        if user_account:
            month_key = datetime.now().strftime("%Y-%m")
            usage_file = usage_tracker.usage_dir / f"usage_{month_key}.jsonl"
            
            if usage_file.exists():
                with open(usage_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            if record.get('job_id') == job_id:
                                cost_info = {
                                    "actual_cost": record['cost_usd'],
                                    "posts_scraped": record['posts_scraped'],
                                    "comments_included": record['comments_included'],
                                    "media_included": record['media_included'],
                                    "pricing_tier": record['pricing_tier']
                                }
                                break
    
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
        error=job.error,
        cost_info=cost_info
    )

@app.get("/scrape/{job_id}/results")
async def get_job_results(
    job_id: str,
    format: ExportFormat = ExportFormat.JSON,
    x_api_key: str = Depends(verify_api_key)
):
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status.value}"
        )
    
    try:
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

@app.get("/jobs")
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 50,
    x_api_key: str = Depends(verify_api_key)
):
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

@app.delete("/scrape/{job_id}")
async def delete_job(job_id: str, x_api_key: str = Depends(verify_api_key)):
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        storage_manager.delete_job_data(job_id)
        job_manager.delete_job(job_id)
        
        return {"message": f"Job {job_id} deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/usage/summary")
async def get_usage_summary(x_api_key: str = Depends(verify_api_key)):
    summary = usage_tracker.get_account_summary(x_api_key)
    
    if not summary:
        raise HTTPException(
            status_code=404,
            detail="Account not found. Please create an account first."
        )
    
    return summary

@app.get("/usage/history/{year}/{month}")
async def get_usage_history(
    year: int,
    month: int,
    x_api_key: str = Depends(verify_api_key)
):
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    
    if not user_account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    history = usage_tracker.get_monthly_usage(user_account.user_id, year, month)
    return history

@app.get("/usage/invoice/{year}/{month}")
async def get_invoice(
    year: int,
    month: int,
    x_api_key: str = Depends(verify_api_key)
):
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    
    if not user_account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    invoice = usage_tracker.generate_invoice(user_account.user_id, year, month)
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice

@app.get("/pricing/tiers")
async def get_pricing_tiers():
    return {
        "tiers": PricingTiers.TIERS,
        "multipliers": PricingTiers.MULTIPLIERS,
        "volume_discounts": PricingTiers.VOLUME_DISCOUNTS
    }

@app.post("/pricing/estimate")
async def estimate_cost(
    request: PricingEstimateRequest,
    x_api_key: str = Depends(verify_api_key)
):
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    
    tier = "professional"
    current_monthly_posts = 0
    
    if user_account:
        tier = user_account.pricing_tier
        current_monthly_posts = user_account.current_month_posts
    
    cost_breakdown = PricingTiers.calculate_cost(
        num_posts=request.num_posts,
        tier=tier,
        include_comments=request.include_comments,
        include_media=request.include_media,
        current_month_posts=current_monthly_posts
    )
    
    tier_info = PricingTiers.TIERS[tier]
    
    return {
        "estimated_cost": cost_breakdown["overage"],
        "cost_per_post": cost_breakdown["overage"] / request.num_posts if request.num_posts > 0 else 0,
        "pricing_tier": tier,
        "base_rate": tier_info["base_price"],
        "multipliers_applied": {
            "comments": request.include_comments,
            "media": request.include_media
        },
        "current_month_posts": current_monthly_posts,
        "volume_discount_eligible": current_monthly_posts + request.num_posts >= 50000
    }

@app.post("/account/create")
async def create_account(request: AccountCreateRequest):
    try:
        account = usage_tracker.create_account(
            email=request.email,
            api_keys=request.api_keys,
            pricing_tier=request.pricing_tier,
            spending_limit=request.spending_limit
        )
        
        return {
            "success": True,
            "user_id": account.user_id,
            "email": account.email,
            "pricing_tier": account.pricing_tier,
            "api_keys": account.api_keys
        }
    
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/account/add-credits")
async def add_credits(
    amount: float,
    x_api_key: str = Depends(verify_api_key)
):
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    
    if not user_account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    usage_tracker.add_credits(user_account.user_id, amount)
    
    return {
        "success": True,
        "credits_added": amount,
        "new_balance": user_account.credits_balance + amount
    }

@app.post("/account/upgrade")
async def upgrade_account(
    new_tier: str,
    x_api_key: str = Depends(verify_api_key)
):
    if new_tier not in PricingTiers.TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Available: {list(PricingTiers.TIERS.keys())}"
        )
    
    user_account = usage_tracker.get_user_from_api_key(x_api_key)
    
    if not user_account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    old_tier = user_account.pricing_tier
    usage_tracker.upgrade_tier(user_account.user_id, new_tier)
    
    return {
        "success": True,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "new_rate": PricingTiers.TIERS[new_tier]["base_price"]
    }

async def run_scrape_job(job_id: str, config: Dict[str, Any], api_key: str):
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting scrape job: {job_id}")
        
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
        
        logger.info(f"Finalizing export for job {job_id}")
        export_file = storage_manager.finalize_export(job_id)
        
        if export_file:
            logger.info(f"Export finalized: {export_file}")
        
        try:
            job_dir = storage_manager.get_job_dir(job_id)
            storage_used_mb = sum(
                f.stat().st_size for f in job_dir.rglob('*') if f.is_file()
            ) / (1024 * 1024)
            
            results_file = job_dir / "results.jsonl"
            actual_posts = 0
            if results_file.exists():
                with open(results_file, 'r') as f:
                    actual_posts = sum(1 for line in f if line.strip())
            
            usage_record = usage_tracker.record_usage(
                api_key=api_key,
                job_id=job_id,
                num_posts=actual_posts,
                include_comments=config['include_comments'],
                include_media=config['include_media'],
                storage_used_mb=storage_used_mb
            )
            
            logger.info(
                f"Usage recorded for job {job_id}: "
                f"{actual_posts} posts, ${usage_record.cost_usd:.4f}"
            )
        
        except Exception as e:
            logger.error(f"Error recording usage for job {job_id}: {str(e)}")
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED)
        logger.info(f"Completed scrape job: {job_id}")
    
    except Exception as e:
        logger.error(f"Error in scrape job {job_id}: {str(e)}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)