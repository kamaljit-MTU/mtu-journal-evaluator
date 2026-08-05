"""
Scoring Engine - 150-point framework with enhanced verification
"""
from typing import List, Dict, Any, Optional
from .models import JournalInput, DomainScore, RejectionTriggerResult
from .enhanced_verifiers import (
    JournalHistoryVerifier, ORCIDEditorVerifier,
    GeographicDiversityVerifier, DeepWebSearcher
)


class ScoringEngine:
    THRESHOLD = 120
    MAX_SCORE = 150

    def __init__(self, journal: JournalInput, verification_data: Optional[Dict] = None):
        self.journal = journal
        self.verification_data = verification_data or {}
        self.fc = self.verification_data.get("firecrawl") or {}
        self.homepage = self.fc.get("homepage_signal") or {}
        self.editorial = self.fc.get("editorial_board_signal") or {}
        self.policies = self.fc.get("policies_signal") or {}
        self.submission = self.fc.get("submission_signal") or {}

    def score(self, trigger_results: List[RejectionTriggerResult]) -> List[DomainScore]:
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

        issn = self.journal.issn_print or self.journal.issn_online
        pts += 5 if issn else 0
        sub.append({"criterion": "ISSN Verification", "earned": 5 if issn else 0, "max": 5,
                    "detail": f"ISSN: {issn}" if issn else "No ISSN provided"})

        suspicious = {"international journal of advanced research", "world journal of", "american journal of"}
        title_ok = not any(p in self.journal.name.lower() for p in suspicious)
        pts += 5 if title_ok else 0
        sub.append({"criterion": "Distinct Title", "earned": 5 if title_ok else 0, "max": 5,
                    "detail": "Unique title" if title_ok else "Suspicious title pattern"})

        pub_ok = bool(self.journal.publisher_name and self.journal.publisher_url)
        pts += 5 if pub_ok else 0
        sub.append({"criterion": "Publisher Legitimacy", "earned": 5 if pub_ok else 0, "max": 5,
                    "detail": f"Publisher: {self.journal.publisher_name}" if pub_ok else "Incomplete publisher info"})

        # Journal History (4 pts)
        history_pts = 2
        history_detail = "History not specified; default 2 pts (2-3 yrs assumed)"
        archive_text = " ".join(str(v) for v in self.homepage.get("archive_claim", [])) if isinstance(self.homepage.get("archive_claim"), list) else str(self.homepage.get("archive_claim", ""))
        years_match = __import__("re").search(r"since\s*(\d{4})|(\d{4})\s*[-–]\s*(?:present|current)", archive_text, __import__("re").IGNORECASE)
        if years_match:
            import datetime
            current_year = datetime.datetime.now().year
            start_year = int(years_match.group(1) or years_match.group(2))
            age = current_year - start_year
            if age >= 3:
                history_pts = 4
                history_detail = f"History verified from page content: active since {start_year} ({age} yrs)"
            elif age >= 2:
                history_pts = 3
                history_detail = f"History verified from page content: active since {start_year} ({age} yrs)"
            elif age >= 1:
                history_pts = 2
                history_detail = f"History verified from page content: active since {start_year} ({age} yrs)"
            else:
                history_pts = 1
                history_detail = f"History verified from page content: active since {start_year} (<1 yr)"
        journal_history = self.verification_data.get("journal_history", {})
        if journal_history.get("sources_checked"):
            sources = journal_history["sources_checked"]
            if len(sources) >= 3:
                history_pts = 4
                history_detail = f"History verified from {len(sources)} sources: {', '.join(sources)}"
            elif len(sources) == 2:
                history_pts = 3
                history_detail = f"History verified from {len(sources)} sources: {', '.join(sources)}"
            elif len(sources) == 1:
                history_pts = 2
                history_detail = f"History check from 1 source: {', '.join(sources)}"
            if journal_history.get("confidence") == "high" and history_pts < 4:
                history_pts = min(4, history_pts + 1)
                history_detail += " (confidence: high)"
        pts += history_pts
        sub.append({"criterion": "Journal History", "earned": history_pts, "max": 4,
                    "detail": history_detail})

        pts += 4 if bool(self.journal.publisher_address) else 0
        sub.append({"criterion": "Publisher Transparency", "earned": 4 if bool(self.journal.publisher_address) else 0, "max": 4,
                    "detail": "Address provided" if bool(self.journal.publisher_address) else "No address"})

        # DOI Verification (4 pts) - Enhanced with Firecrawl
        doi_pts = 0
        doi_detail = "No DOI info"
        if self.journal.doi_prefix:
            dois = self.fc.get("dois") or {}
            if dois.get("error"):
                doi_pts = 2
                doi_detail = "DOI prefix provided, but live DOI verification failed"
            elif dois.get("valid_format") and dois.get("count", 0) > 0:
                doi_pts = 4
                doi_detail = f"Valid DOI prefix with {dois.get('count')} DOI attribution(s) found on journal page"
            elif dois.get("valid_format"):
                doi_pts = 3
                doi_detail = "DOI prefix provided; page contains valid DOI format but none explicitly extracted"
            else:
                doi_pts = 2
                doi_detail = "DOI prefix provided, but DOI attributions on page appear invalid"
        else:
            doi_detail = "No DOI prefix provided"
        pts += doi_pts
        sub.append({"criterion": "DOI Verification", "earned": doi_pts, "max": 4,
                    "detail": doi_detail})

        pub_bonus = 1
        known_reputable = {"elsevier", "springer", "wiley", "ieee", "acm",
                           "oxford university press", "cambridge", "sage",
                           "taylor & francis", "mdpi", "frontiers"}
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
        total_editors = self.editorial.get("total_editors", 0)
        with_aff = self.editorial.get("with_affiliation", 0)
        has_eb = bool(self.journal.editorial_board_url)
        if total_editors > 0 and with_aff / max(total_editors, 1) >= 0.5:
            pts += 4
            detail = f"Editorial board scraped: {total_editors} editors, {with_aff} with affiliations"
        elif total_editors > 0:
            pts += 2
            detail = f"Editorial board scraped: {total_editors} editors, {with_aff} with affiliations"
        elif has_eb:
            pts += 3
            detail = "Editorial board URL provided"
        else:
            detail = "No editorial board info"
        sub.append({"criterion": "Verified Affiliations (50% sample)", "earned": pts, "max": 4,
                    "detail": detail})

        # Geographic Diversity (4 pts)
        geo_pts = 2
        geo_detail = "Diversity not verifiable from input alone; 2 pts default"
        geo_data = self.verification_data.get("geographic_diversity", {})
        if geo_data:
            diversity_rating = geo_data.get("diversity_rating", "poor")
            countries = geo_data.get("countries", [])
            if diversity_rating == "excellent":
                geo_pts = 4
                geo_detail = f"Excellent diversity: {len(countries)} countries represented"
            elif diversity_rating == "good":
                geo_pts = 3
                geo_detail = f"Good diversity: {len(countries)} countries represented"
            elif diversity_rating == "fair":
                geo_pts = 2
                geo_detail = f"Fair diversity: {len(countries)} countries represented"
            else:
                geo_pts = 1
                geo_detail = f"Poor diversity: {len(countries)} countries represented"
            if geo_data.get("needs_human_review"):
                geo_detail += " (flagged for human review)"
        elif total_editors > 0:
            geo_pts = 1
            geo_detail = f"Editorial board present with {total_editors} editors, but geographic data not extracted"
        pts += geo_pts
        sub.append({"criterion": "Geographic/Institutional Diversity", "earned": geo_pts, "max": 4,
                    "detail": geo_detail})

        # EIC h-index (6 pts)
        eic_h_pts = 2
        eic_h_detail = "EIC h-index not provided; 2 pts default"
        h_index_data = self.verification_data.get("h_index_estimation", {})
        if h_index_data:
            estimated = h_index_data.get("estimated", 0)
            total = h_index_data.get("total", 0)
            if estimated > 0 and total > 0:
                rate = estimated / total
                if rate >= 0.5:
                    eic_h_pts = 4
                    eic_h_detail = f"h-index estimated for {estimated}/{total} editors via web search"
                elif rate >= 0.2:
                    eic_h_pts = 3
                    eic_h_detail = f"h-index estimated for {estimated}/{total} editors via web search"
                else:
                    eic_h_pts = 2
                    eic_h_detail = f"h-index estimated for {estimated}/{total} editors via web search"
        elif self.homepage.get("eic_orcid_on_homepage", {}).get("found"):
            eic_h_pts = 2
            eic_h_detail = "EIC identified on homepage; h-index estimation requires additional search"
        pts += eic_h_pts
        sub.append({"criterion": "Editor-in-Chief h-index", "earned": eic_h_pts, "max": 6,
                    "detail": eic_h_detail})

        # ORCID Availability (3 pts) - Enhanced with Firecrawl
        orcid_pts = 1
        orcid_detail = "ORCID data not available; 1 pt default"
        orcid_data = self.verification_data.get("orcid_verification", {})
        if orcid_data:
            total = orcid_data.get("total_editors", 0)
            verified = orcid_data.get("verified", 0)
            verification_rate = orcid_data.get("verification_rate", 0)
            if total > 0:
                if verification_rate >= 0.8:
                    orcid_pts = 3
                    orcid_detail = f"Excellent ORCID verification: {verified}/{total} editors verified ({verification_rate*100:.0f}%)"
                elif verification_rate >= 0.5:
                    orcid_pts = 2
                    orcid_detail = f"Good ORCID verification: {verified}/{total} editors verified ({verification_rate*100:.0f}%)"
                else:
                    orcid_pts = 1
                    orcid_detail = f"Poor ORCID verification: only {verified}/{total} editors verified ({verification_rate*100:.0f}%)"
        eic_orcid = self.fc.get("eic_orcid") or {}
        if eic_orcid.get("orcid_id") and eic_orcid.get("orcid_verified"):
            orcid_pts = 3
            orcid_detail = f"EIC ORCID verified via Firecrawl: {eic_orcid.get('editor_name')} ({eic_orcid.get('orcid_id')})"
        elif eic_orcid.get("orcid_id"):
            orcid_pts = 2
            orcid_detail = f"EIC ORCID found via Firecrawl: {eic_orcid.get('orcid_id')} (not independently verified)"
        pts += orcid_pts
        sub.append({"criterion": "ORCID/ID Availability", "earned": orcid_pts, "max": 3,
                    "detail": orcid_detail})

        # Special Issue Editors (3 pts)
        special_pts = 1
        special_detail = "Not verified; 1 pt default"
        board_text = str(self.editorial)
        if "special issue" in board_text.lower() or "guest editor" in board_text.lower():
            special_pts = 3
            special_detail = "Special issue/guest editors mentioned on editorial board page"
        elif total_editors > 5:
            special_pts = 2
            special_detail = f"Editorial board has {total_editors} editors; special issue editors likely"
        pts += special_pts
        sub.append({"criterion": "Named Special Issue Editors", "earned": special_pts, "max": 3,
                    "detail": special_detail})

        # Editorial Activity (4 pts)
        activity_pts = 2
        activity_detail = "Not verified; 2 pts default"
        if total_editors > 0:
            activity_pts = 3
            activity_detail = f"Active editorial board with {total_editors} editors found on page"
        elif self.editorial.get("editorial_board_present"):
            activity_pts = 3
            activity_detail = "Editorial board page present with active listing"
        pts += activity_pts
        sub.append({"criterion": "Editorial Activity (3-5 years)", "earned": activity_pts, "max": 4,
                    "detail": activity_detail})

        # Editorial Independence Policy (3 pts)
        indep_pts = 0
        indep_detail = "No independence policy found"
        if self.policies.get("review_policy_present") or self.policies.get("editorial_policy_present"):
            indep_pts = 3
            indep_detail = "Editorial/review policy present on policy page"
        elif self.homepage.get("peer_review_claim") or self.policies.get("review_policy_present"):
            indep_pts = 2
            indep_detail = "Peer review policy mentioned"
        elif self.journal.ethics_policy_url:
            indep_pts = 3
            indep_detail = "Policy page present"
        pts += indep_pts
        sub.append({"criterion": "Editorial Independence Policy", "earned": indep_pts, "max": 3,
                    "detail": indep_detail})

        pts += 2
        sub.append({"criterion": "Author-Editor Overlap", "earned": 2, "max": 3,
                    "detail": "Cannot verify from input; 2 pts default"})

        return DomainScore(domain="Editorial Board and Governance",
                           max_points=30, earned_points=pts, sub_criteria=sub)

    def _score_domain3_peer_review(self) -> DomainScore:
        sub = []
        pts = 0

        # Type of Review (6 pts)
        review_pts = 2
        review_detail = "Review type not specified; 2 pts default"
        review_type = self.homepage.get("review_type") or self._infer_review_type_from_policies()
        if review_type == "double-blind":
            review_pts = 6
            review_detail = "Double-blind review stated"
        elif review_type == "single-blind":
            review_pts = 4
            review_detail = "Single-blind review stated"
        elif review_type == "peer review":
            review_pts = 3
            review_detail = "Peer review mentioned but blind type not specified"
        elif self.policies.get("review_policy_present") or self.homepage.get("peer_review_claim"):
            review_pts = 3
            review_detail = "Peer review policy present"
        pts += review_pts
        sub.append({"criterion": "Type of Review (double/single blind)", "earned": review_pts, "max": 6,
                    "detail": review_detail})

        # Reviewer Pool (2 pts)
        reviewer_pts = 1
        reviewer_detail = "Not verifiable; 1 pt default"
        if self.homepage.get("reviewer_pool_claim"):
            reviewer_pts = 2
            reviewer_detail = "Reviewer pool/public call for reviewers found on page"
        elif self.homepage.get("editorial_board_present"):
            reviewer_pts = 1
            reviewer_detail = "Editorial board present but no explicit reviewer pool"
        pts += reviewer_pts
        sub.append({"criterion": "Reviewer Pool", "earned": reviewer_pts, "max": 2,
                    "detail": reviewer_detail})

        # Review Timeline (6 pts)
        timeline_pts = 2
        timeline_detail = "Timeline not specified; 2 pts default"
        timeline = self.submission.get("review_timeline_claim")
        if timeline == ">4 weeks":
            timeline_pts = 6
            timeline_detail = "Review timeline >4 weeks stated on submission page"
        elif timeline == "1-4 weeks":
            timeline_pts = 3
            timeline_detail = "Review timeline 1-4 weeks stated on submission page"
        elif timeline == "<1 week":
            timeline_pts = 0
            timeline_detail = "Review timeline <1 week stated; possible predatory indicator"
        pts += timeline_pts
        sub.append({"criterion": "Review Timeline", "earned": timeline_pts, "max": 6,
                    "detail": timeline_detail})

        # Peer Review History (4 pts)
        history_pts = 1
        history_detail = "Not verifiable; 1 pt default"
        if self.submission.get("peer_review_history_claim"):
            history_pts = 4
            history_detail = "Peer review history visible in metadata/submission page"
        elif self.homepage.get("peer_review_claim"):
            history_pts = 2
            history_detail = "Peer review mentioned but history not explicitly shown"
        pts += history_pts
        sub.append({"criterion": "Peer Review History in Metadata", "earned": history_pts, "max": 4,
                    "detail": history_detail})

        # Acceptance Dates (4 pts)
        accept_pts = 2
        accept_detail = "Not verifiable; 2 pts default"
        if self.submission.get("acceptance_dates_claim"):
            accept_pts = 4
            accept_detail = "Acceptance/received/published dates present on submission or article page"
        pts += accept_pts
        sub.append({"criterion": "Acceptance Dates Precede Publication", "earned": accept_pts, "max": 4,
                    "detail": accept_detail})

        # Appeals Process (4 pts)
        appeals_pts = 2
        appeals_detail = "Not verifiable; 2 pts default"
        if self.policies.get("appeals_present") or self.homepage.get("appeals_claim"):
            appeals_pts = 4
            appeals_detail = "Appeals/complaints process documented on policy page"
        pts += appeals_pts
        sub.append({"criterion": "Appeals Process", "earned": appeals_pts, "max": 4,
                    "detail": appeals_detail})

        # Retraction Policy (4 pts)
        retraction_pts = 0
        retraction_detail = "No retraction policy found"
        if self.policies.get("retraction_policy_present") or self.homepage.get("retraction_claim"):
            retraction_pts = 4
            retraction_detail = "Retraction/correction policy found on policy page"
        elif self.journal.ethics_policy_url:
            retraction_pts = 2
            retraction_detail = "Policy page present; retraction content not verified"
        pts += retraction_pts
        sub.append({"criterion": "Retraction/Correction Policy", "earned": retraction_pts, "max": 4,
                    "detail": retraction_detail})

        return DomainScore(domain="Peer Review and Publishing Process",
                           max_points=30, earned_points=pts, sub_criteria=sub)

    def _score_domain4_website(self) -> DomainScore:
        sub = []
        pts = 0

        # Language Quality (3 pts)
        lang = self.homepage.get("language_quality_signal")
        lang_pts = 2
        lang_detail = "Not verified; 2 pts default"
        if lang == "clean":
            lang_pts = 3
            lang_detail = "Website content appears professionally written"
        elif lang == "major":
            lang_pts = 0
            lang_detail = "Website contains poor language/spam indicators"
        pts += lang_pts
        sub.append({"criterion": "Language Quality", "earned": lang_pts, "max": 3,
                    "detail": lang_detail})

        # Metadata Standards (3 pts)
        meta_pts = 3 if self.homepage.get("metadata_signal") else 1
        meta_detail = "Metadata standards indicators found on page" if self.homepage.get("metadata_signal") else "Website present"
        if self.journal.url:
            meta_pts = max(meta_pts, 1)
        pts += meta_pts
        sub.append({"criterion": "Metadata Standards", "earned": meta_pts, "max": 3,
                    "detail": meta_detail})

        # Citation Format (3 pts)
        cite_pts = 2
        cite_detail = "Not verifiable; 2 pts default"
        if self.homepage.get("citation_format_claim"):
            cite_pts = 3
            cite_detail = "Citation format guidance found on author guidelines page"
        pts += cite_pts
        sub.append({"criterion": "Citation Format Standardization", "earned": cite_pts, "max": 3,
                    "detail": cite_detail})

        # Archive Access (2 pts)
        archive_pts = 1
        archive_detail = "Not verifiable; 1 pt default"
        if self.homepage.get("archive_claim"):
            archive_pts = 2
            archive_detail = "Archive/back issues access indicated on homepage"
        pts += archive_pts
        sub.append({"criterion": "Archive Access", "earned": archive_pts, "max": 2,
                    "detail": archive_detail})

        # Author-oriented Information (3 pts)
        author_pts = 1
        author_detail = "Cannot determine; 1 pt default"
        if self.homepage.get("author_information_claim"):
            author_pts = 3
            author_detail = "Author guidelines/information present"
        pts += author_pts
        sub.append({"criterion": "Not overly author-oriented", "earned": author_pts, "max": 3,
                    "detail": author_detail})

        # Search Functionality (2 pts)
        search_pts = 1
        search_detail = "Not verifiable; 1 pt default"
        if self.homepage.get("search_claim"):
            search_pts = 2
            search_detail = "Search functionality present on homepage"
        pts += search_pts
        sub.append({"criterion": "Search Functionality", "earned": search_pts, "max": 2,
                    "detail": search_detail})

        # Article Licensing (2 pts)
        lic_pts = 1 if self.journal.open_access else 0
        lic_detail = "Open access" if self.journal.open_access else "License not clear"
        if self.homepage.get("licensing_claim") or self.homepage.get("open_access_claim"):
            lic_pts = max(lic_pts, 2 if self.journal.open_access else 1)
            lic_detail = "Licensing information present" if not self.journal.open_access else "Open access license indicated"
        pts += lic_pts
        sub.append({"criterion": "Article Licensing Clear", "earned": lic_pts, "max": 2,
                    "detail": lic_detail})

        # Custom CMS (2 pts)
        cms = self.homepage.get("custom_cms_signal")
        cms_pts = 1
        cms_detail = "Not verifiable; 1 pt default"
        if cms == "default":
            cms_pts = 0
            cms_detail = "Default CMS detected; likely generic template"
        elif cms == "unknown":
            cms_pts = 1
            cms_detail = "No clear CMS fingerprint detected"
        pts += cms_pts
        sub.append({"criterion": "Custom CMS", "earned": cms_pts, "max": 2,
                    "detail": cms_detail})

        return DomainScore(domain="Website and Infrastructure",
                           max_points=20, earned_points=pts, sub_criteria=sub)

    def _score_domain5_metrics(self) -> DomainScore:
        sub = []
        pts = 0

        major = {"scopus", "web of science", "wos", "doaj", "eric",
                 "psycinfo", "heinonline", "lexisnexis"}
        homepage_indexing = [c.lower() for c in self.homepage.get("indexing_claims", [])]
        claimed = {c.lower() for c in self.journal.claimed_indexes}
        combined_indexing = claimed | set(homepage_indexing)
        has_major = bool(combined_indexing & major)
        pts += 6 if has_major else 0
        sub.append({"criterion": "Indexing in Major Databases", "earned": 6 if has_major else 0, "max": 6,
                    "detail": f"Major indexes found: {combined_indexing & major}" if has_major else "No major indexes"})

        bad_metrics = {"sjif", "cosmos", "gif", "citefactor", "ae global index"}
        homepage_metrics = [m.lower() for m in self.homepage.get("metric_claims", [])]
        metric_lower = {m.lower() for m in self.journal.metric_claims} | set(homepage_metrics)
        has_bad = bool(metric_lower & bad_metrics)
        pts += 0 if has_bad else 6
        sub.append({"criterion": "No Misleading Metrics", "earned": 0 if has_bad else 6, "max": 6,
                    "detail": f"Predatory metrics found: {metric_lower & bad_metrics}" if has_bad else "Clean"})

        pts += 1
        sub.append({"criterion": "Google Scholar Citations", "earned": 1, "max": 6,
                    "detail": "Citation count not available; 1 pt default"})

        pts += 1
        sub.append({"criterion": "h5-index", "earned": 1, "max": 2,
                    "detail": "h5-index not available; 1 pt default"})

        return DomainScore(domain="Metrics and Indexing",
                           max_points=20, earned_points=pts, sub_criteria=sub)

    def _score_domain6_ethics(self) -> DomainScore:
        sub = []
        pts = 0

        ethics_pts = 0
        ethics_detail = "No ethics policy found"
        if self.policies.get("cope_member") or self.policies.get("icmje_member") or self.policies.get("wame_member"):
            ethics_pts = 6
            ethics_detail = "Journal is member of COPE/ICMJE/WAME"
        elif self.policies.get("ethics_policy_present") or self.homepage.get("ethics_claim"):
            ethics_pts = 4
            ethics_detail = "Research ethics/publication ethics policy found"
        elif self.journal.ethics_policy_url:
            ethics_pts = 2
            ethics_detail = "Ethics policy URL provided"
        pts += ethics_pts
        sub.append({"criterion": "Research Ethics Policy (COPE/ICMJE/WAME)", "earned": ethics_pts, "max": 6,
                    "detail": ethics_detail})

        ai_pts = 1
        ai_detail = "Not verifiable; 1 pt default"
        if self.policies.get("ai_disclosure_present") or self.homepage.get("ai_disclosure_claim"):
            ai_pts = 3
            ai_detail = "AI disclosure/generative AI policy found"
        elif self.policies.get("ai_disclosure_present") is False and self.homepage.get("ai_disclosure_claim") is False:
            ai_pts = 0
            ai_detail = "No AI disclosure policy found"
        pts += ai_pts
        sub.append({"criterion": "AI Content Disclosure", "earned": ai_pts, "max": 3,
                    "detail": ai_detail})

        plagiarism_pts = 1
        plagiarism_detail = "Not verifiable; 1 pt default"
        if self.policies.get("plagiarism_present") or self.homepage.get("plagiarism_claim"):
            plagiarism_pts = 6
            plagiarism_detail = "Plagiarism check policy present (iThenticate/Turnitin/similarity check)"
        elif self.policies.get("plagiarism_present") is False and self.homepage.get("plagiarism_claim") is False:
            plagiarism_pts = 0
            plagiarism_detail = "No plagiarism check policy found"
        pts += plagiarism_pts
        sub.append({"criterion": "Plagiarism Check (iThenticate/Turnitin)", "earned": plagiarism_pts, "max": 6,
                    "detail": plagiarism_detail})

        cope_pts = 1
        cope_detail = "Not verifiable; 1 pt default"
        if self.policies.get("cope_member") or self.policies.get("icmje_member") or self.policies.get("wame_member"):
            cope_pts = 3
            cope_detail = "Linked to COPE/ICMJE/WAME core practices"
        elif self.policies.get("cope_member") is False and self.policies.get("icmje_member") is False:
            cope_pts = 0
            cope_detail = "No link to COPE/ICMJE/WAME found"
        pts += cope_pts
        sub.append({"criterion": "COPE Core Practices Linked", "earned": cope_pts, "max": 3,
                    "detail": cope_detail})

        coi_pts = 1
        coi_detail = "Not verifiable; 1 pt default"
        if self.policies.get("conflict_of_interest_present"):
            coi_pts = 2
            coi_detail = "Conflict of interest policy found on policy page"
        elif self.policies.get("conflict_of_interest_present") is False:
            coi_pts = 0
            coi_detail = "No conflict of interest policy found"
        pts += coi_pts
        sub.append({"criterion": "Conflict of Interest Policy", "earned": coi_pts, "max": 2,
                    "detail": coi_detail})

        return DomainScore(domain="Ethics and Compliance",
                           max_points=20, earned_points=pts, sub_criteria=sub)

    def _infer_review_type_from_policies(self) -> Optional[str]:
        if self.policies.get("review_policy_present"):
            text = str(self.policies)
            if "double-blind" in text.lower():
                return "double-blind"
            if "single-blind" in text.lower() or "single blind" in text.lower():
                return "single-blind"
            if "peer review" in text.lower():
                return "peer review"
        return None
