"""
MTU Journal Evaluator - Main Evaluator Orchestrator
"""
from typing import List, Optional
from .models import JournalInput, EvaluationResult, VerdictStatus
from .rejection_triggers import RejectionTriggerChecker
from .scoring_engine import ScoringEngine
from .reporting import ReportGenerator


class MTUJournalEvaluator:
    def __init__(self):
        self.scoring = ScoringEngine({})
        self.reporter = ReportGenerator()

    def evaluate(self, journal: JournalInput) -> EvaluationResult:
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
            engine = ScoringEngine(journal)
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

        return EvaluationResult(
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
            },
        )

    def evaluate_and_report(self, journal: JournalInput, fmt: str = "text") -> str:
        result = self.evaluate(journal)
        if fmt == "json":
            return self.reporter.generate_json_report(result)
        return self.reporter.generate_text_report(result)
