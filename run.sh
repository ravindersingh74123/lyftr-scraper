#!/bin/bash

echo "=========================================="
echo "Universal Website Scraper - Starting..."
echo "=========================================="

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Install Playwright browsers
echo "Installing Playwright browsers (Chromium)..."
playwright install chromium
if [ $? -ne 0 ]; then
    echo "Warning: Playwright browser installation failed, but continuing..."
fi

# Install system dependencies for Playwright (if needed)
echo "Installing Playwright system dependencies..."
playwright install-deps chromium 2>/dev/null || echo "Skipping system dependencies (may need sudo)"

echo ""
echo "=========================================="
echo "Starting server on http://localhost:8000"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server with Windows event loop fix
# Use Python to set event loop policy before starting uvicorn
python -c "
import sys
import platform
import asyncio

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print('✓ Windows event loop policy configured')

import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True, loop='asyncio')
"