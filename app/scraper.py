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
            
            logger.info(f"Static HTML length: {len(html)} characters")
            
            # Check if we need JS rendering
            needs_js = self._needs_js_rendering(html)
            has_static_pagination = self._detect_static_pagination(html, url)
            
            logger.info(f"needs_js: {needs_js}, has_static_pagination: {has_static_pagination}")
            
            # Strategy decision tree
            if needs_js and not has_static_pagination:
                # True JS-heavy site - use Playwright
                logger.info("Using Playwright for JS-heavy content")
                all_html_pages, js_interactions = await self._js_scrape(url)
                strategy = "js"
                interactions.update(js_interactions)
            elif has_static_pagination:
                # Static site with pagination - use httpx pagination
                logger.info("Using static pagination (httpx)")
                all_html_pages = await self._static_paginate(url, html, interactions)
                strategy = "static-paginated"
            else:
                # Simple static site
                strategy = "static"
                all_html_pages = [html]
            
            logger.info(f"Total HTML pages to parse: {len(all_html_pages)}")
            
            # Parse all HTML pages and merge results
            result = self._parse_and_merge_pages(all_html_pages, url)
            
            logger.info(f"Parsing complete. Sections found: {len(result.get('sections', []))}")
            
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
            logger.error(f"Scraping failed for {url}: {str(e)}", exc_info=True)
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
    
    def _detect_static_pagination(self, html: str, url: str) -> bool:
        """Detect if the page has pagination links that can be followed with static requests"""
        from selectolax.parser import HTMLParser as SelectolaxParser
        
        tree = SelectolaxParser(html)
        
        # Look for common pagination patterns
        pagination_selectors = [
            'a.next',
            'li.next a',
            'a[rel="next"]',
            '.pagination a',
            '.pager a',
        ]
        
        for selector in pagination_selectors:
            elements = tree.css(selector)
            if elements:
                logger.info(f"Static pagination detected via selector: {selector}")
                return True
        
        # Check URL patterns
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in ['/page-', '/page/', '?page=']):
            logger.info(f"Static pagination detected via URL pattern")
            return True
        
        return False
    
    async def _static_paginate(self, base_url: str, first_html: str, interactions: Dict) -> List[str]:
        """Follow pagination links using static HTTP requests"""
        from selectolax.parser import HTMLParser as SelectolaxParser
        
        html_pages = [first_html]
        current_url = base_url
        pages_visited = 1
        
        logger.info(f"STATIC PAGINATION: Starting from {base_url}")
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            while pages_visited < self.max_pages:
                # Parse current HTML to find next link
                tree = SelectolaxParser(html_pages[-1])
                
                # Try to find next page link
                next_link = None
                next_href = None
                
                # Try different selectors
                selectors = [
                    'li.next a',
                    'a.next',
                    'a[rel="next"]',
                    '.pagination a:contains("next")',
                    '.pager a:contains("next")',
                ]
                
                for selector in selectors:
                    elements = tree.css(selector)
                    for element in elements:
                        href = element.attributes.get('href')
                        if href:
                            # Check if it's not a previous link
                            text = element.text().lower()
                            if 'prev' not in text and 'previous' not in text:
                                next_href = href
                                logger.info(f"STATIC PAGINATION: Found next link with selector '{selector}': {href}")
                                break
                    if next_href:
                        break
                
                if not next_href:
                    logger.info("STATIC PAGINATION: No more next links found")
                    break
                
                # Build absolute URL
                absolute_url = urljoin(current_url, next_href)
                
                # Check if already visited
                if absolute_url in interactions["pages"]:
                    logger.info(f"STATIC PAGINATION: Already visited {absolute_url}")
                    break
                
                try:
                    logger.info(f"STATIC PAGINATION: Fetching page {pages_visited + 1}: {absolute_url}")
                    response = await client.get(absolute_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    response.raise_for_status()
                    
                    page_html = response.text
                    html_pages.append(page_html)
                    interactions["pages"].append(absolute_url)
                    
                    logger.info(f"STATIC PAGINATION: Fetched page {pages_visited + 1} (length: {len(page_html)})")
                    
                    current_url = absolute_url
                    pages_visited += 1
                    
                    # Small delay to be respectful
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"STATIC PAGINATION: Failed to fetch {absolute_url}: {str(e)}")
                    break
        
        logger.info(f"STATIC PAGINATION: Complete - collected {len(html_pages)} pages")
        return html_pages
    
    def _parse_and_merge_pages(self, html_pages: List[str], base_url: str) -> Dict:
        """Parse multiple HTML pages and merge their sections"""
        if not html_pages:
            raise ValueError("No HTML pages to parse")
        
        logger.info(f"Parsing {len(html_pages)} HTML page(s)...")
        
        # Parse first page to get base structure
        result = self.parser.parse(html_pages[0], base_url)
        logger.info(f"First page parsed: {len(result.get('sections', []))} sections")
        
        # If only one page, return as-is
        if len(html_pages) == 1:
            return result
        
        # Parse and merge additional pages
        all_sections = result["sections"]
        
        for i, html in enumerate(html_pages[1:], start=1):
            try:
                logger.info(f"Parsing page {i+1}...")
                page_result = self.parser.parse(html, base_url)
                logger.info(f"Page {i+1} parsed: {len(page_result.get('sections', []))} sections")
                
                # Merge sections from this page
                for section in page_result["sections"]:
                    # Update section ID to avoid conflicts
                    original_id = section["id"]
                    section["id"] = f"{original_id}-page{i+1}"
                    section["label"] = f"{section['label']} (Page {i+1})"
                    all_sections.append(section)
                
                logger.info(f"Merged {len(page_result['sections'])} sections from page {i+1}")
            except Exception as e:
                logger.error(f"Failed to parse page {i+1}: {str(e)}", exc_info=True)
        
        result["sections"] = all_sections
        logger.info(f"Total sections after merging: {len(all_sections)}")
        
        return result
    
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
            'data-reactroot', 'data-react-helmet',
            '__next', '_next/static',
            'id="__nuxt"', 'ng-app', 'v-app'
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
        
        logger.info(f"Text content length after cleaning: {text_length} chars")
        
        # If very little text content, probably needs JS
        if text_length < 500:
            logger.info(f"Needs JS: text_length ({text_length}) < 500")
            return True
        
        # If has JS framework and not much content, use JS
        if has_js_framework and text_length < 2000:
            logger.info(f"Needs JS: has framework and text_length ({text_length}) < 2000")
            return True
        
        return False
    
    async def _js_scrape(self, url: str) -> tuple[List[str], Dict]:
        """Scrape using Playwright for JS-rendered content - returns list of HTML pages"""
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
                # Navigate to URL
                logger.info(f"JS: Navigating to {url}")
                await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
                
                # Wait for network to be idle
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    logger.info("Network idle timeout, continuing anyway")
                
                # Wait a bit for any delayed JS
                await asyncio.sleep(2)
                
                # Remove common noise elements
                await self._remove_noise(page)
                
                # Try clicking tabs or "Load more" buttons
                await self._handle_clicks(page, interactions)
                
                # Get HTML from first page
                html_pages.append(await page.content())
                logger.info(f"JS: Captured HTML from page 1 (length: {len(html_pages[0])})")
                
                # Handle scrolling/pagination and collect additional pages
                additional_pages = await self._handle_scroll_pagination(page, interactions)
                html_pages.extend(additional_pages)
                
                logger.info(f"JS: Total HTML pages collected: {len(html_pages)}")
                
                await browser.close()
                return html_pages, interactions
                
            except Exception as e:
                logger.error(f"JS scraping error: {str(e)}", exc_info=True)
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
            '.morelink'
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
    
    async def _handle_scroll_pagination(self, page, interactions: Dict) -> List[str]:
        """Handle infinite scroll or pagination - returns list of HTML from additional pages"""
        additional_html_pages = []
        
        # First, try to find pagination links
        pagination_html = await self._handle_pagination(page, interactions)
        additional_html_pages.extend(pagination_html)
        
        if not pagination_html:
            # Fall back to infinite scroll
            await self._handle_infinite_scroll(page, interactions)
        
        return additional_html_pages
    
    async def _handle_pagination(self, page, interactions: Dict) -> List[str]:
        """Follow pagination links and return HTML from each page"""
        pages_visited = 1
        current_url = page.url
        html_pages = []
        
        logger.info(f"PAGINATION: Starting from: {current_url}")
        
        # Site-specific pagination strategies
        if 'news.ycombinator.com' in current_url:
            return await self._handle_hackernews_pagination(page, interactions)
        
        pagination_selectors = [
            'a:has-text("next")',
            'a:has-text("Next")',
            'li.next > a',
            'a.next',
            'a[rel="next"]',
        ]
        
        while pages_visited < self.max_pages:
            next_link = None
            next_href = None
            
            for selector in pagination_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        try:
                            is_visible = await element.is_visible()
                            if not is_visible:
                                continue
                            
                            href = await element.get_attribute('href')
                            if not href:
                                continue
                            
                            href_lower = href.lower()
                            if any(term in href_lower for term in ['prev', 'previous', 'back']):
                                continue
                            
                            absolute_url = urljoin(page.url, href)
                            
                            if absolute_url in interactions["pages"]:
                                continue
                            
                            next_link = element
                            next_href = absolute_url
                            logger.info(f"Found pagination link: {absolute_url}")
                            break
                            
                        except Exception as e:
                            continue
                    
                    if next_link:
                        break
                        
                except Exception as e:
                    continue
            
            if not next_link or not next_href:
                logger.info(f"No more next links found")
                break
            
            try:
                logger.info(f"Navigating to page {pages_visited + 1}: {next_href}")
                await page.goto(next_href, wait_until='domcontentloaded', timeout=15000)
                
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass
                
                interactions["pages"].append(next_href)
                await asyncio.sleep(2)
                
                page_html = await page.content()
                html_pages.append(page_html)
                logger.info(f"Captured HTML from page {pages_visited + 1}")
                
                pages_visited += 1
                
            except Exception as e:
                logger.warning(f"Navigation failed: {str(e)}")
                break
        
        return html_pages
    
    async def _handle_hackernews_pagination(self, page, interactions: Dict) -> List[str]:
        """Special handler for Hacker News pagination"""
        pages_visited = 1
        html_pages = []
        
        logger.info("Using Hacker News-specific pagination")
        
        while pages_visited < self.max_pages:
            try:
                more_link = await page.query_selector('a.morelink')
                
                if not more_link:
                    break
                
                href = await more_link.get_attribute('href')
                if not href:
                    break
                
                absolute_url = urljoin(page.url, href)
                
                if absolute_url in interactions["pages"]:
                    break
                
                await page.goto(absolute_url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)
                
                interactions["pages"].append(absolute_url)
                
                page_html = await page.content()
                html_pages.append(page_html)
                
                pages_visited += 1
                
            except Exception as e:
                logger.warning(f"HN pagination failed: {str(e)}")
                break
        
        return html_pages
    
    async def _handle_infinite_scroll(self, page, interactions: Dict):
        """Handle infinite scroll by scrolling down"""
        
        logger.info("Attempting infinite scroll")
        
        for i in range(self.max_scrolls):
            try:
                prev_height = await page.evaluate('document.body.scrollHeight')
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                interactions["scrolls"] += 1
                await asyncio.sleep(3)
                
                new_height = await page.evaluate('document.body.scrollHeight')
                
                if new_height == prev_height:
                    break
                
            except Exception as e:
                break