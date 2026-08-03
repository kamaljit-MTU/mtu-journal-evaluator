"""
Web Crawler Module - automatically fetch journal website data for evaluation.
"""
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse
import re


class JournalCrawler:
    """
    Lightweight crawler that fetches journal homepage and extracts
    key data points needed for MTU evaluation.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def fetch_page(self, url: str) -> str:
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MTU-JournalCrawler/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return f"ERROR: {e}"

    def extract_issn(self, html: str) -> List[str]:
        patterns = [
            r'ISSN[:\s]*(\d{4}-\d{3}[\dXx])',
            r'(?:print|online)[:\s]*ISSN[:\s]*(\d{4}-\d{3}[\dXx])',
        ]
        found = []
        for p in patterns:
            matches = re.findall(p, html, re.IGNORECASE)
            found.extend(m.upper() for m in matches)
        return list(set(found))

    def extract_emails(self, html: str) -> List[str]:
        return list(set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)))

    def extract_links(self, html: str) -> List[str]:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        result = []
        for h in hrefs:
            if h.startswith("http"):
                result.append(h)
            elif h.startswith("/"):
                parsed = urlparse(self.base_url)
                result.append(f"{parsed.scheme}://{parsed.netloc}{h}")
            else:
                result.append(urljoin(self.base_url + "/", h))
        return result

    def find_keyword_presence(self, html: str, keywords: List[str]) -> Dict[str, bool]:
        lower = html.lower()
        return {kw: kw in lower for kw in keywords}

    def analyze(self) -> Dict[str, Any]:
        html = self.fetch_page(self.base_url)
        if html.startswith("ERROR"):
            return {"error": html, "url": self.base_url}

        issns = self.extract_issn(html)
        emails = self.extract_emails(html)
        links = self.extract_links(html)

        submission_keywords = ["submit", "submission", "manuscript", "author guidelines"]
        ethics_keywords = ["ethics", "publication ethics", "cope", "research integrity"]
        review_keywords = ["peer review", "double blind", "single blind", "review policy"]
        editorial_keywords = ["editorial board", "editor-in-chief", "editor in chief"]
        metric_keywords = ["impact factor", "citescore", "scopus", "web of science"]
        predatory_metrics = ["sjif", "cosmos", "gif", "citefactor", "global impact factor"]
        rapid_keywords = ["rapid publication", "fast track", "instant publication"]
        email_only = bool(emails) and not any(
            any(k in link.lower() for k in submission_keywords) for link in links
        )

        checks = {
            "submission_portal_present": any(any(k in l.lower() for k in submission_keywords) for l in links),
            "ethics_policy_present": self.find_keyword_presence(html, ethics_keywords),
            "review_policy_present": self.find_keyword_presence(html, review_keywords),
            "editorial_board_present": self.find_keyword_presence(html, editorial_keywords),
            "metric_claims_present": self.find_keyword_presence(html, metric_keywords),
            "predatory_metrics_present": self.find_keyword_presence(html, predatory_metrics),
            "rapid_publication_claim": self.find_keyword_presence(html, rapid_keywords),
            "email_only_submission": email_only,
        }

        return {
            "url": self.base_url,
            "html_length": len(html),
            "issns_found": issns,
            "emails_found": emails,
            "links_sample": links[:20],
            "checks": checks,
            "raw_html_excerpt": html[:2000],
        }
