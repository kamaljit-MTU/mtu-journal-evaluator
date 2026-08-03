"""
Human Intervention Queue Module
For parameters that cannot be automatically determined or verified.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings

InterventionBase = declarative_base()


class HumanIntervention(InterventionBase):
    __tablename__ = "human_interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Journal context
    journal_name = Column(String(500), nullable=False)
    evaluation_id = Column(Integer)  # Link to main evaluation if exists
    rejection_id = Column(Integer)   # Link to rejected journal if exists
    acceptance_id = Column(Integer)  # Link to accepted journal if exists

    # Intervention details
    parameter_name = Column(String(100), nullable=False)
    parameter_value = Column(Text)
    issue_description = Column(Text, nullable=False)
    severity = Column(String(50), default="medium")  # low, medium, high, critical
    auto_verification_attempted = Column(Boolean, default=True)
    auto_verification_failure_reason = Column(Text)

    # Assignment and workflow
    assigned_to = Column(String(200))
    committee_member_email = Column(String(200))
    status = Column(String(50), default="pending")  # pending, in_progress, resolved, escalated

    # Resolution
    resolution = Column(Text)
    resolution_value = Column(Text)
    resolved_by = Column(String(200))
    resolved_at = Column(DateTime)

    # Email forwarding
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    email_recipient = Column(String(200))

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HumanInterventionQueue:
    def __init__(self):
        db_url = settings.database_url
        if db_url:
            self._engine = create_engine(db_url, pool_pre_ping=True)
        else:
            self._engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}", connect_args={"check_same_thread": False})
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        InterventionBase.metadata.create_all(bind=self._engine, checkfirst=True)

    def get_session(self) -> Session:
        return self._SessionLocal()

    def create_intervention(self, journal_name: str, parameter_name: str,
                           issue_description: str, severity: str = "medium",
                           evaluation_id: Optional[int] = None,
                           rejection_id: Optional[int] = None,
                           acceptance_id: Optional[int] = None,
                           auto_verification_failure_reason: Optional[str] = None) -> int:
        session = self.get_session()
        try:
            intervention = HumanIntervention(
                journal_name=journal_name,
                evaluation_id=evaluation_id,
                rejection_id=rejection_id,
                acceptance_id=acceptance_id,
                parameter_name=parameter_name,
                issue_description=issue_description,
                severity=severity,
                auto_verification_attempted=True,
                auto_verification_failure_reason=auto_verification_failure_reason,
                status="pending"
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
