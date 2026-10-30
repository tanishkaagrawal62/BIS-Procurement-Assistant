import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from .database import Analysis, Recommendation, SessionToken, Standard, User, get_db, initialize_database
from .security import current_user, hash_password, issue_token, verify_password
from .services.pdf import PdfExtractionError, extract_pdf
from .services.report import make_report
from .services.requirements import extract_requirements
from .services.search import recommend, tokens
from .services.bis_live import sync_live_standards

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
KNOW_STANDARDS_URL = "https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails"
@asynccontextmanager
async def lifespan(_app):
    initialize_database()
    yield


app = FastAPI(title="BIS Assist API", version="1.0.0", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("BIS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    remember: bool = False


class Signup(Credentials):
    name: str = Field(min_length=2, max_length=120)


class ManualAnalysis(BaseModel):
    tender_name: str = Field(min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    specification: str = Field(min_length=1, max_length=100_000)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)
    confirmation: str = Field(pattern="^DELETE$")


def timestamp(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def standard_payload(standard: Standard) -> dict:
    return {
        "id": standard.id, "is_number": standard.is_number, "title": standard.title,
        "scope": standard.scope, "revision_year": standard.revision_year,
        "status": standard.status, "amendments": standard.amendments,
        "source_url": standard.source_url, "source_checked_at": timestamp(standard.source_checked_at),
        "provenance": standard.provenance, "verification_state": standard.verification_state,
    }


def analysis_payload(analysis: Analysis) -> dict:
    extracted = json.loads(analysis.requirements_json)
    requirements = {}
    if extracted.get("product") and extracted["product"].get("value"):
        requirements["product"] = {"value": extracted["product"]["value"]}
    for key, value in extracted.items():
        if key in {"product", "source_text", "keywords"} or not isinstance(value, list):
            continue
        requirements[key] = [{"value": item["value"]} for item in value if isinstance(item, dict) and item.get("value")]
    recommendations = []
    for row in sorted(analysis.recommendations, key=lambda item: item.rank):
        recommendations.append({
            "rank": row.rank, "keyword_score": row.keyword_score,
            "semantic_score": row.semantic_score, "combined_score": row.combined_score,
            "evidence": json.loads(row.evidence_json), "uncertainty": json.loads(row.uncertainty_json),
            "standard": standard_payload(row.standard),
        })
    warning = analysis.warning
    if warning and re.search(r"confirm|legal applicability|relevance score|certification requirement", warning, re.I):
        warning = None
    return {
        "id": analysis.id, "tender_name": analysis.tender_name, "location": analysis.location, "filename": analysis.filename,
        "requirements": requirements,
        "created_at": timestamp(analysis.created_at), "status": analysis.status,
        "warning": warning, "recommendations": recommendations,
    }


def matching_text(requirements: dict, full_text: str) -> str:
    """Keep catalogue matching focused on product and technical attributes, not tender boilerplate."""
    parts = []
    product = requirements.get("product")
    if isinstance(product, dict) and product.get("value"):
        parts.append(product["value"])
    for field in ("materials", "grades", "referenced_standards"):
        parts.extend(item["value"] for item in requirements.get(field, []) if isinstance(item, dict) and item.get("value"))
    query = " ".join(dict.fromkeys(parts)).strip()
    return query or " ".join(full_text.split()[:45])


def product_anchor_terms(requirements: dict) -> set[str]:
    product = requirements.get("product")
    if not isinstance(product, dict) or not product.get("value"):
        return set()
    generic = {"industrial", "safety", "equipment", "material", "materials", "product", "products", "routine", "maintenance", "field", "government", "use", "supply", "accordance", "document", "documents", "set", "out", "requirements", "requirement"}
    return {word for word in tokens(product["value"]) if word not in generic}


def owned_analysis(db: Session, user: User, analysis_id: str) -> Analysis:
    row = db.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id)
        .options(joinedload(Analysis.recommendations).joinedload(Recommendation.standard))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return row


def create_analysis(db: Session, user: User, tender_name: str, text: str, filename: str | None = None, location: str | None = None) -> dict:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Enter tender specifications or upload a text-based PDF.")
    extracted = extract_requirements(text)
    query = matching_text(extracted, text)
    live_numbers, live_error = ([], None)
    if os.getenv("BIS_LIVE_SEARCH_ENABLED", "true").lower() == "true":
        live_numbers, live_error = sync_live_standards(db, query)
    ranked, search_info = recommend(db, query, live_numbers, product_anchor_terms(extracted))
    warning = None
    search_info["live_bis_records"] = len(live_numbers)
    if live_error:
        warning = live_error
    elif not live_numbers and search_info["catalogue_records"] == 0:
        warning = "BIS search returned no matching standards. Try adding the product name or specific material and use details."
    elif live_numbers:
        warning = "Recommendations use live BIS catalogue metadata (standard number, title, and withdrawal indicator). Full standard clauses are not included; confirm scope and current status on BIS."
    elif search_info["semantic_search"] == "unavailable":
        warning = search_info["semantic_error"]
    row = Analysis(
        id=str(uuid.uuid4()), user_id=user.id, tender_name=tender_name.strip(), location=location.strip() if location and location.strip() else None, filename=filename,
        raw_text=text, requirements_json=json.dumps(extracted, ensure_ascii=False), status="complete", warning=warning,
    )
    db.add(row)
    db.flush()
    for item in ranked:
        db.add(Recommendation(
            analysis_id=row.id, standard_id=item["standard"].id, rank=item["rank"],
            keyword_score=item["keyword_score"], semantic_score=item["semantic_score"],
            combined_score=item["combined_score"], evidence_json=json.dumps(item["evidence"], ensure_ascii=False),
            uncertainty_json=json.dumps(item["uncertainty"], ensure_ascii=False),
        ))
    db.commit()
    db.refresh(row)
    return {**analysis_payload(row), "search": search_info}


def refresh_legacy_analysis(db: Session, analysis: Analysis) -> None:
    """Upgrade records created before live BIS search was enabled, once on first view."""
    if os.getenv("BIS_LIVE_SEARCH_ENABLED", "true").lower() != "true":
        return
    if analysis.recommendations or not (analysis.warning or "").startswith("No standards catalogue is loaded"):
        return
    extracted = json.loads(analysis.requirements_json)
    query = matching_text(extracted, analysis.raw_text)
    live_numbers, error = sync_live_standards(db, query)
    ranked, _ = recommend(db, query, live_numbers, product_anchor_terms(extracted))
    db.execute(delete(Recommendation).where(Recommendation.analysis_id == analysis.id))
    for item in ranked:
        db.add(Recommendation(
            analysis_id=analysis.id, standard_id=item["standard"].id, rank=item["rank"],
            keyword_score=item["keyword_score"], semantic_score=item["semantic_score"],
            combined_score=item["combined_score"], evidence_json=json.dumps(item["evidence"], ensure_ascii=False),
            uncertainty_json=json.dumps(item["uncertainty"], ensure_ascii=False),
        ))
    analysis.warning = error or (
        "Results refreshed with the latest matching BIS catalogue metadata."
        if ranked else f"BIS search checked {len(live_numbers)} matching catalogue records, but none had enough evidence for a reliable recommendation. Add more specific product or technical details and retry."
    )
    db.commit()
    db.expire(analysis, ["recommendations"])


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected", "standards_loaded": db.scalar(select(func.count(Standard.id))) or 0, "bis_live_search": "enabled" if os.getenv("BIS_LIVE_SEARCH_ENABLED", "true").lower() == "true" else "disabled", "bis_live_verification": "confirm current status on official BIS portal"}


@app.post("/api/auth/signup", status_code=201)
def signup(body: Signup, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": issue_token(db, user), "token_type": "bearer", "user": {"name": user.name, "email": user.email}}


@app.post("/api/auth/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {"access_token": issue_token(db, user, 30 if body.remember else 7), "token_type": "bearer", "user": {"name": user.name, "email": user.email}}


@app.post("/api/auth/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else ""
    if token:
        import hashlib
        token_row = db.get(SessionToken, hashlib.sha256(token.encode()).hexdigest())
        if token_row:
            db.delete(token_row)
            db.commit()
    return Response(status_code=204)


@app.delete("/api/auth/account", status_code=204)
def delete_account(body: DeleteAccountRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect. Account was not deleted.")
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    db.delete(user)
    db.commit()
    return Response(status_code=204)


@app.post("/api/analyses/manual", status_code=201)
def analyse_manual(body: ManualAnalysis, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return create_analysis(db, user, body.tender_name, body.specification, location=body.location)


@app.post("/api/analyses/upload", status_code=201)
async def analyse_upload(
    tender_name: str = Form(..., min_length=1, max_length=300),
    location: str = Form(default="", max_length=200),
    specification: str = Form(default="", max_length=100_000),
    file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db),
):
    filename = Path(file.filename or "tender.pdf").name[:255]
    if not filename.lower().endswith(".pdf") or file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the 20 MB upload limit.")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The selected file is not a valid PDF.")
    try:
        document_text = extract_pdf(data)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    combined_text = "\n\n".join(part for part in (specification.strip(), document_text) if part)
    return create_analysis(db, user, tender_name, combined_text, filename, location)


@app.get("/api/analyses")
def list_analyses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc())).all()
    return [{"id": row.id, "tender_name": row.tender_name, "location": row.location, "filename": row.filename, "created_at": timestamp(row.created_at), "status": row.status, "recommendation_count": len(row.recommendations)} for row in rows]


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_analysis(db, user, analysis_id)
    refresh_legacy_analysis(db, row)
    return analysis_payload(row)


@app.get("/api/analyses/{analysis_id}/report.pdf")
def download_report(analysis_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = make_report(analysis_payload(owned_analysis(db, user, analysis_id)))
    return Response(report, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="bis-analysis-{analysis_id}.pdf"'})


@app.get("/api/standards/{standard_id}/verification")
def verification(standard_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    standard = db.get(Standard, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="Standard record not found in the local catalogue.")
    return {
        "is_number": standard.is_number, "title": standard.title,
        "verification_state": standard.verification_state,
        "current_status": standard.status if standard.verification_state == "live_verified" else None,
        "source_url": standard.source_url or KNOW_STANDARDS_URL,
        "last_checked": timestamp(standard.source_checked_at),
        "message": "Current BIS status could not be verified by a documented live API. Open the official Know Your Standards search to confirm.",
        "official_search_url": KNOW_STANDARDS_URL,
    }
