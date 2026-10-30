"""Export cached BIS search metadata to a readable JSON dataset file."""

import json
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.database import SessionLocal, Standard


OUTPUT = Path(__file__).resolve().parent / "data" / "bis_standards_cache.json"


def export_standards() -> int:
    db = SessionLocal()
    try:
        rows = db.scalars(select(Standard).order_by(Standard.is_number)).all()
        records = []
        for row in rows:
            records.append({
                "is_number": row.is_number,
                "title": row.title,
                "scope": row.scope,
                "keywords": row.keywords.split() if row.keywords else [],
                "department": row.department,
                "revision_year": row.revision_year,
                "status": row.status,
                "amendments": row.amendments,
                "source_url": row.source_url,
                "source_checked_at": row.source_checked_at.isoformat() if row.source_checked_at else None,
                "provenance": row.provenance,
                "verification_state": row.verification_state,
            })
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(records)
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Exported {export_standards()} cached standard records to {OUTPUT}")
