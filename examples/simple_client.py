import requests
import time
import json
from typing import Dict, Any


class InstagramScraperClient:
    """Simple client for Instagram Scraper API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {"X-API-Key": api_key}
    
    def create_job(
        self,
        urls: list,
        scrape_type: str = "post",
        export_format: str = "json",
        include_media: bool = True,
        include_comments: bool = True
    ) -> Dict[str, Any]:
        """Create a new scraping job"""
        response = requests.post(
            f"{self.base_url}/scrape",
            headers=self.headers,
            json={
                "urls": urls,
                "scrape_type": scrape_type,
                "export_format": export_format,
                "include_media": include_media,
                "include_comments": include_comments
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status"""
        response = requests.get(
            f"{self.base_url}/scrape/{job_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 5,
        timeout: int = 600
    ) -> Dict[str, Any]:
        """Wait for job to complete"""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")
            
            status = self.get_status(job_id)
            
            if status["status"] == "completed":
                return status
            elif status["status"] == "failed":
                raise Exception(f"Job failed: {status.get('error', 'Unknown error')}")
            
            print(f"Progress: {status['progress']['percentage']:.1f}%")
            time.sleep(poll_interval)
    
    def get_results(self, job_id: str, format: str = "json") -> Any:
        """Get job results"""
        response = requests.get(
            f"{self.base_url}/scrape/{job_id}/results",
            headers=self.headers,
            params={"format": format}
        )
        response.raise_for_status()
        
        if format == "json":
            return response.json()
        else:
            return response.content
    
    def list_jobs(self, status: str = None, limit: int = 50) -> Dict[str, Any]:
        """List all jobs"""
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/jobs",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()


# Example usage
if __name__ == "__main__":
    client = InstagramScraperClient(
        base_url="http://localhost:8000",
        api_key="dev-key-12345"
    )
    
    # Create scraping job
    print("Creating scrape job...")
    job = client.create_job(
        urls=[
            "https://www.instagram.com/p/ABC123/",
            "https://www.instagram.com/natgeo/"
        ],
        scrape_type="post"
    )
    
    job_id = job["job_id"]
    print(f"Job created: {job_id}")
    
    # Wait for completion
    print("Waiting for completion...")
    status = client.wait_for_completion(job_id)
    print(f"Job completed! Scraped {status['progress']['completed']} items")
    
    # Get results
    print("Downloading results...")
    results = client.get_results(job_id)
    
    # Save to file
    with open(f"results_{job_id}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to results_{job_id}.json")
