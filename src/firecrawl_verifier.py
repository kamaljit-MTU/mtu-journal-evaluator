"""
Firecrawl-backed web verifier for MTU Journal Evaluator.

Uses Firecrawl REST API to scrape journal pages and extract:
- Editor-in-Chief name and ORCID
- DOI patterns/attributions
- Review type, submission portal, ethics policy, editorial board details
- Open access claims, indexing claims, archiving age
- Plagiarism/retraction/appeal/COPE policies
- Author-oriented info, CMS clues, metadata standards, etc.
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

    def scrape(self, url: str, timeout: int = 45) -> Dict[str, Any]:
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

    @staticmethod
    def _find(pattern: str, text: str, flags: int = 0) -> Optional[re.Match]:
        m = re.search(pattern, text, flags)
        return m

    @staticmethod
    def _findall(pattern: str, text: str, flags: int = 0) -> List[str]:
        return re.findall(pattern, text, flags)

    def extract_eic_orcid(self, markdown: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Extract Editor-in-Chief name and ORCID from page markdown."""
        if not markdown:
            return False, None, None

        orcid_match = self._find(r"orcid\.org/(\d{4}-\d{4}-\d{4}-[\dX]{4})", markdown, re.IGNORECASE)
        if not orcid_match:
            orcid_match = self._find(r"(\d{4}-\d{4}-\d{4}-[\dX]{4})", markdown)
        orcid_id = orcid_match.group(1) if orcid_match else None

        eic_pattern = re.compile(
            r"Editor[\-\s]in[\-\s]Chief[:\\s]+([^\\n\\r]{3,80})",
            re.IGNORECASE,
        )
        eic_match = eic_pattern.search(markdown)

        if eic_match:
            editor_name = eic_match.group(1).strip()
            editor_name = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\\1", editor_name).strip()
            found = bool(editor_name)
            return found, editor_name if found else None, orcid_id

        return False, None, orcid_id

    def extract_dois(self, markdown: str, doi_prefix: Optional[str] = None) -> List[str]:
        """Extract DOI references from page markdown."""
        if not markdown:
            return []
        dois = self._findall(r"10\.\d{4,}/[^\s\)\>,]+", markdown, re.IGNORECASE)
        cleaned = []
        for doi in dois:
            doi = doi.rstrip(".,;:!?)")
            if doi:
                cleaned.append(doi)
        if doi_prefix:
            cleaned = [d for d in cleaned if d.startswith(doi_prefix)]
        return list(set(cleaned))

    @staticmethod
    def _contains_any(text: str, phrases: List[str]) -> bool:
        t = text.lower()
        return any(p.lower() in t for p in phrases)

    def analyze_journal_page(self, markdown: str) -> Dict[str, Any]:
        """Analyze journal homepage markdown for common verification signals."""
        if not markdown:
            return {"error": "empty markdown"}

        text = markdown
        return {
            "open_access_claim": self._contains_any(text, ["open access", "gold open access", "green open access"]),
            "peer_review_claim": self._contains_any(text, ["peer review", "double-blind", "single-blind", "refereed"]),
            "review_type": "double-blind" if self._contains_any(text, ["double-blind"]) else (
                "single-blind" if self._contains_any(text, ["single-blind"]) else (
                    "peer review" if self._contains_any(text, ["peer review"]) else "unclear"
                )
            ),
            "reviewer_pool_claim": self._contains_any(text, ["reviewer pool", "reviewers wanted", "become a reviewer"]),
            "plagiarism_claim": self._contains_any(text, ["plagiarism", "similarity check", "ithenticate", "turnitin"]),
            "retraction_claim": self._contains_any(text, ["retraction policy", "retractions", "correction policy"]),
            "appeals_claim": self._contains_any(text, ["appeal", "appeals process", "complaints"]),
            "ethics_claim": self._contains_any(text, ["research ethics", "publication ethics", "cope", "icmje", "wame"]),
            "ai_disclosure_claim": self._contains_any(text, ["ai disclosure", "generative ai", "artificial intelligence disclosure"]),
            "indexing_claims": [
                claim for claim in ["web of science", "scopus", "doaj", "eric", "pubmed", "medline", "jcr", "clarivate"]
                if self._contains_any(text, [claim])
            ],
            "metric_claims": [
                claim for claim in ["impact factor", "sjif", "cosmos", "gif", "h5-index", "h-index", "cite score"]
                if self._contains_any(text, [claim])
            ],
            "submission_portal_claim": self._contains_any(text, ["submit manuscript", "submit article", "online submission", "editorial manager", "scholastica"]),
            "licensing_claim": self._contains_any(text, ["creative commons", "cc by", "license", "open access"]),
            "archive_claim": self._contains_any(text, ["archive", "back issues", "all volumes", "since 19"]),
            "search_claim": self._contains_any(text, ["search", "advanced search", "search articles"]),
            "custom_cms_signal": "default" if self._contains_any(text, ["wordpress", "drupal", "joomla"]) else "unknown",
            "language_quality_signal": "clean" if not self._contains_any(text, ["poor english", "bad grammar", "spam", "click here"]) else "major",
            "metadata_signal": self._contains_any(text, ["oai-pmh", "xml", "metadata", " Dublin Core", "crossref"]),
            "citation_format_claim": self._contains_any(text, ["apa", "mla", "vancouver", "harvard", "chicago"]),
            "author_information_claim": self._contains_any(text, ["author guidelines", "instructions for authors", "guide for authors"]),
        }

    def analyze_editorial_board_page(self, markdown: str) -> Dict[str, Any]:
        """Analyze editorial board page markdown."""
        if not markdown:
            return {"error": "empty markdown"}

        text = markdown
        editors = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            orcids = self._findall(r"orcid\.org/(\d{4}-\d{4}-\d{4}-[\dX]{4})", line, re.IGNORECASE)
            plain_orcids = self._findall(r"(\d{4}-\d{4}-\d{4}-[\dX]{4})", line)
            orcid_id = orcids[0] if orcids else (plain_orcids[0] if plain_orcids else None)
            name_match = self._find(r"^([A-Z][a-z]+(?: [A-Z][a-z]+){1,4})", line)
            name = name_match.group(1).strip() if name_match else line[:80]
            editors.append({"name": name, "orcid": orcid_id})

        unique = []
        seen = set()
        for e in editors:
            if e["name"] not in seen:
                seen.add(e["name"])
                unique.append(e)

        return {
            "editors_found": unique[:50],
            "total_editors": len(unique),
            "with_orcid": sum(1 for e in unique if e.get("orcid")),
            "with_affiliation": sum(1 for e in unique if e.get("affiliation")),
            "editorial_board_present": len(unique) > 0,
            "eic_in_list": self._contains_any(text, ["editor-in-chief", "editor in chief", "chief editor"]),
        }

    def analyze_policies_page(self, markdown: str) -> Dict[str, Any]:
        """Analyze ethics/policies page markdown."""
        if not markdown:
            return {"error": "empty markdown"}
        text = markdown
        return {
            "ethics_policy_present": self._contains_any(text, ["ethics", "publication ethics", "research ethics", "responsible conduct"]),
            "review_policy_present": self._contains_any(text, ["peer review", "review policy", "review process"]),
            "retraction_policy_present": self._contains_any(text, ["retraction policy", "retractions", "correction policy"]),
            "appeals_present": self._contains_any(text, ["appeal", "appeals process", "complaints"]),
            "ai_disclosure_present": self._contains_any(text, ["generative ai", "ai disclosure", "artificial intelligence"]),
            "plagiarism_present": self._contains_any(text, ["plagiarism", "similarity check", "ithenticate", "turnitin"]),
            "conflict_of_interest_present": self._contains_any(text, ["conflict of interest", "coi", "competing interests"]),
            "data_availability_present": self._contains_any(text, ["data availability", "open data", "data sharing"]),
            "cope_member": self._contains_any(text, ["committee on publication ethics", "cope member", "cope.org"]),
            "icmje_member": self._contains_any(text, ["icmje", "international committee of medical journal editors"]),
            "wame_member": self._contains_any(text, ["world association of medical editors", "wame"]),
        }

    def analyze_submission_portal(self, markdown: str) -> Dict[str, Any]:
        if not markdown:
            return {"error": "empty markdown"}
        text = markdown
        return {
            "submission_portal_present": self._contains_any(text, ["submit manuscript", "submit article", "new submission", "start submission"]),
            "review_timeline_claim": ">4 weeks" if self._contains_any(text, ["4 weeks", "six weeks", "eight weeks"]) else (
                "1-4 weeks" if self._contains_any(text, ["2 weeks", "3 weeks", "4 weeks"]) else (
                    "<1 week" if self._contains_any(text, ["rapid", "fast track", "1 week", "72 hours"]) else "unclear"
                )
            ),
            "peer_review_history_claim": self._contains_any(text, ["peer review history", "review history", "previous submissions"]),
            "acceptance_dates_claim": self._contains_any(text, ["acceptance date", "received", "accepted", "published"]),
        }

    def verify_page_signal(self, url: str, kind: str, timeout: int = 45) -> Dict[str, Any]:
        scrape = self.scrape(url, timeout=timeout)
        if scrape.get("error"):
            return {"error": scrape["error"], "url": url, "kind": kind}

        markdown = scrape.get("markdown", "") or ""
        if kind == "journal_homepage":
            base = self.analyze_journal_page(markdown)
            dois = self.extract_dois(markdown)
            eic_found, editor_name, orcid_id = self.extract_eic_orcid(markdown)
            base.update({
                "dois_found_on_homepage": dois,
                "eic_orcid_on_homepage": {
                    "found": eic_found,
                    "editor_name": editor_name,
                    "orcid_id": orcid_id,
                    "orcid_verified": bool(orcid_id and self._verify_orcid_public(orcid_id)),
                }
            })
            return base

        if kind == "editorial_board":
            return self.analyze_editorial_board_page(markdown)

        if kind == "policies":
            return self.analyze_policies_page(markdown)

        if kind == "submission_portal":
            return self.analyze_submission_portal(markdown)

        return {"markdown_length": len(markdown), "url": url, "kind": kind}

    def verify_eic_orcid(self, journal_url: str) -> Dict[str, Any]:
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
        if orcid_id:
            result["orcid_verified"] = self._verify_orcid_public(orcid_id)
        return result

    def verify_doi_attributions(self, journal_url: str, doi_prefix: Optional[str] = None) -> Dict[str, Any]:
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
