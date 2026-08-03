"""
Accepted Journals Database Module
Optional table for journals that passed evaluation with full details.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings

AcceptedBase = declarative_base()


class AcceptedJournal(AcceptedBase):
    __tablename__ = "accepted_journals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journal_name = Column(String(500), nullable=False)
    journal_url = Column(String(1000))
    issn_print = Column(String(20))
    issn_online = Column(String(20))
    doi_prefix = Column(String(50))
    publisher_name = Column(String(500))
    publisher_url = Column(String(1000))
    publisher_address = Column(String(1000))
    editorial_board_url = Column(String(1000))
    submission_portal_url = Column(String(1000))
    ethics_policy_url = Column(String(1000))
    open_access = Column(Boolean, default=False)
    claimed_indexes = Column(Text)

    # Evaluation results
    total_score = Column(Integer)
    max_score = Column(Integer)
    percentage = Column(Float)
    threshold = Column(Integer)
    status = Column(String(50), nullable=False)

    # Domain scores
    authenticity_score = Column(Integer)
    editorial_score = Column(Integer)
    peer_review_score = Column(Integer)
    website_score = Column(Integer)
    metrics_score = Column(Integer)
    ethics_score = Column(Integer)

    # Verification results
    issn_verified = Column(Boolean)
    doi_verified = Column(Boolean)
    publisher_verified = Column(Boolean)
    orcid_verification_rate = Column(Float)
    geographic_diversity_score = Column(Float)
    blacklist_clean = Column(Boolean)

    # Re-evaluation tracking
    re_evaluate_by = Column(String(100))
    last_re_evaluated = Column(DateTime)

    # Metadata
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    evaluated_by = Column(String(200))
    notes = Column(Text)
    raw_data = Column(Text)


class AcceptedJournalDatabase:
    def __init__(self):
        db_url = settings.database_url
        if db_url:
            self._engine = create_engine(db_url, pool_pre_ping=True)
        else:
            self._engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}", connect_args={"check_same_thread": False})
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        AcceptedBase.metadata.create_all(bind=self._engine, checkfirst=True)

    def get_session(self) -> Session:
        return self._SessionLocal()

    def add_accepted(self, result: Dict, evaluated_by: Optional[str] = None) -> int:
        session = self.get_session()
        try:
            domain_scores = {d["domain"]: d["score"] for d in result.get("domain_scores", [])}

            acceptance = AcceptedJournal(
                journal_name=result.get("journal_name"),
                journal_url=result.get("journal_url"),
                issn_print=result.get("issn_print"),
                issn_online=result.get("issn_online"),
                doi_prefix=result.get("doi_prefix"),
                publisher_name=result.get("publisher_name"),
                publisher_url=result.get("publisher_url"),
                publisher_address=result.get("publisher_address"),
                editorial_board_url=result.get("editorial_board_url"),
                submission_portal_url=result.get("submission_portal_url"),
                ethics_policy_url=result.get("ethics_policy_url"),
                open_access=result.get("open_access", False),
                claimed_indexes=json.dumps(result.get("claimed_indexes", [])),

                total_score=result.get("total_score"),
                max_score=result.get("max_score"),
                percentage=result.get("percentage"),
                threshold=result.get("threshold"),
                status=result.get("status"),

                authenticity_score=domain_scores.get("Journal Identification and Authenticity"),
                editorial_score=domain_scores.get("Editorial Board and Governance"),
                peer_review_score=domain_scores.get("Peer Review and Publishing Process"),
                website_score=domain_scores.get("Website and Infrastructure"),
                metrics_score=domain_scores.get("Metrics and Indexing"),
                ethics_score=domain_scores.get("Ethics and Compliance"),

                issn_verified=result.get("verifiers", {}).get("issn", {}).get("valid") if result.get("verifiers") else None,
                doi_verified=result.get("verifiers", {}).get("doi", {}).get("valid") if result.get("verifiers") else None,
                publisher_verified=result.get("verifiers", {}).get("publisher", {}).get("verified") if result.get("verifiers") else None,
                orcid_verification_rate=result.get("orcid_verification_rate"),
                geographic_diversity_score=result.get("geographic_diversity_score"),
                blacklist_clean=not result.get("blacklisted", False),

                re_evaluate_by=result.get("re_evaluate_by"),
                evaluated_at=datetime.utcnow(),
                evaluated_by=evaluated_by,
                notes=result.get("notes"),
                raw_data=json.dumps(result.get("raw_data", {})),
            )
            session.add(acceptance)
            session.commit()
            return acceptance.id
        finally:
            session.close()

    def get_accepted(self, acceptance_id: int) -> Optional[Dict]:
        session = self.get_session()
        try:
            entry = session.query(AcceptedJournal).filter(AcceptedJournal.id == acceptance_id).first()
            if not entry:
                return None
            return self._entry_to_dict(entry)
        finally:
            session.close()

    def list_accepted(self, limit: int = 50, due_re_evaluation: bool = False) -> List[Dict]:
        session = self.get_session()
        try:
            query = session.query(AcceptedJournal).order_by(AcceptedJournal.evaluated_at.desc())
            if due_re_evaluation:
                today = datetime.utcnow().isoformat()
                query = query.filter(
                    AcceptedJournal.re_evaluate_by.isnot(None),
                    AcceptedJournal.re_evaluate_by != "",
                    AcceptedJournal.re_evaluate_by <= today
                )
            entries = query.limit(limit).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def update_re_evaluation(self, acceptance_id: int, re_evaluate_by: str):
        session = self.get_session()
        try:
            entry = session.query(AcceptedJournal).filter(AcceptedJournal.id == acceptance_id).first()
            if entry:
                entry.re_evaluate_by = re_evaluate_by
                entry.last_re_evaluated = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        d = {
            "id": entry.id,
            "journal_name": entry.journal_name,
            "journal_url": entry.journal_url,
            "issn_print": entry.issn_print,
            "issn_online": entry.issn_online,
            "doi_prefix": entry.doi_prefix,
            "publisher_name": entry.publisher_name,
            "publisher_url": entry.publisher_url,
            "publisher_address": entry.publisher_address,
            "editorial_board_url": entry.editorial_board_url,
            "submission_portal_url": entry.submission_portal_url,
            "ethics_policy_url": entry.ethics_policy_url,
            "open_access": entry.open_access,
            "claimed_indexes": json.loads(entry.claimed_indexes) if entry.claimed_indexes else [],
            "total_score": entry.total_score,
            "max_score": entry.max_score,
            "percentage": entry.percentage,
            "threshold": entry.threshold,
            "status": entry.status,
            "authenticity_score": entry.authenticity_score,
            "editorial_score": entry.editorial_score,
            "peer_review_score": entry.peer_review_score,
            "website_score": entry.website_score,
            "metrics_score": entry.metrics_score,
            "ethics_score": entry.ethics_score,
            "issn_verified": entry.issn_verified,
            "doi_verified": entry.doi_verified,
            "publisher_verified": entry.publisher_verified,
            "orcid_verification_rate": entry.orcid_verification_rate,
            "geographic_diversity_score": entry.geographic_diversity_score,
            "blacklist_clean": entry.blacklist_clean,
            "re_evaluate_by": entry.re_evaluate_by,
            "last_re_evaluated": entry.last_re_evaluated.isoformat() if entry.last_re_evaluated else None,
            "evaluated_at": entry.evaluated_at.isoformat() if entry.evaluated_at else None,
            "evaluated_by": entry.evaluated_by,
            "notes": entry.notes,
            "raw_data": json.loads(entry.raw_data) if entry.raw_data else {},
        }
        return d
