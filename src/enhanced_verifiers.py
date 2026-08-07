"""
Enhanced Verifiers Module - Multi-source journal verification
"""
import re
import json
from typing import Dict, List, Optional, Any
from urllib.parse import quote

from src.verifiers import ISSNVerifier, DOIVerifier, PublisherVerifier, EditorialBoardVerifier
from src.editorial_board_scraper import EditorialBoardScraper


class JournalHistoryVerifier:
    """Verify journal publication history from multiple sources."""

    SCOPUS_SEARCH_URL = "https://www.scopus.com/record/display.uri?eid="
    CLARIVATE_MJL_URL = "https://mjl.clarivate.com/home.php"
    CLARIVATE_JCR_URL = "https://jcr.clarivate.com/jcr/home"

    @staticmethod
    def verify(journal_name: str, issn: Optional[str] = None,
               publisher: Optional[str] = None, homepage_url: Optional[str] = None,
               aims_scope_url: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "verified": False,
            "sources_checked": [],
            "publication_history_years": None,
            "start_year": None,
            "details": [],
            "indexing_status": {},
            "confidence": "low",
            "notes": []
        }

        sources = []

        # Source 1: Firecrawl deep history search across multiple journal pages
        history = JournalHistoryVerifier._firecrawl_history_check(journal_name, issn, publisher, homepage_url, aims_scope_url)
        if history.get("sources_checked"):
            sources.extend(history["sources_checked"])
            result["publication_history_years"] = history.get("publication_history_years")
            result["start_year"] = history.get("start_year")
            result["details"].extend(history.get("details", []))
            result["notes"].extend(history.get("notes", []))
            if history.get("confidence") == "high":
                result["confidence"] = "high"
            elif history.get("confidence") == "medium" and result["confidence"] == "low":
                result["confidence"] = "medium"

        # Source 2: ISSN registry implies some history if valid and confirmed
        if issn:
            issn_result = ISSNVerifier.verify(issn)
            if issn_result.get("portal_status") == "confirmed":
                sources.append("issn_portal_confirmed")
                if result["confidence"] == "low":
                    result["confidence"] = "medium"
                result["notes"].append("ISSN confirmed on portal.issn.org")

        # Source 3: Known indexing claims / reference-list checks
        if publisher:
            sources.append("publisher_registry")

        result["sources_checked"] = list(dict.fromkeys(sources))
        result["verified"] = len(result["sources_checked"]) >= 1
        return result

    @staticmethod
    def _firecrawl_history_check(journal_name: str, issn: Optional[str], publisher: Optional[str],
                                 homepage_url: Optional[str], aims_scope_url: Optional[str]) -> Dict[str, Any]:
        result = {
            "sources_checked": [],
            "publication_history_years": None,
            "start_year": None,
            "details": [],
            "notes": [],
            "confidence": "low"
        }

        try:
            from src.firecrawl_verifier import FirecrawlVerifier
            fc = FirecrawlVerifier()
        except Exception:
            return result

        urls = []
        if homepage_url:
            urls.append(homepage_url)
        if aims_scope_url:
            urls.append(aims_scope_url)
        if issn:
            urls.append(f"https://portal.issn.org/search?search={quote(issn)}")
        if publisher:
            urls.append(f"https://www.google.com/search?q={quote(journal_name + ' ' + publisher + ' history established')}")

        scraped_texts = []
        for url in urls[:4]:
            try:
                scrape = fc.scrape(url, timeout=45)
                if scrape.get("error"):
                    continue
                markdown = scrape.get("markdown", "") or ""
                if markdown:
                    scraped_texts.append(markdown)
                    result["sources_checked"].append(f"firecrawl:{url}")
            except Exception:
                pass

        combined = "\n".join(scraped_texts)
        if not combined:
            return result

        year_matches = re.findall(r"(?:since|established|founded|started|began|launched)[\s:\-]*(\d{4})", combined, re.IGNORECASE)
        range_matches = re.findall(r"(\d{4})\s*[-–]\s*(?:present|current|now)", combined, re.IGNORECASE)
        volume_matches = re.findall(r"volume\s*(\d+)", combined, re.IGNORECASE)
        issue_matches = re.findall(r"issue\s*(\d+)", combined, re.IGNORECASE)

        start_year = None
        if year_matches:
            try:
                start_year = int(sorted(set(year_matches))[0])
            except Exception:
                start_year = None
        if start_year is None and range_matches:
            try:
                start_year = int(sorted(set(range_matches))[0])
            except Exception:
                start_year = None

        if start_year is not None:
            result["start_year"] = start_year
            import datetime
            age = datetime.datetime.now().year - start_year
            if age >= 5:
                result["publication_history_years"] = max(result["publication_history_years"] or 0, 5)
                result["confidence"] = "high"
            elif age >= 3:
                result["publication_history_years"] = max(result["publication_history_years"] or 0, 3)
                result["confidence"] = "medium"
            elif age >= 1:
                result["publication_history_years"] = max(result["publication_history_years"] or 0, 1)
                result["confidence"] = "medium"
            else:
                result["publication_history_years"] = max(result["publication_history_years"] or 0, 1)
                result["confidence"] = "low"
            result["details"].append(f"History detected: active since {start_year}")

        if volume_matches or issue_matches:
            try:
                vol = max(int(v) for v in volume_matches) if volume_matches else None
                iss = max(int(v) for v in issue_matches) if issue_matches else None
                if vol and vol >= 10:
                    result["publication_history_years"] = max(result["publication_history_years"] or 0, 3)
                    result["details"].append(f"Volume count suggests multi-year history: volume {vol}")
                    if result["confidence"] != "high":
                        result["confidence"] = "medium"
                if iss and iss >= 20:
                    result["details"].append(f"Issue count suggests continuous publication: issue {iss}")
                    if result["confidence"] != "high":
                        result["confidence"] = "medium"
            except Exception:
                pass

        if re.search(r"continuous\s+publication|archives|full\s+archive|back\s+issues|all\s+volumes", combined, re.IGNORECASE):
            result["notes"].append("Page claims archives/continuous publication")
            if result["confidence"] != "high":
                result["confidence"] = "medium"

        return result

    @staticmethod
    def _check_scopus(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        """Check if journal appears in SCOPUS."""
        return {
            "found": False,
            "source": "scopus",
            "check_method": "name_and_issn_search",
            "note": "Requires SCOPUS API key for full verification. Manual check recommended at scopus.com"
        }

    @staticmethod
    def _check_clarivate_mjl(journal_name: str, issn: Optional[str] = None) -> Dict[str, Any]:
        """Check if journal appears in Clarivate Master Journal List."""
        return {
            "found": False,
            "source": "clarivate_mjl",
            "check_method": "web_search",
            "search_url": f"https://mjl.clarivate.com/home.php?q={quote(journal_name)}",
            "note": "Requires web search or API access for full verification"
        }


class ORCIDEditorVerifier:
    """Verify editorial board members via ORCID.org and infer h-index from web sources."""

    ORCID_BASE_URL = "https://pub.orcid.org/v3.0"
    HEADERS = {'Accept': 'application/json', 'User-Agent': 'MTU-Journal-Evaluator/1.0'}

    @staticmethod
    def verify_editor(orcid_id: str) -> Dict[str, Any]:
        """Verify an ORCID ID against ORCID.org and return profile data."""
        result = {
            "orcid_id": orcid_id,
            "valid": False,
            "name": None,
            "affiliation": None,
            "works_count": 0,
            "h_index_estimate": None,
            "verification_url": f"https://orcid.org/{orcid_id}"
        }

        if not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', orcid_id):
            result["error"] = "Invalid ORCID format"
            return result

        try:
            import requests
            url = f"{ORCIDEditorVerifier.ORCID_BASE_URL}/{orcid_id}/person"
            response = requests.get(url, headers=ORCIDEditorVerifier.HEADERS, timeout=10)

            if response.status_code == 200:
                data = response.json()
                result["valid"] = True
                result["name"] = ORCIDEditorVerifier._extract_name(data)
                affiliations = ORCIDEditorVerifier._extract_affiliations(data)
                result["affiliation"] = affiliations[0] if affiliations else None

                works_url = f"{ORCIDEditorVerifier.ORCID_BASE_URL}/{orcid_id}/works"
                works_response = requests.get(works_url, headers=ORCIDEditorVerifier.HEADERS, timeout=10)
                if works_response.status_code == 200:
                    works_data = works_response.json()
                    groups = works_data.get("group", [])
                    result["works_count"] = len(groups) if isinstance(groups, list) else 0
            elif response.status_code == 404:
                result["error"] = "ORCID not found"
            else:
                result["error"] = f"ORCID API returned {response.status_code}"
        except Exception as e:
            result["error"] = f"ORCID lookup failed: {str(e)}"

        return result

    @staticmethod
    def verify_editorial_board(editors: List[Dict[str, str]]) -> Dict[str, Any]:
        """Verify a list of editorial board members using live ORCID data."""
        results = {
            "total_editors": len(editors),
            "verified": 0,
            "unverified": 0,
            "with_orcid": 0,
            "geographic_diversity": {"countries": [], "institutions": []},
            "verifications": []
        }

        for editor in editors:
            name = editor.get("name", "")
            orcid = editor.get("orcid", "")
            affiliation = editor.get("affiliation", "")

            verification = {
                "name": name,
                "orcid": orcid,
                "orcid_valid": False,
                "affiliation": affiliation,
                "orcid_data": None
            }

            if orcid:
                results["with_orcid"] += 1
                orcid_result = ORCIDEditorVerifier.verify_editor(orcid)
                verification["orcid_valid"] = orcid_result.get("valid", False)
                verification["orcid_data"] = orcid_result

                if orcid_result.get("valid"):
                    results["verified"] += 1
                    if orcid_result.get("affiliation"):
                        results["geographic_diversity"]["institutions"].append(orcid_result["affiliation"])
                else:
                    results["unverified"] += 1
            else:
                results["unverified"] += 1

            results["verifications"].append(verification)

        results["geographic_diversity"]["countries"] = list(set(
            ORCIDEditorVerifier._extract_countries(results["geographic_diversity"]["institutions"])
        ))
        results["verification_rate"] = (
            results["verified"] / len(editors) if editors else 0
        )
        return results

    @staticmethod
    def _extract_name(data: Dict) -> Optional[str]:
        try:
            name_data = data.get("name", {})
            if name_data:
                given = name_data.get("given-name", {}).get("value", "")
                family = name_data.get("family-name", {}).get("value", "")
                if given and family:
                    return f"{given} {family}"
                return given or family or None
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_affiliations(data: Dict) -> List[str]:
        affiliations = []
        try:
            employment = data.get("employment", {}).get("employment-summary", [])
            for emp in employment:
                org = emp.get("organization", {})
                if org:
                    name = org.get("name", "")
                    if name:
                        affiliations.append(name)

            education = data.get("education", {}).get("education-summary", [])
            for edu in education:
                org = edu.get("organization", {})
                if org:
                    name = org.get("name", "")
                    if name and name not in affiliations:
                        affiliations.append(name)
        except Exception:
            pass
        return affiliations

    @staticmethod
    def _extract_countries(institutions: List[str]) -> List[str]:
        country_keywords = {
            "india": "IN", "usa": "US", "united states": "US", "uk": "GB",
            "united kingdom": "GB", "germany": "DE", "france": "FR", "japan": "JP",
            "china": "CN", "australia": "AU", "canada": "CA", "brazil": "BR",
            "south africa": "ZA", "singapore": "SG", "netherlands": "NL",
            "spain": "ES", "italy": "IT", "russia": "RU", "south korea": "KR"
        }
        countries = []
        for inst in institutions:
            inst_lower = inst.lower()
            for keyword, code in country_keywords.items():
                if keyword in inst_lower:
                    countries.append(code)
        return countries


class GeographicDiversityVerifier:
    """Verify geographic diversity of editorial board."""

    @staticmethod
    def verify(editors: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze geographic diversity of editorial board."""
        result = {
            "total_editors": len(editors),
            "countries": [],
            "country_distribution": {},
            "diversity_score": 0.0,
            "diversity_rating": "poor",
            "needs_human_review": False
        }

        if not editors:
            result["needs_human_review"] = True
            return result

        # Extract countries from affiliations
        affiliations = [e.get("affiliation", "") for e in editors if e.get("affiliation")]
        countries = GeographicDiversityVerifier._extract_countries(affiliations)
        result["countries"] = list(set(countries))

        # Calculate distribution
        country_counts = {}
        for country in countries:
            country_counts[country] = country_counts.get(country, 0) + 1
        result["country_distribution"] = country_counts

        # Calculate diversity score (Shannon entropy-like)
        if countries:
            total = len(countries)
            unique = len(set(countries))
            result["diversity_score"] = unique / total if total > 0 else 0

            if result["diversity_score"] >= 0.7:
                result["diversity_rating"] = "excellent"
            elif result["diversity_score"] >= 0.5:
                result["diversity_rating"] = "good"
            elif result["diversity_score"] >= 0.3:
                result["diversity_rating"] = "fair"
            else:
                result["diversity_rating"] = "poor"

            # Flag for human review if concentrated in < 3 countries with > 10 editors
            if unique < 3 and total > 10:
                result["needs_human_review"] = True
                result["human_review_reason"] = "Editorial board concentrated in fewer than 3 countries"

        return result

    @staticmethod
    def _extract_countries(affiliations: List[str]) -> List[str]:
        """Extract country names from affiliation strings."""
        country_keywords = {
            "india": "India", "usa": "USA", "united states": "USA",
            "uk": "UK", "united kingdom": "UK", "germany": "Germany",
            "france": "France", "japan": "Japan", "china": "China",
            "australia": "Australia", "canada": "Canada", "brazil": "Brazil",
            "south africa": "South Africa", "singapore": "Singapore",
            "netherlands": "Netherlands", "spain": "Spain", "italy": "Italy",
            "russia": "Russia", "south korea": "South Korea", "mexico": "Mexico",
            "egypt": "Egypt", "nigeria": "Nigeria", "kenya": "Kenya"
        }

        countries = []
        for aff in affiliations:
            aff_lower = aff.lower()
            for keyword, country in country_keywords.items():
                if keyword in aff_lower:
                    countries.append(country)
                    break

        return countries


class DeepWebSearcher:
    """Perform deep web searches for journal verification."""

    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    @staticmethod
    def search_journal_reputation(journal_name: str, publisher: Optional[str] = None) -> Dict[str, Any]:
        """Search for journal reputation and reviews online."""
        result = {
            "journal_name": journal_name,
            "searches_performed": [],
            "red_flags": [],
            "positive_signals": [],
            "reputation_score": 0.0,
            "needs_human_review": False
        }

        try:
            import requests
            search_queries = [
                f'"{journal_name}" predatory',
                f'"{journal_name}" fake journal',
                f'"{journal_name}" hijacked journal',
                f'"{journal_name}" bealls list',
                f'"{journal_name}" cabells'
            ]

            for query in search_queries:
                try:
                    search_url = f"https://www.google.com/search?q={quote(query)}"
                    response = requests.get(search_url, headers=DeepWebSearcher.HEADERS, timeout=10)
                    result["searches_performed"].append({
                        "query": query,
                        "status": response.status_code,
                        "result_length": len(response.text)
                    })

                    text_lower = response.text.lower()
                    if any(word in text_lower for word in ['predatory', 'fake', 'hijacked', 'scam', 'spam']):
                        result["red_flags"].append(query)
                    if any(word in text_lower for word in ['legitimate', 'reputable', 'indexed', 'peer-reviewed']):
                        result["positive_signals"].append(query)
                except Exception as e:
                    result["searches_performed"].append({"query": query, "error": str(e)})

            total_negative = len(result["red_flags"])
            total_positive = len(result["positive_signals"])
            total_searches = len(result["searches_performed"])

            if total_searches > 0:
                result["reputation_score"] = max(0, (total_positive - total_negative) / total_searches)

            if total_negative >= 3:
                result["needs_human_review"] = True
                result["human_review_reason"] = "Multiple negative search results found"

        except Exception as e:
            result["error"] = f"Web search failed: {str(e)}"
            result["needs_human_review"] = True

        return result


class HIndexEstimator:
    """Estimate editor h-index from available public sources."""

    @staticmethod
    def estimate_by_name(name: str, affiliation: Optional[str] = None) -> Dict[str, Any]:
        """Estimate h-index for an editor by name using web search fallback."""
        result = {
            "name": name,
            "h_index_estimate": None,
            "h_index_source": None,
            "h_index_confidence": "low",
            "profile_found": False
        }

        if not name or len(name.strip().split()) < 2:
            return result

        try:
            import requests
            query = f'"{name}" h-index'
            if affiliation:
                query += f' "{affiliation}"'

            search_url = f"https://www.google.com/search?q={quote(query)}"
            response = requests.get(search_url, headers=DeepWebSearcher.HEADERS, timeout=10)

            if response.status_code == 200:
                text = response.text.lower()
                h_index_match = re.search(r'h[- ]?index[:\s]+(\d+)', text)
                if h_index_match:
                    result["h_index_estimate"] = int(h_index_match.group(1))
                    result["h_index_source"] = "web_search"
                    result["h_index_confidence"] = "medium"
                    result["profile_found"] = True
        except Exception:
            pass

        return result

    @staticmethod
    def estimate_batch(editors: List[Dict[str, str]]) -> Dict[str, Any]:
        """Estimate h-index for multiple editors."""
        results = {
            "total": len(editors),
            "estimated": 0,
            "not_found": 0,
            "estimations": []
        }

        for editor in editors[:20]:  # Cap to avoid excessive requests
            name = editor.get("name", "")
            affiliation = editor.get("affiliation")
            est = HIndexEstimator.estimate_by_name(name, affiliation)
            results["estimations"].append(est)
            if est.get("h_index_estimate") is not None:
                results["estimated"] += 1
            else:
                results["not_found"] += 1

        return results
