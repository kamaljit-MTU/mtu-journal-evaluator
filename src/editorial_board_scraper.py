"""
Editorial Board Scraper
Extracts editor names, ORCIDs, and affiliations from journal editorial board pages.
"""
import re
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BEAUTIFUL_SOUP = True
except ImportError:
    HAS_BEAUTIFUL_SOUP = False


class EditorialBoardScraper:
    """Scrape editorial board pages for editor information."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    ORCID_PATTERN = re.compile(r'0000-\d{4}-\d{4}-[\dX]', re.IGNORECASE)
    EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

    @staticmethod
    def scrape(url: str) -> Dict[str, Any]:
        """Scrape editorial board page and extract editors."""
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
            response = requests.get(url, headers=EditorialBoardScraper.HEADERS, timeout=15)
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
                    name = EditorialBoardScraper._clean_text(link.get_text())
                    parent = link.find_parent(['td', 'li', 'div', 'p'])
                    affiliation = EditorialBoardScraper._clean_text(parent.get_text()) if parent else None
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
                    email_match = EditorialBoardScraper.EMAIL_PATTERN.search(text)

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

        return result

    @staticmethod
    def _clean_text(text: str) -> Optional[str]:
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:300] if text else None
