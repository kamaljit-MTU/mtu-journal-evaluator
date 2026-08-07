"""
Indexing API Checker
Free/limited API checks for DOAJ, ERIC, Scopus, IEEE Xplore.
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
            "scopus": IndexingAPIChecker.check_scopus_free(journal_name, issn),
            "ieee": IndexingAPIChecker.check_ieee_free(journal_name, issn),
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
        try:
            if IndexingAPIChecker.check_scopus_free(journal_name, issn).get("found"):
                claims.append("Scopus")
        except Exception:
            pass
        try:
            if IndexingAPIChecker.check_ieee_free(journal_name, issn).get("found"):
                claims.append("IEEE Xplore")
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
            from src.firecrawl_verifier import FirecrawlVerifier
            q = quote(journal_name)
            url = f"https://doaj.org/api/search/journals/{q}"
            fc = FirecrawlVerifier()
            scrape = fc.scrape(url, timeout=45)
            if scrape.get("error"):
                result["error"] = scrape.get("error")
                result["detail"] = f"DOAJ lookup failed: {scrape.get('error')}"
                return result

            markdown = scrape.get("markdown", "") or ""
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
            from src.firecrawl_verifier import FirecrawlVerifier
            q = quote(journal_name)
            url = f"https://api.eric.ed.gov/?search={q}&format=json"
            fc = FirecrawlVerifier()
            scrape = fc.scrape(url, timeout=45)
            if scrape.get("error"):
                result["error"] = scrape.get("error")
                result["detail"] = f"ERIC lookup failed: {scrape.get('error')}"
                return result

            markdown = scrape.get("markdown", "") or ""
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

    @staticmethod
    def check_scopus_free(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "source": "scopus",
            "found": False,
            "url": None,
            "error": None,
            "detail": "Not found via public/free checks",
        }
        try:
            from urllib.parse import quote
            from src.firecrawl_verifier import FirecrawlVerifier
            q = quote(journal_name)
            url = f"https://www.scopus.com/sources.uri?search={q}"
            fc = FirecrawlVerifier()
            scrape = fc.scrape(url, timeout=45)
            if scrape.get("error"):
                result["error"] = scrape.get("error")
                result["detail"] = f"Scopus lookup failed: {scrape.get('error')}"
                return result

            markdown = scrape.get("markdown", "") or ""
            if journal_name.lower() in markdown.lower():
                result["found"] = True
                result["url"] = url
                result["detail"] = "Journal appears in Scopus public search"
            else:
                result["detail"] = "Not found in Scopus public search"
        except Exception as e:
            result["error"] = str(e)
            result["detail"] = f"Scopus check failed: {e}"
        return result

    @staticmethod
    def check_ieee_free(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "source": "ieee",
            "found": False,
            "url": None,
            "error": None,
            "detail": "Not found via public/free checks",
        }
        try:
            from urllib.parse import quote
            from src.firecrawl_verifier import FirecrawlVerifier
            q = quote(journal_name)
            url = f"https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={q}"
            fc = FirecrawlVerifier()
            scrape = fc.scrape(url, timeout=45)
            if scrape.get("error"):
                result["error"] = scrape.get("error")
                result["detail"] = f"IEEE lookup failed: {scrape.get('error')}"
                return result

            markdown = scrape.get("markdown", "") or ""
            if journal_name.lower() in markdown.lower():
                result["found"] = True
                result["url"] = url
                result["detail"] = "Journal appears in IEEE Xplore public search"
            else:
                result["detail"] = "Not found in IEEE Xplore public search"
        except Exception as e:
            result["error"] = str(e)
            result["detail"] = f"IEEE check failed: {e}"
        return result
