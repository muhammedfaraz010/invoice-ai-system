import io
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_auth_ownership.db"
os.environ["SECRET_KEY"] = "test_secret_key_for_auth_ownership"
os.environ["ADMIN_PASSWORD"] = "admin12345"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from PIL import Image

from database.db import Base, Invoice, SessionLocal, engine
from main import app
from utils.auth import create_admin_user


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        create_admin_user(db)
    finally:
        db.close()


def _register_and_login(client, username, email):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "full_name": username.title(),
            "password": "password123",
        },
    )
    assert response.status_code == 201
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"], response.json()["user"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _png_bytes():
    image = Image.new("RGB", (16, 16), color="white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    data.seek(0)
    return data


def test_user_invoice_isolation_and_admin_access():
    _reset_db()
    client = TestClient(app)

    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin12345"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    token_a, user_a = _register_and_login(client, "usera", "usera@example.com")
    token_b, user_b = _register_and_login(client, "userb", "userb@example.com")

    upload = client.post(
        "/api/upload",
        headers=_auth(token_a),
        files={"file": ("invoice.png", _png_bytes(), "image/png")},
    )
    assert upload.status_code == 200
    invoice_id = upload.json()["invoice_id"]

    db = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        assert invoice is not None
        assert invoice.owner_id == user_a["id"]

        other_invoice = Invoice(
            id="invoice-owned-by-b",
            filename="b.pdf",
            file_path="/tmp/b.pdf",
            owner_id=user_b["id"],
        )
        db.add(other_invoice)
        db.commit()
    finally:
        db.close()

    user_a_list = client.get("/api/my/invoices", headers=_auth(token_a))
    assert user_a_list.status_code == 200
    assert {item["id"] for item in user_a_list.json()["invoices"]} == {invoice_id}

    forbidden = client.get(f"/api/invoice/invoice-owned-by-b", headers=_auth(token_a))
    assert forbidden.status_code == 404

    admin_list = client.get("/api/invoices", headers=_auth(admin_token))
    assert admin_list.status_code == 200
    assert invoice_id not in {item["id"] for item in admin_list.json()["invoices"]}
    assert "invoice-owned-by-b" not in {item["id"] for item in admin_list.json()["invoices"]}

    selected_user_list = client.get(f"/api/users/{user_a['id']}/invoices", headers=_auth(admin_token))
    assert selected_user_list.status_code == 200
    assert {item["id"] for item in selected_user_list.json()["invoices"]} == {invoice_id}

    delete_request = client.post(
        "/api/delete-request",
        headers=_auth(admin_token),
        json={"invoice_id": invoice_id, "reason": "cleanup"},
    )
    assert delete_request.status_code == 200
    assert delete_request.json()["status"] == "Pending"
    request_id = delete_request.json()["id"]

    notifications = client.get("/api/notifications", headers=_auth(token_a))
    assert notifications.status_code == 200
    assert any(item["reference_id"] == request_id for item in notifications.json())

    approved = client.post(
        "/api/approve-delete",
        headers=_auth(token_a),
        json={"request_id": request_id},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    deleted_lookup = client.get(f"/api/invoice/{invoice_id}", headers=_auth(token_a))
    assert deleted_lookup.status_code == 404


def test_registration_validation_and_duplicates():
    _reset_db()
    client = TestClient(app)

    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "password123",
    }

    created = client.post("/api/auth/register", json=payload)
    assert created.status_code == 201
    assert created.json()["message"] == "Registration successful"
    assert created.json()["user"]["username"] == "newuser"
    assert "password" not in created.json()["user"]

    duplicate_username = client.post(
        "/api/auth/register",
        json={**payload, "email": "another@example.com"},
    )
    assert duplicate_username.status_code == 409
    assert duplicate_username.json() == {"detail": "Username already exists"}

    duplicate_email = client.post(
        "/api/auth/register",
        json={**payload, "username": "anotheruser"},
    )
    assert duplicate_email.status_code == 409
    assert duplicate_email.json() == {"detail": "Email already exists"}

    short_password = client.post(
        "/api/auth/register",
        json={**payload, "username": "shortpass", "email": "short@example.com", "password": "short"},
    )
    assert short_password.status_code == 422
    assert short_password.json() == {"detail": "Password too short"}
