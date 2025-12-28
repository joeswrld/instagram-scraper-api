"""
Storage Manager - Handles local file storage for scraped data
Supports JSON, CSV, and ZIP exports
"""

import json
import csv
import zipfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages local storage of scraped Instagram data
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.jobs_dir = self.base_dir / "jobs"
        self.media_dir = self.base_dir / "media"
        self.exports_dir = self.base_dir / "exports"
        
        for dir_path in [self.jobs_dir, self.media_dir, self.exports_dir]:
            dir_path.mkdir(exist_ok=True)
    
    def get_job_dir(self, job_id: str) -> Path:
        """Get or create job directory"""
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(exist_ok=True)
        return job_dir
    
    def save_scraped_data(self, job_id: str, data: Dict[str, Any]) -> None:
        """
        Save scraped data to job directory
        """
        try:
            job_dir = self.get_job_dir(job_id)
            
            # Append to results file
            results_file = job_dir / "results.jsonl"
            
            with open(results_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
            
            logger.info(f"Saved data for job {job_id}")
        
        except Exception as e:
            logger.error(f"Error saving data for job {job_id}: {str(e)}")
            raise
    
    def get_job_results(self, job_id: str, format: str = "json") -> Any:
        """
        Retrieve job results in specified format
        """
        job_dir = self.get_job_dir(job_id)
        results_file = job_dir / "results.jsonl"
        
        if not results_file.exists():
            raise FileNotFoundError(f"No results found for job {job_id}")
        
        if format == "json":
            # Read all lines and return as JSON array
            results = []
            with open(results_file, 'r') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
            return results
        
        elif format == "csv":
            # Convert to CSV
            csv_file = job_dir / "results.csv"
            self._convert_to_csv(results_file, csv_file)
            return str(csv_file)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _convert_to_csv(self, jsonl_file: Path, csv_file: Path) -> None:
        """
        Convert JSONL to CSV format
        """
        results = []
        with open(jsonl_file, 'r') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        if not results:
            return
        
        # Flatten nested data for CSV
        flattened = []
        for item in results:
            flat_item = self._flatten_dict(item)
            flattened.append(flat_item)
        
        # Write to CSV
        if flattened:
            keys = set()
            for item in flattened:
                keys.update(item.keys())
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(keys))
                writer.writeheader()
                writer.writerows(flattened)
    
    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = '',
        sep: str = '_'
    ) -> Dict[str, Any]:
        """
        Flatten nested dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to JSON strings
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def export_results(self, job_id: str, format: str) -> Path:
        """
        Export job results to specified format
        """
        try:
            job_dir = self.get_job_dir(job_id)
            export_dir = self.exports_dir / job_id
            export_dir.mkdir(exist_ok=True)
            
            if format == "json":
                # Copy results to export directory
                src = job_dir / "results.jsonl"
                dst = export_dir / "results.json"
                
                # Convert JSONL to JSON array
                results = []
                with open(src, 'r') as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line))
                
                with open(dst, 'w') as f:
                    json.dump(results, f, indent=2)
                
                return dst
            
            elif format == "csv":
                src = job_dir / "results.jsonl"
                dst = export_dir / "results.csv"
                self._convert_to_csv(src, dst)
                return dst
            
            elif format == "zip":
                return self.create_export_bundle(job_id)
        
        except Exception as e:
            logger.error(f"Error exporting results for job {job_id}: {str(e)}")
            raise
    
    def create_export_bundle(self, job_id: str) -> Path:
        """
        Create a ZIP bundle with all job data
        """
        job_dir = self.get_job_dir(job_id)
        zip_path = self.exports_dir / f"{job_id}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from job directory
            for file_path in job_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(job_dir)
                    zipf.write(file_path, arcname)
        
        logger.info(f"Created export bundle: {zip_path}")
        return zip_path
    
    async def download_media(
        self,
        job_id: str,
        media_url: str,
        filename: str
    ) -> Path:
        """
        Download media file (image/video) from URL
        """
        try:
            media_dir = self.get_job_dir(job_id) / "media"
            media_dir.mkdir(exist_ok=True)
            
            file_path = media_dir / filename
            
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                        
                        logger.info(f"Downloaded media: {filename}")
                        return file_path
                    else:
                        raise Exception(f"Failed to download: {response.status}")
        
        except Exception as e:
            logger.error(f"Error downloading media {filename}: {str(e)}")
            raise
    
    def delete_job_data(self, job_id: str) -> None:
        """
        Delete all data associated with a job
        """
        try:
            job_dir = self.get_job_dir(job_id)
            if job_dir.exists():
                shutil.rmtree(job_dir)
            
            # Delete export if exists
            export_zip = self.exports_dir / f"{job_id}.zip"
            if export_zip.exists():
                export_zip.unlink()
            
            export_dir = self.exports_dir / job_id
            if export_dir.exists():
                shutil.rmtree(export_dir)
            
            logger.info(f"Deleted data for job {job_id}")
        
        except Exception as e:
            logger.error(f"Error deleting job data {job_id}: {str(e)}")
            raise
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage usage statistics
        """
        def get_dir_size(path: Path) -> int:
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        
        return {
            "total_jobs": len(list(self.jobs_dir.iterdir())),
            "jobs_size_mb": get_dir_size(self.jobs_dir) / (1024 * 1024),
            "media_size_mb": get_dir_size(self.media_dir) / (1024 * 1024),
            "exports_size_mb": get_dir_size(self.exports_dir) / (1024 * 1024),
            "total_size_mb": get_dir_size(self.base_dir) / (1024 * 1024)
        }