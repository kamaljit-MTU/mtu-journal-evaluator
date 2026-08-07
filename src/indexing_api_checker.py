"""
Indexing API Checker
Free API checks for DOAJ and ERIC.
"""
import json
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

            text = ""
            try:
                from src.firecrawl_verifier import FirecrawlVerifier
                fc = FirecrawlVerifier()
                scrape = fc.scrape(url, timeout=45)
                if scrape.get("error"):
                    result["error"] = scrape.get("error")
                    result["detail"] = f"DOAJ lookup failed: {scrape.get('error')}"
                    return result
                text = scrape.get("markdown", "") or ""
            except Exception:
                import requests as req
                resp = req.get(url, timeout=30)
                if resp.status_code != 200:
                    result["detail"] = f"DOAJ lookup failed: HTTP {resp.status_code}"
                    return result
                text = resp.text

            found = False
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    results = data.get("results") or data.get("journals") or []
                    if isinstance(results, list) and len(results) > 0:
                        found = True
            except Exception:
                found = journal_name.lower() in text.lower()

            result["found"] = found
            result["url"] = url
            result["detail"] = "Journal appears in DOAJ search result" if found else "Not found in DOAJ search result"
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
            url = f"https://api.ies.ed.gov/eric/?search={q}&format=json"

            text = ""
            try:
                from src.firecrawl_verifier import FirecrawlVerifier
                fc = FirecrawlVerifier()
                scrape = fc.scrape(url, timeout=45)
                if scrape.get("error"):
                    result["error"] = scrape.get("error")
                    result["detail"] = f"ERIC lookup failed: {scrape.get('error')}"
                    return result
                text = scrape.get("markdown", "") or ""
            except Exception:
                import requests as req
                resp = req.get(url, timeout=30)
                if resp.status_code != 200:
                    result["detail"] = f"ERIC lookup failed: HTTP {resp.status_code}"
                    return result
                text = resp.text

            found = False
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    results = data.get("results") or data.get("records") or data.get("response") or []
                    if isinstance(results, list) and len(results) > 0:
                        found = True
            except Exception:
                found = journal_name.lower() in text.lower()

            result["found"] = found
            result["url"] = url
            result["detail"] = "Journal appears in ERIC search result" if found else "Not found in ERIC search result"
        except Exception as e:
            result["error"] = str(e)
            result["detail"] = f"ERIC check failed: {e}"
        return result
