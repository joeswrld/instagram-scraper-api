import csv
from simple_client import InstagramScraperClient


def export_posts_to_csv(results: list, filename: str):
    """Export scraped posts to CSV"""
    if not results:
        print("No results to export")
        return
    
    # Define CSV fields
    fields = [
        "shortcode", "url", "caption", "likes", 
        "comments_count", "timestamp", "owner_username"
    ]
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        
        for post in results:
            row = {
                "shortcode": post.get("shortcode", ""),
                "url": post.get("url", ""),
                "caption": post.get("caption", "")[:100],  # Truncate
                "likes": post.get("likes", 0),
                "comments_count": post.get("comments_count", 0),
                "timestamp": post.get("timestamp", ""),
                "owner_username": post.get("owner", {}).get("username", "")
            }
            writer.writerow(row)
    
    print(f"Exported to {filename}")

