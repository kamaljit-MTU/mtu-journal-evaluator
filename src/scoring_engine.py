"""
Scoring Engine - 150-point framework
"""
from typing import List, Dict, Any
from .models import JournalInput, DomainScore, RejectionTriggerResult


class ScoringEngine:
    THRESHOLD = 120
    MAX_SCORE = 150

    def __init__(self, journal: JournalInput):
        self.journal = journal

    def score(self, trigger_results: List[RejectionTriggerResult]) -> List[DomainScore]:
        # If any automatic rejection trigger fired, skip scoring
        if any(not r.passed for r in trigger_results):
            return []

        domains = [
            self._score_domain1_identification(),
            self._score_domain2_editorial(),
            self._score_domain3_peer_review(),
            self._score_domain4_website(),
            self._score_domain5_metrics(),
            self._score_domain6_ethics(),
        ]
        return domains

    def _score_domain1_identification(self) -> DomainScore:
        sub = []
        pts = 0

        # ISSN Verification (5 pts)
        issn = self.journal.issn_print or self.journal.issn_online
        if issn:
            pts += 5
            sub.append({"criterion": "ISSN Verification", "earned": 5, "max": 5,
                        "detail": f"ISSN: {issn}"})
        else:
            sub.append({"criterion": "ISSN Verification", "earned": 0, "max": 5,
                        "detail": "No ISSN provided"})

        # Distinct Title (5 pts)
        title_ok = not any(p in self.journal.name.lower()
                          for p in ["international journal of advanced research",
                                    "world journal of", "american journal of"])
        pts += 5 if title_ok else 0
        sub.append({"criterion": "Distinct Title", "earned": 5 if title_ok else 0, "max": 5,
                    "detail": "Unique title" if title_ok else "Suspicious title pattern"})

        # Publisher Legitimacy (5 pts)
        pub_ok = bool(self.journal.publisher_name and self.journal.publisher_url)
        pts += 5 if pub_ok else 0
        sub.append({"criterion": "Publisher Legitimacy", "earned": 5 if pub_ok else 0, "max": 5,
                    "detail": f"Publisher: {self.journal.publisher_name}" if pub_ok else "Incomplete publisher info"})

        # Journal History (4 pts)
        # No numeric input here; default to 2 pts (2-3 years) if unknown, 4 if stated 3+
        pts += 2  # neutral default
        sub.append({"criterion": "Journal History", "earned": 2, "max": 4,
                    "detail": "History not specified; default 2 pts (2-3 yrs assumed)"})

        # Publisher Transparency (4 pts)
        trans = bool(self.journal.publisher_address)
        pts += 4 if trans else 0
        sub.append({"criterion": "Publisher Transparency", "earned": 4 if trans else 0, "max": 4,
                    "detail": "Address provided" if trans else "No address"})

        # DOI Verification (4 pts)
        has_doi = bool(self.journal.doi_prefix)
        pts += 4 if has_doi else 0
        sub.append({"criterion": "DOI Verification", "earned": 4 if has_doi else 0, "max": 4,
                    "detail": "DOI prefix provided" if has_doi else "No DOI info"})

        # Reputed Publisher (3 pts)
        # Auto-award if known reputable; otherwise 1 pt as unknown
        pub_bonus = 1
        known_reputable = ["elsevier", "springer", "wiley", "ieee", "acm",
                           "oxford university press", "cambridge", "sage",
                           "taylor & francis", "mdpi", "frontiers"]
        if any(r in (self.journal.publisher_name or "").lower() for r in known_reputable):
            pub_bonus = 3
        pts += pub_bonus
        sub.append({"criterion": "Reputed Publisher", "earned": pub_bonus, "max": 3,
                    "detail": "Known reputable publisher" if pub_bonus == 3 else "Publisher not in known list"})

        return DomainScore(domain="Journal Identification and Authenticity",
                           max_points=30, earned_points=pts, sub_criteria=sub)

    def _score_domain2_editorial(self) -> DomainScore:
        sub = []
        pts = 0

        # Verified Affiliations (4 pts)
        has_eb = bool(self.journal.editorial_board_url)
        pts += 4 if has_eb else 0
        sub.append({"criterion": "Verified Affiliations (50% sample)", "earned": 4 if has_eb else 0, "max": 4,
                    "detail": "Editorial board URL provided" if has_eb else "No editorial board info"})

        # Geographic Diversity (4 pts)
        pts += 2  # neutral default
        sub.append({"criterion": "Geographic/Institutional Diversity", "earned": 2, "max": 4,
                    "detail": "Diversity not verifiable from input alone; 2 pts default"})

        # EIC h-index (6 pts)
        pts += 2  # neutral default
        sub.append({"criterion": "Editor-in-Chief h-index", "earned": 2, "max": 6,
                    "detail": "EIC h-index not provided; 2 pts default"})

        # ORCID Availability (3 pts)
        pts += 1  # neutral default
        sub.append({"criterion": "ORCID/ID Availability", "earned": 1, "max": 3,
                    "detail": "ORCID data not available; 1 pt default"})

        # Special Issue Editors (3 pts)
        pts += 1
        sub.append({"criterion": "Named Special Issue Editors", "earned": 1, "max": 3,
                    "detail": "Not verified; 1 pt default"})

        # Editorial Activity (4 pts)
        pts += 2
        sub.append({"criterion": "Editorial Activity (3-5 years)", "earned": 2, "max": 4,
                    "detail": "Not verified; 2 pts default"})

        # Independence Policy (3 pts)
        indep = bool(self.journal.ethics_policy_url)  # proxy
        pts += 3 if indep else 0
        sub.append({"criterion": "Editorial Independence Policy", "earned": 3 if indep else 0, "max": 3,
                    "detail": "Policy page present" if indep else "No independence policy"})

        # Author-Editor Overlap (3 pts)
        pts += 2  # neutral default
        sub.append({"criterion": "Author-Editor Overlap", "earned": 2, "max": 3,
                    "detail": "Cannot verify from input; 2 pts default"})

        return DomainScore(domain="Editorial Board and Governance",
                           max_points=30, earned_points=pts, sub_criteria=sub)

    def _score_domain3_peer_review(self) -> DomainScore:
        sub = []
        pts = 0

        # Type of Review (6 pts)
        pts += 2  # neutral default
        sub.append({"criterion": "Type of Review (double/single blind)", "earned": 2, "max": 6,
                    "detail": "Review type not specified; 2 pts default"})

        # Reviewer Pool (2 pts)
        pts += 1
        sub.append({"criterion": "Reviewer Pool", "earned": 1, "max": 2,
                    "detail": "Not verifiable; 1 pt default"})

        # Review Timeline (6 pts)
        pts += 2
        sub.append({"criterion": "Review Timeline", "earned": 2, "max": 6,
                    "detail": "Timeline not specified; 2 pts default"})

        # Peer Review History (4 pts)
        pts += 1
        sub.append({"criterion": "Peer Review History in Metadata", "earned": 1, "max": 4,
                    "detail": "Not verifiable; 1 pt default"})

        # Acceptance Dates (4 pts)
        pts += 2
        sub.append({"criterion": "Acceptance Dates Precede Publication", "earned": 2, "max": 4,
                    "detail": "Not verifiable; 2 pts default"})

        # Appeals Process (4 pts)
        pts += 2
        sub.append({"criterion": "Appeals Process", "earned": 2, "max": 4,
                    "detail": "Not verifiable; 2 pts default"})

        # Retraction Policy (4 pts)
        retraction = bool(self.journal.ethics_policy_url)
        pts += 4 if retraction else 0
        sub.append({"criterion": "Retraction/Correction Policy", "earned": 4 if retraction else 0, "max": 4,
                    "detail": "Policy page present" if retraction else "No retraction policy"})

        return DomainScore(domain="Peer Review and Publishing Process",
                           max_points=30, earned_points=pts, sub_criteria=sub)

    def _score_domain4_website(self) -> DomainScore:
        sub = []
        pts = 0

        # Language Quality (3 pts)
        pts += 2  # neutral
        sub.append({"criterion": "Language Quality", "earned": 2, "max": 3,
                    "detail": "Not verified; 2 pts default"})

        # Metadata Standards (3 pts)
        has_url = bool(self.journal.url)
        pts += 3 if has_url else 0
        sub.append({"criterion": "Metadata Standards", "earned": 3 if has_url else 0, "max": 3,
                    "detail": "Website present" if has_url else "No website"})

        # Citation Format (3 pts)
        pts += 2
        sub.append({"criterion": "Citation Format Standardization", "earned": 2, "max": 3,
                    "detail": "Not verifiable; 2 pts default"})

        # Archive Access (2 pts)
        pts += 1
        sub.append({"criterion": "Archive Access", "earned": 1, "max": 2,
                    "detail": "Not verifiable; 1 pt default"})

        # Author-oriented penalty (3 pts)
        # Awards 3 pts if NOT author-oriented; we assume neutral
        pts += 1
        sub.append({"criterion": "Not overly author-oriented", "earned": 1, "max": 3,
                    "detail": "Cannot determine; 1 pt default"})

        # Search Functionality (2 pts)
        pts += 1
        sub.append({"criterion": "Search Functionality", "earned": 1, "max": 2,
                    "detail": "Not verifiable; 1 pt default"})

        # Article Licensing (2 pts)
        pts += 1 if self.journal.open_access else 0
        sub.append({"criterion": "Article Licensing Clear", "earned": 1 if self.journal.open_access else 0, "max": 2,
                    "detail": "Open access" if self.journal.open_access else "License not clear"})

        # Custom CMS (2 pts)
        pts += 1
        sub.append({"criterion": "Custom CMS", "earned": 1, "max": 2,
                    "detail": "Not verifiable; 1 pt default"})

        return DomainScore(domain="Website and Infrastructure",
                           max_points=20, earned_points=pts, sub_criteria=sub)

    def _score_domain5_metrics(self) -> DomainScore:
        sub = []
        pts = 0

        # Indexing in Major Databases (6 pts)
        major = {"scopus", "web of science", "wos", "doaj", "eric",
                 "psycinfo", "heinonline", "lexisnexis"}
        claimed = {c.lower() for c in self.journal.claimed_indexes}
        has_major = bool(claimed & major)
        pts += 6 if has_major else 0
        sub.append({"criterion": "Indexing in Major Databases", "earned": 6 if has_major else 0, "max": 6,
                    "detail": f"Major indexes found: {claimed & major}" if has_major else "No major indexes"})

        # Misleading Metrics (6 pts)
        bad_metrics = {"sjif", "cosmos", "gif", "citefactor", "ae global index"}
        metric_lower = {m.lower() for m in self.journal.metric_claims}
        has_bad = bool(metric_lower & bad_metrics)
        pts += 0 if has_bad else 6
        sub.append({"criterion": "No Misleading Metrics", "earned": 0 if has_bad else 6, "max": 6,
                    "detail": f"Predatory metrics found: {metric_lower & bad_metrics}" if has_bad else "Clean"})

        # Google Scholar Citations (6 pts)
        pts += 1  # unknown default
        sub.append({"criterion": "Google Scholar Citations", "earned": 1, "max": 6,
                    "detail": "Citation count not available; 1 pt default"})

        # h5-index (2 pts)
        pts += 1
        sub.append({"criterion": "h5-index", "earned": 1, "max": 2,
                    "detail": "h5-index not available; 1 pt default"})

        return DomainScore(domain="Metrics and Indexing",
                           max_points=20, earned_points=pts, sub_criteria=sub)

    def _score_domain6_ethics(self) -> DomainScore:
        sub = []
        pts = 0

        # Research Ethics Policy (COPE/ICMJE/WAME) (6 pts)
        has_ethics = bool(self.journal.ethics_policy_url)
        pts += 6 if has_ethics else 0
        sub.append({"criterion": "Research Ethics Policy (COPE/ICMJE/WAME)", "earned": 6 if has_ethics else 0, "max": 6,
                    "detail": "Policy present" if has_ethics else "No ethics policy"})

        # AI Disclosure (3 pts)
        pts += 1  # neutral
        sub.append({"criterion": "AI Content Disclosure", "earned": 1, "max": 3,
                    "detail": "Not verifiable; 1 pt default"})

        # Plagiarism Check (6 pts)
        pts += 1  # neutral
        sub.append({"criterion": "Plagiarism Check (iThenticate/Turnitin)", "earned": 1, "max": 6,
                    "detail": "Not verifiable; 1 pt default"})

        # COPE Core Practices (3 pts)
        pts += 1
        sub.append({"criterion": "COPE Core Practices Linked", "earned": 1, "max": 3,
                    "detail": "Not verifiable; 1 pt default"})

        # Conflict of Interest Policy (2 pts)
        pts += 1
        sub.append({"criterion": "Conflict of Interest Policy", "earned": 1, "max": 2,
                    "detail": "Not verifiable; 1 pt default"})

        return DomainScore(domain="Ethics and Compliance",
                           max_points=20, earned_points=pts, sub_criteria=sub)
