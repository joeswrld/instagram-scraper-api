import asyncio
from simple_client import InstagramScraperClient


async def scrape_multiple_posts(client: InstagramScraperClient, urls: list):
    """Scrape multiple posts in batches"""
    batch_size = 10
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    
    results = []
    
    for idx, batch in enumerate(batches):
        print(f"Processing batch {idx + 1}/{len(batches)}...")
        
        job = client.create_job(
            urls=batch,
            scrape_type="post",
            include_comments=False  # Speed up scraping
        )
        
        status = client.wait_for_completion(job["job_id"])
        batch_results = client.get_results(job["job_id"])
        results.extend(batch_results)
        
        print(f"Batch {idx + 1} complete: {len(batch_results)} items")
    
    return results


# Example usage
if __name__ == "__main__":
    client = InstagramScraperClient(
        base_url="http://localhost:8000",
        api_key="dev-key-12345"
    )
    
    # List of post URLs to scrape
    urls = [
        f"https://www.instagram.com/p/ABC{i:03d}/"
        for i in range(50)
    ]
    
    results = asyncio.run(scrape_multiple_posts(client, urls))
    print(f"Total scraped: {len(results)} posts")


