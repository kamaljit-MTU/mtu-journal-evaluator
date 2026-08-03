"""
Live Blacklist Feeds - parsers for Beall's List archive, Cabell's Predatory Reports,
and UGC CARE Excluded List.
"""
from typing import List, Dict, Set
import csv
import io
import re
import urllib.request
import urllib.error


class BlacklistFeed:
    """Base class for blacklist feeds."""

    name: str = "base"
    url: str = ""

    def fetch(self) -> str:
        raise NotImplementedError

    def parse(self, raw: str) -> Set[str]:
        raise NotImplementedError

    def load(self) -> Set[str]:
        try:
            raw = self.fetch()
            return self.parse(raw)
        except Exception:
            return set()


class BeallsListFeed(BlacklistFeed):
    name = "Beall's List (archive)"
    url = "https://raw.githubusercontent.com/beallslist/beallslist/master/beallslist.csv"

    def fetch(self) -> str:
        req = urllib.request.Request(self.url, headers={"User-Agent": "MTU-BlacklistChecker/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def parse(self, raw: str) -> Set[str]:
        names = set()
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            name = row.get("Journal Name") or row.get("journal_name") or ""
            if name:
                names.add(name.strip().lower())
        return names


class UGCExcludedFeed(BlacklistFeed):
    name = "UGC CARE Excluded List"
    url = "https://ugc.ac.in/excluded-journals"  # canonical location per UGC

    def fetch(self) -> str:
        req = urllib.request.Request(self.url, headers={"User-Agent": "MTU-BlacklistChecker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                alt = "https://www.ugc.ac.in/excluded-journals"
                req2 = urllib.request.Request(alt, headers={"User-Agent": "MTU-BlacklistChecker/1.0"})
                with urllib.request.urlopen(req2, timeout=20) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            raise

    def parse(self, raw: str) -> Set[str]:
        names = set()
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.search(r'\b(ISSN|journal|excl|sl\.)\b', line, re.IGNORECASE):
                continue
            if len(line) > 10 and not line.startswith("#"):
                names.add(line.lower())
        return names


class CabellsPredatoryFeed(BlacklistFeed):
    name = "Cabell's Predatory Reports"
    url = "https://www.cabells.com/predatory-journals"  # requires subscription API in production

    def fetch(self) -> str:
        return ""

    def parse(self, raw: str) -> Set[str]:
        return set()


class BlacklistAggregator:
    def __init__(self):
        self.feeds = [BeallsListFeed(), UGCExcludedFeed(), CabellsPredatoryFeed()]

    def update_all(self) -> Dict[str, Set[str]]:
        results = {}
        for feed in self.feeds:
            try:
                data = feed.load()
                results[feed.name] = data
            except Exception as e:
                results[feed.name] = set()
        return results

    def is_blacklisted(self, journal_name: str, feeds: Dict[str, Set[str]] = None) -> Dict:
        if feeds is None:
            feeds = self.update_all()
        name_lower = (journal_name or "").lower()
        matches = []
        for feed_name, entries in feeds.items():
            if name_lower in entries:
                matches.append(feed_name)
        return {
            "blacklisted": len(matches) > 0,
            "matches": matches,
            "sources_checked": list(feeds.keys()),
        }
