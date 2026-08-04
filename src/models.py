"""
MTU Journal Evaluator - Core Data Models
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class VerdictStatus(Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class RejectionTriggerResult:
    name: str
    passed: bool
    detail: str


@dataclass
class DomainScore:
    domain: str
    max_points: int
    earned_points: int
    sub_criteria: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationResult:
    journal_name: str
    journal_url: str
    status: VerdictStatus
    total_score: int
    max_score: int
    percentage: float
    threshold: int
    rejection_triggers: List[RejectionTriggerResult]
    domain_scores: List[DomainScore]
    summary: str
    recommendations: List[str]
    raw_data: Dict[str, Any] = field(default_factory=dict)
    unverified_parameters: List[str] = field(default_factory=list)


@dataclass
class JournalInput:
    name: str
    url: str
    issn_print: Optional[str] = None
    issn_online: Optional[str] = None
    doi_prefix: Optional[str] = None
    publisher_name: Optional[str] = None
    publisher_url: Optional[str] = None
    publisher_address: Optional[str] = None
    editorial_board_url: Optional[str] = None
    aims_scope_url: Optional[str] = None
    submission_portal_url: Optional[str] = None
    apc_url: Optional[str] = None
    ethics_policy_url: Optional[str] = None
    open_access: bool = False
    submission_email_only: bool = False
    claimed_indexes: List[str] = field(default_factory=list)
    metric_claims: List[str] = field(default_factory=list)
    rapid_publication_claim: bool = False
    lock_pdfs: bool = False
    notes: str = ""
