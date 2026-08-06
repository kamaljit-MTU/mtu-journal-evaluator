"""
FastAPI web interface for MTU Journal Evaluator - v2 with auth and admin routes.
"""
from fastapi import FastAPI, Request, Form, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Dict, Any
import json
import io
import os
import secrets
import datetime
import logging
from types import SimpleNamespace

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
from src.telegram_notifier import TelegramNotifier

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

_jobs: Dict[str, Dict[str, Any]] = {}


def _estimate_search_time(journal: JournalInput) -> str:
    base = 10
    extra = 0
    urls = [journal.url, journal.editorial_board_url, journal.aims_scope_url, journal.submission_portal_url, journal.ethics_policy_url]
    extra += sum(10 for u in urls if u)
    if journal.issn_print or journal.issn_online:
        extra += 10
    if journal.claimed_indexes:
        extra += min(20, len(journal.claimed_indexes) * 3)
    total = min(90, max(20, base + extra))
    return f"{total}–{total + 20} seconds"


def _run_evaluation_job(job_id: str, journal: JournalInput, save_accepted: bool):
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.datetime.now().isoformat()
    try:
        result = evaluator.evaluate(journal, save_accepted=save_accepted)
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["raw_result"] = result
        _jobs[job_id]["report_text"] = evaluator.reporter.generate_text_report(result)
        _jobs[job_id]["eval_id"] = db.save_evaluation(
            json.loads(evaluator.reporter.generate_json_report(result)),
            evaluated_by="web_form",
        )
        _jobs[job_id]["result"] = {
            "status": result.status.value,
            "total_score": result.total_score,
            "max_score": result.max_score,
            "percentage": result.percentage,
            "threshold": result.threshold,
            "summary": result.summary,
            "journal_name": result.journal_name,
            "journal_url": result.journal_url,
            "rejection_triggers": [
                {
                    "name": t.name,
                    "passed": t.passed,
                    "detail": t.detail,
                }
                for t in result.rejection_triggers
            ],
        }
    except Exception as e:
        logging.getLogger(__name__).exception("evaluation job failed: %s", job_id)
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
    finally:
        _jobs[job_id]["finished_at"] = datetime.datetime.now().isoformat()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Optional[dict] = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.post("/evaluate")
async def evaluate_journal(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    url: str = Form(...),
    issn_print: Optional[str] = Form(None),
    issn_online: Optional[str] = Form(None),
    doi_prefix: Optional[str] = Form(None),
    publisher_name: Optional[str] = Form(None),
    publisher_url: Optional[str] = Form(None),
    publisher_address: Optional[str] = Form(None),
    editorial_board_url: Optional[str] = Form(None),
    aims_scope_url: Optional[str] = Form(None),
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
        aims_scope_url=aims_scope_url,
        submission_portal_url=submission_portal_url,
        ethics_policy_url=ethics_policy_url,
        open_access=open_access,
        submission_email_only=submission_email_only,
        claimed_indexes=[x.strip() for x in (claimed_indexes or "").split(",") if x.strip()],
        metric_claims=[x.strip() for x in (metric_claims or "").split(",") if x.strip()],
        rapid_publication_claim=rapid_publication_claim,
        lock_pdfs=lock_pdfs,
    )
    estimated = _estimate_search_time(journal)
    job_id = secrets.token_hex(16)
    _jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "created_at": datetime.datetime.now().isoformat(),
        "journal_name": journal.name,
    }
    background_tasks.add_task(_run_evaluation_job, job_id, journal, save_accepted)
    return templates.TemplateResponse("progress.html", {
        "request": request,
        "user": user,
        "job_id": job_id,
        "estimated": estimated,
        "journal_name": journal.name,
    })


@app.get("/evaluation-status/{job_id}")
async def evaluation_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown evaluation job")
    return JSONResponse({
        "status": job.get("status"),
        "estimated": job.get("estimated"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": job.get("result"),
    })


@app.get("/evaluation-result/{job_id}")
async def evaluation_result_page(request: Request, job_id: str, user: Optional[dict] = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown evaluation job")
    if job.get("status") != "done":
        return RedirectResponse(url=f"/?status=pending&job={job_id}", status_code=303)
    raw = job.get("raw_result")
    report_text = job.get("report_text") or ""
    eval_id = job.get("eval_id") or 0
    if raw is None:
        raise HTTPException(status_code=500, detail="Evaluation result missing")
    result = SimpleNamespace(
        status=SimpleNamespace(value=raw.status.value),
        total_score=raw.total_score,
        max_score=raw.max_score,
        percentage=raw.percentage,
        threshold=raw.threshold,
        summary=raw.summary,
        journal_name=raw.journal_name,
        journal_url=raw.journal_url,
        rejection_triggers=raw.rejection_triggers,
        unverified_parameters=getattr(raw, "unverified_parameters", []),
        raw_data=getattr(raw, "raw_data", {}),
    )
    return templates.TemplateResponse("report.html", {
        "request": request,
        "result": result,
        "report_text": report_text,
        "verifier_results": {},
        "blacklist": {},
        "crawl_data": {},
        "eval_id": eval_id,
        "user": user,
        "evaluated_at": job.get("finished_at", ""),
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
async def admin_login_form(request: Request, error: str = "", next: str = "/admin/interventions"):
    return templates.TemplateResponse("login.html", {"request": request, "error": error, "next": next})


@app.post("/login", response_class=HTMLResponse)
async def admin_login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/admin/interventions")):
    try:
        print(f"[LOGIN] Attempting login for user={username}, next={next}")
        user = authenticate_user(username, password)
        print(f"[LOGIN] authenticate_user returned: {user is not None}")
        if not user:
            print("[LOGIN] Authentication failed - invalid credentials")
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "next": next})
        print(f"[LOGIN] Authentication successful for user={user.get('username')}")
        token = create_access_token({"sub": user["username"], "role": user["role"]})
        print(f"[LOGIN] Token created successfully")
        redirect_target = "/admin/interventions"
        if next and next != "/":
            redirect_target = next
        print(f"[LOGIN] Redirecting to {redirect_target}")
        resp = RedirectResponse(url=redirect_target, status_code=303)
        resp.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, max_age=480*60)
        print(f"[LOGIN] Response created with cookie and redirect")
        return resp
    except Exception as e:
        print(f"[LOGIN] Exception during login: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("login.html", {"request": request, "error": f"Login error: {str(e)}", "next": next})


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
    request: Request,
    eval_id: int = Form(...),
    journal_name: str = Form(...),
    parameter_name: str = Form(...),
    issue_description: str = Form(...),
    severity: str = Form("medium"),
    reviewer_email: str = Form(...),
):
    print(f"[INTERVENTION] Received manual review request for journal={journal_name}, param={parameter_name}, email={reviewer_email}")
    intervention_queue.create_intervention(
        journal_name=journal_name,
        parameter_name=parameter_name,
        issue_description=issue_description,
        severity=severity,
        evaluation_id=eval_id,
        committee_member_email=reviewer_email,
        auto_verification_failure_reason="Public manual review request"
    )
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or reviewer_email or settings.COMMITTEE_EMAIL
    print(f"[INTERVENTION] Using chat_id={chat_id} for notification")
    try:
        sent = TelegramNotifier.send_intervention_notification(
            chat_id=chat_id,
            journal_name=journal_name,
            parameter_name=parameter_name,
            parameter_value="",
            eval_id=eval_id,
            issue_description=issue_description
        )
        print(f"[INTERVENTION] Notification result: {sent}")
    except Exception as e:
        print(f"[INTERVENTION] Notification raised: {e}")
    return RedirectResponse(url="/?review=submitted", status_code=303)


@app.post("/interventions/submit-unverified")
async def submit_unverified_parameter(
    request: Request,
    eval_id: int = Form(...),
    journal_name: str = Form(...),
    parameter_name: str = Form(...),
    parameter_value: str = Form(...),
    reviewer_email: str = Form(...),
    issue_description: Optional[str] = Form(None),
):
    print(f"[INTERVENTION] Received unverified parameter submission for journal={journal_name}, param={parameter_name}, value={parameter_value}, email={reviewer_email}")
    description = issue_description or f"User provided value for unverified parameter: {parameter_name}"
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or reviewer_email or settings.COMMITTEE_EMAIL
    print(f"[INTERVENTION] Using chat_id={chat_id} for notification")
    intervention_queue.create_intervention(
        journal_name=journal_name,
        parameter_name=parameter_name,
        issue_description=description,
        severity="medium",
        evaluation_id=eval_id,
        committee_member_email=reviewer_email,
        parameter_value=parameter_value,
        auto_verification_failure_reason="User-supplied unverified parameter value",
        email_recipient=chat_id,
    )
    try:
        sent = TelegramNotifier.send_intervention_notification(
            chat_id=chat_id,
            journal_name=journal_name,
            parameter_name=parameter_name,
            parameter_value=parameter_value,
            eval_id=eval_id,
            issue_description=description
        )
        print(f"[INTERVENTION] Notification result: {sent}")
    except Exception as e:
        print(f"[INTERVENTION] Notification raised: {e}")
    return RedirectResponse(url=f"/?review=submitted&parameter={parameter_name}", status_code=303)
