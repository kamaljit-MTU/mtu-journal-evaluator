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
    GeographicDiversityVerifier, DeepWebSearcher
)
from .rejected_journals_db import RejectedJournalDatabase
from .accepted_journals_db import AcceptedJournalDatabase
from .human_intervention import HumanInterventionQueue


class MTUJournalEvaluator:
    def __init__(self):
        self.reporter = ReportGenerator()
        self.rejected_db = RejectedJournalDatabase()
        self.accepted_db = AcceptedJournalDatabase()
        self.intervention_queue = HumanInterventionQueue()

    def evaluate(self, journal: JournalInput) -> EvaluationResult:
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

        # 2. Geographic Diversity Verification
        if journal.editorial_board_url:
            # Try to extract editor info from URL (simplified)
            geo_diversity = GeographicDiversityVerifier.verify([])
            verification_data["geographic_diversity"] = geo_diversity

        # 3. Deep Web Search
        web_search = DeepWebSearcher.search_journal_reputation(
            journal.name,
            journal.publisher_name
        )
        verification_data["deep_search"] = web_search

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

    def evaluate_and_report(self, journal: JournalInput, fmt: str = "text") -> str:
        result = self.evaluate(journal)
        if fmt == "json":
            return self.reporter.generate_json_report(result)
        return self.reporter.generate_text_report(result)
