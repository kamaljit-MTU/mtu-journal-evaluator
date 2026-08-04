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
from typing import Any, Callable, Dict, List, Optional, Tuple

import re
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
    check: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None


class AppendixAChecker:
    def __init__(self, journal_data: Dict[str, Any]):
        self.journal_data = journal_data
        self.results: List[Dict[str, Any]] = []

    def _get(self, key: str, default=None):
        return self.journal_data.get(key, default)

    def _fetch_text(self, url: str, timeout: int = 15) -> str:
        try:
            headers = {"User-Agent": "MTU-Journal-Evaluator/1.0"}
            resp = requests.get(url, headers=headers, timeout=timeout)
            return resp.text if resp.status_code == 200 else ""
        except Exception:
            return ""

    def _issn_check(self) -> Tuple[bool, str]:
        issn_print = self._get("issn_print")
        issn_online = self._get("issn_online")
        if not issn_print and not issn_online:
            return False, "No = 0"
        for issn in [issn_print, issn_online]:
            if not issn:
                continue
            text = self._fetch_text(f"https://portal.issn.org/resource/ISSN/{issn}")
            if text and issn in text:
                return True, "Yes = 5"
        return False, "No = 0"

    def _title_check(self) -> Tuple[bool, str]:
        title = self._get("journal_name", "")
        if not title:
            return False, "Cloned = 0"
        suspicious = ["fake", "predatory", "mirror", "clone"]
        lowered = title.lower()
        if any(s in lowered for s in suspicious):
            return False, "Cloned = 0"
        return True, "Unique = 5"

    def _publisher_legitimacy_check(self) -> Tuple[bool, str]:
        publisher = self._get("publisher_name", "")
        if not publisher or publisher.lower() in ["unknown", "anonymous", "n/a", ""]:
            return False, "Anonymous = 0"
        return True, "Registered = 5"

    def _journal_history_check(self) -> Tuple[bool, str]:
        history = self._get("journal_history_years")
        if history is None:
            return False, "Not found"
        if history >= 3:
            return True, ">3 yrs = 4"
        if history >= 2:
            return True, "2–3 yrs = 3"
        if history >= 1:
            return True, "1–2 yrs = 2"
        return True, "<1 yr = 1"

    def _publisher_transparency_check(self) -> Tuple[bool, str]:
        address = self._get("publisher_address", "")
        if address and len(address.strip()) > 5:
            return True, "Full = 4"
        return False, "None = 0"

    def _doi_verification_check(self) -> Tuple[bool, str]:
        doi_prefix = self._get("doi_prefix")
        if not doi_prefix:
            return True, "Not applicable = 4"
        text = self._fetch_text(f"https://doi.org/api/handles/{doi_prefix}")
        if text and "200" in text[:20]:
            return True, "Valid DOI = 4"
        return False, "Fake = 0"

    def _reputed_publisher_check(self) -> Tuple[bool, str]:
        publisher = self._get("publisher_name", "").lower()
        known = [
            "elsevier", "springer", "wiley", "ieee", "oxford university press",
            "cambridge university press", "taylor & francis", "sage", "nature",
            "science", "rg", "frontiers", "mdpi", "hindawi",
        ]
        if any(k in publisher for k in known):
            return True, "Yes = 3"
        return False, "No = 0"

    def _verified_affiliations_check(self) -> Tuple[bool, str]:
        editors = self._get("editors", [])
        if not editors:
            return False, "Otherwise = 0"
        with_aff = sum(1 for e in editors if e.get("affiliation"))
        rate = with_aff / len(editors)
        return rate >= 0.9, f"{'≥90%' if rate >= 0.9 else 'Otherwise'} = {'4' if rate >= 0.9 else '0'}"

    def _geographic_diversity_check(self) -> Tuple[bool, str]:
        countries = self._get("countries", [])
        unique_countries = len(set(c for c in countries if c))
        if unique_countries >= 3:
            return True, "3+/5+ = 4"
        if unique_countries >= 1:
            return True, "3+/5+ = 4"
        return False, "In-house = 0"

    def _editor_h_index_check(self) -> Tuple[bool, str]:
        editors = self._get("editors", [])
        if not editors:
            return False, "<5 = 0"
        h_indices = [e.get("h_index") for e in editors if e.get("h_index") is not None]
        if not h_indices:
            return False, "<5 = 0"
        avg_h = sum(h_indices) / len(h_indices)
        if avg_h >= 15:
            return True, "≥15 = 6"
        if avg_h >= 10:
            return True, "10–14 = 4"
        if avg_h >= 5:
            return True, "5–9 = 2"
        return False, "<5 = 0"

    def _orcid_availability_check(self) -> Tuple[bool, str]:
        editors = self._get("editors", [])
        if not editors:
            return False, "Otherwise = 0"
        with_orcid = sum(1 for e in editors if e.get("orcid"))
        rate = with_orcid / len(editors)
        return rate >= 0.5, f"{'≥50%' if rate >= 0.5 else 'Otherwise'} = {'3' if rate >= 0.5 else '0'}"

    def _special_issue_editors_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "guest editor" in text.lower() or "special issue" in text.lower():
            return True, "Yes = 3"
        return False, "No = 0"

    def _editorial_activity_check(self) -> Tuple[bool, str]:
        editors = self._get("editors", [])
        if not editors:
            return False, "None = 0"
        recent = sum(1 for e in editors if e.get("recent_publications", 0) > 0)
        if recent > 0:
            return True, "Verified = 4"
        return False, "None = 0"

    def _editorial_independence_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "editorial independence" in text.lower() or "independent" in text.lower():
            return True, "Yes = 3"
        return False, "No = 0"

    def _review_type_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Unclear = 0"
        text = self._fetch_text(url)
        if "double-blind" in text.lower() or "single-blind" in text.lower() or "peer review" in text.lower():
            return True, "Double-blind/Single-blind = 6"
        return False, "Unclear = 0"

    def _reviewer_pool_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "")
        if not url:
            return False, "None = 0"
        text = self._fetch_text(url)
        if "reviewer" in text.lower() or "editorial board" in text.lower():
            return True, "Public pool = 2"
        return False, "None = 0"

    def _review_timeline_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "<1 week = 0"
        text = self._fetch_text(url)
        weeks_pattern = re.search(r'(\d+)\s*weeks?', text, re.IGNORECASE)
        if weeks_pattern:
            weeks = int(weeks_pattern.group(1))
            if weeks >= 4:
                return True, ">4 weeks = 6"
            if weeks >= 1:
                return True, "1–4 weeks = 3"
        return False, "<1 week = 0"

    def _peer_review_history_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "<50% = 0"
        text = self._fetch_text(url)
        if "peer review" in text.lower() or "review history" in text.lower():
            return True, "≥80% = 4"
        return False, "<50% = 0"

    def _acceptance_dates_consistency_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "acceptance date" in text.lower() or "submission date" in text.lower():
            return True, "Yes = 4"
        return False, "No = 0"

    def _appeals_process_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "appeal" in text.lower() or "grievance" in text.lower():
            return True, "Yes = 4"
        return False, "No = 0"

    def _retraction_policy_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "retraction" in text.lower() or "correction" in text.lower():
            return True, "Yes = 4"
        return False, "No = 0"

    def _language_quality_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Major = 0"
        text = self._fetch_text(url)
        # Heuristic: too many spelling mistakes
        words = text.lower().split()
        if len(words) < 50:
            return False, "Major = 0"
        return True, "Clean = 3"

    def _metadata_standards_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "None = 0"
        text = self._fetch_text(url)
        if "schema.org" in text or "oai-pmh" in text.lower() or "metadata" in text.lower():
            return True, "Full = 3"
        return False, "None = 0"

    def _citation_format_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Unclear = 0"
        text = self._fetch_text(url)
        for fmt in ["apa", "mla", "vancouver", "chicago", "harvard"]:
            if fmt in text.lower():
                return True, "APA/MLA = 3"
        return False, "Unclear = 0"

    def _archive_access_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "<2 yrs = 0"
        text = self._fetch_text(url)
        years = re.findall(r'20[0-2]\d', text)
        if years:
            unique_years = sorted(set(years))
            if len(unique_years) >= 5:
                return True, "≥5 yrs = 2"
            if len(unique_years) >= 2:
                return True, "2–4 yrs = 1"
        return False, "<2 yrs = 0"

    def _author_oriented_information_check(self) -> Tuple[bool, str]:
        url = self._get("submission_portal_url", "") or self._get("editorial_board_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "submission" in text.lower() or "author guideline" in text.lower():
            return True, "Yes = 3"
        return False, "No = 0"

    def _search_functionality_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "search" in text.lower():
            return True, "Yes = 2"
        return False, "No = 0"

    def _article_licensing_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "creative commons" in text.lower() or "cc by" in text.lower() or "license" in text.lower():
            return True, "Yes = 2"
        return False, "No = 0"

    def _custom_cms_check(self) -> Tuple[bool, str]:
        url = self._get("editorial_board_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Default = 0"
        text = self._fetch_text(url)
        cms_signals = ["wordpress", "drupal", "joomla", "ojs", "open journal systems"]
        if any(cms in text.lower() for cms in cms_signals):
            return True, "Customized = 2"
        return False, "Default = 0"

    def _indexing_in_major_databases_check(self) -> Tuple[bool, str]:
        indexes = self._get("claimed_indexes", [])
        if not indexes:
            return False, "No = 0"
        major = ["scopus", "web of science", "wos", "doaj", "eric", "psycinfo", "heinonline"]
        if any(any(m in idx.lower() for m in major) for idx in indexes):
            return True, "Yes = 6"
        return False, "No = 0"

    def _misleading_metrics_check(self) -> Tuple[bool, str]:
        claims = self._get("metric_claims", [])
        predatory = ["sjif", "cosmos", "gif", "citefactor", "impact factor", "global impact factor"]
        if any(any(p in c.lower() for p in predatory) for c in claims):
            return False, "Used = 0"
        return True, "None used = 6"

    def _google_scholar_citations_check(self) -> Tuple[bool, str]:
        citations = self._get("google_scholar_citations")
        if citations is None:
            return False, "<50 = 1"
        if citations > 100:
            return True, ">100 = 6"
        if citations >= 50:
            return True, "50–100 = 3"
        return True, "<50 = 1"

    def _h5_index_check(self) -> Tuple[bool, str]:
        h5 = self._get("h5_index")
        if h5 is None:
            return False, "Low ranking = 0"
        if h5 > 10:
            return True, "h5 > 10 = 2"
        return False, "Low ranking = 0"

    def _research_ethics_policy_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        keywords = ["cope", "icmje", "wame", "publication ethics", "research ethics"]
        if any(k in text.lower() for k in keywords):
            return True, "Yes = 6"
        return False, "No = 0"

    def _ai_disclosure_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "No = 0"
        text = self._fetch_text(url)
        if "ai" in text.lower() and "disclosure" in text.lower():
            return True, "Yes = 3"
        if "artificial intelligence" in text.lower():
            return True, "Yes = 3"
        return False, "No = 0"

    def _plagiarism_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "None = 0"
        text = self._fetch_text(url)
        if "ithenticate" in text.lower() or "turnitin" in text.lower() or "plagiarism" in text.lower():
            return True, "Regular check = 6"
        return False, "None = 0"

    def _community_standards_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Not compliant = 0"
        text = self._fetch_text(url)
        if "cope" in text.lower() or "core practice" in text.lower():
            return True, "Yes = 3"
        return False, "Not compliant = 0"

    def _conflict_of_interest_policy_check(self) -> Tuple[bool, str]:
        url = self._get("ethics_policy_url", "") or self._get("aims_scope_url", "")
        if not url:
            return False, "Unclear or no policy = 0"
        text = self._fetch_text(url)
        if "conflict of interest" in text.lower() or "disclosure" in text.lower():
            return True, "Yes = 2"
        return False, "Unclear or no policy = 0"

    def check_all(self) -> List[Dict[str, Any]]:
        criteria: List[SubCriterion] = [
            SubCriterion("issn_verification", "ISSN Verification", 5, "Yes = 5", "Not found on portal.issn.org", "https://portal.issn.org", check=self._issn_check),
            SubCriterion("title_verification", "Distinct Title", 5, "Unique = 5", "Mimics known titles", "Scopus, WoS, ERIC, DOAJ", check=self._title_check),
            SubCriterion("publisher_legitimacy", "Publisher Legitimacy", 5, "Registered = 5", "No legal identity", "GST, ROC", check=self._publisher_legitimacy_check),
            SubCriterion("journal_history", "Journal History", 4, ">3 yrs = 4", "New/discontinued", "Archive.org", check=self._journal_history_check),
            SubCriterion("publisher_transparency", "Publisher Transparency", 4, "Full = 4", "Shell/anonymous", "Publisher site", check=self._publisher_transparency_check),
            SubCriterion("doi_verification", "DOI Verification", 4, "Valid DOI = 4", "Broken links", "DOI.org", check=self._doi_verification_check),
            SubCriterion("reputed_publisher", "Reputed publisher", 3, "Yes = 3", "Not published by Reputed publisher", "Publisher catalogue", check=self._reputed_publisher_check),
            SubCriterion("verified_affiliations", "Verified Affiliations", 4, "≥90% = 4", "Fake/Fabricated", "ORCID, Institution board sites", check=self._verified_affiliations_check),
            SubCriterion("geographic_diversity", "Geographic & Institutional Diversity", 4, "3+/5+ = 4", "Monolithic board", "Editorial Page", check=self._geographic_diversity_check),
            SubCriterion("editor_h_index", "Editor-in-Chief h-index check", 6, "≥15 = 6", "Inactive/unknown", "Google Scholar, Scopus", check=self._editor_h_index_check),
            SubCriterion("orcid_availability", "ORCID/ID Availability", 3, "≥50% = 3", "None ORCID", "ORCID, Publons", check=self._orcid_availability_check),
            SubCriterion("special_issue_editors", "Special Issue Editors affiliation", 3, "Yes = 3", "Guest editors hidden", "Journal Issues", check=self._special_issue_editors_check),
            SubCriterion("editorial_activity", "Editorial Activity", 4, "Verified = 4", "Dormant", "Grants.gov", check=self._editorial_activity_check),
            SubCriterion("editorial_independence", "Independence", 3, "Yes = 3", "Publisher control", "Journal policy page", check=self._editorial_independence_check),
            SubCriterion("review_type", "Type of Review", 6, "Double-blind/Single-blind = 6", "No peer review", "Review Policy Page", check=self._review_type_check),
            SubCriterion("reviewer_pool", "Reviewer Pool", 2, "Public pool = 2", "No reviewers shown", "Journal page", check=self._reviewer_pool_check),
            SubCriterion("review_timeline", "Review Timeline", 6, ">4 weeks = 6", "Unrealistic durations", "Article metadata", check=self._review_timeline_check),
            SubCriterion("peer_review_history", "Peer Review History", 4, "≥80% = 4", "No data", "Metadata fields", check=self._peer_review_history_check),
            SubCriterion("acceptance_dates_consistency", "Acceptance Dates Consistency", 4, "Yes = 4", "Backdated acceptances", "Article dates", check=self._acceptance_dates_consistency_check),
            SubCriterion("appeals_process", "Appeals Process", 4, "Yes = 4", "No grievance route", "Submission guidelines", check=self._appeals_process_check),
            SubCriterion("retraction_policy", "Retraction/Correction Policy", 4, "Yes = 4", "No retraction protocol", "Journal policy", check=self._retraction_policy_check),
            SubCriterion("language_quality", "Language Quality", 3, "Clean = 3", "Major issues", "Grammarly, Copyscape", check=self._language_quality_check),
            SubCriterion("metadata_standards", "Metadata Standards", 3, "Full = 3", "None", "OAI-PMH validators", check=self._metadata_standards_check),
            SubCriterion("citation_format", "Citation Format", 3, "APA/MLA = 3", "Inconsistent", "Author guidelines", check=self._citation_format_check),
            SubCriterion("archive_access", "Archive Access", 2, "≥5 yrs = 2", "No archive", "Journal site", check=self._archive_access_check),
            SubCriterion("author_oriented_information", "Author-oriented Information", 3, "Yes = 3", "Reader oriented", "Submission site", check=self._author_oriented_information_check),
            SubCriterion("search_functionality", "Search Functionality", 2, "Yes = 2", "Broken search", "Homepage", check=self._search_functionality_check),
            SubCriterion("article_licensing", "Article Licensing", 2, "Yes = 2", "None", "Article/PDF", check=self._article_licensing_check),
            SubCriterion("custom_cms", "Custom CMS", 2, "Customized = 2", "Basic template", "Page source code", check=self._custom_cms_check),
            SubCriterion("indexing_in_major_databases", "Indexing in Major Databases", 6, "Yes = 6", "Not indexed", "Index sites", check=self._indexing_in_major_databases_check),
            SubCriterion("misleading_metrics", "Misleading Metrics", 6, "None used = 6", "Fake metric", "Homepage", check=self._misleading_metrics_check),
            SubCriterion("google_scholar_citations", "Google Scholar Citations", 6, ">100 = 6", "Low impact", "Google Scholar", check=self._google_scholar_citations_check),
            SubCriterion("h5_index", "h5-index", 2, "h5 > 10 = 2", "Low ranking", "Google Scholar", check=self._h5_index_check),
            SubCriterion("research_ethics_policy", "Research Ethics Policy", 6, "Yes = 6", "None", "COPE/ICMJE/WAME", check=self._research_ethics_policy_check),
            SubCriterion("ai_disclosure", "AI Disclosure", 3, "Yes = 3", "Unclear policy", "Policy page", check=self._ai_disclosure_check),
            SubCriterion("plagiarism_check", "Plagiarism Check", 6, "Regular check = 6", "No screening", "Similarity report", check=self._plagiarism_check),
            SubCriterion("community_standards", "Community Standards", 3, "Yes = 3", "Not compliant", "COPE.org", check=self._community_standards_check),
            SubCriterion("conflict_of_interest_policy", "Conflict of Interest Policy", 2, "Yes = 2", "Unclear or no policy", "Homepage", check=self._conflict_of_interest_policy_check),
        ]

        self.results = []
        for criterion in criteria:
            try:
                passed, indicator = criterion.check()
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
