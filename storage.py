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
    
    def init_job_storage(self, job_id: str, export_format: str) -> None:
        """
        Initialize job storage with format information
        """
        job_dir = self.get_job_dir(job_id)
        
        # Store format preference
        format_file = job_dir / "format.txt"
        with open(format_file, 'w') as f:
            f.write(export_format)
        
        # Initialize empty results file
        results_file = job_dir / "results.jsonl"
        results_file.touch()
    
    def save_scraped_data(self, job_id: str, data: Dict[str, Any]) -> None:
        """
        Save scraped data to job directory (always as JSONL for intermediate storage)
        """
        try:
            job_dir = self.get_job_dir(job_id)
            
            # Append to JSONL results file (intermediate format)
            results_file = job_dir / "results.jsonl"
            
            with open(results_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
            
            logger.info(f"Saved data for job {job_id}")
        
        except Exception as e:
            logger.error(f"Error saving data for job {job_id}: {str(e)}")
            raise
    
    def get_job_format(self, job_id: str) -> str:
        """
        Get the export format preference for a job
        """
        job_dir = self.get_job_dir(job_id)
        format_file = job_dir / "format.txt"
        
        if format_file.exists():
            with open(format_file, 'r') as f:
                return f.read().strip()
        return "json"  # Default
    
    def get_job_results(self, job_id: str, format: str = None) -> Any:
        """
        Retrieve job results in specified format
        If format is None, use the job's preferred format
        """
        job_dir = self.get_job_dir(job_id)
        results_file = job_dir / "results.jsonl"
        
        if not results_file.exists():
            raise FileNotFoundError(f"No results found for job {job_id}")
        
        # Use job's preferred format if not specified
        if format is None:
            format = self.get_job_format(job_id)
        
        # Check if final format already exists
        if format == "json":
            final_file = job_dir / "results.json"
            if final_file.exists():
                with open(final_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Generate from JSONL
            results = self._read_jsonl(results_file)
            
            # Save as JSON for future use
            with open(final_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            return results
        
        elif format == "csv":
            csv_file = job_dir / "results.csv"
            if not csv_file.exists():
                self._convert_to_csv(results_file, csv_file)
            return str(csv_file)
        
        elif format == "zip":
            zip_file = self.exports_dir / f"{job_id}.zip"
            if not zip_file.exists():
                zip_file = self.create_export_bundle(job_id)
            return str(zip_file)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _read_jsonl(self, jsonl_file: Path) -> List[Dict[str, Any]]:
        """
        Read JSONL file and return as list of dictionaries
        """
        results = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        return results
    
    def _convert_to_csv(self, jsonl_file: Path, csv_file: Path) -> None:
        """
        Convert JSONL to CSV format
        """
        results = self._read_jsonl(jsonl_file)
        
        if not results:
            # Create empty CSV
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['No data available'])
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
        Flatten nested dictionary for CSV export
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to JSON strings
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def finalize_export(self, job_id: str) -> Path:
        """
        Finalize export in the user's requested format
        This is called after scraping completes
        """
        try:
            format = self.get_job_format(job_id)
            job_dir = self.get_job_dir(job_id)
            results_file = job_dir / "results.jsonl"
            
            if not results_file.exists() or results_file.stat().st_size == 0:
                logger.warning(f"No results to export for job {job_id}")
                return None
            
            if format == "json":
                # Convert JSONL to JSON
                json_file = job_dir / "results.json"
                results = self._read_jsonl(results_file)
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Exported {len(results)} items to JSON for job {job_id}")
                return json_file
            
            elif format == "csv":
                # Convert JSONL to CSV
                csv_file = job_dir / "results.csv"
                self._convert_to_csv(results_file, csv_file)
                
                logger.info(f"Exported to CSV for job {job_id}")
                return csv_file
            
            elif format == "zip":
                # Create ZIP bundle
                zip_file = self.create_export_bundle(job_id)
                
                logger.info(f"Created ZIP bundle for job {job_id}")
                return zip_file
            
        except Exception as e:
            logger.error(f"Error finalizing export for job {job_id}: {str(e)}")
            raise
    
    def export_results(self, job_id: str, format: str) -> Path:
        """
        Export job results to specified format (legacy method, kept for compatibility)
        """
        return self.finalize_export(job_id)
    
    def create_export_bundle(self, job_id: str) -> Path:
        """
        Create a ZIP bundle with all job data
        """
        job_dir = self.get_job_dir(job_id)
        zip_path = self.exports_dir / f"{job_id}.zip"
        
        # First, ensure JSON and CSV versions exist
        results_file = job_dir / "results.jsonl"
        
        if results_file.exists():
            # Create JSON version
            json_file = job_dir / "results.json"
            if not json_file.exists():
                results = self._read_jsonl(results_file)
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Create CSV version
            csv_file = job_dir / "results.csv"
            if not csv_file.exists():
                self._convert_to_csv(results_file, csv_file)
        
        # Create ZIP with all files
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in job_dir.rglob('*'):
                if file_path.is_file() and file_path.name != 'format.txt':
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
            
            # Skip if already downloaded
            if file_path.exists():
                logger.info(f"Media already exists: {filename}")
                return file_path
            
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        
                        file_size = len(content) / (1024 * 1024)  # MB
                        logger.info(f"Downloaded media: {filename} ({file_size:.2f} MB)")
                        return file_path
                    else:
                        raise Exception(f"HTTP {response.status}: Failed to download")
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading media: {filename}")
            raise Exception("Download timeout after 30 seconds")
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