"""
Database module supporting both SQLite (local dev) and PostgreSQL (production).
Uses SQLAlchemy for ORM.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings

Base = declarative_base()


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journal_name = Column(String(500), nullable=False)
    journal_url = Column(String(1000))
    status = Column(String(50), nullable=False)
    total_score = Column(Integer)
    max_score = Column(Integer)
    percentage = Column(Float)
    threshold = Column(Integer)
    rejection_triggers = Column(Text)
    domain_scores = Column(Text)
    summary = Column(Text)
    recommendations = Column(Text)
    raw_data = Column(Text)
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    evaluated_by = Column(String(200))
    appeal_status = Column(String(50), default="none")
    appeal_notes = Column(Text)
    re_evaluate_by = Column(String(100))


class Database:
    def __init__(self):
        self._engine = None
        self._SessionLocal = None
        self._init_db()

    def _init_db(self):
        db_url = settings.database_url
        if db_url:
            self._engine = create_engine(db_url, pool_pre_ping=True)
        else:
            self._engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}", connect_args={"check_same_thread": False})
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        Base.metadata.create_all(bind=self._engine)

    def get_session(self) -> Session:
        return self._SessionLocal()

    def save_evaluation(self, result: Dict, evaluated_by: Optional[str] = None) -> int:
        session = self.get_session()
        try:
            eval_entry = Evaluation(
                journal_name=result.get("journal_name"),
                journal_url=result.get("journal_url"),
                status=result.get("status"),
                total_score=result.get("total_score"),
                max_score=result.get("max_score"),
                percentage=result.get("percentage"),
                threshold=result.get("threshold"),
                rejection_triggers=json.dumps(result.get("rejection_triggers", [])),
                domain_scores=json.dumps(result.get("domain_scores", [])),
                summary=result.get("summary"),
                recommendations=json.dumps(result.get("recommendations", [])),
                raw_data=json.dumps(result.get("raw_data", {})),
                evaluated_at=datetime.utcnow(),
                evaluated_by=evaluated_by,
            )
            session.add(eval_entry)
            session.commit()
            eval_id = eval_entry.id
            return eval_id
        finally:
            session.close()

    def get_evaluation(self, eval_id: int) -> Optional[Dict]:
        session = self.get_session()
        try:
            entry = session.query(Evaluation).filter(Evaluation.id == eval_id).first()
            if not entry:
                return None
            return self._entry_to_dict(entry)
        finally:
            session.close()

    def list_evaluations(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        session = self.get_session()
        try:
            query = session.query(Evaluation).order_by(Evaluation.evaluated_at.desc())
            if status:
                query = query.filter(Evaluation.status == status)
            entries = query.limit(limit).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def update_appeal(self, eval_id: int, appeal_status: str, appeal_notes: str):
        session = self.get_session()
        try:
            entry = session.query(Evaluation).filter(Evaluation.id == eval_id).first()
            if entry:
                entry.appeal_status = appeal_status
                entry.appeal_notes = appeal_notes
                session.commit()
        finally:
            session.close()

    def schedule_re_evaluation(self, eval_id: int, re_evaluate_by: str):
        session = self.get_session()
        try:
            entry = session.query(Evaluation).filter(Evaluation.id == eval_id).first()
            if entry:
                entry.re_evaluate_by = re_evaluate_by
                session.commit()
        finally:
            session.close()

    def update_status(self, eval_id: int, status: str, notes: str = ""):
        session = self.get_session()
        try:
            entry = session.query(Evaluation).filter(Evaluation.id == eval_id).first()
            if entry:
                entry.status = status
                timestamp = datetime.utcnow().isoformat()
                entry.appeal_notes = (entry.appeal_notes or "") + f"\n[ADMIN OVERRIDE {timestamp}] {notes}"
                session.commit()
        finally:
            session.close()

    def get_due_re_evaluations(self) -> List[Dict]:
        session = self.get_session()
        try:
            today = datetime.utcnow().isoformat()
            entries = session.query(Evaluation).filter(
                Evaluation.re_evaluate_by.isnot(None),
                Evaluation.re_evaluate_by != "",
                Evaluation.re_evaluate_by <= today,
                Evaluation.status.notin_(["REJECTED", "WITHDRAWN"])
            ).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        d = {
            "id": entry.id,
            "journal_name": entry.journal_name,
            "journal_url": entry.journal_url,
            "status": entry.status,
            "total_score": entry.total_score,
            "max_score": entry.max_score,
            "percentage": entry.percentage,
            "threshold": entry.threshold,
            "rejection_triggers": json.loads(entry.rejection_triggers) if entry.rejection_triggers else [],
            "domain_scores": json.loads(entry.domain_scores) if entry.domain_scores else [],
            "summary": entry.summary,
            "recommendations": json.loads(entry.recommendations) if entry.recommendations else [],
            "raw_data": json.loads(entry.raw_data) if entry.raw_data else {},
            "evaluated_at": entry.evaluated_at.isoformat() if entry.evaluated_at else None,
            "evaluated_by": entry.evaluated_by,
            "appeal_status": entry.appeal_status,
            "appeal_notes": entry.appeal_notes,
            "re_evaluate_by": entry.re_evaluate_by,
        }
        return d
