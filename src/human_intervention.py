"""
Human Intervention Queue Module
For parameters that cannot be automatically determined or verified.

Uses the shared SQLAlchemy Base/engine from src.database to avoid duplicate
PostgreSQL type creation on startup.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from src.database import EvaluationDatabase, HumanIntervention


class HumanInterventionQueue(EvaluationDatabase):
    def __init__(self):
        super().__init__()

    def create_intervention(self, journal_name: str, parameter_name: str,
                           issue_description: str, severity: str = "medium",
                           evaluation_id: Optional[int] = None,
                           rejection_id: Optional[int] = None,
                           acceptance_id: Optional[int] = None,
                           auto_verification_failure_reason: Optional[str] = None,
                           committee_member_email: Optional[str] = None,
                           parameter_value: Optional[str] = None,
                           email_recipient: Optional[str] = None) -> int:
        session = self.get_session()
        try:
            intervention = HumanIntervention(
                journal_name=journal_name,
                evaluation_id=evaluation_id,
                rejection_id=rejection_id,
                acceptance_id=acceptance_id,
                parameter_name=parameter_name,
                parameter_value=parameter_value,
                issue_description=issue_description,
                severity=severity,
                auto_verification_attempted=True,
                auto_verification_failure_reason=auto_verification_failure_reason,
                status="pending",
                committee_member_email=committee_member_email,
                email_recipient=email_recipient,
            )
            session.add(intervention)
            session.commit()
            return intervention.id
        finally:
            session.close()

    def assign_to_committee(self, intervention_id: int, committee_member_email: str,
                           assigned_to: str):
        session = self.get_session()
        try:
            intervention = session.query(HumanIntervention).filter(
                HumanIntervention.id == intervention_id
            ).first()
            if intervention:
                intervention.assigned_to = assigned_to
                intervention.committee_member_email = committee_member_email
                intervention.status = "in_progress"
                session.commit()
        finally:
            session.close()

    def resolve_intervention(self, intervention_id: int, resolution: str,
                           resolution_value: str, resolved_by: str):
        session = self.get_session()
        try:
            intervention = session.query(HumanIntervention).filter(
                HumanIntervention.id == intervention_id
            ).first()
            if intervention:
                intervention.resolution = resolution
                intervention.resolution_value = resolution_value
                intervention.resolved_by = resolved_by
                intervention.resolved_at = datetime.utcnow()
                intervention.status = "resolved"
                session.commit()
        finally:
            session.close()

    def mark_email_sent(self, intervention_id: int, email_recipient: str):
        session = self.get_session()
        try:
            intervention = session.query(HumanIntervention).filter(
                HumanIntervention.id == intervention_id
            ).first()
            if intervention:
                intervention.email_sent = True
                intervention.email_sent_at = datetime.utcnow()
                intervention.email_recipient = email_recipient
                session.commit()
        finally:
            session.close()

    def get_pending_interventions(self, limit: int = 50) -> List[Dict]:
        session = self.get_session()
        try:
            entries = session.query(HumanIntervention).filter(
                HumanIntervention.status == "pending"
            ).order_by(HumanIntervention.created_at.desc()).limit(limit).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def get_interventions_by_journal(self, journal_name: str) -> List[Dict]:
        session = self.get_session()
        try:
            entries = session.query(HumanIntervention).filter(
                HumanIntervention.journal_name == journal_name
            ).order_by(HumanIntervention.created_at.desc()).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def escalate_intervention(self, intervention_id: int):
        session = self.get_session()
        try:
            intervention = session.query(HumanIntervention).filter(
                HumanIntervention.id == intervention_id
            ).first()
            if intervention:
                intervention.status = "escalated"
                intervention.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        return {
            "id": entry.id,
            "journal_name": entry.journal_name,
            "evaluation_id": entry.evaluation_id,
            "rejection_id": entry.rejection_id,
            "acceptance_id": entry.acceptance_id,
            "parameter_name": entry.parameter_name,
            "parameter_value": entry.parameter_value,
            "issue_description": entry.issue_description,
            "severity": entry.severity,
            "auto_verification_attempted": entry.auto_verification_attempted,
            "auto_verification_failure_reason": entry.auto_verification_failure_reason,
            "assigned_to": entry.assigned_to,
            "committee_member_email": entry.committee_member_email,
            "status": entry.status,
            "resolution": entry.resolution,
            "resolution_value": entry.resolution_value,
            "resolved_by": entry.resolved_by,
            "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
            "email_sent": entry.email_sent,
            "email_sent_at": entry.email_sent_at.isoformat() if entry.email_sent_at else None,
            "email_recipient": entry.email_recipient,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }
