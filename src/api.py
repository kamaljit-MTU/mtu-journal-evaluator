"""
FastAPI web interface for MTU Journal Evaluator.
"""
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
import json

from src.models import JournalInput
from src.evaluator import MTUJournalEvaluator
from src.crawler import JournalCrawler
from src.blacklist import BlacklistChecker
from src.verifiers import ISSNVerifier, DOIVerifier, PublisherVerifier, EditorialBoardVerifier
from src.database import EvaluationDatabase

app = FastAPI(title="MTU Journal Evaluator")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
db = EvaluationDatabase()
evaluator = MTUJournalEvaluator()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/evaluate")
async def evaluate_journal(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    issn_print: Optional[str] = Form(None),
    issn_online: Optional[str] = Form(None),
    doi_prefix: Optional[str] = Form(None),
    publisher_name: Optional[str] = Form(None),
    publisher_url: Optional[str] = Form(None),
    publisher_address: Optional[str] = Form(None),
    editorial_board_url: Optional[str] = Form(None),
    submission_portal_url: Optional[str] = Form(None),
    ethics_policy_url: Optional[str] = Form(None),
    open_access: bool = Form(False),
    submission_email_only: bool = Form(False),
    claimed_indexes: Optional[str] = Form(None),
    metric_claims: Optional[str] = Form(None),
    rapid_publication_claim: bool = Form(False),
    lock_pdfs: bool = Form(False),
    crawl: bool = Form(False),
):
    journal = JournalInput(
        name=name,
        url=url,
        issn_print=issn_print,
        issn_online=issn_online,
        doi_prefix=doi_prefix,
        publisher_name=publisher_name,
        publisher_url=publisher_url,
        publisher_address=publisher_address,
        editorial_board_url=editorial_board_url,
        submission_portal_url=submission_portal_url,
        ethics_policy_url=ethics_policy_url,
        open_access=open_access,
        submission_email_only=submission_email_only,
        claimed_indexes=[x.strip() for x in (claimed_indexes or "").split(",") if x.strip()],
        metric_claims=[x.strip() for x in (metric_claims or "").split(",") if x.strip()],
        rapid_publication_claim=rapid_publication_claim,
        lock_pdfs=lock_pdfs,
    )

    crawl_data = {}
    if crawl:
        crawler = JournalCrawler(url)
        crawl_data = crawler.analyze()
        # Auto-fill from crawl if missing
        if crawl_data.get("issns_found"):
            if not journal.issn_print:
                journal.issn_print = crawl_data["issns_found"][0]
        checks = crawl_data.get("checks", {})
        if checks.get("email_only_submission"):
            journal.submission_email_only = True
        if checks.get("predatory_metrics_present"):
            journal.metric_claims.extend(
                [k for k, v in checks["predatory_metrics_present"].items() if v]
            )

    report_text = evaluator.evaluate_and_report(journal, fmt="text")
    report_json = evaluator.evaluate_and_report(journal, fmt="json")
    result = json.loads(report_json)

    # Run verifiers
    verifier_results = {
        "issn": ISSNVerifier.verify(journal.issn_print) if journal.issn_print else None,
        "doi": DOIVerifier.verify(journal.doi_prefix) if journal.doi_prefix else None,
        "publisher": PublisherVerifier.verify(
            journal.publisher_name, journal.publisher_url, journal.publisher_address
        ),
        "editorial_board": EditorialBoardVerifier.verify(journal.editorial_board_url),
    }
    blacklist = BlacklistChecker.check(journal.name, journal.claimed_indexes, journal.metric_claims)

    # Save to database
    eval_id = db.save_evaluation(result, evaluated_by="web_form")

    return templates.TemplateResponse("report.html", {
        "request": request,
        "result": result,
        "report_text": report_text,
        "verifier_results": verifier_results,
        "blacklist": blacklist,
        "crawl_data": crawl_data,
        "eval_id": eval_id,
    })


@app.get("/evaluations")
async def list_evaluations(status: Optional[str] = None):
    items = db.list_evaluations(status=status)
    return JSONResponse(items)


@app.get("/evaluations/{eval_id}")
async def get_evaluation(eval_id: int):
    item = db.get_evaluation(eval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(item)


@app.post("/evaluations/{eval_id}/appeal")
async def appeal(eval_id: int, status: str = Form(...), notes: str = Form(...)):
    db.update_appeal(eval_id, status, notes)
    return {"success": True, "eval_id": eval_id, "appeal_status": status}
