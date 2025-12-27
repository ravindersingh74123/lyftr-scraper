from selectolax.parser import HTMLParser as SelectolaxParser
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

class HTMLParser:
    def __init__(self):
        self.max_raw_html_length = 2000  # Characters
        
    def parse(self, html: str, base_url: str) -> Dict:
        """Parse HTML and extract structured data"""
        tree = SelectolaxParser(html)
        
        result = {
            "url": base_url,
            "meta": self._extract_meta(tree, base_url),
            "sections": self._extract_sections(tree, base_url)
        }
        
        return result
    
    def _extract_meta(self, tree: SelectolaxParser, base_url: str) -> Dict:
        """Extract page metadata"""
        meta = {
            "title": "",
            "description": "",
            "language": "en",
            "canonical": None
        }
        
        # Title
        title_tag = tree.css_first('title')
        if title_tag:
            meta["title"] = title_tag.text().strip()
        else:
            # Try og:title
            og_title = tree.css_first('meta[property="og:title"]')
            if og_title and og_title.attributes.get('content'):
                meta["title"] = og_title.attributes['content'].strip()
        
        # Description
        desc_tag = tree.css_first('meta[name="description"]')
        if desc_tag and desc_tag.attributes.get('content'):
            meta["description"] = desc_tag.attributes['content'].strip()
        else:
            # Try og:description
            og_desc = tree.css_first('meta[property="og:description"]')
            if og_desc and og_desc.attributes.get('content'):
                meta["description"] = og_desc.attributes['content'].strip()
        
        # Language
        html_tag = tree.css_first('html')
        if html_tag and html_tag.attributes.get('lang'):
            meta["language"] = html_tag.attributes['lang'].strip()
        
        # Canonical
        canonical_tag = tree.css_first('link[rel="canonical"]')
        if canonical_tag and canonical_tag.attributes.get('href'):
            meta["canonical"] = urljoin(base_url, canonical_tag.attributes['href'])
        
        return meta
    
    def _extract_sections(self, tree: SelectolaxParser, base_url: str) -> List[Dict]:
        """Extract and group content into sections"""
        sections = []
        section_id = 0
        
        # Try to find main content area first
        main_content = tree.css_first('main') or tree.css_first('[role="main"]')
        
        if not main_content:
            main_content = tree.css_first('body')
        
        # Strategy 1: Extract by semantic landmarks
        landmarks = [
            ('header', 'header'),
            ('nav', 'nav'),
            ('main', 'section'),
            ('section', 'section'),
            ('article', 'section'),
            ('aside', 'section'),
            ('footer', 'footer')
        ]
        
        found_sections = []
        processed_elements = set()
        
        for tag, section_type in landmarks:
            elements = tree.css(tag)
            for element in elements:
                # Avoid duplicate processing
                elem_id = id(element)
                if elem_id in processed_elements:
                    continue
                processed_elements.add(elem_id)
                
                section_data = self._parse_section(element, base_url, section_id, section_type)
                if section_data and section_data["content"]["text"].strip():  # Only add if has content
                    found_sections.append(section_data)
                    section_id += 1
        
        # Strategy 2: Extract articles/divs with substantial content
        if len(found_sections) < 5:
            content_sections = self._extract_content_blocks(tree, base_url, section_id, processed_elements)
            found_sections.extend(content_sections)
            section_id += len(content_sections)
        
        # Strategy 3: If we found very few sections, try grouping by headings
        if len(found_sections) < 3:
            heading_sections = self._extract_by_headings(tree, base_url, section_id)
            found_sections.extend(heading_sections)
        
        # If still no sections, create one from body
        if not found_sections:
            body = tree.css_first('body')
            if body:
                section_data = self._parse_section(body, base_url, 0, "unknown")
                if section_data:
                    found_sections.append(section_data)
        
        # Ensure we always return at least one section
        if not found_sections:
            found_sections.append({
                "id": "default-0",
                "type": "unknown",
                "label": "Content",
                "sourceUrl": base_url,
                "content": {
                    "headings": [],
                    "text": "No content extracted",
                    "links": [],
                    "images": [],
                    "lists": [],
                    "tables": []
                },
                "rawHtml": "",
                "truncated": False
            })
        
        return found_sections
    
    def _extract_content_blocks(self, tree: SelectolaxParser, base_url: str, start_id: int, processed_elements: set) -> List[Dict]:
        """Extract divs and articles with substantial content"""
        sections = []
        
        # Look for divs/articles with classes that suggest content
        content_selectors = [
            'article',
            'div[class*="post"]',
            'div[class*="item"]',
            'div[class*="card"]',
            'div[class*="content"]',
            'div[class*="story"]',
            'tr.athing'  # Hacker News specific
        ]
        
        section_id = start_id
        for selector in content_selectors:
            elements = tree.css(selector)
            for element in elements:
                elem_id = id(element)
                if elem_id in processed_elements:
                    continue
                
                # Check if has substantial content
                text = element.text(strip=True)
                if len(text) > 50:  # At least 50 characters
                    processed_elements.add(elem_id)
                    section_data = self._parse_section(element, base_url, section_id, "section")
                    if section_data and section_data["content"]["text"].strip():
                        sections.append(section_data)
                        section_id += 1
        
        return sections
    
    def _extract_by_headings(self, tree: SelectolaxParser, base_url: str, start_id: int) -> List[Dict]:
        """Extract sections by grouping content under headings"""
        sections = []
        headings = tree.css('h1, h2, h3')
        
        for i, heading in enumerate(headings):
            section_id = start_id + i
            
            # Get content between this heading and the next
            content_nodes = []
            current = heading.next
            
            while current:
                if current.tag in ['h1', 'h2', 'h3']:
                    break
                content_nodes.append(current)
                current = current.next
            
            # Create a temporary container
            section_html = heading.html + ''.join([node.html for node in content_nodes if hasattr(node, 'html')])
            temp_tree = SelectolaxParser(section_html)
            temp_node = temp_tree.css_first('body') or temp_tree.root
            
            section_data = self._parse_section(temp_node, base_url, section_id, "section")
            if section_data and section_data["content"]["text"]:
                sections.append(section_data)
        
        return sections
    
    def _parse_section(self, element, base_url: str, section_id: int, section_type: str) -> Optional[Dict]:
        """Parse a single section element"""
        if not element:
            return None
        
        # Extract content
        content = {
            "headings": self._extract_headings(element),
            "text": self._extract_text(element),
            "links": self._extract_links(element, base_url),
            "images": self._extract_images(element, base_url),
            "lists": self._extract_lists(element),
            "tables": self._extract_tables(element)
        }
        
        # Generate label
        label = self._generate_label(content, element)
        
        # Determine more specific type
        specific_type = self._determine_section_type(element, section_type)
        
        # Get raw HTML (truncated)
        raw_html = element.html if hasattr(element, 'html') else str(element)
        truncated = len(raw_html) > self.max_raw_html_length
        if truncated:
            raw_html = raw_html[:self.max_raw_html_length]
        
        return {
            "id": f"{specific_type}-{section_id}",
            "type": specific_type,
            "label": label,
            "sourceUrl": base_url,
            "content": content,
            "rawHtml": raw_html,
            "truncated": truncated
        }
    
    def _extract_headings(self, element) -> List[str]:
        """Extract all headings from element"""
        headings = []
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            heading_elements = element.css(tag)
            for h in heading_elements:
                text = h.text().strip()
                if text:
                    headings.append(text)
        return headings
    
    def _extract_text(self, element) -> str:
        """Extract visible text from element"""
        # Remove script and style tags
        for tag in element.css('script, style'):
            tag.decompose()
        
        text = element.text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _extract_links(self, element, base_url: str) -> List[Dict]:
        """Extract all links from element"""
        links = []
        seen_hrefs = set()
        
        for link in element.css('a[href]'):
            href = link.attributes.get('href', '')
            text = link.text().strip()
            
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Make absolute
            absolute_href = urljoin(base_url, href)
            
            # Avoid duplicates
            if absolute_href in seen_hrefs:
                continue
            seen_hrefs.add(absolute_href)
            
            links.append({
                "text": text or "(no text)",
                "href": absolute_href
            })
        
        return links[:50]  # Limit to 50 links per section
    
    def _extract_images(self, element, base_url: str) -> List[Dict]:
        """Extract all images from element"""
        images = []
        seen_srcs = set()
        
        for img in element.css('img'):
            src = img.attributes.get('src') or img.attributes.get('data-src')
            alt = img.attributes.get('alt', '')
            
            if not src:
                continue
            
            # Make absolute
            absolute_src = urljoin(base_url, src)
            
            # Avoid duplicates
            if absolute_src in seen_srcs:
                continue
            seen_srcs.add(absolute_src)
            
            images.append({
                "src": absolute_src,
                "alt": alt
            })
        
        return images[:20]  # Limit to 20 images per section
    
    def _extract_lists(self, element) -> List[List[str]]:
        """Extract lists from element"""
        lists = []
        
        for list_elem in element.css('ul, ol'):
            items = []
            for li in list_elem.css('li'):
                text = li.text().strip()
                if text:
                    items.append(text)
            if items:
                lists.append(items)
        
        return lists[:10]  # Limit to 10 lists per section
    
    def _extract_tables(self, element) -> List[List[List[str]]]:
        """Extract tables from element"""
        tables = []
        
        for table in element.css('table'):
            rows = []
            for tr in table.css('tr'):
                cells = []
                for cell in tr.css('td, th'):
                    text = cell.text().strip()
                    cells.append(text)
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        
        return tables[:5]  # Limit to 5 tables per section
    
    def _generate_label(self, content: Dict, element) -> str:
        """Generate a human-readable label for the section"""
        # Try to use first heading
        if content["headings"]:
            return content["headings"][0]
        
        # Try to use element's aria-label or title
        if hasattr(element, 'attributes'):
            aria_label = element.attributes.get('aria-label')
            if aria_label:
                return aria_label.strip()
            
            title = element.attributes.get('title')
            if title:
                return title.strip()
        
        # Fall back to first 5-7 words of text
        text = content["text"]
        if text:
            words = text.split()[:7]
            label = ' '.join(words)
            if len(words) >= 7:
                label += '...'
            return label
        
        return "Content"
    
    def _determine_section_type(self, element, default_type: str) -> str:
        """Determine more specific section type"""
        if not hasattr(element, 'tag') and not hasattr(element, 'attributes'):
            return default_type
        
        # Check tag name
        tag = element.tag if hasattr(element, 'tag') else None
        if tag == 'nav':
            return 'nav'
        if tag == 'header':
            return 'hero'
        if tag == 'footer':
            return 'footer'
        
        # Check attributes for clues
        attrs = element.attributes if hasattr(element, 'attributes') else {}
        class_name = attrs.get('class', '').lower()
        id_name = attrs.get('id', '').lower()
        
        combined = class_name + ' ' + id_name
        
        if any(word in combined for word in ['hero', 'banner', 'jumbotron']):
            return 'hero'
        if any(word in combined for word in ['nav', 'menu', 'navigation']):
            return 'nav'
        if any(word in combined for word in ['footer']):
            return 'footer'
        if any(word in combined for word in ['pricing', 'price']):
            return 'pricing'
        if any(word in combined for word in ['faq', 'question']):
            return 'faq'
        if any(word in combined for word in ['grid', 'cards']):
            return 'grid'
        if any(word in combined for word in ['list']):
            return 'list'
        
        return default_type