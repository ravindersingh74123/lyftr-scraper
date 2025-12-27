"""
Enhanced Playwright helper with improved click handling
Replace the content of app/playwright_helper.py with this version
"""
import sys
import asyncio
import platform
import json

# Set correct event loop policy for Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def handle_clicks(page, interactions):
    """Enhanced click handler with better detection and error handling"""
    clicked = 0
    max_clicks = 8  # Increased from 5
    
    print("🔍 Starting click detection...", file=sys.stderr)
    
    # Strategy 1: Click tabs with expanded selectors
    tab_selectors = [
        # Standard tab roles
        '[role="tab"]:not([aria-selected="true"])',
        'button[role="tab"]:not([aria-selected="true"])',
        'a[role="tab"]:not([aria-selected="true"])',
        
        # Common tab patterns
        '[data-state="inactive"]',
        '[aria-selected="false"]',
        '.tab:not(.active):not(.selected)',
        '.tab-item:not(.active):not(.selected)',
        'button.tab:not(.active)',
        
        # Framework-specific
        '[data-headlessui-state=""]',  # Headless UI inactive tabs
        '.chakra-tabs__tab:not([aria-selected="true"])',  # Chakra UI
        '.MuiTab-root:not(.Mui-selected)',  # Material UI
        
        # Generic button patterns that might be tabs
        'nav button:not(.active)',
        '[class*="tab"][class*="button"]:not([class*="active"])',
    ]
    
    for selector in tab_selectors:
        if clicked >= max_clicks:
            break
        
        try:
            # Wait for potential elements to load
            await asyncio.sleep(0.5)
            
            elements = await page.query_selector_all(selector)
            print(f"  Found {len(elements)} elements for selector: {selector}", file=sys.stderr)
            
            for i, element in enumerate(elements[:5]):
                if clicked >= max_clicks:
                    break
                
                try:
                    # Multiple visibility/clickability checks
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if not is_visible or not is_enabled:
                        continue
                    
                    # Get element info for logging
                    try:
                        text = await element.inner_text()
                        text = text.strip()[:40] if text else ""
                    except:
                        text = ""
                    
                    try:
                        aria_label = await element.get_attribute('aria-label')
                        if aria_label:
                            text = text or aria_label[:40]
                    except:
                        pass
                    
                    label = text or f"element-{i}"
                    
                    # Try to click with multiple strategies
                    click_success = False
                    
                    # Strategy A: Normal click
                    try:
                        await element.click(timeout=3000, force=False)
                        click_success = True
                    except:
                        # Strategy B: Force click (for elements behind overlays)
                        try:
                            await element.click(timeout=3000, force=True)
                            click_success = True
                        except:
                            # Strategy C: JavaScript click
                            try:
                                await element.evaluate('el => el.click()')
                                click_success = True
                            except:
                                pass
                    
                    if click_success:
                        interactions["clicks"].append({
                            "selector": selector,
                            "index": i,
                            "text": label
                        })
                        clicked += 1
                        print(f"  ✓ Clicked: {label}", file=sys.stderr)
                        
                        # Wait for content to load after click
                        await asyncio.sleep(2)
                        
                        # Try to wait for network idle
                        try:
                            await page.wait_for_load_state('networkidle', timeout=3000)
                        except:
                            pass
                    
                except Exception as e:
                    print(f"  ✗ Failed to click element {i}: {str(e)[:50]}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"  ✗ Selector error '{selector}': {str(e)[:50]}", file=sys.stderr)
            continue
    
    # Strategy 2: Load more / Show more buttons
    load_more_selectors = [
        # Text-based (most reliable)
        'button:has-text("Load more")',
        'button:has-text("load more")',
        'button:has-text("Show more")',
        'button:has-text("show more")',
        'button:has-text("See more")',
        'button:has-text("View more")',
        'button:has-text("More")',
        
        'a:has-text("Load more")',
        'a:has-text("Show more")',
        'a:has-text("See more")',
        
        # Class-based
        '[class*="load-more"]',
        '[class*="loadmore"]',
        '[class*="show-more"]',
        '[class*="showmore"]',
        '[class*="view-more"]',
        'button[class*="more"]',
        
        # Data attributes
        '[data-action*="load"]',
        '[data-action*="more"]',
    ]
    
    for selector in load_more_selectors:
        if clicked >= max_clicks:
            break
        
        try:
            await asyncio.sleep(0.5)
            elements = await page.query_selector_all(selector)
            print(f"  Found {len(elements)} load-more for: {selector}", file=sys.stderr)
            
            for i, element in enumerate(elements[:3]):
                if clicked >= max_clicks:
                    break
                
                try:
                    if not await element.is_visible() or not await element.is_enabled():
                        continue
                    
                    try:
                        text = await element.inner_text()
                        text = text.strip()[:40] if text else "load-more"
                    except:
                        text = "load-more"
                    
                    # Try clicking
                    click_success = False
                    try:
                        await element.click(timeout=3000)
                        click_success = True
                    except:
                        try:
                            await element.click(timeout=3000, force=True)
                            click_success = True
                        except:
                            try:
                                await element.evaluate('el => el.click()')
                                click_success = True
                            except:
                                pass
                    
                    if click_success:
                        interactions["clicks"].append({
                            "selector": selector,
                            "index": i,
                            "text": text
                        })
                        clicked += 1
                        print(f"  ✓ Clicked load-more: {text}", file=sys.stderr)
                        
                        # Longer wait for load-more buttons
                        await asyncio.sleep(3)
                        
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except:
                            pass
                    
                except Exception as e:
                    print(f"  ✗ Failed load-more {i}: {str(e)[:50]}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"  ✗ Load-more selector error: {str(e)[:50]}", file=sys.stderr)
            continue
    
    print(f"✅ Click phase complete: {clicked} clicks performed", file=sys.stderr)
    return clicked

async def scrape_with_playwright(url: str, max_scrolls: int = 5):
    """Run Playwright scraping with enhanced click handling"""
    from playwright.async_api import async_playwright
    
    interactions = {
        "clicks": [],
        "scrolls": 0,
        "pages": [url]
    }
    
    html_pages = []
    
    print(f"🚀 Starting Playwright scrape for: {url}", file=sys.stderr)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            # Navigate
            print("📄 Loading page...", file=sys.stderr)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for network idle
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            
            # Initial wait for JS to execute
            await asyncio.sleep(3)
            print("✓ Page loaded", file=sys.stderr)
            
            # Handle clicks (tabs, buttons, etc.)
            print("\n🖱️  Phase 1: Handling clicks", file=sys.stderr)
            clicked_count = await handle_clicks(page, interactions)
            
            if clicked_count > 0:
                print(f"✓ {clicked_count} clicks performed, waiting for content...", file=sys.stderr)
                await asyncio.sleep(2)
            else:
                print("ℹ️  No clickable elements found", file=sys.stderr)
            
            # Handle infinite scroll
            print("\n📜 Phase 2: Handling scroll", file=sys.stderr)
            initial_count = await page.evaluate(
                'document.querySelectorAll(".quote, div.quote, article, .item, section, [class*=card], [class*=post]").length'
            )
            print(f"  Initial element count: {initial_count}", file=sys.stderr)
            
            scrolls_performed = 0
            no_change_count = 0
            
            for i in range(max_scrolls):
                prev_height = await page.evaluate('document.body.scrollHeight')
                
                # Scroll to bottom
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                scrolls_performed += 1
                print(f"  Scroll {i+1}/{max_scrolls} performed", file=sys.stderr)
                
                # Wait for content
                await asyncio.sleep(3)
                
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass
                
                # Check changes
                new_height = await page.evaluate('document.body.scrollHeight')
                new_count = await page.evaluate(
                    'document.querySelectorAll(".quote, div.quote, article, .item, section, [class*=card], [class*=post]").length'
                )
                
                elements_added = new_count - initial_count
                print(f"  → Height: {prev_height} → {new_height}, Elements: {initial_count} → {new_count} (+{elements_added})", file=sys.stderr)
                
                if new_height == prev_height and new_count == initial_count:
                    no_change_count += 1
                    print(f"  ℹ️  No change detected ({no_change_count}/2)", file=sys.stderr)
                    
                    if no_change_count >= 2:
                        print("  ✓ No more content, stopping scroll", file=sys.stderr)
                        break
                else:
                    no_change_count = 0
                    initial_count = new_count
                
                await asyncio.sleep(1)
            
            interactions["scrolls"] = scrolls_performed
            print(f"✓ Scroll phase complete: {scrolls_performed} scrolls", file=sys.stderr)
            
            # Get final HTML
            print("\n📦 Collecting HTML...", file=sys.stderr)
            html_pages.append(await page.content())
            print(f"✓ HTML collected: {len(html_pages[0])} characters", file=sys.stderr)
            
            await browser.close()
            
            print("\n✅ Playwright scraping complete!", file=sys.stderr)
            return {
                "html_pages": html_pages,
                "interactions": interactions,
                "success": True
            }
            
        except Exception as e:
            print(f"\n❌ Error during scraping: {str(e)}", file=sys.stderr)
            await browser.close()
            return {
                "html_pages": [],
                "interactions": interactions,
                "success": False,
                "error": str(e)
            }

if __name__ == "__main__":
    # Read arguments
    url = sys.argv[1] if len(sys.argv) > 1 else "https://vercel.com"
    max_scrolls = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    print(f"Arguments: url={url}, max_scrolls={max_scrolls}", file=sys.stderr)
    
    # Run scraping
    result = asyncio.run(scrape_with_playwright(url, max_scrolls))
    
    # Output as JSON to stdout
    print(json.dumps(result))