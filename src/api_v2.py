"""
FastAPI web interface for MTU Journal Evaluator - v2 with auth and admin routes.
"""
from fastapi import FastAPI, Request, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional
import json
import io

from src.config import settings
from src.models import JournalInput
from src.evaluator import MTUJournalEvaluator
from src.blacklist import BlacklistChecker
from src.blacklist_feeds import BlacklistAggregator
from src.verifiers import ISSNVerifier, DOIVerifier, PublisherVerifier, EditorialBoardVerifier
from src.database import EvaluationDatabase
from src.auth import get_current_user, require_admin, authenticate_user, create_access_token
from src.admin_api import admin_router
from src.batch_import import BatchImporter
from src.human_intervention import HumanInterventionQueue
from src.accepted_journals_db import AcceptedJournalDatabase
from src.rejected_journals_db import RejectedJournalDatabase
from src.email_notifier import EmailNotifier

app = FastAPI(title="MTU Journal Evaluator")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
db = EvaluationDatabase()
evaluator = MTUJournalEvaluator()
aggregator = BlacklistAggregator()
intervention_queue = HumanInterventionQueue()
accepted_db = AcceptedJournalDatabase()
rejected_db = RejectedJournalDatabase()

app.include_router(admin_router)
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Optional[dict] = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


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
    save_accepted: bool = Form(True),
    user: Optional[dict] = Depends(get_current_user),
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

    result = evaluator.evaluate(journal, save_accepted=save_accepted)
    report_text = evaluator.reporter.generate_text_report(result)
    report_json = evaluator.reporter.generate_json_report(result)
    result_dict = json.loads(report_json)

    verifier_results = {
        "issn": ISSNVerifier.verify(journal.issn_print) if journal.issn_print else None,
        "doi": DOIVerifier.verify(journal.doi_prefix) if journal.doi_prefix else None,
        "publisher": PublisherVerifier.verify(
            journal.publisher_name, journal.publisher_url, journal.publisher_address
        ),
        "editorial_board": EditorialBoardVerifier.verify(journal.editorial_board_url),
    }
    blacklist = BlacklistChecker.check(journal.name, journal.claimed_indexes, journal.metric_claims)

    # Also check live blacklist feeds
    live_blacklists = aggregator.is_blacklisted(journal.name)
    if live_blacklists["blacklisted"]:
        blacklist["blacklisted"] = True
        blacklist["issues"].extend(
            [f"Found in blacklist feed: {m}" for m in live_blacklists["matches"]]
        )

    eval_id = db.save_evaluation(result_dict, evaluated_by="web_form")
    return templates.TemplateResponse("report.html", {
        "request": request,
        "result": result,
        "report_text": report_text,
        "verifier_results": verifier_results,
        "blacklist": blacklist,
        "crawl_data": {},
        "eval_id": eval_id,
        "user": user,
    })


@app.get("/evaluations")
async def list_evaluations(status: Optional[str] = None, user: Optional[dict] = Depends(get_current_user)):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    items = db.list_evaluations(status=status)
    return JSONResponse(items)


@app.get("/evaluations/{eval_id}")
async def get_evaluation(eval_id: int, user: Optional[dict] = Depends(get_current_user)):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    item = db.get_evaluation(eval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(item)


@app.post("/evaluations/{eval_id}/appeal")
async def appeal(eval_id: int, status: str = Form(...), notes: str = Form(...), user: Optional[dict] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.update_appeal(eval_id, status, notes)
    return {"success": True, "eval_id": eval_id, "appeal_status": status}


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, max_age=480*60)
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("access_token")
    return resp


@app.get("/accepted", response_class=HTMLResponse)
async def public_accepted(request: Request):
    items = accepted_db.list_accepted(limit=200)
    return templates.TemplateResponse("admin/accepted.html", {"request": request, "items": items, "user": None})


@app.get("/rejected", response_class=HTMLResponse)
async def public_rejected(request: Request):
    items = rejected_db.list_rejected(limit=200)
    return templates.TemplateResponse("admin/rejected.html", {"request": request, "items": items, "user": None})


@app.post("/batch")
async def batch_import(
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(require_admin),
):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    filename = file.filename or ""
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        rows = BatchImporter.parse_excel(io.BytesIO(content))
    else:
        rows = BatchImporter.parse_csv(text)
    results = BatchImporter.batch_evaluate(rows, save=True)
    accepted = sum(1 for r in results if r.get("status") == "ACCEPTED")
    rejected = sum(1 for r in results if r.get("status") == "REJECTED")
    conditional = sum(1 for r in results if r.get("status") == "CONDITIONAL")
    errors = sum(1 for r in results if r.get("status") == "ERROR")
    return templates.TemplateResponse("batch_report.html", {
        "request": request,
        "results": results,
        "stats": {"total": len(results), "accepted": accepted, "rejected": rejected, "conditional": conditional, "errors": errors},
    })


@app.post("/admin/interventions/{eval_id}/request")
async def request_manual_review(
    eval_id: int,
    journal_name: str = Form(...),
    parameter_name: str = Form(...),
    issue_description: str = Form(...),
    severity: str = Form("medium"),
    reviewer_email: str = Form(...),
    user: Optional[dict] = Depends(get_current_user),
):
    intervention_queue.create_intervention(
        journal_name=journal_name,
        parameter_name=parameter_name,
        issue_description=issue_description,
        severity=severity,
        evaluation_id=eval_id,
        committee_member_email=reviewer_email,
        auto_verification_failure_reason="Manual review requested from report page"
    )
    return RedirectResponse(url="/admin/interventions", status_code=303)


@app.post("/interventions/request")
async def public_request_manual_review(
    eval_id: int = Form(...),
    journal_name: str = Form(...),
    parameter_name: str = Form(...),
    issue_description: str = Form(...),
    severity: str = Form("medium"),
    reviewer_email: str = Form(...),
):
    intervention_queue.create_intervention(
        journal_name=journal_name,
        parameter_name=parameter_name,
        issue_description=issue_description,
        severity=severity,
        evaluation_id=eval_id,
        committee_member_email=reviewer_email,
        auto_verification_failure_reason="Public manual review request"
    )
    EmailNotifier.send_intervention_notification(
        to_email=reviewer_email or settings.COMMITTEE_EMAIL,
        journal_name=journal_name,
        parameter_name=parameter_name,
        parameter_value="",
        eval_id=eval_id,
        issue_description=issue_description
    )
    return RedirectResponse(url="/?review=submitted", status_code=303)


@app.post("/interventions/submit-unverified")
async def submit_unverified_parameter(
    eval_id: int = Form(...),
    journal_name: str = Form(...),
    parameter_name: str = Form(...),
    parameter_value: str = Form(...),
    reviewer_email: str = Form(...),
    issue_description: Optional[str] = Form(None),
):
    description = issue_description or f"User provided value for unverified parameter: {parameter_name}"
    committee_email = reviewer_email or settings.COMMITTEE_EMAIL
    intervention_queue.create_intervention(
        journal_name=journal_name,
        parameter_name=parameter_name,
        issue_description=description,
        severity="medium",
        evaluation_id=eval_id,
        committee_member_email=reviewer_email,
        parameter_value=parameter_value,
        auto_verification_failure_reason="User-supplied unverified parameter value",
        email_recipient=committee_email,
    )
    EmailNotifier.send_intervention_notification(
        to_email=committee_email,
        journal_name=journal_name,
        parameter_name=parameter_name,
        parameter_value=parameter_value,
        eval_id=eval_id,
        issue_description=description
    )
    return RedirectResponse(url=f"/?review=submitted&parameter={parameter_name}", status_code=303)
