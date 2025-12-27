import asyncio
import sys
import platform

# Set event loop policy for Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("✓ Windows ProactorEventLoopPolicy set")

async def test_playwright():
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.system()}")
    
    try:
        from playwright.async_api import async_playwright
        print("✓ Playwright imported successfully")
        
        async with async_playwright() as p:
            print("✓ Playwright context created")
            
            browser = await p.chromium.launch(headless=True)
            print("✓ Browser launched")
            
            page = await browser.new_page()
            print("✓ Page created")
            
            await page.goto('https://quotes.toscrape.com/scroll')
            print("✓ Page loaded")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Try to scroll
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            print("✓ Scroll executed")
            
            await asyncio.sleep(2)
            
            # Get content
            html = await page.content()
            print(f"✓ Content retrieved: {len(html)} characters")
            
            # Count quotes
            quotes = await page.query_selector_all('.quote')
            print(f"✓ Found {len(quotes)} quotes")
            
            await browser.close()
            print("✓ Browser closed")
            
            print("\n✅ SUCCESS! Playwright is working correctly!")
            return True
            
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_playwright())
    sys.exit(0 if result else 1)