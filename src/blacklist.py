"""
Blacklist integration - Beall's List, Cabell's Predatory Reports, UGC CARE Excluded, DOAJ blacklist.
"""
from typing import List, Dict


class BlacklistChecker:
    # In production, these would be fetched from APIs or maintained as curated JSON files.
    # For now we use keyword-based known predatory indicators and placeholder URLs.
    BLACKLIST_SOURCES = [
        "Beall's List (historical archive)",
        "Cabell's Predatory Reports API",
        "UGC CARE Excluded List",
        "DOAJ blacklist / journals falsely claiming DOAJ indexing",
    ]

    KNOWN_PREDATORY_KEYWORDS = [
        "international journal of advanced research",
        "world journal of",
        "american journal of",
        "european journal of",
        "advance journal",
        "science journal",
    ]

    @staticmethod
    def check(journal_name: str, claimed_indexes: List[str], metric_claims: List[str]) -> Dict:
        issues = []
        name_lower = (journal_name or "").lower()
        for kw in BlacklistChecker.KNOWN_PREDATORY_KEYWORDS:
            if kw in name_lower:
                issues.append(f"Title matches known predatory pattern: '{kw}'")

        suspicious_indexes = {"sjif", "cosmos", "gif", "citefactor", "ae global index"}
        for idx in claimed_indexes:
            if idx.lower() in suspicious_indexes:
                issues.append(f"Claimed index is a known predatory metric/index: {idx}")

        for mc in metric_claims:
            ml = mc.lower()
            if any(s in ml for s in ["sjif", "cosmos impact factor", "global impact factor"]):
                issues.append(f"Predatory metric claim: {mc}")

        blacklisted = len(issues) > 0
        return {
            "blacklisted": blacklisted,
            "issues": issues,
            "sources_checked": BlacklistChecker.BLACKLIST_SOURCES,
            "note": (
                "Live API integration with Beall's, Cabell's, and UGC CARE Excluded "
                "is required for authoritative blacklist status."
            ),
        }
