#!/usr/bin/env python3
"""
MTU Journal Evaluator - CLI
Usage:
  python -m mtu_journal_evaluator.cli journal_name --url URL [options]
  python -m mtu_journal_evaluator.cli --demo
  python -m mtu_journal_evaluator.cli --json input.json
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure the parent directory is on sys.path when run as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import JournalInput, VerdictStatus
from src.evaluator import MTUJournalEvaluator


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mtu-journal-evaluator",
        description="MTU Automated Journal Evaluation System"
    )
    p.add_argument("name", nargs="?", help="Journal name")
    p.add_argument("--url", help="Journal website URL")
    p.add_argument("--issn-print", dest="issn_print", help="Print ISSN")
    p.add_argument("--issn-online", dest="issn_online", help="Online ISSN")
    p.add_argument("--doi-prefix", dest="doi_prefix", help="DOI prefix")
    p.add_argument("--publisher", dest="publisher", help="Publisher name")
    p.add_argument("--publisher-url", dest="publisher_url", help="Publisher URL")
    p.add_argument("--publisher-address", dest="publisher_address", help="Publisher address")
    p.add_argument("--editorial-board-url", dest="editorial_board_url", help="Editorial board URL")
    p.add_argument("--submission-portal", dest="submission_portal", help="Submission portal URL")
    p.add_argument("--ethics-policy-url", dest="ethics_policy_url", help="Ethics policy URL")
    p.add_argument("--open-access", dest="open_access", action="store_true", help="Is open access")
    p.add_argument("--submission-email-only", dest="submission_email_only", action="store_true")
    p.add_argument("--claimed-index", dest="claimed_indexes", action="append", default=[])
    p.add_argument("--metric-claim", dest="metric_claims", action="append", default=[])
    p.add_argument("--rapid-claim", dest="rapid_publication_claim", action="store_true")
    p.add_argument("--lock-pdfs", dest="lock_pdfs", action="store_true")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--demo", action="store_true", help="Run demo with sample journals")
    p.add_argument("--json-file", dest="json_file", help="Load journal from JSON file")
    return p


def run_demo():
    evaluator = MTUJournalEvaluator()
    samples = [
        JournalInput(
            name="IEEE Transactions on Neural Networks and Learning Systems",
            url="https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",
            issn_print="2162-237X",
            issn_online="2162-2388",
            doi_prefix="10.1109",
            publisher_name="IEEE",
            publisher_url="https://www.ieee.org",
            publisher_address="445 Hoes Lane, Piscataway, NJ 08854, USA",
            editorial_board_url="https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",
            submission_portal_url="https://ieeexplore.ieee.org",
            ethics_policy_url="https://www.ieee.org/publications/rights/peer-review.html",
            open_access=False,
            claimed_indexes=["Scopus", "Web of Science", "IEEE Xplore"],
            metric_claims=["Impact Factor (Clarivate)", "CiteScore (Scopus)"],
        ),
        JournalInput(
            name="International Journal of Advanced Research in Science",
            url="http://www.ijars.in",
            issn_print="2320-1234",
            issn_online="",
            doi_prefix="",
            publisher_name="Advanced Research Publications",
            publisher_url="http://www.advancedresearchpub.in",
            publisher_address="",
            editorial_board_url="",
            submission_portal_url="",
            submission_email_only=True,
            ethics_policy_url="",
            open_access=False,
            claimed_indexes=["SJIF", "Cosmos"],
            metric_claims=["SJIF 2024: 7.8", "Cosmos Impact Factor"],
            rapid_publication_claim=True,
        ),
    ]
    for s in samples:
        print(f"\n{'='*70}")
        print(f"Evaluating: {s.name}")
        report = evaluator.evaluate_and_report(s, fmt="text")
        print(report)


def main():
    parser = build_parser()
    args = parser.parse_args()
    evaluator = MTUJournalEvaluator()

    if args.demo:
        run_demo()
        return

    if args.json_file:
        with open(args.json_file, "r") as f:
            data = json.load(f)
        journal = JournalInput(**data)
        report = evaluator.evaluate_and_report(journal, fmt=args.format)
        print(report)
        return

    if not args.name:
        parser.print_help()
        sys.exit(1)

    journal = JournalInput(
        name=args.name,
        url=args.url or "",
        issn_print=args.issn_print,
        issn_online=args.issn_online,
        doi_prefix=args.doi_prefix,
        publisher_name=args.publisher,
        publisher_url=args.publisher_url,
        publisher_address=args.publisher_address,
        editorial_board_url=args.editorial_board_url,
        submission_portal=args.submission_portal,
        ethics_policy_url=args.ethics_policy_url,
        open_access=args.open_access,
        submission_email_only=args.submission_email_only,
        claimed_indexes=args.claimed_indexes,
        metric_claims=args.metric_claims,
        rapid_publication_claim=args.rapid_publication_claim,
        lock_pdfs=args.lock_pdfs,
    )
    report = evaluator.evaluate_and_report(journal, fmt=args.format)
    print(report)


if __name__ == "__main__":
    main()
