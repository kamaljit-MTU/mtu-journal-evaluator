#!/usr/bin/env python3
"""
MTU Journal Evaluator runner - supports CLI, demo, web server, batch, and re-evaluation modes.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.demo_data import SAMPLE_JOURNALS
from src.models import JournalInput
from src.evaluator import MTUJournalEvaluator
from src.database import EvaluationDatabase
from src.crawler import JournalCrawler
from src.batch_import import BatchImporter
from src.re_evaluate import run_due_re_evaluations


def run_demo():
    evaluator = MTUJournalEvaluator()
    for s in SAMPLE_JOURNALS:
        print(f"\n{'='*70}")
        print(f"Evaluating: {s.name}")
        report = evaluator.evaluate_and_report(s, fmt="text")
        print(report)


def run_web():
    import uvicorn
    uvicorn.run(
        "src.api_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


def run_crawl(url: str):
    crawler = JournalCrawler(url)
    data = crawler.analyze()
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))


def run_batch(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    content = path.read_bytes()
    if path.suffix in (".xlsx", ".xls"):
        rows = BatchImporter.parse_excel(str(path))
    else:
        text = content.decode("utf-8", errors="ignore")
        rows = BatchImporter.parse_csv(text)
    print(f"Loaded {len(rows)} rows from {file_path}")
    results = BatchImporter.batch_evaluate(rows, save=True)
    accepted = sum(1 for r in results if r.get("status") == "ACCEPTED")
    rejected = sum(1 for r in results if r.get("status") == "REJECTED")
    conditional = sum(1 for r in results if r.get("status") == "CONDITIONAL")
    errors = sum(1 for r in results if r.get("status") == "ERROR")
    print(f"Results: {accepted} accepted, {rejected} rejected, {conditional} conditional, {errors} errors")


def run_re_evaluate(dry_run: bool = False):
    run_due_re_evaluations(dry_run=dry_run)


def build_parser():
    p = argparse.ArgumentParser(prog="mtu-journal-evaluator")
    p.add_argument("--demo", action="store_true", help="Run demo with sample journals")
    p.add_argument("--web", action="store_true", help="Launch web interface on http://0.0.0.0:8000")
    p.add_argument("--crawl", metavar="URL", help="Crawl a journal website and show extracted data")
    p.add_argument("--batch", metavar="FILE", help="Batch import CSV/Excel file for evaluation")
    p.add_argument("--re-evaluate", action="store_true", help="Run due re-evaluations from database")
    p.add_argument("--dry-run", action="store_true", help="Dry run for re-evaluation (no DB writes)")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.web:
        run_web()
        return

    if args.crawl:
        run_crawl(args.crawl)
        return

    if args.batch:
        run_batch(args.batch)
        return

    if args.re_evaluate:
        run_re_evaluate(dry_run=args.dry_run)
        return

    if args.demo:
        run_demo()
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
