"""
Live Data Verifiers - external lookups for ISSN, DOI, publisher, and editorial data.
"""
from typing import Optional
import re
from urllib.parse import quote


class ISSNVerifier:
    ISSN_PORTAL_URL = "https://portal.issn.org/"

    @staticmethod
    def verify_format(issn: str) -> bool:
        return bool(re.match(r'^\d{4}-\d{3}[\dX]$', issn, re.IGNORECASE))

    @staticmethod
    def verify_check_digit(issn: str) -> bool:
        clean = issn.replace("-", "").upper()
        if len(clean) != 8:
            return False
        total = 0
        for i, ch in enumerate(clean[:7]):
            if not ch.isdigit():
                return False
            total += int(ch) * (8 - i)
        check = (11 - (total % 11)) % 11
        check_char = "X" if check == 10 else str(check)
        return clean[7] == check_char

    @staticmethod
    def verify(issn: str) -> dict:
        fmt_ok = ISSNVerifier.verify_format(issn)
        check_ok = ISSNVerifier.verify_check_digit(issn) if fmt_ok else False
        return {
            "issn": issn,
            "format_valid": fmt_ok,
            "check_digit_valid": check_ok,
            "portal_url": f"{ISSNVerifier.ISSN_PORTAL_URL}{issn}",
            "status": "valid" if (fmt_ok and check_ok) else "invalid",
        }

    @staticmethod
    def search_portal(journal_name: str) -> dict:
        """Best-effort search for an ISSN using Firecrawl scraping of the ISSN portal search page."""
        try:
            from src.firecrawl_verifier import FirecrawlVerifier
            fc = FirecrawlVerifier()
            search_url = f"{ISSNVerifier.ISSN_PORTAL_URL}?search={quote(journal_name)}"
            scrape = fc.scrape(search_url, timeout=45)
            if scrape.get("error"):
                return {
                    "searched_name": journal_name,
                    "found": False,
                    "issn": None,
                    "source_url": search_url,
                    "error": scrape["error"],
                }
            markdown = scrape.get("markdown", "") or ""
            matches = re.findall(r"\b\d{4}-\d{3}[\dX]\b", markdown, re.IGNORECASE)
            seen = []
            for m in matches:
                candidate = m.upper()
                if candidate not in seen:
                    seen.append(candidate)
            found = len(seen) > 0
            return {
                "searched_name": journal_name,
                "found": found,
                "issn": seen[0] if found else None,
                "all_matches": seen[:5],
                "source_url": search_url,
                "error": None,
            }
        except Exception as e:
            return {
                "searched_name": journal_name,
                "found": False,
                "issn": None,
                "source_url": None,
                "error": str(e),
            }


class DOIVerifier:
    DOI_ORG_URL = "https://doi.org/"

    @staticmethod
    def verify_format(doi: str) -> bool:
        return bool(re.match(r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$', doi))

    @staticmethod
    def verify(doi: str) -> dict:
        fmt_ok = DOIVerifier.verify_format(doi)
        return {
            "doi": doi,
            "format_valid": fmt_ok,
            "resolver_url": f"{DOIVerifier.DOI_ORG_URL}{doi}",
            "status": "valid" if fmt_ok else "invalid"
        }


class PublisherVerifier:
    KNOWN_REPUTABLE = [
        "elsevier", "springer", "wiley", "ieee", "acm", "oxford university press",
        "cambridge", "sage", "taylor & francis", "mdpi", "frontiers", "nature",
        "science", "bmj", "lancet", "plos", "hindawi", "wiley-blackwell",
    ]

    @staticmethod
    def verify(publisher_name: str, publisher_url: str, publisher_address: str) -> dict:
        name_lower = (publisher_name or "").lower()
        reputable = any(r in name_lower for r in PublisherVerifier.KNOWN_REPUTABLE)
        has_url = bool(publisher_url and "http" in publisher_url)
        has_address = bool(publisher_address and len(publisher_address.strip()) > 5)
        return {
            "publisher_name": publisher_name,
            "reputable": reputable,
            "has_url": has_url,
            "has_address": has_address,
            "status": "verified" if (reputable and has_url and has_address) else "unverified"
        }


class EditorialBoardVerifier:
    @staticmethod
    def verify(board_url: str) -> dict:
        has_url = bool(board_url and "http" in board_url)
        return {
            "board_url": board_url,
            "has_url": has_url,
            "status": "available" if has_url else "not_found"
        }
