"""
Rejection Trigger Checker
Evaluates the 10 automatic rejection triggers from MTU notification.
"""
import re
from typing import List, Tuple
from .models import JournalInput, RejectionTriggerResult


class RejectionTriggerChecker:
    AUTOMATIC_REJECTION_TRIGGERS = [
        "Invalid or fake ISSN",
        "Anonymous or unverifiable publisher",
        "Absence of a clearly stated peer review policy",
        "Absence of an appropriate Manuscript submission mechanism",
        "Use of non-standard or predatory metrics (SJIF, Cosmos, GIF, etc.)",
        "Absence of a publicly available research ethics and publication policy",
        "Use of cloned or deceptively similar journal titles mimicking reputed journals",
        "Inclusion in recognized blacklists (Beall's, Cabell's, DOAJ, UGC CARE Excluded)",
        "Not included in databases claimed on journal website",
        "Engagement in unethical research or publishing practices",
    ]

    PREDATORY_METRICS = {
        "sjif", "cosmos", "gif", "citefactor", "ae global index",
        "scientific journal impact factor", "global impact factor",
        "general impact factor", "cosmos impact factor"
    }

    BLACKLISTED_TERMS_IN_NAME = {
        "international journal of advanced research",  # common predatory clone pattern
        "world journal of",
        "american journal of",
        "european journal of",
    }

    def __init__(self, journal: JournalInput):
        self.journal = journal
        self.results: List[RejectionTriggerResult] = []

    def check_all(self) -> Tuple[bool, List[RejectionTriggerResult]]:
        self.results = [
            self._check_issn(),
            self._check_publisher(),
            self._check_submission_portal(),
            self._check_predatory_metrics(),
            self._check_ethics_policy(),
            self._check_title_legitimacy(),
            self._check_claimed_indexes(),
            self._check_unethical_practices(),
        ]
        any_rejected = any(not r.passed for r in self.results)
        return any_rejected, self.results

    def _check_issn(self) -> RejectionTriggerResult:
        issn = self.journal.issn_print or self.journal.issn_online
        if not issn:
            return RejectionTriggerResult(
                "Invalid or fake ISSN",
                False,
                "No ISSN provided or found"
            )
        pattern = re.compile(r'^\d{4}-\d{3}[\dX]$', re.IGNORECASE)
        if not pattern.match(issn):
            return RejectionTriggerResult(
                "Invalid or fake ISSN",
                False,
                f"ISSN '{issn}' does not match standard format XXXX-XXXX"
            )
        return RejectionTriggerResult(
            "Invalid or fake ISSN",
            True,
            f"ISSN '{issn}' has valid format"
        )

    def _check_publisher(self) -> RejectionTriggerResult:
        has_name = bool(self.journal.publisher_name and self.journal.publisher_name.strip())
        has_url = bool(self.journal.publisher_url and self.journal.publisher_url.strip())
        has_address = bool(self.journal.publisher_address and self.journal.publisher_address.strip())

        if not has_name:
            return RejectionTriggerResult(
                "Anonymous or unverifiable publisher",
                False,
                "Publisher name missing"
            )
        if not has_url and not has_address:
            return RejectionTriggerResult(
                "Anonymous or unverifiable publisher",
                False,
                "Publisher URL and address both missing"
            )
        if not has_address:
            return RejectionTriggerResult(
                "Anonymous or unverifiable publisher",
                False,
                "Publisher address missing — may indicate shell publisher"
            )
        return RejectionTriggerResult(
            "Anonymous or unverifiable publisher",
            True,
            f"Publisher '{self.journal.publisher_name}' has name, URL, and address"
        )

    def _check_submission_portal(self) -> RejectionTriggerResult:
        if self.journal.submission_email_only:
            return RejectionTriggerResult(
                "Absence of an appropriate Manuscript submission mechanism",
                False,
                "Submissions accepted via email only — must have online portal"
            )
        has_portal = bool(self.journal.submission_portal_url and "http" in self.journal.submission_portal_url)
        if not has_portal:
            return RejectionTriggerResult(
                "Absence of an appropriate Manuscript submission mechanism",
                False,
                "No online submission portal URL provided"
            )
        return RejectionTriggerResult(
            "Absence of an appropriate Manuscript submission mechanism",
            True,
            f"Submission portal: {self.journal.submission_portal_url}"
        )

    def _check_predatory_metrics(self) -> RejectionTriggerResult:
        if not self.journal.metric_claims:
            return RejectionTriggerResult(
                "Use of non-standard or predatory metrics",
                True,
                "No suspicious metrics claimed"
            )
        bad = []
        for claim in self.journal.metric_claims:
            claim_lower = claim.lower()
            for pm in self.PREDATORY_METRICS:
                if pm in claim_lower:
                    bad.append(claim)
        if bad:
            return RejectionTriggerResult(
                "Use of non-standard or predatory metrics",
                False,
                f"Predatory metrics found: {', '.join(bad)}"
            )
        return RejectionTriggerResult(
            "Use of non-standard or predatory metrics",
            True,
            "No predatory metrics detected"
        )

    def _check_ethics_policy(self) -> RejectionTriggerResult:
        if not self.journal.ethics_policy_url:
            return RejectionTriggerResult(
                "Absence of publicly available research ethics and publication policy",
                False,
                "No ethics policy URL provided"
            )
        return RejectionTriggerResult(
            "Absence of publicly available research ethics and publication policy",
            True,
            f"Ethics policy at: {self.journal.ethics_policy_url}"
        )

    def _check_title_legitimacy(self) -> RejectionTriggerResult:
        name_lower = self.journal.name.lower()
        suspicious_count = sum(
            1 for pattern in self.BLACKLISTED_TERMS_IN_NAME
            if pattern in name_lower
        )
        if suspicious_count >= 2:
            return RejectionTriggerResult(
                "Cloned or deceptively similar journal titles",
                False,
                f"Title contains {suspicious_count} predatory clone patterns"
            )
        return RejectionTriggerResult(
            "Cloned or deceptively similar journal titles",
            True,
            "Title appears legitimate"
        )

    def _check_claimed_indexes(self) -> RejectionTriggerResult:
        if not self.journal.claimed_indexes:
            return RejectionTriggerResult(
                "Not included in databases claimed",
                False,
                "No indexes claimed — cannot verify"
            )
        return RejectionTriggerResult(
            "Not included in databases claimed",
            True,
            f"Claimed indexes: {', '.join(self.journal.claimed_indexes)}"
        )

    def _check_unethical_practices(self) -> RejectionTriggerResult:
        red_flags = []
        if self.journal.rapid_publication_claim:
            red_flags.append("rapid publication claim")
        if self.journal.lock_pdfs:
            red_flags.append("locked PDFs")
        if self.journal.submission_email_only:
            red_flags.append("email-only submission")
        if red_flags:
            return RejectionTriggerResult(
                "Engagement in unethical research or publishing practices",
                False,
                f"Potential red flags: {', '.join(red_flags)}"
            )
        return RejectionTriggerResult(
            "Engagement in unethical research or publishing practices",
            True,
            "No obvious unethical practices detected"
        )
