"""
MTU Journal Evaluator - Main Evaluator Orchestrator v2 with enhanced verification
"""
from typing import List, Optional, Dict, Any
from .models import JournalInput, EvaluationResult, VerdictStatus
from .rejection_triggers import RejectionTriggerChecker
from .scoring_engine import ScoringEngine
from .reporting import ReportGenerator
from .enhanced_verifiers import (
    JournalHistoryVerifier, ORCIDEditorVerifier,
    GeographicDiversityVerifier, DeepWebSearcher, HIndexEstimator
)
from .editorial_board_scraper import EditorialBoardScraper
from .rejected_journals_db import RejectedJournalDatabase
from .accepted_journals_db import AcceptedJournalDatabase
from .human_intervention import HumanInterventionQueue
from .reference_lists import ReferenceListChecker
from .appendix_a import AppendixAChecker
from .firecrawl_verifier import FirecrawlVerifier
from .verifiers import ISSNVerifier


class MTUJournalEvaluator:
    def __init__(self):
        self.reporter = ReportGenerator()
        self.rejected_db = RejectedJournalDatabase()
        self.accepted_db = AcceptedJournalDatabase()
        self.intervention_queue = HumanInterventionQueue()

    def evaluate(self, journal: JournalInput, save_accepted: bool = True) -> EvaluationResult:
        # Phase 0: Enhanced Verification
        verification_data = self._run_enhanced_verifications(journal)

        # Phase 1: Rejection Trigger Check
        checker = RejectionTriggerChecker(journal)
        any_rejected, trigger_results = checker.check_all()

        # Phase 2: Scoring (only if not auto-rejected)
        domain_scores: List = []
        total_score = 0
        percentage = 0.0
        recommendations: List[str] = []

        if any_rejected:
            status = VerdictStatus.REJECTED
            total_score = 0
            failed = [t.name for t in trigger_results if not t.passed]
            summary = (
                f"Journal REJECTED due to {len(failed)} automatic rejection trigger(s): "
                f"{'; '.join(failed)}. No further scoring performed."
            )
            recommendations = [
                "Resolve all rejection triggers before resubmission.",
                "Ensure valid ISSN, legitimate publisher, online submission portal.",
                "Remove any predatory metric claims (SJIF, Cosmos, GIF, etc.).",
                "Publish a clear research ethics and publication policy.",
            ]
        else:
            engine = ScoringEngine(journal, verification_data)
            domain_scores = engine.score(trigger_results)
            total_score = sum(d.earned_points for d in domain_scores)
            percentage = (total_score / ScoringEngine.MAX_SCORE) * 100

            if total_score >= ScoringEngine.THRESHOLD:
                status = VerdictStatus.ACCEPTED
                summary = (
                    f"Journal ACCEPTED. Scored {total_score}/{ScoringEngine.MAX_SCORE} "
                    f"({percentage:.1f}%), meeting the minimum threshold of "
                    f"{ScoringEngine.THRESHOLD}/{ScoringEngine.MAX_SCORE}."
                )
                recommendations = [
                    "Journal meets MTU quality standards.",
                    "Maintain current standards and transparency.",
                    "Re-evaluation recommended every 3 years.",
                ]
            else:
                status = VerdictStatus.CONDITIONAL
                summary = (
                    f"Journal CONDITIONAL. Scored {total_score}/{ScoringEngine.MAX_SCORE} "
                    f"({percentage:.1f}%), below the minimum threshold of "
                    f"{ScoringEngine.THRESHOLD}/{ScoringEngine.MAX_SCORE}."
                )
                weak = [d.domain for d in domain_scores
                        if d.earned_points / d.max_points < 0.7]
                recommendations = [
                    f"Improve scoring in weak domains: {', '.join(weak)}.",
                    "Ensure all sub-criteria documentation is publicly available.",
                    "Consider re-evaluation after improvements.",
                ]

        appendix_checks = AppendixAChecker({
            "issn_print": journal.issn_print,
            "issn_online": journal.issn_online,
            "journal_name": journal.name,
            "publisher_name": journal.publisher_name,
            "publisher_address": journal.publisher_address,
            "doi_prefix": journal.doi_prefix,
            "journal_history_years": verification_data.get("journal_history", {}).get("years"),
            "verification_data": verification_data,
            "claimed_indexes": journal.claimed_indexes,
            "metric_claims": journal.metric_claims,
            "editorial_board_url": journal.editorial_board_url,
            "aims_scope_url": journal.aims_scope_url,
            "submission_portal_url": journal.submission_portal_url,
            "ethics_policy_url": journal.ethics_policy_url,
            "editors": verification_data.get("editorial_board_scrape", {}).get("editors", []),
            "countries": verification_data.get("geographic_diversity", {}).get("countries", []),
            "google_scholar_citations": verification_data.get("h_index_estimation", {}).get("estimated", 0),
            "h5_index": verification_data.get("h_index_estimation", {}).get("h5_index"),
        }).check_all()

        result = EvaluationResult(
            journal_name=journal.name,
            journal_url=journal.url,
            status=status,
            total_score=total_score,
            max_score=ScoringEngine.MAX_SCORE,
            percentage=percentage,
            threshold=ScoringEngine.THRESHOLD,
            rejection_triggers=trigger_results,
            domain_scores=domain_scores,
            summary=summary,
            recommendations=recommendations,
            appendix_checks=appendix_checks,
            unverified_parameters=self._collect_unverified_parameters({"appendix_checks": appendix_checks}),
            raw_data={
                "issn_print": journal.issn_print,
                "issn_online": journal.issn_online,
                "publisher": journal.publisher_name,
                "claimed_indexes": journal.claimed_indexes,
                "metric_claims": journal.metric_claims,
                "open_access": journal.open_access,
                "verification_data": verification_data,
            },
        )

        # Phase 3: Save to appropriate database and handle interventions
        self._post_evaluation_actions(result, journal, verification_data)

        return result

    def _run_enhanced_verifications(self, journal: JournalInput) -> Dict[str, Any]:
        """Run all enhanced verifications."""
        verification_data = {}

        # 1. Journal History Verification
        journal_history = JournalHistoryVerifier.verify(
            journal.name,
            journal.issn_print or journal.issn_online,
            journal.publisher_name
        )
        verification_data["journal_history"] = journal_history

        # 2. Scrape editorial board and augment with ORCID/h-index lookups
        editors = []
        if journal.editorial_board_url:
            scraped = EditorialBoardScraper.scrape(journal.editorial_board_url, augment=True)
            editors = scraped.get("editors", [])
            if scraped.get("success"):
                verification_data["editorial_board_scrape"] = {
                    "url": journal.editorial_board_url,
                    "total_editors": scraped.get("total_editors", 0),
                    "with_orcid": scraped.get("with_orcid", 0),
                    "with_affiliation": scraped.get("with_affiliation", 0),
                    "countries": scraped.get("countries", []),
                    "editors": editors[:100],
                }

        if editors:
            # Use augmented ORCIDs and h-indices from scraper
            orcid_verification = ORCIDEditorVerifier.verify_editorial_board(editors)
            verification_data["orcid_verification"] = orcid_verification

            # h-index estimation from augmented editor data
            h_index_estimations = []
            for editor in editors:
                if editor.get("h_index") is not None:
                    h_index_estimations.append({
                        "name": editor.get("name"),
                        "h_index_estimate": editor.get("h_index"),
                        "h_index_source": editor.get("h_index_source"),
                        "h_index_confidence": editor.get("h_index_confidence", "low"),
                    })
            h_index_results = {
                "total": len(editors),
                "estimated": len(h_index_estimations),
                "not_found": len(editors) - len(h_index_estimations),
                "estimations": h_index_estimations,
            }
            verification_data["h_index_estimation"] = h_index_results

            # Geographic diversity from verified affiliations
            geo_data = GeographicDiversityVerifier.verify(editors)
            if not geo_data.get("countries"):
                geo_data["countries"] = orcid_verification.get("geographic_diversity", {}).get("countries", [])
            verification_data["geographic_diversity"] = geo_data
        else:
            # Fallback if no editorial board URL or scraping failed
            verification_data["orcid_verification"] = {
                "total_editors": 0,
                "verified": 0,
                "verification_rate": 0.0,
                "needs_human_review": True,
                "human_review_reason": "Editorial board data could not be retrieved"
            }
            verification_data["geographic_diversity"] = {
                "total_editors": 0,
                "countries": [],
                "diversity_rating": "unknown",
                "needs_human_review": True
            }
            verification_data["h_index_estimation"] = {
                "total": 0,
                "estimated": 0,
                "not_found": 0
            }

        # 3. Deep Web Search
        web_search = DeepWebSearcher.search_journal_reputation(
            journal.name,
            journal.publisher_name
        )
        verification_data["deep_search"] = web_search

        # 4. Reference Lists: Beall's, Clarivate MJL/JCR, UGC CARE
        ref_check = ReferenceListChecker.check_all(
            journal.name,
            journal.issn_print or journal.issn_online,
            journal.publisher_name
        )
        verification_data["reference_lists"] = ref_check

        # 5. Firecrawl-backed page verification
        firecrawl = FirecrawlVerifier()
        page_url = journal.url or (journal.editorial_board_url or journal.aims_scope_url or journal.submission_portal_url)
        if page_url:
            eic_orcid = firecrawl.verify_eic_orcid(page_url)
            dois = firecrawl.verify_doi_attributions(
                page_url,
                doi_prefix=journal.doi_prefix or None,
            )
            homepage_signal = firecrawl.verify_page_signal(page_url, kind="journal_homepage")

            editorial_board_signal = {}
            if journal.editorial_board_url:
                editorial_board_signal = firecrawl.verify_page_signal(journal.editorial_board_url, kind="editorial_board")

            policies_signal = {}
            policies_url = journal.aims_scope_url or journal.ethics_policy_url
            if policies_url:
                policies_signal = firecrawl.verify_page_signal(policies_url, kind="policies")

            submission_signal = {}
            if journal.submission_portal_url:
                submission_signal = firecrawl.verify_page_signal(journal.submission_portal_url, kind="submission_portal")

            firecrawl_payload = {
                "eic_orcid": eic_orcid,
                "dois": dois,
                "homepage_signal": homepage_signal,
                "editorial_board_signal": editorial_board_signal,
                "policies_signal": policies_signal,
                "submission_signal": submission_signal,
            }
            if eic_orcid.get("error") or dois.get("error"):
                firecrawl_payload["error"] = eic_orcid.get("error") or dois.get("error")
            verification_data["firecrawl"] = firecrawl_payload

        # 6. ISSN Portal search fallback when no ISSN provided or additional confirmation needed
        issn_search = {}
        if not journal.issn_print and not journal.issn_online and journal.name:
            issn_search = ISSNVerifier.search_portal(journal.name)
        elif journal.name:
            issn_search = ISSNVerifier.search_portal(journal.name)
        verification_data["issn_portal_search"] = issn_search

        return verification_data

    def _post_evaluation_actions(self, result: EvaluationResult, journal: JournalInput,
                                verification_data: Dict[str, Any]):
        """Save to databases and create interventions if needed."""
        if result.status == VerdictStatus.REJECTED:
            # Save to rejected journals database
            rejected_data = {
                "journal_name": result.journal_name,
                "journal_url": result.journal_url,
                "issn_print": journal.issn_print,
                "issn_online": journal.issn_online,
                "publisher_name": journal.publisher_name,
                "publisher_url": journal.publisher_url,
                "submission_email": None,  # Will be populated if email-only
                "rejection_reason": result.summary,
                "rejection_triggers": [{"name": t.name, "passed": t.passed, "detail": t.detail}
                                       for t in result.rejection_triggers if not t.passed],
                "total_score": result.total_score,
                "max_score": result.max_score,
                "percentage": result.percentage,
                "blacklist_matches": [],
                "red_flags": verification_data.get("deep_search", {}).get("red_flags", []),
                "deep_search": verification_data.get("deep_search", {}),
                "is_human_review": verification_data.get("deep_search", {}).get("needs_human_review", False),
                "human_review_reason": verification_data.get("deep_search", {}).get("human_review_reason"),
                "raw_data": result.raw_data,
            }
            self.rejected_db.add_rejected(rejected_data)

            # Create human intervention if needed
            if rejected_data["is_human_review"]:
                self.intervention_queue.create_intervention(
                    journal_name=result.journal_name,
                    parameter_name="deep_web_search",
                    issue_description=f"Journal flagged for human review: {rejected_data['human_review_reason']}",
                    severity="high",
                    rejection_id=rejected_data.get("id"),
                    auto_verification_failure_reason="Multiple negative search results"
                )

        elif result.status in (VerdictStatus.ACCEPTED, VerdictStatus.CONDITIONAL):
            # Save to accepted journals database
            accepted_data = {
                "journal_name": result.journal_name,
                "journal_url": result.journal_url,
                "issn_print": journal.issn_print,
                "issn_online": journal.issn_online,
                "doi_prefix": journal.doi_prefix,
                "publisher_name": journal.publisher_name,
                "publisher_url": journal.publisher_url,
                "publisher_address": journal.publisher_address,
                "editorial_board_url": journal.editorial_board_url,
                "submission_portal_url": journal.submission_portal_url,
                "ethics_policy_url": journal.ethics_policy_url,
                "open_access": journal.open_access,
                "claimed_indexes": journal.claimed_indexes,
                "total_score": result.total_score,
                "max_score": result.max_score,
                "percentage": result.percentage,
                "threshold": result.threshold,
                "status": result.status.value,
                "orcid_verification_rate": verification_data.get("orcid_verification", {}).get("verification_rate"),
                "geographic_diversity_score": verification_data.get("geographic_diversity", {}).get("diversity_score"),
                "blacklist_clean": True,
                "notes": "; ".join(result.recommendations),
                "raw_data": result.raw_data,
            }
            self.accepted_db.add_accepted(accepted_data)

    def _collect_unverified_parameters(self, verification_data: Dict[str, Any]) -> List[str]:
        """Collect Appendix A sub-criterion parameters that failed verification or need human review."""
        unverified: List[str] = []

        # Use authoritative Appendix A checklist if present
        appendix_checks = verification_data.get("appendix_checks") or []
        for check in appendix_checks:
            if not check.get("passed"):
                key = check.get("key")
                if key:
                    unverified.append(key)

        return unverified

    def evaluate_and_report(self, journal: JournalInput, fmt: str = "text", save_accepted: bool = True) -> str:
        result = self.evaluate(journal, save_accepted=save_accepted)
        if fmt == "json":
            return self.reporter.generate_json_report(result)
        return self.reporter.generate_text_report(result)
