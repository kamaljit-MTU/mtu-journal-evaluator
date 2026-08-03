"""
Scheduled Re-evaluation Runner
Scans the database for journals due for re-evaluation and re-runs them.
"""
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database import EvaluationDatabase
from src.evaluator import MTUJournalEvaluator
from src.models import JournalInput, VerdictStatus


def run_due_re_evaluations(dry_run: bool = False):
    db = EvaluationDatabase()
    evaluator = MTUJournalEvaluator()
    conn = db._get_conn(db)
    c = conn.cursor()
    today = datetime.utcnow().isoformat()
    c.execute("""
        SELECT id, journal_name, journal_url, raw_data, re_evaluate_by
        FROM evaluations
        WHERE re_evaluate_by IS NOT NULL
          AND re_evaluate_by != ''
          AND re_evaluate_by <= ?
          AND status NOT IN ('REJECTED', 'WITHDRAWN')
    """, (today,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("No journals due for re-evaluation.")
        return

    print(f"Found {len(rows)} journal(s) due for re-evaluation.")
    updated = []
    for row in rows:
        eval_id, name, url, raw_data_json, re_evaluate_by = row
        try:
            raw_data = __import__('json').loads(raw_data_json) if raw_data_json else {}
        except Exception:
            raw_data = {}
        journal = JournalInput(
            name=name,
            url=url or "",
            issn_print=raw_data.get("issn_print"),
            issn_online=raw_data.get("issn_online"),
            doi_prefix=raw_data.get("doi_prefix"),
            publisher_name=raw_data.get("publisher"),
            publisher_url=raw_data.get("publisher_url"),
            publisher_address=raw_data.get("publisher_address"),
            editorial_board_url=raw_data.get("editorial_board_url"),
            submission_portal_url=raw_data.get("submission_portal_url"),
            ethics_policy_url=raw_data.get("ethics_policy_url"),
            open_access=raw_data.get("open_access", False),
            submission_email_only=raw_data.get("submission_email_only", False),
            claimed_indexes=raw_data.get("claimed_indexes", []),
            metric_claims=raw_data.get("metric_claims", []),
            rapid_publication_claim=raw_data.get("rapid_publication_claim", False),
            lock_pdfs=raw_data.get("lock_pdfs", False),
        )
        result = evaluator.evaluate(journal)
        report_json = evaluator.reporter.generate_json_report(result)
        result_dict = __import__('json').loads(report_json)

        if dry_run:
            print(f"  [{eval_id}] {name} -> {result.status.value} ({result.total_score}/{result.max_score})")
            updated.append((eval_id, result.status.value, result.total_score))
        else:
            conn2 = db._get_conn(db)
            c2 = conn2.cursor()
            c2.execute("""
                UPDATE evaluations
                SET status = ?, total_score = ?, max_score = ?, percentage = ?,
                    rejection_triggers = ?, domain_scores = ?, summary = ?,
                    recommendations = ?, evaluated_at = ?, evaluated_by = COALESCE(evaluated_by, 'scheduler')
                WHERE id = ?
            """, (
                result.status.value,
                result.total_score,
                result.max_score,
                result.percentage,
                __import__('json').dumps([{"name": t.name, "passed": t.passed, "detail": t.detail} for t in result.rejection_triggers]),
                __import__('json').dumps([{"domain": d.domain, "max_points": d.max_points, "earned_points": d.earned_points, "sub_criteria": d.sub_criteria} for d in result.domain_scores]),
                result.summary,
                __import__('json').dumps(result.recommendations),
                datetime.utcnow().isoformat(),
                eval_id,
            ))
            conn2.commit()
            conn2.close()
            print(f"  [{eval_id}] {name} -> {result.status.value} ({result.total_score}/{result.max_score})")
            updated.append((eval_id, result.status.value, result.total_score))

    return updated


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-evaluate journals whose re-evaluate_by date has passed")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be re-evaluated without changing DB")
    args = parser.parse_args()
    run_due_re_evaluations(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
