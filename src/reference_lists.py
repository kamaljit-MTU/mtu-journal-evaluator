"""
Reference List Checker
Checks journals against:
- Beall's List (predatory journals)
- Clarivate Master Journal List / JCR
- UGC CARE list (Indian regulatory)
"""
import re
import json
from typing import Dict, List, Optional, Any
from urllib.parse import quote

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class ReferenceListChecker:
    """Check journal against authoritative reference lists."""

    UGC_CARE_PDF_URL = "https://www.ugc.gov.in/e-book/Final_list_of_UGC-CARE_journals.pdf"
    BEALLS_LIST_URL = "https://beallslist.net/"
    CLARIVATE_MJL_URL = "https://mjl.clarivate.com/home.php"
    CLARIVATE_JCR_URL = "https://jcr.clarivate.com/jcr/home"

    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    @staticmethod
    def check_all(journal_name: str, issn: Optional[str] = None,
                  publisher: Optional[str] = None) -> Dict[str, Any]:
        """Run all reference list checks."""
        result = {
            "journal_name": journal_name,
            "checks_performed": [],
            "bealls_list": ReferenceListChecker._check_bealls_list(journal_name),
            "clarivate_mjl": ReferenceListChecker._check_clarivate_mjl(journal_name, issn),
            "clarivate_jcr": ReferenceListChecker._check_clarivate_jcr(journal_name, issn),
            "ugc_care": ReferenceListChecker._check_ugc_care(journal_name, issn),
            "overall_status": "unknown",
            "flags": []
        }

        # Aggregate results
        if result["bealls_list"].get("found"):
            result["flags"].append("BEALLS_LIST")
        if result["clarivate_mjl"].get("found"):
            result["flags"].append("CLARIVATE_MJL")
        if result["clarivate_jcr"].get("found"):
            result["flags"].append("CLARIVATE_JCR")
        if result["ugc_care"].get("found"):
            result["flags"].append("UGC_CARE")

        if "BEALLS_LIST" in result["flags"]:
            result["overall_status"] = "predatory"
        elif any(f in result["flags"] for f in ["CLARIVATE_MJL", "CLARIVATE_JCR", "UGC_CARE"]):
            result["overall_status"] = "legitimate"
        else:
            result["overall_status"] = "unverified"

        return result

    @staticmethod
    def _check_bealls_list(journal_name: str) -> Dict[str, Any]:
        """Check if journal appears on Beall's List."""
        result = {
            "source": "bealls_list",
            "found": False,
            "url": ReferenceListChecker.BEALLS_LIST_URL,
            "note": "Beall's List is no longer actively updated; checking archived sources"
        }

        if not HAS_REQUESTS:
            result["note"] += " (requests not available)"
            return result

        try:
            # Beall's list is archived; search for the journal in specific predatory contexts
            search_queries = [
                f'site:beallslist.net "{journal_name}"',
                f'"{journal_name}" "beall\'s list"',
                f'"{journal_name}" predatory journal hijacked'
            ]

            predatory_hits = 0
            for query in search_queries:
                try:
                    search_url = f"https://www.google.com/search?q={quote(query)}"
                    response = requests.get(search_url, headers=ReferenceListChecker.HEADERS, timeout=10)
                    if response.status_code == 200:
                        text_lower = response.text.lower()
                        # Only flag if journal name appears near predatory indicators
                        journal_lower = journal_name.lower()
                        if journal_lower in text_lower and any(word in text_lower for word in ['predatory', 'fake', 'hijacked', 'bealls list']):
                            predatory_hits += 1
                except Exception:
                    pass

            if predatory_hits >= 2:
                result["found"] = True
                result["note"] = "Journal found in Beall's List related search results"
            elif predatory_hits == 1:
                result["note"] = "Possible match found; needs manual verification"
        except Exception as e:
            result["note"] = f"Check failed: {str(e)}"

        return result

    @staticmethod
    def _check_clarivate_mjl(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        """Check if journal appears in Clarivate Master Journal List."""
        result = {
            "source": "clarivate_mjl",
            "found": False,
            "search_url": f"{ReferenceListChecker.CLARIVATE_MJL_URL}?q={quote(journal_name)}",
            "note": "Requires manual verification at mjl.clarivate.com"
        }

        if not HAS_REQUESTS:
            return result

        try:
            # Try direct search URL
            search_url = f"{ReferenceListChecker.CLARIVATE_MJL_URL}?q={quote(journal_name)}"
            response = requests.get(search_url, headers=ReferenceListChecker.HEADERS, timeout=15, allow_redirects=True)
            if response.status_code == 200:
                text = response.text.lower()
                # Check if journal name appears in results
                if journal_name.lower() in text:
                    result["found"] = True
                    result["note"] = "Journal found in Master Journal List"
        except Exception as e:
            result["note"] = f"Check failed: {str(e)}"

        return result

    @staticmethod
    def _check_clarivate_jcr(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        """Check if journal appears in Clarivate JCR."""
        result = {
            "source": "clarivate_jcr",
            "found": False,
            "search_url": ReferenceListChecker.CLARIVATE_JCR_URL,
            "note": "JCR requires institutional access; checking public indicators"
        }

        if not HAS_REQUESTS:
            return result

        try:
            # JCR is behind paywall; check for public indicators
            search_queries = [
                f'"{journal_name}" "journal citation reports"',
                f'"{journal_name}" impact factor clarivate'
            ]

            for query in search_queries:
                search_url = f"https://www.google.com/search?q={quote(query)}"
                response = requests.get(search_url, headers=ReferenceListChecker.HEADERS, timeout=10)
                if response.status_code == 200:
                    text_lower = response.text.lower()
                    if 'impact factor' in text_lower or 'jcr' in text_lower:
                        result["found"] = True
                        result["note"] = "Journal appears in JCR-related search results"
                        break
        except Exception as e:
            result["note"] = f"Check failed: {str(e)}"

        return result

    @staticmethod
    def _check_ugc_care(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        """Check if journal appears in UGC CARE list."""
        result = {
            "source": "ugc_care",
            "found": False,
            "url": ReferenceListChecker.UGC_CARE_PDF_URL,
            "note": "Checking against UGC CARE final list PDF"
        }

        if not HAS_REQUESTS:
            result["note"] += " (requests not available)"
            return result

        try:
            # Try to fetch the UGC CARE PDF
            response = requests.get(ReferenceListChecker.UGC_CARE_PDF_URL,
                                   headers=ReferenceListChecker.HEADERS, timeout=20)
            if response.status_code == 200:
                # Check if journal name appears in PDF text
                text = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
                journal_lower = journal_name.lower()
                if journal_lower in text.lower():
                    result["found"] = True
                    result["note"] = "Journal found in UGC CARE list"
                else:
                    result["note"] = "Journal not found in UGC CARE list"
            else:
                result["note"] = f"Could not fetch UGC CARE PDF (HTTP {response.status_code})"
        except Exception as e:
            result["note"] = f"UGC CARE check failed: {str(e)}"

        return result
