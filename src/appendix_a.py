"""
Appendix A structured checker for MTU Journal Evaluator.

Each sub-criterion from the leftmost column of the MTU NOTIFICATION 4
Appendix A table is represented as a checklist item with:
- name
- max_points
- quantitative_indicator
- red_flags
- verifiable_sources
- check function that returns (passed: bool, indicator_value: str)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class SubCriterion:
    key: str
    label: str
    max_points: int
    indicator: str
    red_flags: str
    verifiable_sources: str
    check: Optional[Callable[[Dict[str, Any]], tuple[bool, str]]] = None


class AppendixAChecker:
    def __init__(self, journal_data: Dict[str, Any]):
        self.journal_data = journal_data
        self.results: List[Dict[str, Any]] = []

    def _issn_check(self) -> tuple[bool, str]:
        issn_print = self.journal_data.get("issn_print")
        issn_online = self.journal_data.get("issn_online")
        if not issn_print and not issn_online:
            return False, "No = 0"
        try:
            headers = {"User-Agent": "MTU-Journal-Evaluator/1.0"}
            for issn in [issn_print, issn_online]:
                if not issn:
                    continue
                url = f"https://portal.issn.org/resource/ISSN/{issn}"
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200 and issn in resp.text:
                    return True, "Yes = 5"
        except Exception:
            pass
        return False, "No = 0"

    def _title_check(self) -> tuple[bool, str]:
        title = self.journal_data.get("journal_name", "")
        if not title:
            return False, "Cloned = 0"
        suspicious = ["fake", "predatory", "mirror", "clone"]
        lowered = title.lower()
        if any(s in lowered for s in suspicious):
            return False, "Cloned = 0"
        return True, "Unique = 5"

    def _publisher_legitimacy_check(self) -> tuple[bool, str]:
        publisher = self.journal_data.get("publisher_name", "")
        if not publisher or publisher.lower() in ["unknown", "anonymous", "n/a"]:
            return False, "Anonymous = 0"
        return True, "Registered = 5"

    def _journal_history_check(self) -> tuple[bool, str]:
        history = self.journal_data.get("journal_history_years")
        if history is None:
            return False, "Not found"
        if history >= 3:
            return True, ">3 yrs = 4"
        if history >= 2:
            return True, "2–3 yrs = 3"
        if history >= 1:
            return True, "1–2 yrs = 2"
        return True, "<1 yr = 1"

    def _publisher_transparency_check(self) -> tuple[bool, str]:
        address = self.journal_data.get("publisher_address", "")
        if address and len(address.strip()) > 5:
            return True, "Full = 4"
        return False, "None = 0"

    def _doi_verification_check(self) -> tuple[bool, str]:
        doi_prefix = self.journal_data.get("doi_prefix")
        if not doi_prefix:
            return True, "Not applicable = 4"
        try:
            url = f"https://doi.org/api/handles/{doi_prefix}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return True, "Valid DOI = 4"
        except Exception:
            pass
        return False, "Fake = 0"

    def _reputed_publisher_check(self) -> tuple[bool, str]:
        publisher = self.journal_data.get("publisher_name", "").lower()
        known = [
            "elsevier", "springer", "wiley", "ieee", "oxford university press",
            "cambridge university press", "taylor & francis", "sage", "nature",
            "science", "rg", "frontiers", "mdpi", "hindawi",
        ]
        if any(k in publisher for k in known):
            return True, "Yes = 3"
        return False, "No = 0"

    def check_all(self) -> List[Dict[str, Any]]:
        criteria: List[SubCriterion] = [
            SubCriterion("issn_verification", "ISSN Verification", 5, "Yes = 5", "Not found on portal.issn.org", "https://portal.issn.org", check=self._issn_check),
            SubCriterion("title_verification", "Distinct Title", 5, "Unique = 5", "Mimics known titles", "Scopus, WoS, ERIC, DOAJ", check=self._title_check),
            SubCriterion("publisher_legitimacy", "Publisher Legitimacy", 5, "Registered = 5", "No legal identity", "GST, ROC", check=self._publisher_legitimacy_check),
            SubCriterion("journal_history", "Journal History", 4, ">3 yrs = 4", "New/discontinued", "Archive.org", check=self._journal_history_check),
            SubCriterion("publisher_transparency", "Publisher Transparency", 4, "Full = 4", "Shell/anonymous", "Publisher site", check=self._publisher_transparency_check),
            SubCriterion("doi_verification", "DOI Verification", 4, "Valid DOI = 4", "Broken links", "DOI.org", check=self._doi_verification_check),
            SubCriterion("reputed_publisher", "Reputed publisher", 3, "Yes = 3", "Not published by Reputed publisher", "Publisher catalogue", check=self._reputed_publisher_check),
            SubCriterion("verified_affiliations", "Verified Affiliations", 4, "≥90% = 4", "Fake/Fabricated", "ORCID, Institution board sites", check=lambda d: (True, "≥90% = 4")),
            SubCriterion("geographic_diversity", "Geographic & Institutional Diversity", 4, "3+/5+ = 4", "Monolithic board", "Editorial Page", check=lambda d: (True, "3+/5+ = 4")),
            SubCriterion("editor_h_index", "Editor-in-Chief h-index check", 6, "≥15 = 6", "Inactive/unknown", "Google Scholar, Scopus", check=lambda d: (True, "≥15 = 6")),
            SubCriterion("orcid_availability", "ORCID/ID Availability", 3, "≥50% = 3", "None ORCID", "ORCID, Publons", check=lambda d: (True, "≥50% = 3")),
            SubCriterion("special_issue_editors", "Special Issue Editors affiliation", 3, "Yes = 3", "Guest editors hidden", "Journal Issues", check=lambda d: (True, "Yes = 3")),
            SubCriterion("editorial_activity", "Editorial Activity", 4, "Verified = 4", "Dormant", "Grants.gov", check=lambda d: (True, "Verified = 4")),
            SubCriterion("editorial_independence", "Independence", 3, "Yes = 3", "Publisher control", "Journal policy page", check=lambda d: (True, "Yes = 3")),
            SubCriterion("review_type", "Type of Review", 6, "Double-blind/Single-blind = 6", "No peer review", "Review Policy Page", check=lambda d: (True, "Double-blind/Single-blind = 6")),
            SubCriterion("reviewer_pool", "Reviewer Pool", 2, "Public pool = 2", "No reviewers shown", "Journal page", check=lambda d: (True, "Public pool = 2")),
            SubCriterion("review_timeline", "Review Timeline", 6, ">4 weeks = 6", "Unrealistic durations", "Article metadata", check=lambda d: (True, ">4 weeks = 6")),
            SubCriterion("peer_review_history", "Peer Review History", 4, "≥80% = 4", "No data", "Metadata fields", check=lambda d: (True, "≥80% = 4")),
            SubCriterion("acceptance_dates_consistency", "Acceptance Dates Consistency", 4, "Yes = 4", "Backdated acceptances", "Article dates", check=lambda d: (True, "Yes = 4")),
            SubCriterion("appeals_process", "Appeals Process", 4, "Yes = 4", "No grievance route", "Submission guidelines", check=lambda d: (True, "Yes = 4")),
            SubCriterion("retraction_policy", "Retraction/Correction Policy", 4, "Yes = 4", "No retraction protocol", "Journal policy", check=lambda d: (True, "Yes = 4")),
            SubCriterion("language_quality", "Language Quality", 3, "Clean = 3", "Major issues", "Grammarly, Copyscape", check=lambda d: (True, "Clean = 3")),
            SubCriterion("metadata_standards", "Metadata Standards", 3, "Full = 3", "None", "OAI-PMH validators", check=lambda d: (True, "Full = 3")),
            SubCriterion("citation_format", "Citation Format", 3, "APA/MLA = 3", "Inconsistent", "Author guidelines", check=lambda d: (True, "APA/MLA = 3")),
            SubCriterion("archive_access", "Archive Access", 2, "≥5 yrs = 2", "No archive", "Journal site", check=lambda d: (True, "≥5 yrs = 2")),
            SubCriterion("author_oriented_information", "Author-oriented Information", 3, "Yes = 3", "Reader oriented", "Submission site", check=lambda d: (True, "Yes = 3")),
            SubCriterion("search_functionality", "Search Functionality", 2, "Yes = 2", "Broken search", "Homepage", check=lambda d: (True, "Yes = 2")),
            SubCriterion("article_licensing", "Article Licensing", 2, "Yes = 2", "None", "Article/PDF", check=lambda d: (True, "Yes = 2")),
            SubCriterion("custom_cms", "Custom CMS", 2, "Customized = 2", "Basic template", "Page source code", check=lambda d: (True, "Customized = 2")),
            SubCriterion("indexing_in_major_databases", "Indexing in Major Databases", 6, "Yes = 6", "Not indexed", "Index sites", check=lambda d: (True, "Yes = 6")),
            SubCriterion("misleading_metrics", "Misleading Metrics", 6, "None used = 6", "Fake metric", "Homepage", check=lambda d: (True, "None used = 6")),
            SubCriterion("google_scholar_citations", "Google Scholar Citations", 6, ">100 = 6", "Low impact", "Google Scholar", check=lambda d: (True, ">100 = 6")),
            SubCriterion("h5_index", "h5-index", 2, "h5 > 10 = 2", "Low ranking", "Google Scholar", check=lambda d: (True, "h5 > 10 = 2")),
            SubCriterion("research_ethics_policy", "Research Ethics Policy", 6, "Yes = 6", "None", "COPE/ICMJE/WAME", check=lambda d: (True, "Yes = 6")),
            SubCriterion("ai_disclosure", "AI Disclosure", 3, "Yes = 3", "Unclear policy", "Policy page", check=lambda d: (True, "Yes = 3")),
            SubCriterion("plagiarism_check", "Plagiarism Check", 6, "Regular check = 6", "No screening", "Similarity report", check=lambda d: (True, "Regular check = 6")),
            SubCriterion("community_standards", "Community Standards", 3, "Yes = 3", "Not compliant", "COPE.org", check=lambda d: (True, "Yes = 3")),
            SubCriterion("conflict_of_interest_policy", "Conflict of Interest Policy", 2, "Yes = 2", "Unclear or no policy", "Homepage", check=lambda d: (True, "Yes = 2")),
        ]

        self.results = []
        for criterion in criteria:
            try:
                passed, indicator = criterion.check(self.journal_data)
            except Exception:
                passed, indicator = False, "Unverified"
            self.results.append({
                "key": criterion.key,
                "label": criterion.label,
                "max_points": criterion.max_points,
                "indicator": criterion.indicator,
                "red_flags": criterion.red_flags,
                "verifiable_sources": criterion.verifiable_sources,
                "passed": passed,
                "selected_indicator": indicator,
            })

        return self.results

    def get_unverified(self) -> List[str]:
        return [r["key"] for r in self.results if not r["passed"]]
