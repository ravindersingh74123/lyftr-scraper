# Design Notes

## Static vs JS Fallback

**Strategy**: Static-first with intelligent fallback to JavaScript rendering.

The scraper attempts static HTML fetching using `httpx` first, then analyzes the response to determine if JavaScript rendering is necessary. The fallback is triggered when:

1. **Minimal text content**: Less than 500 characters of visible text in the body
2. **JS framework detection**: Presence of React, Vue, Angular, Next.js markers in HTML
3. **Framework + Low content**: JS framework detected AND less than 2000 characters of content

This heuristic-based approach optimizes performance by avoiding Playwright when unnecessary, while ensuring JS-heavy sites are properly rendered. The strategy is documented in the `_needs_js_rendering()` method of `UniversalScraper`.

**Rationale**: Static scraping is ~10x faster than browser automation, so we maximize its use while ensuring we don't miss JS-rendered content.

## Wait Strategy for JS

- [x] Network idle
- [ ] Fixed sleep
- [x] Wait for selectors
- [ ] Custom wait conditions

**Details**: 

When using Playwright for JS rendering, the scraper uses a combined strategy:

1. **Network Idle Wait**: Primary wait condition using `wait_until='networkidle'` to ensure all network requests complete
2. **Additional Sleep**: 2-second sleep after page load to catch delayed JavaScript execution
3. **Implicit Selector Waits**: When interacting with elements (clicks), uses timeout-based waits for selectors to become available

This multi-layered approach handles various JS rendering patterns, from immediate DOM updates to lazy-loaded content. The network idle strategy works well for most modern SPAs while the additional sleep catches edge cases with delayed renders.

## Click & Scroll Strategy

**Click flows implemented**:
- **Tab clicks**: Detects and clicks `[role="tab"]`, `button[aria-selected]`, and elements with tab-related classes
- **Load more buttons**: Searches for buttons/links with text like "Load more", "Show more", "See more", "View more"
- **Click limit**: Maximum 3 tabs clicked per page to avoid excessive interaction
- **Wait after click**: 1-2 second wait after each click to allow content to load

**Scroll / pagination approach**:
- **Pagination priority**: First attempts to find and follow pagination links (Next, ›, >, [rel="next"])
- **Infinite scroll fallback**: If no pagination links found, performs infinite scroll by:
  - Scrolling to bottom of page
  - Waiting 2 seconds for new content
  - Checking if page height increased
  - Repeating up to 3 times
- **URL tracking**: Records all visited page URLs in `interactions.pages`

**Stop conditions**:
- **Max depth**: 3 pages/scrolls maximum (configurable via `self.max_pages` and `self.max_scrolls`)
- **Timeout**: 30-second timeout per page load
- **No new content**: Stops scrolling if page height doesn't change after scroll
- **Element unavailable**: Stops clicking if next button/link not found or not visible

## Section Grouping & Labels

**How sections are grouped**:

The parser uses a hierarchical strategy:

1. **Semantic landmarks** (Priority 1): Groups content by HTML5 semantic elements:
   - `<header>` → hero section
   - `<nav>` → navigation section
   - `<main>`, `<section>`, `<article>` → content sections
   - `<footer>` → footer section

2. **Heading-based grouping** (Priority 2): If semantic grouping yields <3 sections, groups content under `h1`, `h2`, `h3` headings, treating each heading and its following content as a section.

3. **Full body fallback** (Priority 3): If no sections found, treats entire `<body>` as single section.

**How section `type` and `label` are derived**:

**Type determination**:
- Checks element tag name (nav, header, footer)
- Analyzes class and id attributes for keywords (hero, banner, pricing, faq, grid, list)
- Falls back to generic types (section, unknown)

**Label generation** (in priority order):
1. First heading (`h1`-`h6`) found in section
2. Element's `aria-label` attribute
3. Element's `title` attribute
4. First 5-7 words of section text (with "..." if truncated)
5. Default "Content" if all else fails

This approach ensures meaningful, human-readable labels while maintaining structure.

## Noise Filtering & Truncation

**What is filtered out**:

The scraper proactively removes common noise elements before parsing:

- **Cookie banners**: Elements with class/id containing "cookie", "gdpr", "consent"
- **Modal dialogs**: Elements with `[role="dialog"]` or class "modal"
- **Overlays**: Elements with class containing "popup" or "overlay"
- **Banners**: General banner elements that contain privacy/consent text

**Filtering strategy**:
- Pattern-based selector matching combined with text content validation
- Only removes elements that contain keywords like "cookie", "consent", "privacy", "gdpr", "accept"
- Runs before content extraction to avoid including noise in sections

**How `rawHtml` is truncated and `truncated` flag is set**:

- **Character limit**: 2000 characters maximum for `rawHtml` field
- **Truncation logic**: 
  ```python
  if len(raw_html) > 2000:
      raw_html = raw_html[:2000]
      truncated = True
  else:
      truncated = False
  ```
- **Rationale**: Prevents massive JSON responses while preserving enough HTML for debugging and context understanding
- **Full content available**: The truncated `rawHtml` is only for reference; full content is extracted into the structured `content` object

## Error Handling Strategy

All errors are caught and recorded in the `errors` array with:
- `message`: Human-readable error description
- `phase`: Where the error occurred (fetch, render, parse, scrape)

The scraper returns partial data when possible rather than failing completely, ensuring clients always receive valid JSON structure even on errors.

## Performance Considerations

- **Static-first**: Minimizes expensive browser automation
- **Selector caching**: Reuses parsed elements where possible
- **Content limits**: Caps links (50), images (20), lists (10), tables (5) per section
- **Timeouts**: Prevents hanging on slow/broken sites
- **Async operations**: Uses async/await for concurrent operations where possible

## Future Improvements

Potential enhancements not implemented in this MVP:

1. **Parallel scraping**: Scrape multiple pages concurrently
2. **Caching**: Cache results to avoid re-scraping same URLs
3. **Robots.txt respect**: Check and honor robots.txt rules
4. **Rate limiting**: Built-in rate limiter for responsible scraping
5. **Custom selectors**: Allow users to specify custom selectors for content
6. **Content extraction**: More sophisticated content extraction (e.g., articles, products)
7. **Proxy support**: Route requests through proxies for IP rotation
8. **Session handling**: Maintain cookies/sessions across requests