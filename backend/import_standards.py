"""Import a reviewed JSON catalogue exported from an official BIS source.

This tool does not download or scrape BIS. It rejects non-BIS source hosts and
never marks imported records as live-verified.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from backend.app.database import SessionLocal, Standard, initialize_database

ALLOWED_HOSTS = {"bis.gov.in", "www.bis.gov.in", "services.bis.gov.in", "standards.bis.gov.in", "standardsbis.bsbedge.com"}


def import_catalogue(path: Path) -> int:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Catalogue must be a JSON array.")
    initialize_database()
    db = SessionLocal()
    imported = 0
    try:
        for record in records:
            required = {"is_number", "title", "source_url", "provenance", "verification_state"}
            missing = required.difference(record)
            if missing:
                raise ValueError(f"Record is missing fields: {', '.join(sorted(missing))}")
            if any(str(record[key]).startswith("REPLACE_WITH_") for key in ("is_number", "title")):
                raise ValueError("Replace all template values with verified BIS catalogue data before import.")
            host = (urlparse(record["source_url"]).hostname or "").lower()
            if urlparse(record["source_url"]).scheme != "https" or host not in ALLOWED_HOSTS:
                raise ValueError(f"Source must be an official BIS host: {record['is_number']}")
            if record["verification_state"] not in {"cached", "unverified", "live_search"}:
                raise ValueError("Importer cannot mark records live-verified.")
            if not record["provenance"].strip():
                raise ValueError("Each record needs an official source and retrieval-date note.")
            if record["provenance"].startswith("Replace with"):
                raise ValueError("Replace the template provenance with the source checked and retrieval date.")
            checked_at = datetime.fromisoformat(record["source_checked_at"]).astimezone(timezone.utc) if record.get("source_checked_at") else None
            values = {
                "is_number": record["is_number"].strip(), "title": record["title"].strip(),
                "scope": record.get("scope"), "keywords": " ".join(record.get("keywords", [])),
                "department": record.get("department"), "revision_year": record.get("revision_year"),
                "status": record.get("status"), "amendments": record.get("amendments"),
                "source_url": record["source_url"], "provenance": record["provenance"],
                "verification_state": record["verification_state"], "source_checked_at": checked_at,
            }
            row = db.query(Standard).filter_by(is_number=values["is_number"]).one_or_none()
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                db.add(Standard(**values))
            imported += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalogue", type=Path, help="Reviewed JSON array containing official BIS source and provenance")
    args = parser.parse_args()
    print(f"Imported or updated {import_catalogue(args.catalogue)} records.")
