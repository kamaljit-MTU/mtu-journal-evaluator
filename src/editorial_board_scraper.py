"""
Editorial Board Scraper
Extracts editor names, ORCIDs, and affiliations from journal editorial board pages.
Also searches ORCID.org for missing ORCID IDs and searches for h-index via web search.
"""
import re
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, quote

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BEAUTIFUL_SOUP = True
except ImportError:
    HAS_BEAUTIFUL_SOUP = False


class EditorialBoardScraper:
    """Scrape editorial board pages for editor information and augment with ORCID/h-index lookups."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    ORCID_HEADERS = {
        'User-Agent': 'MTU-Journal-Evaluator/1.0 (mailto:research@mtu.edu)',
        'Accept': 'application/json'
    }

    ORCID_PATTERN = re.compile(r'0000-\d{4}-\d{4}-[\dX]{4}', re.IGNORECASE)
    EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    H_INDEX_PATTERN = re.compile(r'h[- ]?index[:\\s]+(\\d+)', re.IGNORECASE)

    @staticmethod
    def scrape(url: str, augment: bool = True) -> Dict[str, Any]:
        """Scrape editorial board page and extract editors, with optional ORCID/h-index augmentation."""
        result = {
            "url": url,
            "success": False,
            "editors": [],
            "editor_in_chief": None,
            "total_editors": 0,
            "with_orcid": 0,
            "with_affiliation": 0,
            "countries": [],
            "error": None
        }

        if not HAS_BEAUTIFUL_SOUP:
            result["error"] = "BeautifulSoup not installed; install beautifulsoup4 for board scraping"
            return result

        try:
            response = requests.get(url, headers=EditorialBoardScraper.HEADERS, timeout=20)
            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')
            editors = []

            # Strategy 1: Look for ORCID links directly
            orcid_links = soup.find_all('a', href=re.compile(r'orcid\.org', re.IGNORECASE))
            for link in orcid_links:
                orcid_match = EditorialBoardScraper.ORCID_PATTERN.search(link.get('href', ''))
                if orcid_match:
                    orcid_id = orcid_match.group(0)
                    parent = link.find_parent(['td', 'li', 'div', 'p', 'article'])
                    name = None
                    if parent:
                        heading = parent.find(['h1','h2','h3','h4','h5','h6','strong','b'])
                        if heading:
                            name = EditorialBoardScraper._clean_text(heading.get_text())
                        if not name:
                            text = parent.get_text(separator=' ', strip=True)
                            first_line = text.split('\n')[0].strip()
                            if first_line and len(first_line) > 2 and len(first_line) < 200:
                                name = first_line[:200]
                    if not name:
                        name = EditorialBoardScraper._clean_text(link.get_text())
                    affiliation = EditorialBoardScraper._clean_text(parent.get_text()) if parent else None
                    if name and len(name) > 2 and 'orcid' not in name.lower():
                        editors.append({
                            "name": name,
                            "orcid": orcid_id,
                            "affiliation": affiliation,
                            "source": "orcid_link"
                        })

            # Strategy 2: Look for structured tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    text = ' '.join(c.get_text() for c in cells)
                    orcid_match = EditorialBoardScraper.ORCID_PATTERN.search(text)

                    if orcid_match or len(cells) >= 2:
                        editor = {
                            "name": EditorialBoardScraper._clean_text(cells[0].get_text()),
                            "orcid": orcid_match.group(0) if orcid_match else None,
                            "affiliation": EditorialBoardScraper._clean_text(cells[1].get_text()) if len(cells) > 1 else None,
                            "source": "table_row"
                        }
                        if editor["name"] and len(editor["name"]) > 2:
                            editors.append(editor)

            # Strategy 3: Look for div/list patterns with names
            if not editors:
                name_candidates = soup.find_all(['div', 'li', 'p'], class_=re.compile(r'editor|board|member|author', re.IGNORECASE))
                for elem in name_candidates[:50]:
                    text = elem.get_text(separator=' ', strip=True)
                    orcid_match = EditorialBoardScraper.ORCID_PATTERN.search(text)
                    orcid_link = elem.find('a', href=re.compile(r'orcid\.org', re.IGNORECASE))

                    if len(text) > 3 and len(text) < 200:
                        editors.append({
                            "name": text.split('\n')[0][:200],
                            "orcid": orcid_match.group(0) if orcid_match else (EditorialBoardScraper.ORCID_PATTERN.search(orcid_link.get('href', '')).group(0) if orcid_link else None),
                            "affiliation": None,
                            "source": "heuristic"
                        })

            # Deduplicate by name/orcid
            seen = set()
            unique_editors = []
            for e in editors:
                key = (e.get("name") or "") + (e.get("orcid") or "")
                if key and key not in seen:
                    seen.add(key)
                    unique_editors.append(e)
            editors = unique_editors

            result["editors"] = editors[:100]  # Cap
            result["total_editors"] = len(editors)
            result["with_orcid"] = sum(1 for e in editors if e.get("orcid"))
            result["with_affiliation"] = sum(1 for e in editors if e.get("affiliation"))
            result["success"] = len(editors) > 0

        except Exception as e:
            result["error"] = str(e)

        # Augment with ORCID lookups and h-index estimation
        if augment and result["success"]:
            EditorialBoardScraper._augment_editors(editors)

        return result

    @staticmethod
    def _augment_editors(editors: List[Dict[str, Any]]):
        """Augment editor records with missing ORCIDs and h-indices."""
        for editor in editors:
            name = editor.get("name", "")
            parts = name.strip().split()

            # Search ORCID if missing
            if not editor.get("orcid") and len(parts) >= 2:
                orcid_id = EditorialBoardScraper._search_orcid_by_name(parts[0], parts[-1])
                if orcid_id:
                    editor["orcid"] = orcid_id
                    editor["orcid_source"] = "orcid_search"
                else:
                    editor["orcid_source"] = "not_found"

            # Estimate h-index via web search
            if name:
                h_index = EditorialBoardScraper._search_h_index_by_name(name, editor.get("affiliation"))
                editor["h_index"] = h_index.get("h_index_estimate")
                editor["h_index_source"] = h_index.get("h_index_source")
                editor["h_index_confidence"] = h_index.get("h_index_confidence")

    @staticmethod
    def _search_orcid_by_name(given_name: str, family_name: str) -> Optional[str]:
        """Search ORCID.org public API for an ORCID ID by name."""
        try:
            query = f'givenNames:{quote(given_name)}+familyName:{quote(family_name)}'
            url = f"https://pub.orcid.org/v3.0/expanded-search/?q={query}"
            response = requests.get(url, headers=EditorialBoardScraper.ORCID_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get("expanded-result", [])
                if results:
                    return results[0].get("orcid-id")
        except Exception:
            pass
        return None

    @staticmethod
    def _search_h_index_by_name(name: str, affiliation: Optional[str] = None) -> Dict[str, Any]:
        """Search for h-index via web search fallback."""
        result = {
            "h_index_estimate": None,
            "h_index_source": None,
            "h_index_confidence": "low"
        }

        if not name or len(name.strip().split()) < 2:
            return result

        try:
            query = f'"{name}" h-index'
            if affiliation:
                query += f' "{affiliation}"'

            search_url = f"https://www.google.com/search?q={quote(query)}"
            response = requests.get(search_url, headers=EditorialBoardScraper.HEADERS, timeout=10)

            if response.status_code == 200:
                text = response.text.lower()
                h_index_match = EditorialBoardScraper.H_INDEX_PATTERN.search(text)
                if h_index_match:
                    result["h_index_estimate"] = int(h_index_match.group(1))
                    result["h_index_source"] = "web_search"
                    result["h_index_confidence"] = "medium"
        except Exception:
            pass

        return result

    @staticmethod
    def _clean_text(text: str) -> Optional[str]:
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:300] if text else None
