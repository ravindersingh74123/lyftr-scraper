# Universal Website Scraper

A robust, full-stack web scraping application that intelligently extracts structured data from any website, seamlessly handling both static HTML and JavaScript-rendered content with advanced interaction capabilities.

## 🌟 Features

### Core Capabilities
- **🧠 Intelligent Scraping**: Automatic detection and handling of static vs JS-rendered pages
- **🎯 Smart Fallback Strategy**: Static-first approach with seamless Playwright fallback
- **🔄 Interactive Navigation**: 
  - Clicks tabs and interactive elements
  - Handles "Load More" and "Show More" buttons
  - Supports pagination (depth ≥ 3)
  - Infinite scroll detection and execution
- **📊 Structured Output**: Section-aware JSON with comprehensive metadata
- **🧹 Noise Filtering**: Automatically removes cookie banners, modals, and overlays
- **🎨 Modern UI**: Clean, gradient-based interface with real-time feedback
- **📥 Export Capability**: Download complete scraping results as JSON

### Technical Highlights
- Multi-strategy content extraction (landmarks, headings, content blocks)
- Absolute URL resolution for all links and images
- Comprehensive error handling with detailed reporting
- Windows-compatible async event loop handling
- Subprocess-based Playwright execution for stability
- Real-time progress logging and status updates

## 🚀 Quick Start

### Prerequisites
- **Python**: 3.10 or higher
- **pip**: Python package manager
- **OS**: Linux, macOS, or Windows

### One-Command Setup

```bash
chmod +x run.sh && ./run.sh
```

The script automatically:
1. ✅ Creates a virtual environment
2. ✅ Installs all Python dependencies
3. ✅ Installs Playwright Chromium browser
4. ✅ Configures Windows event loop (if on Windows)
5. ✅ Starts server on `http://localhost:8000`

### Verify Installation

Once the server starts, test the endpoints:

**Health Check:**
```bash
curl http://localhost:8000/healthz
# Expected: {"status":"ok"}
```

**Test Scrape:**
```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

**Web Interface:**
Open your browser and navigate to: `http://localhost:8000`

## 📚 API Documentation

### `GET /healthz`
Health check endpoint to verify server status.

**Response:**
```json
{
  "status": "ok"
}
```

### `POST /scrape`
Main scraping endpoint that extracts structured data from any URL.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "result": {
    "url": "https://example.com",
    "scrapedAt": "2025-12-27T10:00:00Z",
    "meta": {
      "title": "Page Title",
      "description": "Meta description",
      "language": "en",
      "canonical": "https://example.com",
      "strategy": "static|js|static-paginated|static-fallback"
    },
    "sections": [
      {
        "id": "hero-0",
        "type": "hero",
        "label": "Welcome to Example",
        "sourceUrl": "https://example.com",
        "content": {
          "headings": ["Welcome"],
          "text": "Full text content...",
          "links": [
            {"text": "Learn More", "href": "https://example.com/learn"}
          ],
          "images": [
            {"src": "https://example.com/img.png", "alt": "Hero image"}
          ],
          "lists": [["Item 1", "Item 2"]],
          "tables": []
        },
        "rawHtml": "<section>...</section>",
        "truncated": true
      }
    ],
    "interactions": {
      "clicks": [
        "button[role='tab'][0]: Features",
        "button:has-text('Load more')[0]: Load more items"
      ],
      "scrolls": 3,
      "pages": [
        "https://example.com",
        "https://example.com?page=2",
        "https://example.com?page=3"
      ]
    },
    "errors": []
  }
}
```

## 🧪 Tested URLs

The scraper has been extensively tested with the following sites:

### 1. **Static Content** - Wikipedia
**URL**: `https://en.wikipedia.org/wiki/Artificial_intelligence`

**Characteristics:**
- Well-structured semantic HTML
- Clear heading hierarchy (h1-h6)
- Multiple content sections
- Rich metadata
- Extensive internal linking
- Tables and lists

**Strategy**: `static`  
**Sections**: ~15-20 sections  
**Performance**: ~2-3 seconds

---

### 2. **JS-Rendered + Interactive Tabs** - Vercel
**URL**: `https://vercel.com/`

**Characteristics:**
- Next.js/React-based SPA
- Dynamic tab switching
- Lazy-loaded content
- Modern framework patterns
- Minimal initial HTML

**Strategy**: `js`  
**Interactions**: 3-5 tab clicks  
**Sections**: ~10-15 sections  
**Performance**: ~15-20 seconds

---

### 3. **Static Pagination** - Hacker News
**URL**: `https://news.ycombinator.com/`

**Characteristics:**
- Simple HTML structure
- "More" pagination link
- Consistent item structure
- Server-side rendering
- Minimal JavaScript

**Strategy**: `static-paginated`  
**Pages Visited**: 3 (depth = 3)  
**Sections**: ~90 items (30 per page)  
**Performance**: ~5-7 seconds

---

### 4. **Infinite Scroll** - Quotes to Scrape
**URL**: `https://quotes.toscrape.com/scroll`

**Characteristics:**
- JavaScript-based infinite scroll
- Dynamic content loading
- AJAX requests on scroll
- Progressive content reveal

**Strategy**: `js`  
**Scrolls**: 5  
**Sections**: ~30-50 quote items  
**Performance**: ~20-25 seconds

---

### Additional Compatible Sites

**Static/Documentation:**
- `https://developer.mozilla.org/en-US/docs/Web/JavaScript` - MDN docs
- `https://www.python.org/` - Python.org
- `https://docs.github.com/` - GitHub docs

**JS-Heavy/Interactive:**
- `https://nextjs.org/docs` - Next.js docs with navigation
- `https://mui.com/material-ui/react-tabs/` - Material UI tabs
- `https://tailwindcss.com/` - Tailwind CSS site

**Pagination/Scroll:**
- `https://dev.to/t/javascript` - Dev.to feed
- `https://unsplash.com/s/photos/nature` - Unsplash gallery
- `https://infinite-scroll.com/demo/full-page/` - Infinite scroll demo

## 🏗️ Project Structure

```
lyftr-scraper/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI app, routes, frontend
│   ├── scraper.py               # Scraping orchestration
│   ├── parser.py                # HTML parsing & section extraction
│   └── playwright_helper.py     # Playwright subprocess handler
├── venv/                        # Virtual environment (created by run.sh)
├── run.sh                       # Automated setup & startup script
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── design_notes.md              # Technical design decisions
├── capabilities.json            # Feature implementation matrix
├── SETUP_GUIDE.md              # Detailed setup instructions
└── .gitignore                  # Git ignore patterns
```

## 🔧 Configuration

### Scraper Settings
Customize behavior in `app/scraper.py`:

```python
class UniversalScraper:
    def __init__(self):
        self.timeout = 30           # Request timeout (seconds)
        self.max_pages = 5          # Max pagination depth
        self.max_scrolls = 5        # Max scroll iterations
```

### Parser Settings
Adjust parsing in `app/parser.py`:

```python
class HTMLParser:
    def __init__(self):
        self.max_raw_html_length = 2000  # Max chars for rawHtml
```

### Playwright Settings
Configure in `app/playwright_helper.py`:

```python
max_clicks = 8                    # Max click interactions
viewport = {'width': 1920, 'height': 1080}  # Browser viewport
```

## 🎯 How It Works

### 1. **Request Phase**
User submits URL via frontend or API endpoint.

### 2. **Static Attempt**
- Fetches HTML using `httpx` (fast HTTP client)
- Analyzes content length and JS framework markers
- Determines if static HTML is sufficient

### 3. **JS Fallback (if needed)**
- Launches Playwright Chromium in subprocess
- Waits for network idle + JS execution
- Handles interactions (clicks, scrolls, pagination)
- Extracts final rendered HTML

### 4. **Parsing Phase**
- Groups content into semantic sections
- Extracts metadata, headings, text, links, images
- Generates human-readable labels
- Filters noise (cookie banners, modals)

### 5. **Response**
Returns structured JSON with sections, metadata, and interaction logs.

## 🛡️ Error Handling

The scraper gracefully handles various error scenarios:

### HTTP Errors
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Access blocked (may need different user-agent)
- **404 Not Found**: Invalid URL
- **500+ Server Errors**: Target site issues

### Network Errors
- **Connection Failed**: Firewall, network issues, or invalid domain
- **Timeout**: Page takes longer than configured timeout
- **Too Many Redirects**: Redirect loop detected

### Rendering Errors
- **Playwright Timeout**: Page failed to load in Playwright
- **No Content**: Page has no extractable content
- **JS Execution Failed**: JavaScript rendering issues

All errors are captured in the `errors` array with detailed messages and phase information.

## ⚠️ Known Limitations

### Technical Constraints
- **Single Domain**: Optimized for same-origin scraping (doesn't follow external links)
- **No Authentication**: Cannot handle login-protected content
- **No CAPTCHA**: Cannot bypass CAPTCHA challenges
- **Rate Limiting**: No built-in rate limiting (use responsibly)
- **Heavy SPAs**: Very complex single-page apps might not render completely

### Performance Considerations
- **Memory Usage**: Large pages with many sections can use significant memory
- **Playwright Overhead**: JS rendering adds 10-20 seconds per page
- **Concurrent Requests**: Server handles one request at a time (no parallelization)

### Browser Detection
- **Anti-Bot Systems**: Some sites detect and block Playwright
- **Cloudflare**: May challenge automated browsers
- **Dynamic Anti-Scraping**: Sites with aggressive bot detection may fail

### Content Extraction
- **Shadow DOM**: Content in shadow DOM may be missed
- **Lazy Loading**: Some lazy-loaded content might not trigger
- **Dynamic Updates**: Real-time updates (WebSocket) are not captured

## 🐛 Troubleshooting

### Issue: Playwright Installation Fails

**Solution:**
```bash
# Manual installation
source venv/bin/activate
playwright install chromium

# Install system dependencies (Linux)
sudo playwright install-deps chromium

# macOS usually works without additional deps
```

### Issue: Port 8000 Already in Use

**Solution:**
```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>

# Or use a different port
uvicorn app.main:app --port 8080
```

### Issue: "Module not found" Errors

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Windows Event Loop Errors

**Solution:**
The project includes Windows-specific event loop handling. If issues persist:

```python
# Already implemented in run.sh and scraper.py
import asyncio
import platform

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

### Issue: Scraping Returns Empty Sections

**Possible Causes:**
1. Site requires JavaScript rendering (check `meta.strategy` in response)
2. Site blocks automated requests (check `errors` array)
3. Content is in iframes or shadow DOM

**Solutions:**
- Enable JavaScript rendering (automatic fallback should trigger)
- Check if site allows scraping (robots.txt)
- Inspect browser's Network tab for API endpoints

## 🔐 Best Practices

### Responsible Scraping
- **Respect robots.txt**: Check if scraping is allowed
- **Rate Limiting**: Add delays between requests for same domain
- **User-Agent**: Use descriptive user-agent identifying your bot
- **Terms of Service**: Review target site's ToS before scraping
- **API First**: Use official APIs when available

### Performance Optimization
- **Static First**: Let the static-first strategy work (it's 10x faster)
- **Minimize Depth**: Use lower `max_pages` and `max_scrolls` when possible
- **Batch Processing**: Process multiple URLs sequentially rather than repeatedly
- **Caching**: Consider caching results for frequently accessed URLs

### Security Considerations
- **Validate URLs**: Never scrape user-provided URLs without validation
- **Sanitize Output**: HTML content may contain XSS vectors
- **Resource Limits**: Set memory and CPU limits in production
- **Timeout Enforcement**: Always enforce timeouts to prevent hangs

## 📊 Performance Metrics

Average performance on tested sites:

| Site Type | Strategy | Time | Sections | Pages |
|-----------|----------|------|----------|-------|
| Static (Wikipedia) | static | 2-3s | 15-20 | 1 |
| JS-Heavy (Vercel) | js | 15-20s | 10-15 | 1 |
| Paginated (HN) | static-paginated | 5-7s | ~90 | 3 |
| Infinite Scroll | js | 20-25s | 30-50 | 1 |

## 🚢 Deployment

### Development
```bash
./run.sh
# Server runs with auto-reload
```

### Production
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run with production ASGI server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (Optional)
While the project is designed to run with `./run.sh`, you can containerize it:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    playwright install chromium && \
    playwright install-deps chromium

COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🧪 Testing

### Manual Testing
Use the provided test URLs or the web interface at `http://localhost:8000`.

### API Testing with curl
```bash
# Health check
curl http://localhost:8000/healthz

# Simple scrape
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}' | jq

# Save to file
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://quotes.toscrape.com/scroll"}' \
  > result.json
```

### Automated Testing
```bash
# Install pytest
pip install pytest pytest-asyncio

# Run tests (if implemented)
pytest tests/
```

## 📝 Changelog

### Version 1.0.0 (Current)
- ✅ Static scraping with httpx + selectolax
- ✅ JS rendering fallback with Playwright
- ✅ Click handling (tabs, buttons)
- ✅ Infinite scroll support
- ✅ Static pagination (3+ pages)
- ✅ Section-aware parsing
- ✅ Noise filtering
- ✅ Modern web UI
- ✅ Windows compatibility
- ✅ Comprehensive error handling

