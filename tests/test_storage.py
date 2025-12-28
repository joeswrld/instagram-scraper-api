import json
import pytest
from pathlib import Path
import tempfile
from storage import StorageManager


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield StorageManager(Path(tmpdir))


def test_save_and_retrieve_data(storage):
    """Test saving and retrieving scraped data"""
    job_id = "test_job_1"
    data = {
        "type": "post",
        "shortcode": "ABC123",
        "caption": "Test post"
    }
    
    # Save data
    storage.save_scraped_data(job_id, data)
    
    # Retrieve data
    results = storage.get_job_results(job_id, "json")
    assert len(results) == 1
    assert results[0]["shortcode"] == "ABC123"


def test_flatten_dict(storage):
    """Test dictionary flattening for CSV"""
    nested = {
        "user": {
            "name": "John",
            "age": 30
        },
        "tags": ["tag1", "tag2"]
    }
    
    flat = storage._flatten_dict(nested)
    assert "user_name" in flat
    assert flat["user_name"] == "John"
    assert isinstance(flat["tags"], str)  # JSON string


def test_storage_stats(storage):
    """Test storage statistics"""
    stats = storage.get_storage_stats()
    assert "total_jobs" in stats
    assert "total_size_mb" in stats


