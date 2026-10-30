"""Fetch current standard metadata from BIS's public Know Your Standards search."""

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import re

import httpx
from sqlalchemy.orm import Session

from ..database import Standard

BIS_SEARCH_URL = "https://standardsadmin.bis.gov.in/review-service/searchKnowStandards"
BIS_SOURCE_URL = "https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails"
STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "shall", "must", "should",
    "supply", "procure", "purchase", "tender", "required", "requirement", "specification",
    "procurement", "standard", "testing", "test", "inspection", "including", "provide", "minimum", "maximum",
    "sample", "demo", "official", "government", "page", "only", "opwfs", "applicable",
    "applicability", "certification", "requirement", "accordance", "intended", "current",
    "compliance", "conformity", "details", "information", "document", "documents",
    "bidder", "bidders", "where", "shall", "accepted", "eligible", "manufacturer", "authorised",
    "authorized", "offer", "offered", "routine", "schedule", "particular", "purchase", "evidence",
    "suitable", "classification", "classification", "set", "out", "grade",
}


def _queries(text: str) -> list[str]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for word in re.findall(r"[A-Za-z][A-Za-z-]{3,}", text.lower()):
        if word.endswith("s") and not word.endswith("ss") and len(word) > 5:
            word = word[:-1]
        if word not in STOP_WORDS and len(word) >= 4:
            counts[word] = counts.get(word, 0) + 1
            first_seen.setdefault(word, len(first_seen))
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))[:3]]


def sync_live_standards(db: Session, text: str) -> tuple[list[str], str | None]:
    """Cache real BIS metadata matching high-signal terms; never fetch copyrighted PDFs."""
    queries = _queries(text)
    if not queries:
        return [], "Add a product name or specific technical terms so BIS search can find standards."

    records: dict[str, dict] = {}
    try:
        def fetch(query: str):
            return httpx.post(BIS_SEARCH_URL, json={"searchText": query}, timeout=10.0, follow_redirects=False)

        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            for query, response in zip(queries, pool.map(fetch, queries)):
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "SUCCESS" or not isinstance(payload.get("data"), list):
                    raise ValueError("BIS returned an unexpected search response.")
                for item in payload["data"]:
                    number = str(item.get("standardNumber") or "").strip()
                    title = str(item.get("standardName") or "").strip()
                    if number and title:
                        records[number] = item
    except (httpx.HTTPError, ValueError) as exc:
        return [], f"BIS live search is temporarily unavailable ({type(exc).__name__}). Please retry later."

    checked_at = datetime.now(timezone.utc)
    for number, item in records.items():
        withdrawn = item.get("withdrawStatus") == 1
        values = {
            "is_number": number,
            "title": str(item["standardName"]).strip(),
            "scope": "",
            "keywords": "",
            "revision_year": int(number.rsplit(":", 1)[1]) if re.search(r":\d{4}$", number) else None,
            "status": "Withdrawn" if withdrawn else "Not marked withdrawn in BIS search",
            "source_url": BIS_SOURCE_URL,
            "source_checked_at": checked_at,
            "provenance": f"BIS public Know Your Standards keyword search; fetched {checked_at.date().isoformat()}; metadata only.",
            "verification_state": "live_search",
        }
        row = db.query(Standard).filter_by(is_number=number).one_or_none()
        if row:
            for field, value in values.items():
                setattr(row, field, value)
        else:
            db.add(Standard(**values))
    db.commit()
    return list(records), None
