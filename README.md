# Universal Website Scraper

A full-stack web scraping application that extracts structured data from any website, handling both static HTML and JavaScript-rendered content.

## Features

- 🔍 **Smart Scraping**: Automatically detects and handles both static and JS-rendered pages
- 🎯 **Interactive Navigation**: Clicks tabs, "Load more" buttons, and handles pagination
- 📊 **Structured Output**: Returns section-aware JSON with metadata, content, and interactions
- 🧹 **Noise Filtering**: Removes cookie banners, modals, and other overlay elements
- 🎨 **Beautiful UI**: Clean, modern interface for entering URLs and viewing results
- 📥 **Export JSON**: Download complete scraping results

## Tech Stack

- **Backend**: FastAPI + Python 3.10+
- **Static Scraping**: httpx + selectolax
- **JS Rendering**: Playwright (Chromium)
- **Frontend**: Vanilla HTML/CSS/JavaScript (embedded in FastAPI)

## Setup and Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Quick Start

1. **Clone the repository** (or extract the files):
   ```bash
   cd lyftr-scraper
   ```

2. **Make the run script executable**:
   ```bash
   chmod +x run.sh
   ```

3. **Run the application**:
   ```bash
   ./run.sh
   ```

   This script will:
   - Create a virtual environment
   - Install all dependencies
   - Install Playwright browsers
   - Start the server on `http://localhost:8000`

4. **Access the application**:
   - Open your browser and go to: `http://localhost:8000`
   - Enter a URL and click "Scrape"

### Manual Installation (Alternative)

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
```bash
GET /healthz
```

Response:
```json
{
  "status": "ok"
}
```

### Scrape URL
```bash
POST /scrape
Content-Type: application/json

{
  "url": "https://example.com"
}
```

Response:
```json
{
  "result": {
    "url": "https://example.com",
    "scrapedAt": "2025-12-27T10:00:00Z",
    "meta": {
      "title": "Page Title",
      "description": "Page description",
      "language": "en",
      "canonical": "https://example.com"
    },
    "sections": [...],
    "interactions": {
      "clicks": [],
      "scrolls": 0,
      "pages": ["https://example.com"]
    },
    "errors": []
  }
}
```

## Testing URLs

The scraper has been tested with the following URLs:

### 1. Static Content
**URL**: `https://en.wikipedia.org/wiki/Artificial_intelligence`

**Notes**: 
- Well-structured HTML with clear semantic sections
- Multiple headings and content blocks
- Good test for static scraping capabilities
- Tests section grouping and metadata extraction

### 2. JS-Rendered Content with Tabs
**URL**: `https://vercel.com/`

**Notes**:
- Heavy JavaScript rendering
- Interactive tabs and dynamic content
- Tests JS rendering fallback
- Tests click interactions for tabs
- Good example of modern marketing site

### 3. Pagination
**URL**: `https://news.ycombinator.com/`

**Notes**:
- Simple but effective pagination ("More" link at bottom)
- Tests pagination depth (3+ pages)
- Static HTML but with multi-page navigation
- Tests URL tracking across pages

### Additional Test URLs

You can also try:
- `https://developer.mozilla.org/en-US/docs/Web/JavaScript` - Technical documentation
- `https://nextjs.org/docs` - JS-heavy docs with navigation
- `https://dev.to/t/javascript` - Infinite scroll or load more buttons

## Project Structure

```
lyftr-scraper/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI application and routes
│   ├── scraper.py           # Scraping logic (static + JS)
│   └── parser.py            # HTML parsing and section extraction
├── run.sh                   # Startup script
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── design_notes.md         # Design decisions and strategies
└── capabilities.json       # Feature implementation status
```

## How It Works

1. **Request Phase**: User submits a URL via the frontend or API
2. **Static Attempt**: First tries to fetch and parse static HTML
3. **JS Fallback**: If insufficient content detected, uses Playwright
4. **Interaction Phase**: Clicks tabs/buttons, scrolls or follows pagination
5. **Parsing Phase**: Extracts sections, metadata, and content
6. **Response**: Returns structured JSON with all extracted data

## Known Limitations

- **Rate Limiting**: No built-in rate limiting; be respectful of target sites
- **Single Domain**: Currently optimized for same-origin scraping
- **Timeout**: Maximum 30-second timeout per page load
- **Captchas**: Cannot bypass CAPTCHA or authentication
- **Anti-Bot**: Some sites may block automated browsers
- **Heavy JavaScript**: Very complex SPAs might not render completely
- **Dynamic Content**: Some lazy-loaded content might be missed

## Configuration

You can modify these settings in `app/scraper.py`:

```python
self.timeout = 30           # Request timeout in seconds
self.max_pages = 3          # Maximum pagination depth
self.max_scrolls = 3        # Maximum scroll iterations
```

## Troubleshooting

### Playwright Installation Issues

If Playwright fails to install browsers:
```bash
# Install manually
playwright install chromium

# Install system dependencies (may need sudo)
playwright install-deps chromium
```

### Port Already in Use

If port 8000 is already in use:
```bash
# Change the port in run.sh or run manually:
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Module Not Found Errors

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Development

### Running Tests
```bash
# Install pytest (optional)
pip install pytest

# Run tests (if implemented)
pytest
```

### Debug Mode
The server runs with `--reload` flag by default, which auto-reloads on code changes.

## Contributing

This is an assignment project, but suggestions are welcome!

## License

MIT License (or as specified by Lyftr AI)

## Contact

For questions about this assignment, contact: careers@lyftr.ai

---

**Built for Lyftr AI Full-Stack Assignment**