from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, validator
from datetime import datetime
import logging
from typing import Optional

from app.scraper import UniversalScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Universal Website Scraper")

# Request/Response Models
class ScrapeRequest(BaseModel):
    url: HttpUrl
    
    @validator('url')
    def validate_url_scheme(cls, v):
        if v.scheme not in ['http', 'https']:
            raise ValueError('Only http(s) URLs are supported')
        return v

class HealthResponse(BaseModel):
    status: str

# Initialize scraper
scraper = UniversalScraper()

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    """
    Scrape a given URL and return structured JSON data
    """
    try:
        url_str = str(request.url)
        logger.info(f"Starting scrape for URL: {url_str}")
        
        # Perform scraping
        result = await scraper.scrape(url_str)
        
        logger.info(f"Scrape completed for URL: {url_str}")
        return {"result": result}
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend HTML"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Universal Website Scraper</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            .header {
                text-align: center;
                color: white;
                margin-bottom: 40px;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
            }
            
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .scrape-box {
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                margin-bottom: 30px;
            }
            
            .input-group {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            
            input[type="text"] {
                flex: 1;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            
            input[type="text"]:focus {
                outline: none;
                border-color: #667eea;
            }
            
            button {
                padding: 12px 32px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.3s;
            }
            
            button:hover:not(:disabled) {
                background: #5568d3;
            }
            
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            
            .loading {
                text-align: center;
                padding: 20px;
                color: #667eea;
                font-weight: 600;
            }
            
            .error {
                background: #fee;
                color: #c33;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #c33;
            }
            
            .results {
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            
            .results-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
            }
            
            .results-header h2 {
                color: #333;
            }
            
            .download-btn {
                background: #10b981;
                padding: 10px 24px;
                font-size: 14px;
            }
            
            .download-btn:hover {
                background: #059669;
            }
            
            .meta-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            
            .meta-info h3 {
                margin-bottom: 10px;
                color: #667eea;
            }
            
            .meta-item {
                margin-bottom: 8px;
                color: #555;
            }
            
            .meta-item strong {
                color: #333;
            }
            
            .sections-container {
                margin-top: 20px;
            }
            
            .section {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-bottom: 15px;
                overflow: hidden;
            }
            
            .section-header {
                background: #f8f9fa;
                padding: 15px 20px;
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: background 0.3s;
            }
            
            .section-header:hover {
                background: #e9ecef;
            }
            
            .section-title {
                font-weight: 600;
                color: #333;
            }
            
            .section-type {
                background: #667eea;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            
            .section-content {
                display: none;
                padding: 20px;
                background: white;
            }
            
            .section-content.active {
                display: block;
            }
            
            .json-viewer {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                overflow-x: auto;
                max-height: 400px;
                overflow-y: auto;
            }
            
            .json-viewer pre {
                margin: 0;
                font-size: 13px;
                line-height: 1.5;
                color: #333;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            
            .stat-card {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
            }
            
            .stat-value {
                font-size: 2rem;
                font-weight: bold;
                color: #667eea;
            }
            
            .stat-label {
                color: #666;
                margin-top: 5px;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Universal Website Scraper</h1>
                <p>Extract structured data from any website</p>
            </div>
            
            <div class="scrape-box">
                <div class="input-group">
                    <input 
                        type="text" 
                        id="urlInput" 
                        placeholder="Enter URL (e.g., https://example.com)"
                        value="https://en.wikipedia.org/wiki/Artificial_intelligence"
                    >
                    <button onclick="scrapeUrl()" id="scrapeBtn">Scrape</button>
                </div>
                <div id="loading" class="loading" style="display: none;">
                    ⏳ Scraping in progress... This may take a moment.
                </div>
                <div id="error" class="error" style="display: none;"></div>
            </div>
            
            <div id="results" class="results" style="display: none;">
                <div class="results-header">
                    <h2>Scraping Results</h2>
                    <button onclick="downloadJson()" class="download-btn">⬇️ Download JSON</button>
                </div>
                
                <div id="metaInfo" class="meta-info"></div>
                <div id="stats" class="stats"></div>
                <div id="sections" class="sections-container"></div>
            </div>
        </div>
        
        <script>
            let currentResult = null;
            
            async function scrapeUrl() {
                const urlInput = document.getElementById('urlInput');
                const url = urlInput.value.trim();
                
                if (!url) {
                    showError('Please enter a URL');
                    return;
                }
                
                if (!url.startsWith('http://') && !url.startsWith('https://')) {
                    showError('URL must start with http:// or https://');
                    return;
                }
                
                // Reset UI
                document.getElementById('error').style.display = 'none';
                document.getElementById('results').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('scrapeBtn').disabled = true;
                
                try {
                    const response = await fetch('/scrape', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ url: url })
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Scraping failed');
                    }
                    
                    const data = await response.json();
                    currentResult = data.result;
                    displayResults(data.result);
                    
                } catch (error) {
                    showError(error.message);
                } finally {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('scrapeBtn').disabled = false;
                }
            }
            
            function showError(message) {
                const errorDiv = document.getElementById('error');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
            }
            
            function displayResults(result) {
                // Display meta information
                const metaHtml = `
                    <h3>📄 Page Metadata</h3>
                    <div class="meta-item"><strong>Title:</strong> ${result.meta.title || 'N/A'}</div>
                    <div class="meta-item"><strong>Description:</strong> ${result.meta.description || 'N/A'}</div>
                    <div class="meta-item"><strong>Language:</strong> ${result.meta.language || 'N/A'}</div>
                    <div class="meta-item"><strong>URL:</strong> ${result.url}</div>
                    <div class="meta-item"><strong>Scraped At:</strong> ${new Date(result.scrapedAt).toLocaleString()}</div>
                `;
                document.getElementById('metaInfo').innerHTML = metaHtml;
                
                // Display stats
                const statsHtml = `
                    <div class="stat-card">
                        <div class="stat-value">${result.sections.length}</div>
                        <div class="stat-label">Sections Found</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${result.interactions.clicks.length}</div>
                        <div class="stat-label">Clicks Performed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${result.interactions.scrolls}</div>
                        <div class="stat-label">Scrolls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${result.interactions.pages.length}</div>
                        <div class="stat-label">Pages Visited</div>
                    </div>
                `;
                document.getElementById('stats').innerHTML = statsHtml;
                
                // Display sections
                const sectionsHtml = result.sections.map((section, index) => `
                    <div class="section">
                        <div class="section-header" onclick="toggleSection(${index})">
                            <span class="section-title">${section.label}</span>
                            <span class="section-type">${section.type}</span>
                        </div>
                        <div class="section-content" id="section-${index}">
                            <div class="json-viewer">
                                <pre>${JSON.stringify(section, null, 2)}</pre>
                            </div>
                        </div>
                    </div>
                `).join('');
                document.getElementById('sections').innerHTML = sectionsHtml;
                
                document.getElementById('results').style.display = 'block';
            }
            
            function toggleSection(index) {
                const content = document.getElementById(`section-${index}`);
                content.classList.toggle('active');
            }
            
            function downloadJson() {
                if (!currentResult) return;
                
                const dataStr = JSON.stringify(currentResult, null, 2);
                const dataBlob = new Blob([dataStr], { type: 'application/json' });
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `scrape-${Date.now()}.json`;
                link.click();
                URL.revokeObjectURL(url);
            }
            
            // Allow Enter key to submit
            document.getElementById('urlInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    scrapeUrl();
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)