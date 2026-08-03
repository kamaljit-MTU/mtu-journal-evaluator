"""
Report Generator - produces structured evaluation reports
"""
import json
from typing import List
from .models import EvaluationResult, RejectionTriggerResult, DomainScore


class ReportGenerator:
    def generate_text_report(self, result: EvaluationResult) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("MTU JOURNAL EVALUATION REPORT")
        lines.append("=" * 70)
        lines.append(f"Journal:        {result.journal_name}")
        lines.append(f"URL:            {result.journal_url}")
        lines.append(f"Evaluated:      {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Status
        status_icon = "✓" if result.status.value == "ACCEPTED" else "✗"
        if result.status.value == "CONDITIONAL":
            status_icon = "?"
        lines.append(f"STATUS:         {status_icon} {result.status.value}")
        lines.append(f"SCORE:          {result.total_score}/{result.max_score} ({result.percentage:.1f}%)")
        lines.append(f"THRESHOLD:      {result.threshold}/{result.max_score}")
        lines.append("")

        # Rejection Triggers
        lines.append("-" * 70)
        lines.append("AUTOMATIC REJECTION TRIGGER CHECK")
        lines.append("-" * 70)
        if not result.rejection_triggers:
            lines.append("  [SKIPPED — journal already rejected or not scored]")
        else:
            for trigger in result.rejection_triggers:
                icon = "PASS" if trigger.passed else "FAIL"
                lines.append(f"  [{icon}] {trigger.name}")
                lines.append(f"         Detail: {trigger.detail}")
        lines.append("")

        # Domain Scores
        if result.domain_scores:
            lines.append("-" * 70)
            lines.append("DOMAIN SCORES")
            lines.append("-" * 70)
            for domain in result.domain_scores:
                pct = (domain.earned_points / domain.max_points * 100) if domain.max_points > 0 else 0
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"\n  {domain.domain}")
                lines.append(f"  Score: {domain.earned_points}/{domain.max_points} [{bar}] {pct:.0f}%")
                for sc in domain.sub_criteria:
                    lines.append(f"    • {sc['criterion']}: {sc['earned']}/{sc['max']} — {sc['detail']}")
            lines.append("")

        # Summary
        lines.append("-" * 70)
        lines.append("SUMMARY")
        lines.append("-" * 70)
        lines.append(f"  {result.summary}")
        lines.append("")

        # Recommendations
        if result.recommendations:
            lines.append("-" * 70)
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 70)
            for rec in result.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def generate_json_report(self, result: EvaluationResult) -> str:
        def _trigger_to_dict(t):
            return {"name": t.name, "passed": t.passed, "detail": t.detail}

        def _domain_to_dict(d):
            return {
                "domain": d.domain,
                "max_points": d.max_points,
                "earned_points": d.earned_points,
                "percentage": round(d.earned_points / d.max_points * 100, 1) if d.max_points > 0 else 0,
                "sub_criteria": d.sub_criteria,
            }

        data = {
            "journal_name": result.journal_name,
            "journal_url": result.journal_url,
            "status": result.status.value,
            "total_score": result.total_score,
            "max_score": result.max_score,
            "percentage": round(result.percentage, 1),
            "threshold": result.threshold,
            "rejection_triggers": [_trigger_to_dict(t) for t in result.rejection_triggers],
            "domain_scores": [_domain_to_dict(d) for d in result.domain_scores],
            "summary": result.summary,
            "recommendations": result.recommendations,
            "raw_data": result.raw_data,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
