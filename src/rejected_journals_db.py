"""
Rejected Journals Database Module
Dedicated table for journals that failed evaluation with full details.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from src.database import EvaluationDatabase, RejectedJournal


class RejectedJournalDatabase(EvaluationDatabase):
    def __init__(self):
        super().__init__()

    def add_rejected(self, result: Dict, evaluated_by: Optional[str] = None) -> int:
        session = self.get_session()
        try:
            rejection = RejectedJournal(
                journal_name=result.get("journal_name"),
                journal_url=result.get("journal_url"),
                issn_print=result.get("issn_print"),
                issn_online=result.get("issn_online"),
                publisher_name=result.get("publisher_name"),
                publisher_url=result.get("publisher_url"),
                submission_email=result.get("submission_email"),
                rejection_reason=result.get("rejection_reason"),
                rejection_triggers=json.dumps(result.get("rejection_triggers", [])),
                total_score=result.get("total_score"),
                max_score=result.get("max_score"),
                percentage=result.get("percentage"),
                blacklist_matches=json.dumps(result.get("blacklist_matches", [])),
                red_flags=json.dumps(result.get("red_flags", [])),
                deep_search_results=json.dumps(result.get("deep_search", {})),
                is_human_review=result.get("is_human_review", False),
                human_review_reason=result.get("human_review_reason"),
                evaluated_at=datetime.utcnow(),
                evaluated_by=evaluated_by,
                raw_data=json.dumps(result.get("raw_data", {})),
            )
            session.add(rejection)
            session.commit()
            return rejection.id
        finally:
            session.close()

    def get_rejected(self, rejection_id: int) -> Optional[Dict]:
        session = self.get_session()
        try:
            entry = session.query(RejectedJournal).filter(RejectedJournal.id == rejection_id).first()
            if not entry:
                return None
            return self._entry_to_dict(entry)
        finally:
            session.close()

    def list_rejected(self, limit: int = 50, needs_review: bool = False) -> List[Dict]:
        session = self.get_session()
        try:
            query = session.query(RejectedJournal).order_by(RejectedJournal.evaluated_at.desc())
            if needs_review:
                query = query.filter(RejectedJournal.is_human_review == True)
                query = query.filter(RejectedJournal.human_review_status == "pending")
            entries = query.limit(limit).all()
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()

    def update_human_review_status(self, rejection_id: int, status: str, notes: str = ""):
        session = self.get_session()
        try:
            entry = session.query(RejectedJournal).filter(RejectedJournal.id == rejection_id).first()
            if entry:
                entry.human_review_status = status
                entry.human_review_notes = notes
                session.commit()
        finally:
            session.close()

    def update_committee_review(self, rejection_id: int, decision: str, notes: str, reviewed_by: str):
        session = self.get_session()
        try:
            entry = session.query(RejectedJournal).filter(RejectedJournal.id == rejection_id).first()
            if entry:
                entry.committee_reviewed = True
                entry.committee_decision = decision
                entry.committee_notes = notes
                entry.committee_reviewed_by = reviewed_by
                entry.committee_reviewed_at = datetime.utcnow()
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
            "publisher_name": entry.publisher_name,
            "publisher_url": entry.publisher_url,
            "submission_email": entry.submission_email,
            "rejection_reason": entry.rejection_reason,
            "rejection_triggers": json.loads(entry.rejection_triggers) if entry.rejection_triggers else [],
            "total_score": entry.total_score,
            "max_score": entry.max_score,
            "percentage": entry.percentage,
            "blacklist_matches": json.loads(entry.blacklist_matches) if entry.blacklist_matches else [],
            "red_flags": json.loads(entry.red_flags) if entry.red_flags else [],
            "deep_search_results": json.loads(entry.deep_search_results) if entry.deep_search_results else {},
            "is_human_review": entry.is_human_review,
            "human_review_reason": entry.human_review_reason,
            "human_review_status": entry.human_review_status,
            "human_review_notes": entry.human_review_notes,
            "committee_reviewed": entry.committee_reviewed,
            "committee_decision": entry.committee_decision,
            "committee_notes": entry.committee_notes,
            "committee_reviewed_by": entry.committee_reviewed_by,
            "committee_reviewed_at": entry.committee_reviewed_at.isoformat() if entry.committee_reviewed_at else None,
            "evaluated_at": entry.evaluated_at.isoformat() if entry.evaluated_at else None,
            "evaluated_by": entry.evaluated_by,
            "raw_data": json.loads(entry.raw_data) if entry.raw_data else {},
        }
        return d
