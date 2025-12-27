import httpx
import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.parser import HTMLParser

logger = logging.getLogger(__name__)

class UniversalScraper:
    def __init__(self):
        self.parser = HTMLParser()
        self.timeout = 30  # seconds
        self.max_pages = 3
        self.max_scrolls = 3
        
    async def scrape(self, url: str) -> Dict:
        """Main scraping orchestrator"""
        errors = []
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        
        try:
            # Try static scraping first
            logger.info(f"Attempting static scrape for {url}")
            html, strategy = await self._try_static_scrape(url)
            
            # Check if we need JS rendering
            if self._needs_js_rendering(html):
                logger.info(f"Static scrape insufficient, falling back to JS rendering for {url}")
                html, js_interactions = await self._js_scrape(url)
                strategy = "js"
                interactions.update(js_interactions)
            else:
                strategy = "static"
                # Even for static pages, try to handle pagination
                if 'news.ycombinator.com' in url or 'page=' in url:
                    logger.info("Detected pagination site, using JS for better interaction handling")
                    html, js_interactions = await self._js_scrape(url)
                    strategy = "js"
                    interactions.update(js_interactions)
            
            # Parse the HTML
            result = self.parser.parse(html, url)
            
            # Add metadata
            result["scrapedAt"] = datetime.now(timezone.utc).isoformat()
            result["interactions"] = interactions
            result["errors"] = errors
            
            # Optional: add strategy info
            if "meta" not in result:
                result["meta"] = {}
            result["meta"]["strategy"] = strategy
            
            return result
            
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {str(e)}")
            errors.append({
                "message": str(e),
                "phase": "scrape"
            })
            
            # Return minimal valid response even on error
            return {
                "url": url,
                "scrapedAt": datetime.now(timezone.utc).isoformat(),
                "meta": {
                    "title": "",
                    "description": "",
                    "language": "en",
                    "canonical": None
                },
                "sections": [{
                    "id": "error-0",
                    "type": "unknown",
                    "label": "Error",
                    "sourceUrl": url,
                    "content": {
                        "headings": [],
                        "text": f"Failed to scrape: {str(e)}",
                        "links": [],
                        "images": [],
                        "lists": [],
                        "tables": []
                    },
                    "rawHtml": "",
                    "truncated": False
                }],
                "interactions": interactions,
                "errors": errors
            }
    
    async def _try_static_scrape(self, url: str) -> tuple[str, str]:
        """Attempt static HTML fetch"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                return response.text, "static"
        except Exception as e:
            logger.error(f"Static scrape failed: {str(e)}")
            raise
    
    def _needs_js_rendering(self, html: str) -> bool:
        """
        Heuristic to determine if JS rendering is needed.
        Returns True if the page appears to be JS-heavy or has minimal content.
        """
        html_lower = html.lower()
        
        # Check for JS framework markers
        js_markers = [
            'react', 'vue', 'angular', 'next.js',
            'data-reactroot', 'data-react-helmet',
            '__next', '_next/static',
            'id="__nuxt"', 'id="app"'
        ]
        
        has_js_framework = any(marker in html_lower for marker in js_markers)
        
        # Check for body content
        body_start = html_lower.find('<body')
        body_end = html_lower.find('</body>')
        
        if body_start == -1 or body_end == -1:
            return True
        
        body_content = html[body_start:body_end]
        
        # Remove script and style tags
        import re
        clean_body = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        clean_body = re.sub(r'<style[^>]*>.*?</style>', '', clean_body, flags=re.DOTALL | re.IGNORECASE)
        clean_body = re.sub(r'<[^>]+>', ' ', clean_body)
        
        text_length = len(clean_body.strip())
        
        # If very little text content, probably needs JS
        if text_length < 500:
            return True
        
        # If has JS framework and not much content, use JS
        if has_js_framework and text_length < 2000:
            return True
        
        return False
    
    async def _js_scrape(self, url: str) -> tuple[str, Dict]:
        """Scrape using Playwright for JS-rendered content"""
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                # Navigate to URL
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
                
                # Wait for network to be idle
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    logger.info("Network idle timeout, continuing anyway")
                
                # Wait a bit for any delayed JS
                await asyncio.sleep(3)  # Increased from 2 to 3
                
                # Remove common noise elements
                await self._remove_noise(page)
                
                # Try clicking tabs or "Load more" buttons
                await self._handle_clicks(page, interactions)
                
                # Handle scrolling/pagination
                await self._handle_scroll_pagination(page, interactions)
                
                # Get final HTML
                html = await page.content()
                
                await browser.close()
                return html, interactions
                
            except Exception as e:
                logger.error(f"JS scraping error: {str(e)}")
                await browser.close()
                raise
    
    async def _remove_noise(self, page):
        """Remove common noise elements like cookie banners"""
        noise_selectors = [
            '[class*="cookie"]',
            '[id*="cookie"]',
            '[class*="gdpr"]',
            '[class*="consent"]',
            '[class*="banner"]',
            '[role="dialog"]',
            '.modal',
            '[class*="popup"]',
            '[class*="overlay"]'
        ]
        
        for selector in noise_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        text = await element.inner_text()
                        if any(keyword in text.lower() for keyword in ['cookie', 'consent', 'privacy', 'gdpr', 'accept']):
                            await element.evaluate('el => el.remove()')
                            logger.info(f"Removed noise element: {selector}")
                    except:
                        pass
            except:
                pass
    
    async def _handle_clicks(self, page, interactions: Dict):
        """Handle clicking tabs or 'Load more' buttons"""
        
        # Try clicking tabs
        tab_selectors = [
            '[role="tab"]:not([aria-selected="true"])',
            'button[aria-selected="false"]',
            '.tab:not(.active)',
            '[class*="tab"]:not(.active)'
        ]
        
        clicked_tabs = 0
        for selector in tab_selectors:
            if clicked_tabs >= 3:
                break
            try:
                tabs = await page.query_selector_all(selector)
                for i, tab in enumerate(tabs[:3]):
                    if clicked_tabs >= 3:
                        break
                    try:
                        is_visible = await tab.is_visible()
                        if is_visible:
                            await tab.click(timeout=5000)
                            interactions["clicks"].append(f"{selector}[{i}]")
                            clicked_tabs += 1
                            await asyncio.sleep(1)
                            logger.info(f"Clicked tab: {selector}[{i}]")
                    except:
                        pass
            except:
                pass
        
        # Try clicking "Load more" / "Show more" buttons
        load_more_selectors = [
            'button:has-text("Load more")',
            'button:has-text("Show more")',
            'button:has-text("See more")',
            'button:has-text("View more")',
            'a:has-text("Load more")',
            'a:has-text("Show more")',
            'a:has-text("More")',
            '[class*="load-more"]',
            '[class*="show-more"]',
            '.morelink'  # Hacker News specific
        ]
        
        for selector in load_more_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        await button.click(timeout=5000)
                        interactions["clicks"].append(selector)
                        await asyncio.sleep(2)
                        logger.info(f"Clicked load more: {selector}")
                        break
            except Exception as e:
                logger.debug(f"Could not click {selector}: {str(e)}")
    
    async def _handle_scroll_pagination(self, page, interactions: Dict):
        """Handle infinite scroll or pagination"""
        
        # First, try to find pagination links
        pagination_handled = await self._handle_pagination(page, interactions)
        
        if not pagination_handled:
            # Fall back to infinite scroll
            await self._handle_infinite_scroll(page, interactions)
    
    async def _handle_pagination(self, page, interactions: Dict) -> bool:
        """Follow pagination links"""
        pages_visited = 1
        current_url = page.url
        
        logger.info(f"Starting pagination from: {current_url}")
        
        # Site-specific pagination strategies
        if 'news.ycombinator.com' in current_url:
            return await self._handle_hackernews_pagination(page, interactions)
        
        # Generic pagination
        pagination_selectors = [
            'a:has-text("Next")',
            'a:has-text("›")',
            'a:has-text(">")',
            'a:has-text("More")',
            'a[rel="next"]',
            '.pagination a:last-child',
            '[class*="next"]',
            '[class*="more"]'
        ]
        
        while pages_visited < self.max_pages:
            next_link = None
            next_href = None
            
            for selector in pagination_selectors:
                try:
                    link = await page.query_selector(selector)
                    if link:
                        is_visible = await link.is_visible()
                        href = await link.get_attribute('href')
                        
                        if is_visible and href:
                            next_link = link
                            next_href = href
                            logger.info(f"Found pagination link: {selector} -> {href}")
                            break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {str(e)}")
            
            if not next_link or not next_href:
                logger.info("No more pagination links found")
                break
            
            try:
                # Build absolute URL
                absolute_url = urljoin(page.url, next_href)
                
                # Avoid infinite loops
                if absolute_url in interactions["pages"]:
                    logger.info(f"Already visited {absolute_url}, stopping")
                    break
                
                # Navigate to the next page
                logger.info(f"Navigating to page {pages_visited + 1}: {absolute_url}")
                await page.goto(absolute_url, wait_until='domcontentloaded', timeout=15000)
                
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    logger.debug("Network idle timeout")
                
                interactions["pages"].append(absolute_url)
                await asyncio.sleep(2)
                
                pages_visited += 1
                logger.info(f"Successfully navigated to page {pages_visited}")
                
            except Exception as e:
                logger.warning(f"Pagination navigation failed: {str(e)}")
                break
        
        logger.info(f"Pagination complete: visited {pages_visited} pages")
        return pages_visited > 1
    
    async def _handle_hackernews_pagination(self, page, interactions: Dict) -> bool:
        """Special handler for Hacker News pagination"""
        pages_visited = 1
        
        logger.info("Using Hacker News-specific pagination")
        
        while pages_visited < self.max_pages:
            try:
                # Hacker News uses a.morelink at the bottom
                more_link = await page.query_selector('a.morelink')
                
                if not more_link:
                    logger.info("No 'More' link found on Hacker News")
                    break
                
                # Get the href
                href = await more_link.get_attribute('href')
                if not href:
                    logger.info("More link has no href")
                    break
                
                # Build absolute URL
                absolute_url = urljoin(page.url, href)
                
                # Check if already visited
                if absolute_url in interactions["pages"]:
                    logger.info(f"Already visited {absolute_url}")
                    break
                
                logger.info(f"HN: Clicking 'More' to go to: {absolute_url}")
                
                # Navigate to next page
                await page.goto(absolute_url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)
                
                interactions["pages"].append(absolute_url)
                pages_visited += 1
                
                logger.info(f"HN: Successfully navigated to page {pages_visited}")
                
            except Exception as e:
                logger.warning(f"HN pagination failed: {str(e)}")
                break
        
        logger.info(f"HN pagination complete: {pages_visited} pages visited")
        return pages_visited > 1
    
    async def _handle_infinite_scroll(self, page, interactions: Dict):
        """Handle infinite scroll by scrolling down"""
        
        logger.info("Attempting infinite scroll")
        
        for i in range(self.max_scrolls):
            try:
                # Get current height
                prev_height = await page.evaluate('document.body.scrollHeight')
                
                # Scroll to bottom
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                interactions["scrolls"] += 1
                
                # Wait for new content
                await asyncio.sleep(3)
                
                # Try to trigger any lazy load
                await page.evaluate('''
                    window.dispatchEvent(new Event('scroll'));
                    window.dispatchEvent(new Event('resize'));
                ''')
                
                await asyncio.sleep(1)
                
                # Get new height
                new_height = await page.evaluate('document.body.scrollHeight')
                
                logger.info(f"Scroll {i+1}: height {prev_height} -> {new_height}")
                
                # If height didn't change, we've reached the end
                if new_height == prev_height:
                    logger.info(f"Reached end of infinite scroll after {i+1} scrolls")
                    break
                    
                logger.info(f"Scroll {i+1} completed, new content loaded")
                
            except Exception as e:
                logger.warning(f"Scroll {i+1} failed: {str(e)}")
                break