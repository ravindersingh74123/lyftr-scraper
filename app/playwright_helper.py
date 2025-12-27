"""
Helper script to run Playwright in a separate process with correct event loop policy
This is needed because FastAPI's event loop on Windows doesn't support subprocess
"""
import sys
import asyncio
import platform
import json

# Set correct event loop policy for Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def handle_clicks(page, interactions):
    """Handle clicking tabs, buttons, and interactive elements"""
    clicked = 0
    
    # Strategy 1: Click tabs
    tab_selectors = [
        '[role="tab"]:not([aria-selected="true"])',
        'button[role="tab"]:not([aria-selected="true"])',
        '[data-state="inactive"]',
        '.tab:not(.active)',
        'button[aria-selected="false"]',
    ]
    
    for selector in tab_selectors:
        if clicked >= 5:
            break
        try:
            elements = await page.query_selector_all(selector)
            for i, element in enumerate(elements[:5]):
                if clicked >= 5:
                    break
                try:
                    if await element.is_visible():
                        # Get text for logging
                        text = await element.inner_text()
                        text = text.strip()[:30] if text else f"element-{i}"
                        
                        await element.click(timeout=3000)
                        interactions["clicks"].append(f"{selector}[{i}]: {text}")
                        clicked += 1
                        await asyncio.sleep(1.5)
                except Exception as e:
                    pass
        except:
            pass
    
    # Strategy 2: Click "Load more" / "Show more" buttons
    load_more_selectors = [
        'button:has-text("Load more")',
        'button:has-text("Show more")',
        'button:has-text("View more")',
        'a:has-text("Load more")',
        '[class*="load-more"]',
        '[class*="show-more"]',
    ]
    
    for selector in load_more_selectors:
        if clicked >= 5:
            break
        try:
            elements = await page.query_selector_all(selector)
            for i, element in enumerate(elements[:3]):
                if clicked >= 5:
                    break
                try:
                    if await element.is_visible():
                        text = await element.inner_text()
                        text = text.strip()[:30] if text else "load-more"
                        
                        await element.click(timeout=3000)
                        interactions["clicks"].append(f"{selector}: {text}")
                        clicked += 1
                        await asyncio.sleep(2)
                except:
                    pass
        except:
            pass
    
    return clicked

async def scrape_with_playwright(url: str, max_scrolls: int = 5):
    """Run Playwright scraping"""
    from playwright.async_api import async_playwright
    
    interactions = {
        "clicks": [],
        "scrolls": 0,
        "pages": [url]
    }
    
    html_pages = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Navigate
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for network idle
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            
            await asyncio.sleep(2)
            
            # Handle clicks (tabs, buttons, etc.)
            clicked_count = await handle_clicks(page, interactions)
            if clicked_count > 0:
                # Wait after clicks for content to load
                await asyncio.sleep(2)
            
            # Handle infinite scroll
            initial_count = await page.evaluate(
                'document.querySelectorAll(".quote, div.quote, article, .item, section, [class*=card]").length'
            )
            
            scrolls_performed = 0
            no_change_count = 0
            
            for i in range(max_scrolls):
                prev_height = await page.evaluate('document.body.scrollHeight')
                
                # Scroll
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                scrolls_performed += 1
                
                # Wait
                await asyncio.sleep(3)
                
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass
                
                # Check changes
                new_height = await page.evaluate('document.body.scrollHeight')
                new_count = await page.evaluate(
                    'document.querySelectorAll(".quote, div.quote, article, .item, section, [class*=card]").length'
                )
                
                if new_height == prev_height and new_count == initial_count:
                    no_change_count += 1
                    if no_change_count >= 2:
                        break
                else:
                    no_change_count = 0
                    initial_count = new_count
                
                await asyncio.sleep(1)
            
            interactions["scrolls"] = scrolls_performed
            
            # Get HTML
            html_pages.append(await page.content())
            
            await browser.close()
            
            return {
                "html_pages": html_pages,
                "interactions": interactions,
                "success": True
            }
            
        except Exception as e:
            await browser.close()
            return {
                "html_pages": [],
                "interactions": interactions,
                "success": False,
                "error": str(e)
            }

if __name__ == "__main__":
    # Read arguments
    url = sys.argv[1] if len(sys.argv) > 1 else "https://quotes.toscrape.com/scroll"
    max_scrolls = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    # Run scraping
    result = asyncio.run(scrape_with_playwright(url, max_scrolls))
    
    # Output as JSON
    print(json.dumps(result))