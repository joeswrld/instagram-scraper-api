"""
Job Manager - Handles job lifecycle and status tracking
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Job data structure"""
    job_id: str
    urls: List[str]
    scrape_type: str
    export_format: str
    include_media: bool
    include_comments: bool
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    error: Optional[str] = None


class JobManager:
    """
    Manages scraping jobs lifecycle
    Thread-safe job tracking and status updates
    """
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.lock = Lock()
    
    def create_job(
        self,
        job_id: str,
        urls: List[str],
        scrape_type: str,
        export_format: str,
        include_media: bool,
        include_comments: bool
    ) -> Job:
        """
        Create a new scraping job
        """
        with self.lock:
            job = Job(
                job_id=job_id,
                urls=urls,
                scrape_type=scrape_type,
                export_format=export_format,
                include_media=include_media,
                include_comments=include_comments,
                total_items=len(urls)
            )
            
            self.jobs[job_id] = job
            logger.info(f"Created job: {job_id}")
            
            return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve job by ID
        """
        with self.lock:
            return self.jobs.get(job_id)
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None
    ) -> None:
        """
        Update job status
        """
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].status = status
                self.jobs[job_id].updated_at = datetime.now()
                
                if error:
                    self.jobs[job_id].error = error
                
                logger.info(f"Job {job_id} status updated to: {status.value}")
    
    def update_progress(
        self,
        job_id: str,
        completed: int,
        total: int,
        failed: int = 0
    ) -> None:
        """
        Update job progress
        """
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].completed_items = completed
                self.jobs[job_id].total_items = total
                self.jobs[job_id].failed_items = failed
                self.jobs[job_id].updated_at = datetime.now()
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Job]:
        """
        List jobs with optional status filter
        """
        with self.lock:
            jobs = list(self.jobs.values())
            
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            return jobs[:limit]
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from tracking
        """
        with self.lock:
            if job_id in self.jobs:
                del self.jobs[job_id]
                logger.info(f"Deleted job: {job_id}")
                return True
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get job statistics
        """
        with self.lock:
            return {
                "total": len(self.jobs),
                "queued": len([j for j in self.jobs.values() if j.status == JobStatus.QUEUED]),
                "running": len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING]),
                "completed": len([j for j in self.jobs.values() if j.status == JobStatus.COMPLETED]),
                "failed": len([j for j in self.jobs.values() if j.status == JobStatus.FAILED]),
            }
    
    def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Remove jobs older than specified days
        """
        with self.lock:
            cutoff = datetime.now().timestamp() - (days * 86400)
            
            old_jobs = [
                job_id for job_id, job in self.jobs.items()
                if job.created_at.timestamp() < cutoff
                and job.status in [JobStatus.COMPLETED, JobStatus.FAILED]
            ]
            
            for job_id in old_jobs:
                del self.jobs[job_id]
            
            logger.info(f"Cleaned up {len(old_jobs)} old jobs")
            return len(old_jobs)