# ============================================
# config.py
# Configuration management

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""
    
    # API Settings
    API_KEYS = set(os.getenv("API_KEYS", "dev-key-12345").split(","))
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    WORKERS = int(os.getenv("WORKERS", 4))
    
    # Storage Settings
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
    MAX_STORAGE_GB = int(os.getenv("MAX_STORAGE_GB", 10))
    
    # Scraping Settings
    MAX_URLS_PER_JOB = int(os.getenv("MAX_URLS_PER_JOB", 100))
    SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY_SECONDS", 2.0))
    MAX_COMMENTS_PER_POST = int(os.getenv("MAX_COMMENTS_PER_POST", 50))
    MAX_POSTS_PER_PROFILE = int(os.getenv("MAX_POSTS_PER_PROFILE", 12))
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 3600))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "scraper.log")
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        
        if not cls.API_KEYS:
            raise ValueError("At least one API key must be configured")

