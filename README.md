# Instagram Scraper API

Production-ready Python API for scraping public Instagram data with local storage.

## Features

✅ **Pure Python** - No external database services required  
✅ **FastAPI** - Modern, async web framework  
✅ **Local Storage** - JSON, CSV, ZIP exports  
✅ **Batch Processing** - Scrape multiple URLs asynchronously  
✅ **Job Management** - Track scraping progress in real-time  
✅ **Media Downloads** - Save images and videos locally  
✅ **Rate Limiting** - Built-in delays to respect Instagram  
✅ **Type Safety** - Full type hints throughout  
✅ **Docker Ready** - Easy deployment with Docker

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd instagram-scraper-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Configuration

Edit `.env` file:

```env
API_KEYS=your-secret-key-here
DATA_DIR=./data
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Run Server

```bash
# Development
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t instagram-scraper .
docker run -p 8000:8000 -v $(pwd)/data:/app/data instagram-scraper
```

## API Endpoints

### POST /scrape
Create a new scraping job

**Request:**
```json
{
  "urls": [
    "https://www.instagram.com/p/ABC123/",
    "https://www.instagram.com/username/"
  ],
  "scrape_type": "post",
  "export_format": "json",
  "include_media": true,
  "include_comments": true
}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "queued",
  "message": "Scrape job created successfully. Processing 2 URL(s)"
}
```

### GET /scrape/{job_id}
Get job status and progress

**Response:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "running",
  "created_at": "2025-01-15T10:30:00",
  "updated_at": "2025-01-15T10:31:30",
  "progress": {
    "total": 2,
    "completed": 1,
    "failed": 0,
    "percentage": 50.0
  }
}
```

### GET /scrape/{job_id}/results
Download scraped results

**Query Parameters:**
- `format`: `json`, `csv`, or `zip`

**Response:** File download

### GET /jobs
List all jobs

**Query Parameters:**
- `status`: Filter by status (optional)
- `limit`: Number of jobs to return (default: 50)

### DELETE /scrape/{job_id}
Delete a job and its data

## Usage Examples

### Python Client

```python
import requests
import time

API_URL = "http://localhost:8000"
API_KEY = "your-secret-key-here"

headers = {"X-API-Key": API_KEY}

# Create scrape job
response = requests.post(
    f"{API_URL}/scrape",
    headers=headers,
    json={
        "urls": [
            "https://www.instagram.com/p/ABC123/",
            "https://www.instagram.com/natgeo/"
        ],
        "scrape_type": "post",
        "export_format": "json",
        "include_media": True,
        "include_comments": True
    }
)

job = response.json()
job_id = job["job_id"]
print(f"Job created: {job_id}")

# Poll for completion
while True:
    status_response = requests.get(
        f"{API_URL}/scrape/{job_id}",
        headers=headers
    )
    status = status_response.json()
    
    print(f"Status: {status['status']} - {status['progress']['percentage']:.1f}%")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(5)

# Download results
if status["status"] == "completed":
    results_response = requests.get(
        f"{API_URL}/scrape/{job_id}/results?format=json",
        headers=headers
    )
    
    results = results_response.json()
    print(f"Scraped {len(results)} items")
    
    # Save to file
    with open(f"results_{job_id}.json", "w") as f:
        json.dump(results, f, indent=2)
```

### cURL Examples

```bash
# Create job
curl -X POST http://localhost:8000/scrape \
  -H "X-API-Key: your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.instagram.com/p/ABC123/"],
    "scrape_type": "post",
    "export_format": "json",
    "include_media": true,
    "include_comments": true
  }'

# Check status
curl http://localhost:8000/scrape/a1b2c3d4e5f6 \
  -H "X-API-Key: your-secret-key-here"

# Download results
curl http://localhost:8000/scrape/a1b2c3d4e5f6/results?format=json \
  -H "X-API-Key: your-secret-key-here" \
  -o results.json

# List all jobs
curl http://localhost:8000/jobs \
  -H "X-API-Key: your-secret-key-here"
```

## Scrape Types

### Post Scraping
```json
{
  "scrape_type": "post",
  "urls": ["https://www.instagram.com/p/SHORTCODE/"]
}
```

**Extracted Data:**
- Caption, likes, comments count
- Timestamp, location
- Hashtags, mentions
- Media URLs (images/videos)
- Public comments (up to 50)

### Profile Scraping
```json
{
  "scrape_type": "profile",
  "urls": ["https://www.instagram.com/username/"]
}
```

**Extracted Data:**
- Username, full name, bio
- Followers, following counts
- Post count, verification status
- Profile picture URL
- Recent posts (up to 12)

### Hashtag Scraping
```json
{
  "scrape_type": "hashtag",
  "urls": ["https://www.instagram.com/explore/tags/hashtag/"]
}
```

**Extracted Data:**
- Total post count
- Recent posts (up to 20)
- Post metadata

### Place Scraping
```json
{
  "scrape_type": "place",
  "urls": ["https://www.instagram.com/explore/locations/PLACE_ID/"]
}
```

**Note:** Place scraping has limited support.

## Data Structure

### Post Data Example
```json
{
  "type": "post",
  "shortcode": "ABC123",
  "url": "https://www.instagram.com/p/ABC123/",
  "caption": "Beautiful sunset 🌅",
  "likes": 1234,
  "comments_count": 56,
  "timestamp": "2025-01-15T10:30:00",
  "is_video": false,
  "owner": {
    "username": "photographer",
    "user_id": "12345"
  },
  "location": {
    "name": "California, USA",
    "id": "67890"
  },
  "hashtags": ["sunset", "nature", "photography"],
  "mentions": ["friend1", "friend2"],
  "media": [
    {
      "type": "image",
      "url": "https://..."
    }
  ],
  "comments": [
    {
      "user": "commenter1",
      "text": "Amazing photo!",
      "created_at": "2025-01-15T11:00:00",
      "likes": 5
    }
  ],
  "scraped_at": "2025-01-15T12:00:00"
}
```

## Storage Structure

```
data/
├── jobs/
│   ├── job_id_1/
│   │   ├── results.jsonl    # Line-delimited JSON results
│   │   ├── results.csv      # CSV export
│   │   └── media/           # Downloaded media files
│   │       ├── image1.jpg
│   │       └── video1.mp4
│   └── job_id_2/
├── media/                   # Shared media cache
└── exports/                 # ZIP export bundles
    ├── job_id_1.zip
    └── job_id_2.zip
```

## Error Handling

The API handles errors gracefully:

- **Invalid URLs**: Returns error in results
- **Private Accounts**: Notes access restriction
- **Rate Limits**: Built-in delays between requests
- **Network Errors**: Retries with exponential backoff
- **Job Failures**: Tracked in job status

## Security

### API Key Authentication
All endpoints require `X-API-Key` header:

```python
headers = {"X-API-Key": "your-secret-key"}
```

### Rate Limiting
Built-in delays prevent Instagram rate limiting:
- 2 seconds between requests (configurable)
- Respects Instagram's robots.txt

### Data Privacy
- Only scrapes **public** data
- No login required
- No private content access
- No credential storage

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEYS` | Comma-separated API keys | `dev-key-12345` |
| `DATA_DIR` | Data storage directory | `./data` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `WORKERS` | Uvicorn workers | `4` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_URLS_PER_JOB` | Max URLs per job | `100` |
| `SCRAPE_DELAY_SECONDS` | Delay between scrapes | `2.0` |

## Monitoring & Logs

### Logging
Logs are written to:
- Console (stdout)
- `scraper.log` file (optional)

### Health Check
```bash
curl http://localhost:8000/
```

### Storage Stats
Check disk usage programmatically using `StorageManager.get_storage_stats()`

## Production Deployment

### Systemd Service

```ini
# /etc/systemd/system/instagram-scraper.service
[Unit]
Description=Instagram Scraper API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/instagram-scraper
Environment="PATH=/opt/instagram-scraper/venv/bin"
ExecStart=/opt/instagram-scraper/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name scraper.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Troubleshooting

### Common Issues

**"Invalid API key"**
- Check `X-API-Key` header
- Verify key in `.env` file

**"Job not found"**
- Job may have been deleted
- Check job ID spelling

**"Rate limited by Instagram"**
- Increase `SCRAPE_DELAY_SECONDS`
- Reduce concurrent jobs

**"No results found"**
- Check if account/post is private
- Verify URL format

## License

MIT License - See LICENSE file

## Disclaimer

This tool is for educational and research purposes only. Always respect Instagram's Terms of Service and robots.txt. Use responsibly and ethically. The developers are not responsible for misuse of this tool.

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: [repository-url]/wiki