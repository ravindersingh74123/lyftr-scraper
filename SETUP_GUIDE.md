# Quick Setup Guide

## One-Command Setup

```bash
chmod +x run.sh && ./run.sh
```

That's it! The script will handle everything and start the server on `http://localhost:8000`.

## What Happens During Setup

1. ✅ Creates virtual environment (`venv/`)
2. ✅ Activates virtual environment
3. ✅ Installs Python dependencies
4. ✅ Installs Playwright Chromium browser
5. ✅ Starts server on port 8000

## Verify Installation

Once the server starts, test the endpoints:

### 1. Health Check
```bash
curl http://localhost:8000/healthz
```

Expected response:
```json
{"status":"ok"}
```

### 2. Test Scrape
```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

### 3. Open Browser
Navigate to: `http://localhost:8000`

## Manual Testing with UI

1. Open `http://localhost:8000` in your browser
2. Enter a test URL:
   - `https://en.wikipedia.org/wiki/Artificial_intelligence`
   - `https://vercel.com/`
   - `https://news.ycombinator.com/`
3. Click "Scrape"
4. View results and download JSON

## Common Issues

### Issue: "Port 8000 already in use"
**Solution**: Kill the process using the port or change the port:
```bash
# Find process
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8080
```

### Issue: "playwright command not found"
**Solution**: Make sure you're in the virtual environment:
```bash
source venv/bin/activate
playwright install chromium
```

### Issue: "Permission denied: ./run.sh"
**Solution**: Make the script executable:
```bash
chmod +x run.sh
```

### Issue: Playwright browser installation fails
**Solution**: Install system dependencies:
```bash
# On Ubuntu/Debian
playwright install-deps chromium

# On macOS
# Usually works without additional deps

# On other Linux
# May need to install system libraries
```

## Project Structure Verification

After setup, your directory should look like:

```
lyftr-scraper/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── scraper.py
│   └── parser.py
├── venv/                  # Created by run.sh
├── run.sh
├── requirements.txt
├── README.md
├── design_notes.md
├── capabilities.json
├── .gitignore
└── SETUP_GUIDE.md
```

## Next Steps

1. ✅ Server is running at `http://localhost:8000`
2. ✅ Test the health endpoint
3. ✅ Open the UI in browser
4. ✅ Try scraping different URLs
5. ✅ Review the JSON output
6. ✅ Check `design_notes.md` for implementation details

## For Submission

Before submitting to Lyftr AI:

1. ✅ Test all three primary URLs
2. ✅ Verify `capabilities.json` is accurate
3. ✅ Update `README.md` with your specific test results
4. ✅ Push to GitHub
5. ✅ Email careers@lyftr.ai with subject: "Full-Stack Assignment – [Your Name]"

## Support

For issues specific to this assignment, contact: careers@lyftr.ai