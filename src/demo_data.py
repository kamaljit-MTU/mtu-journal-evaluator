#!/usr/bin/env python3
"""Sample journal data for testing."""
from src.models import JournalInput

SAMPLE_JOURNALS = [
    JournalInput(
        name="IEEE Transactions on Neural Networks and Learning Systems",
        url="https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",
        issn_print="2162-237X",
        issn_online="2162-2388",
        doi_prefix="10.1109",
        publisher_name="IEEE",
        publisher_url="https://www.ieee.org",
        publisher_address="445 Hoes Lane, Piscataway, NJ 08854, USA",
        editorial_board_url="https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",
        submission_portal_url="https://ieeexplore.ieee.org",
        ethics_policy_url="https://www.ieee.org/publications/rights/peer-review.html",
        open_access=False,
        claimed_indexes=["Scopus", "Web of Science", "IEEE Xplore"],
        metric_claims=["Impact Factor (Clarivate)", "CiteScore (Scopus)"],
    ),
    JournalInput(
        name="International Journal of Advanced Research in Science",
        url="http://www.ijars.in",
        issn_print="2320-1234",
        issn_online="",
        doi_prefix="",
        publisher_name="Advanced Research Publications",
        publisher_url="http://www.advancedresearchpub.in",
        publisher_address="",
        editorial_board_url="",
        submission_portal_url="",
        submission_email_only=True,
        ethics_policy_url="",
        open_access=False,
        claimed_indexes=["SJIF", "Cosmos"],
        metric_claims=["SJIF 2024: 7.8", "Cosmos Impact Factor"],
        rapid_publication_claim=True,
    ),
]
