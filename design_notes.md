# Design Notes

## Static vs JS Fallback

**Strategy**: Static-first with intelligent JS rendering fallback via heuristic analysis.

### Decision Logic

The scraper implements a three-stage decision process:

#### Stage 1: Static Fetch Attempt
- Uses `httpx` with standard browser headers
- Timeout: 30 seconds
- Follows redirects automatically
- Handles HTTP errors gracefully (401, 403, 404, 5xx)

#### Stage 2: JS Necessity Detection
After successful static fetch, analyzes HTML to determine if JavaScript rendering is needed:

**Triggers for JS Fallback:**
1. **URL Pattern Detection**:
   - URLs containing `/scroll`, `/js`, `ajax` → Force JS
   - Infinite scroll demos and known JS-heavy sites
   
2. **Minimal Content Detection**:
   - Less than 500 characters of visible text in `<body>` → JS likely needed
   - Accounts for script/style tag removal in calculation

3. **Framework Markers**:
   - React: `data-reactroot`, `data-react-helmet`, `__next`, `_next/static`
   - Vue: `data-vue-`, `v-cloak`, `v-app`, `id="__nuxt"`
   - Angular: `ng-app`, `ng-version`
   - Infinite Scroll: `infinite-scroll`, `data-infinite`, `lazy-load`

4. **Framework + Low Content Heuristic**:
   - JS framework detected AND less than 2000 characters → JS rendering
   - Prevents false positives from framework templates with server-rendered content

#### Stage 3: Fallback Execution
If JS is needed or static fetch fails completely, launches Playwright in subprocess.

### Implementation Details

```python
def _needs_js_rendering(self, html: str, url: str) -> bool:
    # 1. Check URL patterns
    if any(pattern in url.lower() for pattern in ['/scroll', '/js', 'ajax']):
        return True
    
    # 2. Check framework markers
    js_markers = ['data-reactroot', '__next', 'v-app', 'ng-app']
    has_framework = any(marker in html.lower() for marker in js_markers)
    
    # 3. Calculate visible text (remove scripts/styles)
    clean_text_length = len(cleaned_body)
    
    # 4. Apply heuristics
    if clean_text_length < 500:
        return True  # Too little content
    if has_framework and clean_text_length < 2000:
        return True  # Framework with limited content
    
    return False  # Static is sufficient
```

### Rationale

**Performance Optimization**: Static scraping is ~10x faster than Playwright (2-3s vs 15-20s). By detecting when JS is truly necessary, we minimize expensive browser automation.

**Accuracy**: The multi-factor heuristic catches edge cases:
- Server-rendered React/Next.js apps (have framework markers but sufficient content)
- Progressive enhancement sites (work without JS)
- Lazy-loaded content that requires JS
- Pure static sites with minimal frameworks

**Fallback Safety**: If static fails completely (connection errors, timeouts), we skip heuristics and force Playwright.

### Strategy Output

The `meta.strategy` field documents which approach was used:
- `"static"`: Static HTML sufficient
- `"js"`: JS rendering required (heuristic detected)
- `"js-forced"`: Static fetch failed, forced JS
- `"static-fallback"`: JS rendering failed, using static HTML as last resort
- `"static-paginated"`: Static HTML with pagination followed

---

## Wait Strategy for JS

- [x] Network idle
- [ ] Fixed sleep only
- [x] Wait for selectors
- [x] Adaptive waiting

**Details**: 

When Playwright is used, the scraper employs a **layered waiting strategy** to ensure all content is loaded:

### Layer 1: Initial Page Load
```python
await page.goto(url, wait_until='domcontentloaded', timeout=30000)
```
- Waits for DOM to be parsed and ready
- 30-second timeout for slow sites
- Allows early interaction with static elements

### Layer 2: Network Idle
```python
await page.wait_for_load_state('networkidle', timeout=10000)
```
- Waits until no network activity for 500ms
- Catches AJAX requests, API calls, lazy-loaded images
- 10-second timeout to prevent hanging on persistent connections

### Layer 3: JS Execution Buffer
```python
await asyncio.sleep(3)  # After page load
await asyncio.sleep(2)  # After each click
```
- Fixed delays allow JavaScript to execute fully
- Catches delayed DOM updates (setTimeout, requestAnimationFrame)
- Essential for frameworks that batch updates

### Layer 4: Interaction-Specific Waits
```python
await element.click(timeout=3000)  # Per-element timeout
await page.wait_for_load_state('networkidle', timeout=5000)  # Post-click
```
- Each click has its own timeout
- Waits for network activity after interactions
- Prevents premature content extraction

### Layer 5: Scroll Detection
```python
prev_height = await page.evaluate('document.body.scrollHeight')
await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
await asyncio.sleep(3)  # Wait for new content
new_height = await page.evaluate('document.body.scrollHeight')

if new_height == prev_height:
    no_change_count += 1  # Stop after 2 no-change iterations
```
- Monitors page height changes
- Waits 3 seconds per scroll for content to load
- Stops when no new content appears (2 consecutive attempts)

### Rationale

This multi-layered approach handles various rendering patterns:
- **Immediate renders**: Caught by domcontentloaded + network idle
- **Delayed renders**: Caught by sleep buffers
- **User-triggered renders**: Caught by interaction waits
- **Infinite scroll**: Caught by height monitoring

The combination ensures we don't miss content while avoiding excessive waiting.

---

## Click & Scroll Strategy

### Click Flows Implemented

#### 1. Tab Clicking
**Detection Strategy**: Multi-selector approach with expanded patterns

**Tab Selectors** (priority order):
```javascript
// Standard ARIA roles
'[role="tab"]:not([aria-selected="true"])'
'button[role="tab"]:not([aria-selected="true"])'

// Common patterns
'.tab:not(.active)', '.tab-item:not(.active)'
'[data-state="inactive"]', '[aria-selected="false"]'

// Framework-specific
'[data-headlessui-state=""]'  // Headless UI
'.chakra-tabs__tab:not([aria-selected="true"])'  // Chakra UI
'.MuiTab-root:not(.Mui-selected)'  // Material UI
```

**Execution Logic**:
1. Try each selector in order
2. Check visibility and enabled state
3. Attempt three click strategies:
   - Normal click (respects element positioning)
   - Force click (ignores overlays)
   - JavaScript click (bypasses browser restrictions)
4. Wait 2 seconds + network idle after each click
5. Maximum 8 tabs per page

**Interaction Recording**:
```json
{
  "selector": "[role='tab'][0]",
  "index": 0,
  "text": "Features"
}
```

#### 2. "Load More" Button Clicking
**Detection Strategy**: Text-based and pattern-based

**Load More Selectors**:
```javascript
// Text-based (most reliable)
'button:has-text("Load more")'
'button:has-text("Show more")'
'a:has-text("See more")'

// Class-based
'[class*="load-more"]', '[class*="show-more"]'

// Data attributes
'[data-action*="load"]', '[data-action*="more"]'
```

**Execution Logic**:
1. Case-insensitive text matching
2. Three-strategy click attempt (same as tabs)
3. Longer wait (3 seconds + network idle) for content loading
4. Maximum 3 clicks per button type

### Scroll / Pagination Approach

#### Priority 1: Static Pagination (if detected in static HTML)
**Detection**:
```python
# Link-based
'a.next', 'li.next a', 'a[rel="next"]'
'.pagination a', 'a.morelink'

# URL-based
'/page-', '/page/', '?page='
```

**Execution** (using httpx, no Playwright):
1. Parse HTML for next link
2. Make HTTP request to next page
3. Record URL in `interactions.pages`
4. Repeat until max_pages (default: 5) or no next link
5. Merge all HTML pages for parsing

**Special Case - Hacker News**:
```python
async def _handle_hackernews_pagination(page, interactions):
    more_link = await page.query_selector('a.morelink')
    href = await more_link.get_attribute('href')
    # Follow "More" link iteratively
```

#### Priority 2: Browser Pagination (if Playwright is active)
**Detection**:
```javascript
'a:has-text("next")', 'a:has-text("Next")'
'li.next > a', 'a[rel="next"]'
```

**Execution**:
1. Find next link in current page
2. Navigate with Playwright: `page.goto(next_url)`
3. Wait for load + network idle
4. Record page URL
5. Extract HTML
6. Repeat until max_pages

#### Priority 3: Infinite Scroll (if no pagination found)
**Detection**: Automatic fallback if using Playwright

**Execution**:
```python
for i in range(max_scrolls):  # Default: 5
    # Get current state
    prev_height = await page.evaluate('document.body.scrollHeight')
    prev_count = await page.evaluate('/* count elements */')
    
    # Scroll to bottom
    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    
    # Wait for content
    await asyncio.sleep(3)
    await page.wait_for_load_state('networkidle', timeout=5000)
    
    # Check for changes
    new_height = await page.evaluate('document.body.scrollHeight')
    new_count = await page.evaluate('/* count elements */')
    
    if no_changes_for_2_iterations:
        break  # Stop scrolling
```

**Change Detection**:
- Monitors `document.body.scrollHeight`
- Counts content elements (`.quote`, `article`, `.item`, etc.)
- Stops after 2 consecutive iterations with no changes

**Recording**:
```json
{
  "scrolls": 5,
  "pages": ["https://example.com"]  // Single page for infinite scroll
}
```

### Stop Conditions

#### Max Depth Limits
- `max_pages = 5`: Maximum pagination pages to follow
- `max_scrolls = 5`: Maximum scroll iterations
- `max_clicks = 8`: Maximum interactive elements to click

**Rationale**: Prevents infinite loops and excessive resource usage

#### Content-Based Stops
- **No new content**: Height unchanged for 2 consecutive scrolls
- **No next link**: Pagination chain ends
- **Element not found**: Next button/link not in DOM

#### Time-Based Stops
- **Page load timeout**: 30 seconds per page
- **Element wait timeout**: 3-5 seconds per interaction
- **Total scrape timeout**: Implicit (sum of all operations)

#### Error-Based Stops
- **Click failures**: After 3 failed click strategies, skip element
- **Navigation failures**: If `page.goto()` fails, stop pagination
- **Playwright crashes**: Caught and recorded in errors array

---

## Section Grouping & Labels

### How Sections Are Grouped

The parser uses a **hierarchical fallback strategy** with three levels:

#### Strategy 1: Semantic Landmarks (Priority)
Groups content by HTML5 semantic elements:

```python
landmarks = [
    ('header', 'hero'),    # <header> → hero section
    ('nav', 'nav'),        # <nav> → navigation
    ('main', 'section'),   # <main> → content section
    ('section', 'section'),
    ('article', 'section'),
    ('aside', 'section'),
    ('footer', 'footer')   # <footer> → footer section
]
```

**Benefits**:
- Respects page structure intent
- Natural grouping for well-formed HTML
- Captures header, nav, main content, footer automatically

**Deduplication**: Tracks processed elements by ID to avoid duplicates

#### Strategy 2: Content Block Extraction (Supplementary)
If fewer than 5 sections from landmarks, finds content-rich elements:

```python
content_selectors = [
    'article',
    'div[class*="post"]',
    'div[class*="item"]',
    'div[class*="card"]',
    'div[class*="content"]',
    'div[class*="story"]',
    'tr.athing'  # Hacker News specific
]
```

**Criteria**:
- Minimum 50 characters of text
- Not already processed
- Has meaningful content (not just whitespace)

**Purpose**: Catches content in divs when semantic tags aren't used

#### Strategy 3: Heading-Based Grouping (Fallback)
If still fewer than 3 sections, groups by headings (h1-h3):

```python
for heading in ['h1', 'h2', 'h3']:
    # Group heading + following content until next heading
    content_nodes = []
    current = heading.next
    while current and current.tag not in ['h1', 'h2', 'h3']:
        content_nodes.append(current)
```

**Benefits**:
- Works for articles and documentation
- Natural reading flow
- Handles nested content hierarchies

#### Strategy 4: Full Body Fallback (Last Resort)
If no sections found at all, wraps entire `<body>` as single section.

**Purpose**: Ensures response always has at least one section (requirement)

### How Section `type` and `label` Are Derived

#### Type Determination (Priority Order)

**1. Tag-Based Types**:
```python
if element.tag == 'nav':
    return 'nav'
if element.tag == 'header':
    return 'hero'
if element.tag == 'footer':
    return 'footer'
```

**2. Class/ID-Based Types**:
```python
combined = class_name + ' ' + id_name

if 'hero' in combined or 'banner' in combined:
    return 'hero'
if 'nav' in combined or 'menu' in combined:
    return 'nav'
if 'pricing' in combined or 'price' in combined:
    return 'pricing'
if 'faq' in combined or 'question' in combined:
    return 'faq'
if 'grid' in combined or 'cards' in combined:
    return 'grid'
```

**3. Default Fallback**:
```python
return 'section'  # or 'unknown'
```

**Available Types**:
- `hero`: Hero sections, headers, banners
- `nav`: Navigation menus
- `footer`: Page footers
- `section`: Generic content sections
- `list`: Lists of items
- `grid`: Card grids, galleries
- `faq`: FAQ sections
- `pricing`: Pricing tables
- `unknown`: Unclassifiable content

#### Label Generation (Priority Order)

**1. First Heading (Primary)**:
```python
if content["headings"]:
    return content["headings"][0]
```
- Most accurate representation
- User-intended section name

**2. ARIA Label (Accessibility)**:
```python
aria_label = element.attributes.get('aria-label')
if aria_label:
    return aria_label.strip()
```
- Accessibility-first content description
- Often more descriptive than headings

**3. Title Attribute**:
```python
title = element.attributes.get('title')
if title:
    return title.strip()
```
- Tooltip text as fallback

**4. First 5-7 Words of Text (Generated)**:
```python
words = text.split()[:7]
label = ' '.join(words)
if len(words) >= 7:
    label += '...'
```
- Last resort for unlabeled content
- Truncated with ellipsis if longer

**5. Default "Content"**:
```python
return "Content"
```
- Absolute fallback

### Example Section Output

```json
{
  "id": "hero-0",
  "type": "hero",
  "label": "Welcome to Our Platform",
  "sourceUrl": "https://example.com",
  "content": {
    "headings": ["Welcome to Our Platform", "Get Started Today"],
    "text": "Full text content here...",
    "links": [
      {"text": "Sign Up", "href": "https://example.com/signup"}
    ],
    "images": [
      {"src": "https://example.com/hero.jpg", "alt": "Hero image"}
    ],
    "lists": [],
    "tables": []
  },
  "rawHtml": "<header class=\"hero\">...</header>",
  "truncated": true
}
```

---

## Noise Filtering & Truncation

### What Gets Filtered

The scraper proactively removes common noise elements before parsing:

#### Noise Element Patterns

**1. Cookie Banners**:
```python
'[class*="cookie"]'
'[id*="cookie"]'
'[class*="gdpr"]'
'[class*="consent"]'
```

**2. Modal Dialogs**:
```python
'[role="dialog"]'
'.modal'
'[class*="popup"]'
```

**3. Overlays**:
```python
'[class*="overlay"]'
'[class*="backdrop"]'
```

### Filtering Strategy

**Two-Phase Approach**:

#### Phase 1: Playwright Removal (Before HTML Extraction)
```python
async def _remove_noise(self, page):
    for selector in noise_selectors:
        elements = await page.query_selector_all(selector)
        for element in elements:
            text = await element.inner_text()
            # Verify it's actually noise (contains keywords)
            if any(kw in text.lower() for kw in ['cookie', 'consent', 'privacy']):
                await element.evaluate('el => el.remove()')
```

**Benefits**:
- Removes from DOM before HTML capture
- Prevents noise in screenshots/visual artifacts
- Reduces HTML size

#### Phase 2: Parser Removal (During Section Extraction)
```python
# In _extract_text()
for tag in element.css('script, style'):
    tag.decompose()  # Remove completely
```

**Targets**:
- `<script>` tags (JavaScript code)
- `<style>` tags (CSS rules)
- HTML comments

**Benefits**:
- Cleans visible text
- Reduces token count
- Improves readability

### Content Validation

**Keyword Matching**: Only removes elements that contain specific keywords:
```python
keywords = ['cookie', 'consent', 'privacy', 'gdpr', 'accept', 'decline']
```

**Prevents False Positives**: A `<div class="cookie-recipe">` won't be removed unless it contains "cookie consent" text.

### Truncation Strategy

#### rawHtml Truncation

**Configuration**:
```python
self.max_raw_html_length = 2000  # characters
```

**Logic**:
```python
raw_html = element.html if hasattr(element, 'html') else str(element)
truncated = len(raw_html) > self.max_raw_html_length

if truncated:
    raw_html = raw_html[:self.max_raw_html_length]
```

**Output**:
```json
{
  "rawHtml": "<section class=\"content\">...[truncated at 2000 chars]",
  "truncated": true
}
```

**Rationale**:
- **JSON Size**: Prevents massive responses (some sections have 50KB+ HTML)
- **Readability**: 2000 chars is enough for debugging/inspection
- **Complete Data**: Full content is extracted into structured `content` object

#### Content Limits (Per Section)

To prevent memory issues and bloated responses:

```python
# In parser methods
links[:50]      # Max 50 links per section
images[:20]     # Max 20 images per section
lists[:10]      # Max 10 lists per section
tables[:5]      # Max 5 tables per section
```

**Rationale**:
- Most sections have far fewer than these limits
- Prevents edge cases (navigation with 500 links)
- Maintains response structure consistency

### Text Cleaning

**Whitespace Normalization**:
```python
text = re.sub(r'\s+', ' ', text).strip()
```

**Removes**:
- Multiple spaces → single space
- Newlines, tabs → single space
- Leading/trailing whitespace

**Result**: Clean, readable text suitable for analysis or display

---

## Error Handling Strategy

### Error Categories

#### 1. HTTP/Network Errors
```python
# Static fetch phase
except httpx.HTTPStatusError as e:
    status = e.response.status_code
    if status == 401:
        error = "Authentication required"
    elif status == 403:
        error = "Access forbidden (may be blocking bots)"
    elif status == 404:
        error = "Page not found"
    else:
        error = f"HTTP {status}"
```

**Recording**:
```json
{
  "message": "Access forbidden: Site may be blocking automated requests",
  "phase": "static-fetch",
  "type": "HTTPStatusError"
}
```

#### 2. Playwright Errors
```python
# JS rendering phase
except PlaywrightTimeout:
    error = "Playwright timeout - page took too long to load"
except Exception as e:
    error = f"JS rendering failed: {str(e)}"
```

#### 3. Parsing Errors
```python
# Parse phase
except Exception as e:
    logger.error(f"Failed to parse page: {str(e)}")
    # Continue with partial data if possible
```

### Error Response Strategy

**Graceful Degradation**: Always return valid JSON, even on complete failure

```python
def _create_error_response(self, url, error_msg, interactions, errors):
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
```

**Benefits**:
- Client always receives parseable JSON
- Error details in `errors` array
- Partial data preserved when available

### Multi-Layer Fallback

```
Static Fetch → JS Rendering → Static Fallback → Error Response
     ↓              ↓               ↓                ↓
   Success      Success        Partial           Complete
   (fast)      (slower)        (risky)           Failure
```

**Example Flow**:
1. Static fetch fails (403 Forbidden)
2. Try Playwright → Works
3. Return JS-rendered content with error note

```json
{
  "meta": {"strategy": "js-forced"},
  "errors": [
    {
      "message": "Access forbidden: Site may be blocking automated requests",
      "phase": "static-fetch"
    }
  ]
}
```

### Validation

**Post-Processing Validation**:
```python
def _validate_result(self, result):
    assert "url" in result
    assert "sections" in result
    assert len(result["sections"]) > 0
    assert any(s["content"]["text"].strip() for s in result["sections"])
```

**Purpose**: Ensures response meets API contract before returning

---

## Architecture Decisions

### Subprocess Playwright (Windows Compatibility)

**Problem**: Windows has different async event loop behavior than Unix

**Solution**: Run Playwright in separate subprocess
```python
subprocess.run([
    sys.executable, 
    "app/playwright_helper.py", 
    url, 
    str(max_scrolls)
])
```

**Benefits**:
- Isolated event loop (no conflicts)
- Process-level error isolation
- Cross-platform compatibility

**Communication**: JSON via stdout/stderr

### Parser Architecture

**Separation of Concerns**:
- `scraper.py`: Orchestration, fetching, interactions
- `parser.py`: HTML parsing, section extraction
- `playwright_helper.py`: Browser automation

**Benefits**:
- Testable components
- Reusable parsers
- Clear responsibilities

### Frontend Integration

**Embedded HTML**: Single-file frontend in `main.py`

**Rationale**:
- No build step required
- Simple deployment
- Self-contained application

**Alternative**: Could use React + separate build process

---

## Performance Considerations

### Optimization Strategies

**1. Static-First**: Avoid Playwright when possible (10x speedup)

**2. Async I/O**: Use `asyncio` for concurrent operations
```python
async with httpx.AsyncClient() as client:
    # Non-blocking HTTP requests
```

**3. Content Limits**: Cap extracted items to prevent memory bloat

**4. Selector Efficiency**: Use CSS selectors (fast) over XPath

**5. Early Returns**: Stop processing when sufficient data collected

### Memory Management

**HTML Storage**: Only store HTML pages temporarily during merge

**Incremental Parsing**: Parse and discard HTML immediately

**Content Streaming**: Could implement (future enhancement)

---

## Future Enhancements

### Not Implemented (Scope)

1. **Caching**: Redis/memcached for repeated URLs
2. **Rate Limiting**: Throttle requests per domain
3. **Proxy Rotation**: IP rotation for blocked sites
4. **Parallel Scraping**: Concurrent URL processing
5. **Custom Selectors**: User-specified content extraction
6. **API Endpoints**: Expose parser as separate service
7. **Webhooks**: Callback URLs for async scraping
8. **Scheduled Scraping**: Cron-like recurring jobs

### Considered Trade-offs

**Depth Limit**: Set at 3+ to balance completeness vs. speed

**Click Limit**: 8 clicks prevents excessive interaction overhead

**Timeout Values**: Balanced between patience and responsiveness

---

## Testing Approach

### Manual Testing Coverage

✅ **Static sites**: Wikipedia, MDN, Python.org  
✅ **JS-heavy sites**: Vercel, Next.js docs, MUI  
✅ **Pagination**: Hacker News, Dev.to  
✅ **Infinite scroll**: Quotes to Scrape  
✅ **Error cases**: Invalid URLs, 404s, blocked sites  

### Validation

All responses tested against schema:
- Required fields present
- Correct types
- Non-empty sections
- Absolute URLs
- ISO8601 timestamps

---

**Last Updated**: December 27, 2025  
**Author**: Ravinder Singh  
**Project**: Lyftr AI Full-Stack Assignment
