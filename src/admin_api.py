"""
MTU Journal Evaluator - Admin Dashboard API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from src.models import JournalInput, VerdictStatus
from src.evaluator import MTUJournalEvaluator
from src.database import EvaluationDatabase
from src.auth import require_admin, get_current_user
from src.blacklist import BlacklistChecker
from src.blacklist_feeds import BlacklistAggregator
from src.human_intervention import HumanInterventionQueue

admin_router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
db = EvaluationDatabase()
evaluator = MTUJournalEvaluator()
aggregator = BlacklistAggregator()
intervention_queue = HumanInterventionQueue()


@admin_router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: Optional[dict] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    status_filter = request.query_params.get("status")
    evaluations = db.list_evaluations(limit=200, status=status_filter)

    stats = {
        "total": len(evaluations),
        "accepted": sum(1 for e in evaluations if e.get("status") == "ACCEPTED"),
        "rejected": sum(1 for e in evaluations if e.get("status") == "REJECTED"),
        "conditional": sum(1 for e in evaluations if e.get("status") == "CONDITIONAL"),
        "pending_appeal": sum(1 for e in evaluations if e.get("appeal_status") == "pending"),
    }

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "evaluations": evaluations,
        "stats": stats,
        "filter": status_filter or "all",
    })


@admin_router.get("/admin/evaluations/{eval_id}", response_class=HTMLResponse)
async def admin_view_evaluation(request: Request, eval_id: int, user: Optional[dict] = Depends(get_current_user)):
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    item = db.get_evaluation(eval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return templates.TemplateResponse("admin/evaluation_detail.html", {
        "request": request,
        "user": user,
        "item": item,
    })


@admin_router.post("/admin/evaluations/{eval_id}/override")
async def admin_override(
    eval_id: int,
    new_status: str = Form(...),
    notes: str = Form(""),
    user: Optional[dict] = Depends(require_admin),
):
    item = db.get_evaluation(eval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    if new_status not in ("ACCEPTED", "REJECTED", "CONDITIONAL"):
        raise HTTPException(status_code=400, detail="Invalid status")

    db.update_status(eval_id, new_status, notes)
    return RedirectResponse(url=f"/admin/evaluations/{eval_id}", status_code=303)


@admin_router.post("/admin/evaluations/{eval_id}/schedule")
async def admin_schedule(
    eval_id: int,
    re_evaluate_by: str = Form(...),
    user: Optional[dict] = Depends(require_admin),
):
    db.schedule_re_evaluation(eval_id, re_evaluate_by)
    return RedirectResponse(url=f"/admin/evaluations/{eval_id}", status_code=303)


@admin_router.get("/admin/blacklists")
async def admin_blacklists(user: Optional[dict] = Depends(require_admin)):
    feeds = aggregator.update_all()
    summary = {}
    for name, entries in feeds.items():
        summary[name] = {
            "count": len(entries),
            "sample": list(entries)[:10],
        }
    return {"feeds": summary}


@admin_router.get("/admin/interventions", response_class=HTMLResponse)
async def admin_interventions(request: Request, user: Optional[dict] = Depends(get_current_user)):
    try:
        if not user:
            next_url = str(request.url).replace(str(request.base_url), "/")
            if next_url.startswith("//"):
                next_url = "/admin/interventions"
            return RedirectResponse(url=f"/admin/login?next={next_url}", status_code=303)
        if user.get("role") != "admin":
            return RedirectResponse(url="/", status_code=303)

        status_filter = request.query_params.get("status", "pending")
        if status_filter == "pending":
            interventions = intervention_queue.get_pending_interventions(limit=100)
        elif status_filter == "all":
            interventions = intervention_queue.get_pending_interventions(limit=500)
        else:
            interventions = intervention_queue.get_pending_interventions(limit=100)

        print(f"[ADMIN] Rendering interventions page with {len(interventions)} items, filter={status_filter}, user={user.get('username')}")
        return templates.TemplateResponse("admin/interventions.html", {
            "request": request,
            "user": user,
            "interventions": interventions,
            "filter": status_filter,
        })
    except Exception as e:
        print(f"[ADMIN] Error in interventions page: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(f"<h1>Error loading interventions</h1><pre>{e}</pre>", status_code=500)


@admin_router.post("/admin/interventions/{intervention_id}/assign")
async def assign_intervention(
    intervention_id: int,
    committee_email: str = Form(...),
    assigned_to: str = Form(...),
    user: Optional[dict] = Depends(require_admin),
):
    intervention_queue.assign_to_committee(intervention_id, committee_email, assigned_to)
    return RedirectResponse(url="/admin/interventions", status_code=303)


@admin_router.post("/admin/interventions/{intervention_id}/resolve")
async def resolve_intervention(
    intervention_id: int,
    resolution: str = Form(...),
    resolution_value: str = Form(""),
    user: Optional[dict] = Depends(require_admin),
):
    intervention_queue.resolve_intervention(intervention_id, resolution, resolution_value, user.get("username", "admin"))
    return RedirectResponse(url="/admin/interventions", status_code=303)


@admin_router.post("/admin/interventions/{intervention_id}/escalate")
async def escalate_intervention(
    intervention_id: int,
    user: Optional[dict] = Depends(require_admin),
):
    intervention_queue.escalate_intervention(intervention_id)
    return RedirectResponse(url="/admin/interventions", status_code=303)


@admin_router.get("/admin/rejected", response_class=HTMLResponse)
async def admin_rejected(request: Request, user: Optional[dict] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    evaluations = db.list_evaluations(limit=200, status="REJECTED")
    return templates.TemplateResponse("admin/rejected.html", {
        "request": request,
        "user": user,
        "evaluations": evaluations,
    })


@admin_router.get("/admin/accepted", response_class=HTMLResponse)
async def admin_accepted(request: Request, user: Optional[dict] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    evaluations = db.list_evaluations(limit=200, status="ACCEPTED")
    return templates.TemplateResponse("admin/accepted.html", {
        "request": request,
        "user": user,
        "evaluations": evaluations,
    })


# Monkey-patch EvaluationDatabase with _get_conn helper for admin override
from src.database import EvaluationDatabase as _EvaluationDatabase

def _get_conn(self):
    return self._SessionLocal()

EvaluationDatabase._get_conn = _get_conn
