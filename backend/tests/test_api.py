from io import BytesIO

import fitz
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, Standard, get_db
from backend.app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("BIS_LIVE_SEARCH_ENABLED", "false")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def signup_and_auth(client, email="buyer@example.com"):
    response = client.post("/api/auth/signup", json={"name": "Buyer", "email": email, "password": "safe-password-123"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def pdf_bytes(text="Supply stainless steel bolts. Material carbon steel. Strength testing required."):
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(60, 700, text)
    document.save()
    return buffer.getvalue()


def test_health_and_auth_passwords_are_not_plaintext(client):
    assert client.get("/api/health").json()["database"] == "connected"
    signup = client.post("/api/auth/signup", json={"name": "Buyer", "email": "buyer@example.com", "password": "safe-password-123"})
    assert signup.status_code == 201
    assert "safe-password-123" not in str(signup.json())
    assert client.post("/api/auth/login", json={"email": "buyer@example.com", "password": "wrong-password"}).status_code == 401


def test_manual_analysis_persists_and_is_private(client):
    headers = signup_and_auth(client)
    response = client.post("/api/analyses/manual", headers=headers, json={"tender_name": "Steel fasteners", "specification": "Supply carbon steel bolts, 12 mm, strength testing required."})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "complete"
    assert body["requirements"]["materials"]
    assert "raw_text" not in body
    assert "source_text" not in body["requirements"]
    assert body["recommendations"] == []
    assert "BIS search returned no matching standards" in body["warning"]
    assert client.get("/api/analyses").status_code == 401
    assert client.get("/api/analyses", headers=headers).json()[0]["id"] == body["id"]


def test_pdf_upload_and_real_pdf_report(client):
    headers = signup_and_auth(client)
    response = client.post("/api/analyses/upload", headers=headers, data={"tender_name": "PDF tender"}, files={"file": ("tender.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 201, response.text
    report = client.get(f"/api/analyses/{response.json()['id']}/report.pdf", headers=headers)
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF")
    assert fitz.open(stream=report.content, filetype="pdf").page_count == 1


def test_invalid_pdf_and_cross_account_access_are_rejected(client):
    headers = signup_and_auth(client)
    invalid = client.post("/api/analyses/upload", headers=headers, data={"tender_name": "Bad file"}, files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert invalid.status_code == 415
    analysis = client.post("/api/analyses/manual", headers=headers, json={"tender_name": "Private", "specification": "Steel bolts for equipment."}).json()
    other = signup_and_auth(client, "other@example.com")
    assert client.get(f"/api/analyses/{analysis['id']}", headers=other).status_code == 404


def test_logout_revokes_bearer_session(client):
    headers = signup_and_auth(client)
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/analyses", headers=headers).status_code == 401


def test_account_deletion_requires_password_and_removes_history(client):
    headers = signup_and_auth(client)
    created = client.post("/api/analyses/manual", headers=headers, json={"tender_name": "Remove me", "specification": "Steel bolts for an assembly."})
    assert created.status_code == 201

    wrong_password = client.request("DELETE", "/api/auth/account", headers=headers, json={"password": "incorrect-password", "confirmation": "DELETE"})
    assert wrong_password.status_code == 401
    assert client.get("/api/analyses", headers=headers).status_code == 200

    deleted = client.request("DELETE", "/api/auth/account", headers=headers, json={"password": "safe-password-123", "confirmation": "DELETE"})
    assert deleted.status_code == 204
    assert client.get("/api/analyses", headers=headers).status_code == 401

    replacement = signup_and_auth(client)
    assert client.get("/api/analyses", headers=replacement).json() == []


def test_catalogue_search_is_distinct_and_limited_to_three(client):
    from backend.app.services.search import recommend

    # These are test fixtures and are never inserted into production data.
    db = next(app.dependency_overrides[get_db]())
    for number in range(4):
        db.add(Standard(
            is_number=f"TEST-FIXTURE-{number}", title=f"Test fixture carbon steel bolt standard {number}",
            scope="Test fixture record for steel bolt matching", keywords="carbon steel bolts testing",
            source_url="https://www.services.bis.gov.in/", provenance="TEST FIXTURE ONLY; not a genuine catalogue record",
            verification_state="unverified",
        ))
    db.commit()
    results, metadata = recommend(db, "Supply carbon steel bolts and strength testing requirements.")
    assert len(results) == 3
    assert len({item["standard"].is_number for item in results}) == len(results)
    assert metadata["keyword_search"] == "bm25"
    db.close()


def test_scanned_pdf_returns_clear_ocr_message(client):
    headers = signup_and_auth(client)
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.showPage()
    document.save()
    response = client.post("/api/analyses/upload", headers=headers, data={"tender_name": "Scanned"}, files={"file": ("scan.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 422
    assert "OCR is not configured" in response.json()["detail"]


def test_bm25_handles_empty_and_relevant_catalogue():
    from backend.app.services.search import bm25_scores
    assert bm25_scores("steel bolts", []) == []
    scores = bm25_scores("steel bolts", ["steel bolts", "office chair"])
    assert scores[0] > scores[1]
