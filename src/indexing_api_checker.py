"""
Indexing API Checker
Free/limited API checks for DOAJ, ERIC.
"""
import re
from typing import Dict, Any, Optional, List


class IndexingAPIChecker:
    @staticmethod
    def check_all(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        return {
            "journal_name": journal_name,
            "doaj": IndexingAPIChecker.check_doaj(journal_name, issn),
            "eric": IndexingAPIChecker.check_eric(journal_name),
            "indexing_claims": IndexingAPIChecker._collect_claims(
                journal_name,
                issn,
            ),
        }

    @staticmethod
    def _collect_claims(journal_name: str, issn: Optional[str]) -> List[str]:
        claims: List[str] = []
        try:
            if IndexingAPIChecker.check_doaj(journal_name, issn).get("found"):
                claims.append("DOAJ")
        except Exception:
            pass
        try:
            if IndexingAPIChecker.check_eric(journal_name).get("found"):
                claims.append("ERIC")
        except Exception:
            pass
        return claims

    @staticmethod
    def check_doaj(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "source": "doaj",
            "found": False,
            "url": None,
            "error": None,
            "detail": "Not found",
        }
        try:
            from urllib.parse import quote
            q = quote(journal_name)
            if issn:
                q = f"issn:{issn}"
            url = f"https://doaj.org/api/search/journals/{q}"
            fc = None
            try:
                from src.firecrawl_verifier import FirecrawlVerifier
                fc = FirecrawlVerifier()
            except Exception:
                fc = None

            data = None
            if fc:
                scrape = fc.scrape(url, timeout=45)
                if scrape.get("error"):
                    result["error"] = scrape.get("error")
                    result["detail"] = f"DOAJ lookup failed: {scrape.get('error')}"
                    return result
                markdown = scrape.get("markdown", "") or ""
                data = {"markdown": markdown, "source_url": url}
            else:
                import requests as req
                resp = req.get(url, timeout=30)
                if resp.status_code != 200:
                    result["detail"] = f"DOAJ lookup failed: HTTP {resp.status_code}"
                    return result
                data = {"markdown": resp.text, "source_url": url}

            markdown = data.get("markdown", "") or ""
            if journal_name.lower() in markdown.lower():
                result["found"] = True
                result["url"] = url
                result["detail"] = "Journal appears in DOAJ search result"
            else:
                result["detail"] = "Not found in DOAJ search result"
        except Exception as e:
            result["error"] = str(e)
            result["detail"] = f"DOAJ check failed: {e}"
        return result

    @staticmethod
    def check_eric(journal_name: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "source": "eric",
            "found": False,
            "url": None,
            "error": None,
            "detail": "Not found",
        }
        try:
            from urllib.parse import quote
            q = quote(journal_name)
            url = f"https://api.eric.ed.gov/?search={q}&format=json"
            fc = None
            try:
                from src.firecrawl_verifier import FirecrawlVerifier
                fc = FirecrawlVerifier()
            except Exception:
                fc = None

            data = None
            if fc:
                scrape = fc.scrape(url, timeout=45)
                if scrape.get("error"):
                    result["error"] = scrape.get("error")
                    result["detail"] = f"ERIC lookup failed: {scrape.get('error')}"
                    return result
                markdown = scrape.get("markdown", "") or ""
                data = {"markdown": markdown, "source_url": url}
            else:
                import requests as req
                resp = req.get(url, timeout=30)
                if resp.status_code != 200:
                    result["detail"] = f"ERIC lookup failed: HTTP {resp.status_code}"
                    return result
                data = {"markdown": resp.text, "source_url": url}

            markdown = data.get("markdown", "") or ""
            if journal_name.lower() in markdown.lower():
                result["found"] = True
                result["url"] = url
                result["detail"] = "Journal appears in ERIC search result"
            else:
                result["detail"] = "Not found in ERIC search result"
        except Exception as e:
            result["error"] = str(e)
            result["detail"] = f"ERIC check failed: {e}"
        return result
