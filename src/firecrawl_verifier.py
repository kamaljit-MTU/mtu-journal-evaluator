"""
Firecrawl-backed web verifier for MTU Journal Evaluator.

Uses Firecrawl REST API to scrape journal pages and extract:
- Editor-in-Chief name and ORCID
- DOI patterns/attributions
- Other verifiable signals from the journal website
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests


FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v2"


class FirecrawlVerifier:
    """Verifies journal metadata by scraping with Firecrawl."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FIRECRAWL_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def scrape(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        """Scrape a URL via Firecrawl and return markdown + metadata."""
        if not self.api_key:
            return {"error": "FIRECRAWL_API_KEY not configured"}

        endpoint = f"{FIRECRAWL_BASE_URL}/scrape"
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        try:
            resp = requests.post(
                endpoint, headers=self.headers, json=payload, timeout=timeout
            )
            resp.raise_for_status()
            data = resp.json()
            markdown = data.get("data", {}).get("markdown", "")
            return {"url": url, "markdown": markdown, "error": None}
        except requests.RequestException as e:
            return {"url": url, "markdown": "", "error": str(e)}

    def extract_eic_orcid(self, markdown: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Extract Editor-in-Chief name and ORCID from page markdown.

        Returns:
            (found, editor_name, orcid_id)
        """
        if not markdown:
            return False, None, None

        # Look for ORCID pattern
        orcid_match = re.search(r"orcid\.org/(\d{4}-\d{4}-\d{4}-[\dX]{4})", markdown, re.IGNORECASE)
        if not orcid_match:
            # Try plain ORCID ID pattern
            orcid_match = re.search(r"(\d{4}-\d{4}-\d{4}-[\dX]{4})", markdown)

        orcid_id = orcid_match.group(1) if orcid_match else None

        # Look for "Editor-in-Chief" or "Editor In Chief" context
        eic_pattern = re.compile(
            r"Editor[\-\s]in[\-\s]Chief[:\s]+([^\n\r]{3,80})",
            re.IGNORECASE,
        )
        eic_match = eic_pattern.search(markdown)

        if eic_match:
            editor_name = eic_match.group(1).strip()
            # Clean up markdown links: [Name](url) -> Name
            editor_name = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", editor_name)
            editor_name = editor_name.strip()
            found = bool(editor_name)
            return found, editor_name if found else None, orcid_id

        return False, None, orcid_id

    def extract_dois(self, markdown: str, doi_prefix: Optional[str] = None) -> List[str]:
        """
        Extract DOI references from page markdown.

        Args:
            markdown: Page content
            doi_prefix: Optional DOI prefix to filter by, e.g., "10.1109"

        Returns:
            List of DOIs found
        """
        if not markdown:
            return []

        # Match DOI patterns: 10.prefix/suffix
        doi_pattern = re.compile(r"10\.\d{4,}/[^\s\)\>,]+", re.IGNORECASE)
        dois = doi_pattern.findall(markdown)

        # Clean trailing punctuation
        cleaned = []
        for doi in dois:
            doi = doi.rstrip(".,;:!?)")
            if doi:
                cleaned.append(doi)

        if doi_prefix:
            cleaned = [d for d in cleaned if d.startswith(doi_prefix)]

        return list(set(cleaned))

    def verify_eic_orcid(self, journal_url: str) -> Dict[str, Any]:
        """
        Scrape journal page and verify Editor-in-Chief ORCID.

        Returns dict with:
            - found: bool
            - editor_name: str or None
            - orcid_id: str or None
            - orcid_verified: bool
            - source_url: str
            - error: str or None
        """
        result: Dict[str, Any] = {
            "found": False,
            "editor_name": None,
            "orcid_id": None,
            "orcid_verified": False,
            "source_url": journal_url,
            "error": None,
        }

        scrape_result = self.scrape(journal_url)
        if scrape_result.get("error"):
            result["error"] = scrape_result["error"]
            return result

        markdown = scrape_result.get("markdown", "")
        found, editor_name, orcid_id = self.extract_eic_orcid(markdown)

        result["found"] = found
        result["editor_name"] = editor_name
        result["orcid_id"] = orcid_id if orcid_id else None

        # Verify ORCID against orcid.org public registry
        if orcid_id:
            result["orcid_verified"] = self._verify_orcid_public(orcid_id)

        return result

    def verify_doi_attributions(self, journal_url: str, doi_prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape journal page and extract DOI attributions.

        Returns dict with:
            - dois_found: list[str]
            - count: int
            - valid_format: bool
            - error: str or None
        """
        scrape_result = self.scrape(journal_url)
        if scrape_result.get("error"):
            return {
                "dois_found": [],
                "count": 0,
                "valid_format": False,
                "source_url": journal_url,
                "error": scrape_result["error"],
            }

        markdown = scrape_result.get("markdown", "")
        dois = self.extract_dois(markdown, doi_prefix=doi_prefix)

        # Basic format validation: DOI must start with 10.
        valid = all(d.startswith("10.") for d in dois) if dois else False

        return {
            "dois_found": dois,
            "count": len(dois),
            "valid_format": valid,
            "source_url": journal_url,
            "error": None,
        }

    def _verify_orcid_public(self, orcid_id: str) -> bool:
        """Check if ORCID ID exists in public registry."""
        try:
            url = f"https://orcid.org/{orcid_id}"
            resp = requests.get(url, headers={"User-Agent": "MTU/1.0"}, timeout=15)
            return resp.status_code == 200
        except Exception:
            return False
