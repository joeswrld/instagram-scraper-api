import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "dev-key-12345"
HEADERS = {"X-API-Key": API_KEY}


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()


def test_authentication_required():
    """Test API key authentication"""
    response = client.post("/scrape", json={
        "urls": ["https://www.instagram.com/p/ABC123/"],
        "scrape_type": "post"
    })
    assert response.status_code == 401


def test_create_scrape_job():
    """Test creating a scrape job"""
    response = client.post(
        "/scrape",
        headers=HEADERS,
        json={
            "urls": ["https://www.instagram.com/p/ABC123/"],
            "scrape_type": "post",
            "export_format": "json",
            "include_media": True,
            "include_comments": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_get_job_status():
    """Test getting job status"""
    # Create job first
    create_response = client.post(
        "/scrape",
        headers=HEADERS,
        json={
            "urls": ["https://www.instagram.com/p/ABC123/"],
            "scrape_type": "post"
        }
    )
    job_id = create_response.json()["job_id"]
    
    # Get status
    response = client.get(f"/scrape/{job_id}", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert "status" in data


def test_list_jobs():
    """Test listing jobs"""
    response = client.get("/jobs", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


