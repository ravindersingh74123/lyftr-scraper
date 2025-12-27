import sys
import platform

# CRITICAL: Must be set BEFORE any async operations
if platform.system() == 'Windows':
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("✓ Windows event loop policy set in scraper.py")
    except:
        pass

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
        self.max_pages = 5
        self.max_scrolls = 5
        self.playwright_available = True
        
    """
Complete working scrape() method for app/scraper.py
Replace the entire scrape() method with this version
"""

    async def scrape(self, url: str) -> Dict:
        """Main scraping orchestrator with improved error handling"""
        errors = []
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        
        html = None
        strategy = "unknown"
        static_failed = False
        static_error = None
        js_error = None
        
        try:
            # Try static scraping first
            logger.info(f"Attempting static scrape for {url}")
            
            try:
                html, strategy = await self._try_static_scrape(url)
                logger.info(f"Static HTML fetched: {len(html)} characters")
            except Exception as e:
                static_error = e
                static_error_msg = str(e)
                logger.warning(f"Static scrape failed: {static_error_msg}")
                static_failed = True
                
                # Categorize the error
                error_type = type(e).__name__
                if "401" in static_error_msg or "Unauthorized" in static_error_msg:
                    error_category = "Authentication required"
                elif "403" in static_error_msg or "Forbidden" in static_error_msg:
                    error_category = "Access forbidden"
                elif "404" in static_error_msg:
                    error_category = "Page not found"
                elif "ConnectError" in error_type:
                    error_category = "Connection failed"
                elif "Timeout" in error_type:
                    error_category = "Request timeout"
                else:
                    error_category = error_type
                
                errors.append({
                    "message": f"{error_category}: {static_error_msg}",
                    "phase": "static-fetch",
                    "type": error_type
                })
            
            # If static failed or we need JS rendering
            if static_failed or (html and self._needs_js_rendering(html, url)):
                if static_failed:
                    logger.info(f"Static scraping failed, forcing Playwright")
                else:
                    logger.info(f"JS rendering needed, attempting Playwright")
                
                try:
                    all_html_pages, js_interactions = await self._js_scrape(url)
                    strategy = "js" if not static_failed else "js-forced"
                    interactions.update(js_interactions)
                    
                    logger.info(f"Playwright succeeded: {len(all_html_pages)} pages")
                    
                except Exception as e:
                    js_error = e
                    logger.error(f"Playwright also failed: {str(e)}")
                    
                    # If we have static HTML from earlier, use it as last resort
                    if html and not static_failed:
                        logger.info("Falling back to static HTML despite JS detection")
                        all_html_pages = [html]
                        strategy = "static-fallback"
                        errors.append({
                            "message": f"JS rendering failed: {str(js_error)}",
                            "phase": "js-fallback"
                        })
                    else:
                        # Total failure - can't get any HTML
                        logger.error(f"Complete failure - no HTML available")
                        errors.append({
                            "message": f"All scraping methods failed",
                            "phase": "complete-failure"
                        })
                        
                        # Determine which error to show
                        final_error = static_error if static_error else js_error
                        error_msg = str(final_error) if final_error else "Unknown error"
                        
                        return self._create_error_response(
                            url, 
                            error_msg,
                            interactions, 
                            errors
                        )
            else:
                # Static HTML is sufficient
                has_pagination = self._detect_static_pagination(html, url)
                
                if has_pagination:
                    logger.info("Static pagination detected, using httpx")
                    all_html_pages = await self._static_paginate(url, html, interactions)
                    strategy = "static-paginated"
                else:
                    strategy = "static"
                    all_html_pages = [html]
            
            logger.info(f"Strategy: {strategy}, Pages collected: {len(all_html_pages)}")
            
            # Parse all HTML pages and merge results
            result = self._parse_and_merge_pages(all_html_pages, url)
            
            logger.info(f"Parsing complete. Sections: {len(result.get('sections', []))}")
            
            # Add metadata
            result["scrapedAt"] = datetime.now(timezone.utc).isoformat()
            result["interactions"] = interactions
            result["errors"] = errors
            
            # Add strategy info
            if "meta" not in result:
                result["meta"] = {}
            result["meta"]["strategy"] = strategy
            
            # Validate result
            self._validate_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {str(e)}", exc_info=True)
            errors.append({
                "message": str(e),
                "phase": "scrape"
            })
            
            return self._create_error_response(url, str(e), interactions, errors)
    
    def _validate_result(self, result: Dict):
        """Validate that result meets all requirements"""
        assert "url" in result, "Missing required field: url"
        assert "scrapedAt" in result, "Missing required field: scrapedAt"
        assert "meta" in result, "Missing required field: meta"
        assert "sections" in result, "Missing required field: sections"
        assert "interactions" in result, "Missing required field: interactions"
        
        assert isinstance(result["sections"], list), "sections must be a list"
        assert len(result["sections"]) > 0, "sections must not be empty"
        
        # Check at least one section has content
        has_content = False
        for section in result["sections"]:
            if section.get("content", {}).get("text", "").strip():
                has_content = True
                break
        assert has_content, "At least one section must have non-empty content.text"
        
        logger.info("✓ Result validation passed")
    
    def _create_error_response(self, url: str, error_msg: str, interactions: Dict, errors: List) -> Dict:
        """Create a valid error response"""
        return {
            "url": url,
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
            "meta": {
                "title": "Error",
                "description": "Scraping failed",
                "language": "en",
                "canonical": None,
                "strategy": "error"
            },
            "sections": [{
                "id": "error-0",
                "type": "unknown",
                "label": "Error",
                "sourceUrl": url,
                "content": {
                    "headings": [],
                    "text": f"Failed to scrape: {error_msg}",
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
    
    def _needs_js_rendering(self, html: str, url: str = "") -> bool:
        """
        Enhanced heuristic to determine if JS rendering is needed.
        """
        html_lower = html.lower()
        url_lower = url.lower()
        
        # Check URL patterns that indicate JS-heavy sites
        js_url_patterns = [
            '/scroll',  # Infinite scroll pages
            '/js',      # JS demo pages
            'ajax',     # AJAX content
        ]
        
        # Force JS rendering for known JS-heavy URL patterns
        if any(pattern in url_lower for pattern in js_url_patterns):
            logger.info(f"Needs JS: URL pattern detected ({url})")
            return True
        
        # Check for JS framework markers
        js_markers = [
            'data-reactroot', 'data-react-helmet',
            '__next', '_next/static',
            'id="__nuxt"', 'ng-app', 'v-app',
            'data-vue-', 'v-cloak',
        ]
        
        has_js_framework = any(marker in html_lower for marker in js_markers)
        
        # Check for infinite scroll indicators
        infinite_scroll_indicators = [
            'infinite-scroll',
            'infinite_scroll',
            'data-infinite',
            'scroll-container',
            'lazy-load',
            'data-scroll',
        ]
        
        has_infinite_scroll = any(indicator in html_lower for indicator in infinite_scroll_indicators)
        
        if has_infinite_scroll:
            logger.info(f"Needs JS: Infinite scroll detected in HTML")
            return True
        
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
            logger.info(f"Needs JS: minimal content ({text_length} chars)")
            return True
        
        # If has JS framework and not much content, use JS
        if has_js_framework and text_length < 2000:
            logger.info(f"Needs JS: JS framework detected with limited content")
            return True
        
        logger.info(f"Static sufficient: {text_length} chars")
        return False
    
    def _detect_static_pagination(self, html: str, url: str) -> bool:
        """Detect if the page has pagination links"""
        from selectolax.parser import HTMLParser as SelectolaxParser
        
        tree = SelectolaxParser(html)
        
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
        
        logger.info(f"Static pagination starting from {base_url}")
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            while pages_visited < self.max_pages:
                tree = SelectolaxParser(html_pages[-1])
                next_href = None
                
                selectors = [
                    'li.next a',
                    'a.next',
                    'a[rel="next"]',
                    '.pagination a',
                    'a.morelink',
                ]
                
                for selector in selectors:
                    elements = tree.css(selector)
                    for element in elements:
                        href = element.attributes.get('href')
                        if href:
                            text = element.text().lower()
                            if 'prev' not in text and 'previous' not in text:
                                next_href = href
                                logger.info(f"Found next link: {href}")
                                break
                    if next_href:
                        break
                
                if not next_href:
                    logger.info("No more pagination links found")
                    break
                
                absolute_url = urljoin(current_url, next_href)
                
                if absolute_url in interactions["pages"]:
                    logger.info(f"Already visited {absolute_url}")
                    break
                
                try:
                    logger.info(f"Fetching page {pages_visited + 1}: {absolute_url}")
                    response = await client.get(absolute_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    response.raise_for_status()
                    
                    page_html = response.text
                    html_pages.append(page_html)
                    interactions["pages"].append(absolute_url)
                    
                    logger.info(f"✓ Page {pages_visited + 1} fetched ({len(page_html)} chars)")
                    
                    current_url = absolute_url
                    pages_visited += 1
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Failed to fetch {absolute_url}: {str(e)}")
                    break
        
        logger.info(f"Static pagination complete: {len(html_pages)} pages collected")
        return html_pages
    
    def _parse_and_merge_pages(self, html_pages: List[str], base_url: str) -> Dict:
        """Parse multiple HTML pages and merge their sections"""
        if not html_pages:
            raise ValueError("No HTML pages to parse")
        
        logger.info(f"Parsing {len(html_pages)} HTML page(s)...")
        
        result = self.parser.parse(html_pages[0], base_url)
        logger.info(f"Page 1 parsed: {len(result.get('sections', []))} sections")
        
        if len(html_pages) == 1:
            return result
        
        all_sections = result["sections"]
        
        for i, html in enumerate(html_pages[1:], start=1):
            try:
                logger.info(f"Parsing page {i+1}...")
                page_result = self.parser.parse(html, base_url)
                logger.info(f"Page {i+1} parsed: {len(page_result.get('sections', []))} sections")
                
                for section in page_result["sections"]:
                    original_id = section["id"]
                    section["id"] = f"{original_id}-page{i+1}"
                    section["label"] = f"{section['label']} (Page {i+1})"
                    all_sections.append(section)
                
                logger.info(f"✓ Merged {len(page_result['sections'])} sections from page {i+1}")
            except Exception as e:
                logger.error(f"Failed to parse page {i+1}: {str(e)}", exc_info=True)
        
        result["sections"] = all_sections
        logger.info(f"Total sections after merging: {len(all_sections)}")
        
        return result
    
    
    async def _try_static_scrape(self, url: str) -> tuple[str, str]:
        """
        Attempt static HTML fetch with better error handling
        Returns (html, strategy) or raises exception
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, 
                follow_redirects=True,
                verify=True  # Verify SSL certificates
            ) as client:
                response = await client.get(url, headers=headers)
                
                # Check status code
                if response.status_code == 401:
                    raise Exception(f"Authentication required (401). Site requires login or API key.")
                elif response.status_code == 403:
                    raise Exception(f"Access forbidden (403). Site may be blocking automated requests.")
                elif response.status_code == 404:
                    raise Exception(f"Page not found (404). URL may be incorrect.")
                elif response.status_code >= 400:
                    raise Exception(f"HTTP {response.status_code}: {response.reason_phrase}")
                
                response.raise_for_status()  # Raise for other status codes
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    logger.warning(f"Non-HTML content type: {content_type}")
                
                return response.text, "static"
                
        except httpx.HTTPStatusError as e:
            # HTTP error status codes (4xx, 5xx)
            status_code = e.response.status_code
            logger.error(f"HTTP error {status_code} for {url}")
            raise Exception(f"HTTP {status_code}: {e.response.reason_phrase}")
            
        except httpx.ConnectError as e:
            # Connection failed
            logger.error(f"Connection failed for {url}: {str(e)}")
            raise Exception(f"Connection failed. Check firewall/network settings or try Playwright mode.")
            
        except httpx.TimeoutException as e:
            # Request timeout
            logger.error(f"Timeout for {url}")
            raise Exception(f"Request timeout after {self.timeout} seconds")
            
        except httpx.TooManyRedirects as e:
            # Too many redirects
            logger.error(f"Too many redirects for {url}")
            raise Exception(f"Too many redirects")
            
        except Exception as e:
            # Other errors
            logger.error(f"Static scrape error for {url}: {str(e)}")
            raise

        
    async def _js_scrape(self, url: str) -> tuple[List[str], Dict]:
        """Scrape using Playwright via subprocess (Windows fix)"""
        import subprocess
        import json
        
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        
        try:
            # Run Playwright in separate process with correct event loop
            logger.info("Running Playwright in subprocess (Windows compatibility)")
            
            result = subprocess.run(
                [sys.executable, "app/playwright_helper.py", url, str(self.max_scrolls)],
                capture_output=True,
                text=True,
                timeout=90
            )
            
            if result.returncode != 0:
                logger.error(f"Playwright stderr: {result.stderr}")
                raise Exception(f"Playwright subprocess failed: {result.stderr}")
            
            # Log stderr for debugging
            if result.stderr:
                logger.info(f"Playwright logs:\n{result.stderr}")
            
            # Parse result
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON. Output: {result.stdout[:500]}")
                raise Exception(f"Failed to parse Playwright output: {e}")
            
            if not data.get("success"):
                raise Exception(data.get("error", "Unknown error"))
            
            html_pages = data["html_pages"]
            pw_interactions = data["interactions"]
            
            # Format clicks for better display
            formatted_clicks = []
            for click in pw_interactions.get("clicks", []):
                if isinstance(click, dict):
                    formatted_clicks.append(
                        f"{click['selector']}[{click['index']}]: {click['text']}"
                    )
                else:
                    formatted_clicks.append(click)
            
            interactions["clicks"] = formatted_clicks
            interactions["scrolls"] = pw_interactions.get("scrolls", 0)
            interactions["pages"] = pw_interactions.get("pages", [url])
            
            logger.info(f"Playwright subprocess: {len(html_pages)} pages, "
                       f"{len(formatted_clicks)} clicks, {interactions['scrolls']} scrolls")
            
            return html_pages, interactions
            
        except subprocess.TimeoutExpired:
            logger.error("Playwright subprocess timeout")
            raise Exception("Playwright timeout")
        except Exception as e:
            logger.error(f"Playwright subprocess error: {str(e)}")
            raise


    async def _remove_noise(self, page):
        """Remove common noise elements"""
        noise_selectors = [
            '[class*="cookie"]', '[id*="cookie"]',
            '[class*="gdpr"]', '[class*="consent"]',
            '[role="dialog"]', '.modal',
        ]
        
        for selector in noise_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        text = await element.inner_text()
                        if any(kw in text.lower() for kw in ['cookie', 'consent', 'privacy']):
                            await element.evaluate('el => el.remove()')
                    except:
                        pass
            except:
                pass
    
    async def _handle_clicks(self, page, interactions: Dict):
        """Handle clicking tabs or 'Load more' buttons"""
        tab_selectors = [
            '[role="tab"]:not([aria-selected="true"])',
            'button[aria-selected="false"]',
        ]
        
        clicked_tabs = 0
        for selector in tab_selectors:
            if clicked_tabs >= 5:
                break
            try:
                tabs = await page.query_selector_all(selector)
                for i, tab in enumerate(tabs[:5]):
                    if clicked_tabs >= 5:
                        break
                    try:
                        if await tab.is_visible():
                            await tab.click(timeout=5000)
                            interactions["clicks"].append(f"{selector}[{i}]")
                            clicked_tabs += 1
                            await asyncio.sleep(1)
                            logger.info(f"Clicked tab: {selector}[{i}]")
                    except:
                        pass
            except:
                pass
    
    async def _handle_scroll_pagination(self, page, interactions: Dict) -> List[str]:
        """Handle scrolling or pagination"""
        additional_html_pages = []
        
        # Try pagination first
        pagination_html = await self._handle_pagination(page, interactions)
        additional_html_pages.extend(pagination_html)
        
        if not pagination_html:
            # Fall back to infinite scroll
            await self._handle_infinite_scroll(page, interactions)
        
        return additional_html_pages
    
    async def _handle_pagination(self, page, interactions: Dict) -> List[str]:
        """Follow pagination links"""
        pages_visited = 1
        html_pages = []
        
        if 'news.ycombinator.com' in page.url:
            return await self._handle_hackernews_pagination(page, interactions)
        
        pagination_selectors = [
            'a:has-text("next")', 'a:has-text("Next")',
            'li.next > a', 'a.next', 'a[rel="next"]',
        ]
        
        while pages_visited < self.max_pages:
            next_href = None
            
            for selector in pagination_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        try:
                            if not await element.is_visible():
                                continue
                            href = await element.get_attribute('href')
                            if not href or 'prev' in href.lower():
                                continue
                            
                            absolute_url = urljoin(page.url, href)
                            if absolute_url in interactions["pages"]:
                                continue
                            
                            next_href = absolute_url
                            break
                        except:
                            continue
                    if next_href:
                        break
                except:
                    continue
            
            if not next_href:
                break
            
            try:
                await page.goto(next_href, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)
                
                interactions["pages"].append(next_href)
                html_pages.append(await page.content())
                pages_visited += 1
                
            except Exception as e:
                logger.warning(f"Pagination failed: {str(e)}")
                break
        
        return html_pages
    
    async def _handle_hackernews_pagination(self, page, interactions: Dict) -> List[str]:
        """Hacker News-specific pagination"""
        pages_visited = 1
        html_pages = []
        
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
                html_pages.append(await page.content())
                pages_visited += 1
                
            except Exception as e:
                break
        
        return html_pages
    
    async def _handle_infinite_scroll(self, page, interactions: Dict):
        """
        Enhanced infinite scroll handler
        """
        logger.info("Starting infinite scroll handling...")
        
        # Get initial content count
        try:
            initial_count = await page.evaluate('''() => {
                return document.querySelectorAll('div.quote, .quote, article, .item').length;
            }''')
            logger.info(f"Initial element count: {initial_count}")
        except:
            initial_count = 0
        
        scrolls_performed = 0
        no_change_count = 0
        
        for i in range(self.max_scrolls):
            try:
                # Get current state
                prev_height = await page.evaluate('document.body.scrollHeight')
                
                logger.info(f"Scroll {i+1}: Current height={prev_height}")
                
                # Scroll to bottom
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                scrolls_performed += 1
                
                # Wait for content to load
                await asyncio.sleep(3)  # Increased wait time
                
                # Additional wait for network
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass
                
                # Check if height changed
                new_height = await page.evaluate('document.body.scrollHeight')
                
                # Count elements again
                try:
                    new_count = await page.evaluate('''() => {
                        return document.querySelectorAll('div.quote, .quote, article, .item').length;
                    }''')
                    elements_added = new_count - initial_count
                    logger.info(f"After scroll {i+1}: height={new_height}, elements={new_count} (+{elements_added})")
                except:
                    new_count = initial_count
                    elements_added = 0
                
                # Check if content was added
                height_changed = new_height > prev_height
                elements_changed = new_count > initial_count
                
                if not height_changed and not elements_changed:
                    no_change_count += 1
                    logger.info(f"No change detected (count: {no_change_count})")
                    
                    if no_change_count >= 2:
                        logger.info("No new content after 2 attempts, stopping scroll")
                        break
                else:
                    no_change_count = 0
                    logger.info(f"✓ New content loaded (height: {prev_height}→{new_height}, elements: {initial_count}→{new_count})")
                    initial_count = new_count
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"Scroll {i+1} failed: {str(e)}")
                break
        
        interactions["scrolls"] = scrolls_performed
        logger.info(f"Infinite scroll complete: {scrolls_performed} scrolls performed")