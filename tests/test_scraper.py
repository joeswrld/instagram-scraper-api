import pytest
from scraper import InstagramScraper
from storage import StorageManager
from pathlib import Path
import tempfile


@pytest.fixture
def storage():
    """Create temporary storage for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield StorageManager(Path(tmpdir))


@pytest.fixture
def scraper(storage):
    """Create scraper instance"""
    return InstagramScraper(storage)


def test_extract_post_shortcode(scraper):
    """Test extracting shortcode from post URL"""
    url = "https://www.instagram.com/p/ABC123DEF/"
    shortcode = scraper._extract_identifier(url, "post")
    assert shortcode == "ABC123DEF"


def test_extract_username(scraper):
    """Test extracting username from profile URL"""
    url = "https://www.instagram.com/username/"
    username = scraper._extract_identifier(url, "profile")
    assert username == "username"


def test_extract_hashtag(scraper):
    """Test extracting hashtag from URL"""
    url = "https://www.instagram.com/explore/tags/sunset/"
    hashtag = scraper._extract_identifier(url, "hashtag")
    assert hashtag == "sunset"


