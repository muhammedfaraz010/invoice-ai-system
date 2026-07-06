"""
Invoice AI System — FastAPI Backend
Main application entry point
"""
import os
import time
import logging
import shutil
import uuid
import traceback
import importlib.util
from pathlib import Path
from typing import Optional, List
from urllib.parse import unquote
from datetime import datetime

from fastapi import (
    FastAPI, File, UploadFile, Depends, HTTPException,
    Query, BackgroundTasks, status, Request
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from config import settings
from database.db import (
    create_tables, get_db, SessionLocal, Invoice, AgentAction, ChatHistory, User,
    DeleteRequest, DeleteUserRequest, Notification, AuditLog,
)
from models.schemas import (
    ChatRequest, ChatResponse, InvoiceResponse,
    AnalyticsSummary, UserCreate, UserLogin, Token,
    UserProfile, UserProfileUpdate, UserAdminUpdate, UserStatusUpdate,
    DeleteRequestCreate, DeleteDecision, DeleteUserRequestCreate, DeleteUserDecision,
)
from modules.ocr import ocr_engine
from modules.extraction import extraction_engine
from modules.validation import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED,
    build_validation_summary,
    validation_engine,
)
from modules.embeddings import embedding_store
from modules.rag import rag_engine
from modules.agents import invoice_agent
from utils.auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    get_current_user, create_admin_user, require_role, ALGORITHM
)
from utils.error_handling import (
    ProcessingStageError,
    processing_exception_middleware,
    structured_error,
)

# ──────────────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("logs", "error.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Invoice AI System",
    description="AI-powered invoice processing with OCR, NLP extraction, validation, RAG chatbot, and agent automation.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(processing_exception_middleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    logger.debug("[Response generation] Returning HTTP error response: %s", exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=structured_error("API", str(exc.detail), str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    if request.url.path == "/api/auth/register":
        errors = exc.errors()
        message = "Invalid registration request"
        if errors:
            field = errors[0].get("loc", [""])[-1]
            if field == "email":
                message = "Valid email is required"
            elif field == "password":
                message = "Password too short"
            elif field in {"username", "full_name"}:
                message = f"{str(field).replace('_', ' ').title()} is required"
        logger.warning("Invalid registration request: %s", message)
        return JSONResponse(status_code=422, content={"detail": message})
    logger.exception(exc)
    traceback.print_exc()
    return JSONResponse(
        status_code=422,
        content=structured_error("Request validation", "Invalid request", str(exc)),
    )


@app.on_event("startup")
def startup():
    create_tables()
    db = SessionLocal()
    try:
        create_admin_user(db)
    finally:
        db.close()
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info("✅ Invoice AI System started.")


# ──────────────────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────────────────

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        username = data.username.strip()
        email = str(data.email).strip().lower()
        full_name = data.full_name.strip()

        if not username:
            return JSONResponse(status_code=422, content={"detail": "Username is required"})
        if not email:
            return JSONResponse(status_code=422, content={"detail": "Email is required"})
        if len(data.password) < 8:
            return JSONResponse(status_code=422, content={"detail": "Password too short"})

        if db.query(User).filter(User.username == username).first():
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": "Username already exists"},
            )
        if db.query(User).filter(User.email == email).first():
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": "Email already exists"},
            )

        password_hash = hash_password(data.password)
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            legacy_hashed_password=password_hash,
            role="user",
            status="Active",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Registered new user: username=%s email=%s", user.username, user.email)
        return {
            "message": "Registration successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        }
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Registration failed due to duplicate constraint")
        traceback.print_exc()
        detail = "User already exists"
        message = str(getattr(exc, "orig", exc)).lower()
        if "username" in message:
            detail = "Username already exists"
        elif "email" in message:
            detail = "Email already exists"
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": detail})
    except OperationalError as exc:
        db.rollback()
        logger.exception("Registration failed because the database is unavailable")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database unavailable"},
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Registration failed due to a database error")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Registration failed due to a database error"},
        )
    except Exception:
        db.rollback()
        logger.exception("Unexpected registration failure")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Registration failed"},
        )


@app.post("/api/auth/login", response_model=Token, tags=["Auth"])
def login(data: UserLogin, request: Request, db: Session = Depends(get_db)):
    username = (data.username or "").strip()
    logger.info("[Authentication] Login request received")
    logger.info("[Authentication] Username=%s ip=%s", username, request_ip(request))

    try:
        user = db.query(User).filter(User.username == username).first()
        logger.info("[Authentication] User found=%s", bool(user))
    except OperationalError as exc:
        logger.exception("[Authentication] Database connection failed during login lookup")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=structured_error("Database", "Database connection failed", str(exc)),
        )
    except SQLAlchemyError as exc:
        logger.exception("[Authentication] Database error during login lookup")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=structured_error("Database", "Database error", str(exc)),
        )

    if not user:
        logger.warning("[Authentication] Login failed: user not found username=%s", username)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=structured_error("Authentication", "User not found"),
        )

    logger.info(
        "[Authentication] User active=%s status=%s role=%s",
        user.is_active,
        user.status,
        user.role,
    )
    if not user.is_active or (user.status and user.status.lower() == "inactive"):
        logger.warning("[Authentication] Login failed: inactive user username=%s", username)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=structured_error("Authentication", "User is inactive"),
        )

    password_ok = verify_password(data.password, user.hashed_password)
    logger.info("[Authentication] Password verification result=%s username=%s", password_ok, username)
    if not password_ok:
        logger.warning("[Authentication] Login failed: invalid password username=%s", username)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=structured_error("Authentication", "Invalid password"),
        )

    payload = {"sub": str(user.id), "role": user.role}
    logger.info("[Authentication] JWT generation started user_id=%s role=%s", user.id, user.role)
    try:
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)
        logger.info("[Authentication] JWT generation succeeded user_id=%s", user.id)
    except Exception as exc:
        logger.exception("[Authentication] JWT generation failed user_id=%s", user.id)
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=structured_error("Authentication", "JWT generation failed", str(exc)),
        )

    try:
        create_audit_log(db, "user.login", actor_id=user.id, target_user_id=user.id, request=request)
        db.commit()
        logger.info("[Authentication] Login audit log saved user_id=%s", user.id)
    except OperationalError as exc:
        db.rollback()
        logger.exception("[Authentication] Database connection failed while saving login audit")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=structured_error("Database", "Database connection failed", str(exc)),
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("[Authentication] Database error while saving login audit")
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=structured_error("Database", "Database error", str(exc)),
        )

    logger.info("[Authentication] Login response returned username=%s user_id=%s", username, user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user.to_profile(),
    }


@app.get("/api/auth/me", response_model=UserProfile, tags=["Auth"])
def me(user: User = Depends(get_current_user)):
    return user.to_profile()


@app.put("/api/auth/profile", response_model=UserProfile, tags=["Auth"])
def update_profile(
    data: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.email and data.email != user.email:
        if db.query(User).filter(User.email == data.email, User.id != user.id).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.password is not None:
        if len(data.password) < 8:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")
        user.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(user)
    return user.to_profile()


@app.get("/api/users", tags=["Users"])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    rows = []
    for user in users:
        profile = user.to_profile()
        invoices = db.query(Invoice).filter(Invoice.owner_id == user.id, Invoice.deleted_at.is_(None)).all()
        storage_bytes = 0
        for invoice in invoices:
            if invoice.file_path and os.path.exists(invoice.file_path):
                storage_bytes += os.path.getsize(invoice.file_path)
        last_login = (
            db.query(AuditLog)
            .filter(AuditLog.actor_id == user.id, AuditLog.action == "user.login")
            .order_by(desc(AuditLog.created_at))
            .first()
        )
        profile.update({
            "invoice_count": len(invoices),
            "storage_bytes": storage_bytes,
            "last_login": str(last_login.created_at) if last_login else None,
        })
        rows.append(profile)
    return rows


@app.put("/api/users/{user_id}", response_model=UserProfile, tags=["Users"])
def update_user(
    user_id: str,
    data: UserAdminUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if data.email and data.email != user.email:
        if db.query(User).filter(User.email == data.email, User.id != user.id).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.role is not None:
        if data.role not in {"admin", "user"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role must be admin or user")
        previous_role = user.role
        user.role = data.role
        if previous_role != user.role:
            create_audit_log(
                db,
                "user.role_changed",
                actor_id=admin.id,
                target_user_id=user.id,
                request=request,
                details={"previous_role": previous_role, "new_role": user.role},
            )
    if data.is_active is not None:
        user.is_active = data.is_active
        user.status = "Active" if data.is_active else "Inactive"
    db.commit()
    db.refresh(user)
    return user.to_profile()


def _set_user_active_status(db: Session, target: User, active: bool, admin: User) -> None:
    if not active and target.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins cannot deactivate themselves")

    if not active and target.role == "admin" and target.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
        if active_admins <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot deactivate the last active admin")

    target.is_active = active
    target.status = "Active" if active else "Inactive"


@app.patch("/api/users/{user_id}/status", response_model=UserProfile, tags=["Users"])
def update_user_status(
    user_id: str,
    data: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    requested_status = data.status.strip()
    if requested_status not in {"Active", "Inactive"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status must be Active or Inactive")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    previous_status = user.status or ("Active" if user.is_active else "Inactive")
    _set_user_active_status(db, user, requested_status == "Active", admin)
    db.commit()
    db.refresh(user)

    logger.info(
        "User status changed: target_id=%s target_username=%s previous_status=%s new_status=%s changed_by=%s",
        user.id,
        user.username,
        previous_status,
        requested_status,
        admin.id,
    )
    create_audit_log(
        db,
        "user.status_changed",
        actor_id=admin.id,
        target_user_id=user.id,
        request=request,
        details={"previous_status": previous_status, "new_status": requested_status},
    )
    db.commit()
    return user.to_profile()


@app.delete("/api/users/{user_id}", tags=["Users"])
def deactivate_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    previous_status = user.status or ("Active" if user.is_active else "Inactive")
    _set_user_active_status(db, user, False, admin)
    db.commit()
    logger.info(
        "User status changed: target_id=%s target_username=%s previous_status=%s new_status=Inactive changed_by=%s",
        user.id,
        user.username,
        previous_status,
        admin.id,
    )
    create_audit_log(
        db,
        "user.status_changed",
        actor_id=admin.id,
        target_user_id=user.id,
        request=request,
        details={"previous_status": previous_status, "new_status": "Inactive"},
    )
    db.commit()
    return {"message": "User deactivated", "id": user_id}


# ──────────────────────────────────────────────────────
# INVOICE ROUTES
# ──────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def is_python_package_available(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def dependency_error(package_name: str) -> dict:
    return structured_error("Dependency", "Missing Python package", package_name)


def verify_upload_dependencies(ext: str) -> Optional[dict]:
    """Check validation dependencies without treating OCR dependencies as bad files."""
    required = []
    if ext == ".pdf":
        required = [
            ("PyMuPDF, pdf2image, or pypdfium2", None),
        ]
    elif ext in {".png", ".jpg", ".jpeg"}:
        required = [
            ("Pillow", "PIL"),
        ]

    for package_name, import_name in required:
        if import_name is None:
            if not any(is_python_package_available(name) for name in ("fitz", "pdf2image", "pypdfium2")):
                return dependency_error(package_name)
            continue
        if not is_python_package_available(import_name):
            return dependency_error(package_name)

    return None


def validate_pdf(file_path: str) -> dict:
    """Validate that a PDF exists, opens, and has at least one page."""
    logger.debug("[PDF LOADING] Started")
    path = Path(file_path)

    if not path.exists():
        return structured_error("PDF Validation", "Invalid or corrupted PDF", "File does not exist.")
    if not path.is_file() or path.stat().st_size <= 0:
        return structured_error("PDF Validation", "Invalid or corrupted PDF", "File is empty.")
    if path.suffix.lower() != ".pdf":
        return structured_error("PDF Validation", "Invalid or corrupted PDF", "File extension is not .pdf.")

    if is_python_package_available("fitz"):
        try:
            import fitz

            with fitz.open(file_path) as document:
                if document.page_count < 1:
                    return structured_error("PDF Validation", "Invalid or corrupted PDF", "PDF contains no pages.")
            logger.debug("[PDF LOADING] Success via PyMuPDF")
            return {"success": True}
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            return structured_error("PDF Validation", "Invalid or corrupted PDF", str(e))

    if is_python_package_available("pdf2image"):
        try:
            from pdf2image import pdfinfo_from_path

            pdf_info = pdfinfo_from_path(file_path)
            page_count = int(pdf_info.get("Pages", 0) or 0)
            if page_count < 1:
                return structured_error("PDF Validation", "Invalid or corrupted PDF", "PDF contains no pages.")
            logger.debug("[PDF LOADING] Success via pdf2image")
            return {"success": True}
        except Exception as e:
            logger.debug("pdf2image PDF validation fallback failed: %s", e)

    if is_python_package_available("pypdfium2"):
        try:
            import pypdfium2

            document = pypdfium2.PdfDocument(file_path)
            try:
                if len(document) < 1:
                    return structured_error("PDF Validation", "Invalid or corrupted PDF", "PDF contains no pages.")
            finally:
                document.close()
            logger.debug("[PDF LOADING] Success via pypdfium2")
            return {"success": True}
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            return structured_error("PDF Validation", "Invalid or corrupted PDF", str(e))

    return structured_error("Dependency", "Missing Python package", "PyMuPDF, pdf2image, or pypdfium2")


def normalize_invoice_id(invoice_id: str) -> str:
    """Accept IDs pasted from JSON/Swagger with surrounding quotes."""
    return unquote(invoice_id).strip().strip("\"'")


def error_response(stage: str, error: str, details: Optional[str] = None, status_code: int = 400):
    logger.debug("[Response generation] Returning error response for stage=%s", stage)
    return JSONResponse(
        status_code=status_code,
        content=structured_error(stage, error, details),
    )


def scoped_invoice_query(db: Session, user: User):
    return db.query(Invoice).filter(Invoice.owner_id == user.id, Invoice.deleted_at.is_(None))


def selected_user_invoice_query(db: Session, selected_user_id: str):
    return db.query(Invoice).filter(Invoice.owner_id == selected_user_id, Invoice.deleted_at.is_(None))


def request_ip(request: Optional[Request]) -> Optional[str]:
    return request.client.host if request and request.client else None


def create_audit_log(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
) -> None:
    db.add(AuditLog(
        actor_id=actor_id,
        target_user_id=target_user_id,
        invoice_id=invoice_id,
        action=action,
        ip_address=request_ip(request),
        details=details or {},
    ))


def create_notification(
    db: Session,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    reference_id: Optional[str] = None,
) -> None:
    db.add(Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        reference_id=reference_id,
    ))


def get_selected_user_or_404(db: Session, user_id: str) -> User:
    selected = db.query(User).filter(User.id == user_id).first()
    if not selected:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return selected


def soft_delete_invoice(db: Session, invoice: Invoice, actor: User, reason: Optional[str], request: Optional[Request]) -> None:
    invoice.deleted_at = datetime.utcnow()
    invoice.deleted_by = actor.id
    invoice.deleted_reason = reason or "Deleted by owner"
    create_audit_log(
        db,
        "invoice.soft_deleted",
        actor_id=actor.id,
        target_user_id=invoice.owner_id,
        invoice_id=invoice.id,
        request=request,
        details={"reason": invoice.deleted_reason},
    )


def permanently_delete_invoice(db: Session, invoice: Invoice) -> None:
    invoice_id = invoice.id
    if invoice.file_path and os.path.exists(invoice.file_path):
        os.remove(invoice.file_path)
    embedding_store.delete_embedding(invoice_id)
    db.query(AgentAction).filter(AgentAction.invoice_id == invoice_id).delete(synchronize_session=False)
    db.delete(invoice)


def permanently_delete_user_data(db: Session, target: User) -> None:
    invoices = db.query(Invoice).filter(Invoice.owner_id == target.id).all()
    for invoice in invoices:
        permanently_delete_invoice(db, invoice)
    db.query(ChatHistory).filter(ChatHistory.user_id == target.id).delete(synchronize_session=False)
    db.query(Notification).filter(Notification.user_id == target.id).delete(synchronize_session=False)
    db.query(DeleteRequest).filter(DeleteRequest.target_user == target.id).delete(synchronize_session=False)
    db.query(DeleteUserRequest).filter(DeleteUserRequest.target_user == target.id).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.target_user_id == target.id).delete(synchronize_session=False)
    db.delete(target)


def validate_saved_upload(file_path: str, filename: str, file_size: int) -> None:
    """Validate uploaded files before extraction starts."""
    logger.debug("[VALIDATION] Started for %s", filename)
    ext = Path(filename).suffix.lower()

    try:
        if ext not in ALLOWED_EXTENSIONS:
            raise ProcessingStageError(
                "Upload",
                f"Unsupported file type: {ext or 'unknown'}",
                f"Allowed file types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        if file_size <= 0 or not os.path.exists(file_path) or os.path.getsize(file_path) <= 0:
            raise ProcessingStageError("Upload", "Empty files are not supported.")

        dependency_failure = verify_upload_dependencies(ext)
        if dependency_failure:
            raise ProcessingStageError(
                dependency_failure["stage"],
                dependency_failure["error"],
                dependency_failure["details"],
            )

        if ext == ".pdf":
            pdf_result = validate_pdf(file_path)
            if not pdf_result.get("success"):
                raise ProcessingStageError(
                    pdf_result["stage"],
                    pdf_result["error"],
                    pdf_result.get("details"),
                )

        elif ext in {".png", ".jpg", ".jpeg"}:
            try:
                from PIL import Image

                with Image.open(file_path) as image:
                    image.verify()
            except Exception as e:
                logger.exception(e)
                traceback.print_exc()
                raise ProcessingStageError("Validation", "Unsupported or corrupted image file", str(e)) from e

        logger.debug("[VALIDATION] Success for %s", filename)

    except ProcessingStageError:
        raise
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise ProcessingStageError("Validation", "File validation failed", str(e)) from e


def persist_invoice_error(db: Session, invoice: Invoice, error: dict) -> None:
    logger.debug("[Database] Persisting processing error")
    try:
        invoice.extraction_status = "failed"
        invoice.validation_status = STATUS_FAILED
        invoice.validation_errors = [error.get("error") or "Invoice could not be processed."]
        invoice.failed_stage = error.get("stage")
        invoice.processing_error = error
        db.commit()
        logger.debug("[Database] Processing error persisted")
    except Exception as e:
        db.rollback()
        logger.exception(e)
        traceback.print_exc()
        raise ProcessingStageError("Database", "Unable to save invoice", str(e)) from e


@app.post("/api/upload", tags=["Invoice"])
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an invoice file (PDF/image) and trigger background processing."""
    logger.debug("[UPLOAD] Started for %s", file.filename)
    try:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return error_response(
                "Upload",
                f"Unsupported file type: {ext or 'unknown'}",
                f"Allowed file types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        if file.size and file.size > settings.max_file_size_mb * 1024 * 1024:
            return error_response(
                "Upload",
                f"File too large. Max size: {settings.max_file_size_mb}MB",
            )

        invoice_id = str(uuid.uuid4())
        save_name = f"{invoice_id}{ext}"
        save_path = os.path.join(settings.upload_dir, save_name)

        try:
            logger.debug("[UPLOAD] Saving file to %s", save_path)
            with open(save_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_size = os.path.getsize(save_path)
            validate_saved_upload(save_path, file.filename, saved_size)
            logger.debug("[UPLOAD] Success")
        except ProcessingStageError as e:
            if os.path.exists(save_path):
                os.remove(save_path)
            return error_response(e.stage, e.error, e.details)
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            if os.path.exists(save_path):
                os.remove(save_path)
            return error_response("Upload", "Unable to save uploaded file", str(e))

        try:
            logger.debug("[DATABASE] Started invoice record save")
            invoice = Invoice(
                id=invoice_id,
                filename=file.filename,
                file_path=save_path,
                owner_id=user.id,
                owner_role=user.role,
                created_by=user.id,
            )
            db.add(invoice)
            create_audit_log(
                db,
                "invoice.uploaded",
                actor_id=user.id,
                target_user_id=user.id,
                invoice_id=invoice_id,
                request=request,
                details={"filename": file.filename},
            )
            db.commit()
            logger.debug("[DATABASE] Saved")
        except Exception as e:
            db.rollback()
            logger.exception(e)
            traceback.print_exc()
            return error_response("Database", "Unable to save invoice", str(e), status_code=500)

        background_tasks.add_task(process_invoice_background, invoice_id, save_path)

        logger.debug("[RESPONSE] Upload response generated")
        return {
            "success": True,
            "invoice_id": invoice_id,
            "filename": file.filename,
            "status": "uploaded",
            "message": "Invoice is being processed. Check /api/invoice/{id} for results.",
        }

    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        return error_response("Upload", "Upload failed", str(e), status_code=500)


@app.post("/api/extract/{invoice_id}", tags=["Invoice"])
def extract_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger extraction for an already-uploaded invoice."""
    invoice_id = normalize_invoice_id(invoice_id)
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    result = process_invoice(invoice_id, invoice.file_path, db)
    db.refresh(invoice)
    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)
    return invoice.to_dict()


@app.get("/api/invoice/{invoice_id}", tags=["Invoice"])
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice_id = normalize_invoice_id(invoice_id)
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return invoice.to_dict()


@app.get("/api/invoices", tags=["Invoice"])
def list_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    vendor: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = scoped_invoice_query(db, user)
    if vendor:
        query = query.filter(Invoice.vendor_name.ilike(f"%{vendor}%"))
    if status:
        status_aliases = {
            STATUS_VERIFIED: [STATUS_VERIFIED, "valid"],
            STATUS_COMPLETE: [STATUS_COMPLETE],
            STATUS_NEEDS_REVIEW: [STATUS_NEEDS_REVIEW, "invalid"],
            STATUS_FAILED: [STATUS_FAILED],
            "valid": [STATUS_VERIFIED, "valid"],
            "invalid": [STATUS_NEEDS_REVIEW, "invalid"],
        }
        values = status_aliases.get(status, [status])
        query = query.filter(Invoice.validation_status.in_(values))

    total = query.count()
    invoices = query.order_by(desc(Invoice.upload_time)).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "invoices": [inv.to_dict() for inv in invoices],
    }


@app.get("/api/my/invoices", tags=["Invoice"])
def list_my_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    vendor: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_invoices(page, size, vendor, status, db, user)


@app.get("/api/users/{user_id}", response_model=UserProfile, tags=["Users"])
def get_user_workspace_profile(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_selected_user_or_404(db, user_id).to_profile()


@app.get("/api/users/{user_id}/invoices", tags=["Users"])
def list_user_invoices(
    user_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    vendor: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    get_selected_user_or_404(db, user_id)
    query = selected_user_invoice_query(db, user_id)
    if vendor:
        query = query.filter(Invoice.vendor_name.ilike(f"%{vendor}%"))
    if status:
        query = query.filter(Invoice.validation_status == status)
    total = query.count()
    invoices = query.order_by(desc(Invoice.upload_time)).offset((page - 1) * size).limit(size).all()
    return {"total": total, "page": page, "size": size, "invoices": [inv.to_dict() for inv in invoices]}


@app.get("/api/users/{user_id}/chat-history", tags=["Users"])
def list_user_chat_history(
    user_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    get_selected_user_or_404(db, user_id)
    history = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
        .all()
    )
    return [h.to_dict() if hasattr(h, "to_dict") else {
        "id": h.id,
        "question": h.question,
        "answer": h.answer,
        "sources": h.sources,
        "created_at": str(h.created_at),
    } for h in history]


@app.get("/api/users/{user_id}/activity-log", tags=["Users"])
def list_user_activity_log(
    user_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    get_selected_user_or_404(db, user_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.target_user_id == user_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    return [log.to_dict() for log in logs]


@app.get("/api/users/{user_id}/storage", tags=["Users"])
def get_user_storage_usage(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    get_selected_user_or_404(db, user_id)
    invoices = db.query(Invoice).filter(Invoice.owner_id == user_id).all()
    total_bytes = 0
    for invoice in invoices:
        if invoice.file_path and os.path.exists(invoice.file_path):
            total_bytes += os.path.getsize(invoice.file_path)
    return {"user_id": user_id, "invoice_count": len(invoices), "storage_bytes": total_bytes}


@app.get("/api/invoice/{invoice_id}/download", tags=["Invoice"])
def download_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice_id = normalize_invoice_id(invoice_id)
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == invoice_id).first()
    if not invoice or not invoice.file_path or not os.path.exists(invoice.file_path):
        raise HTTPException(404, "Invoice not found")
    return FileResponse(invoice.file_path, filename=invoice.filename)


@app.delete("/api/invoice/{invoice_id}", tags=["Invoice"])
def delete_invoice(
    invoice_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice_id = normalize_invoice_id(invoice_id)
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    soft_delete_invoice(db, invoice, user, "Deleted by owner", request)
    db.commit()
    return {"message": "Invoice deleted", "id": invoice_id}


@app.post("/api/delete-request", tags=["Delete Requests"])
def create_delete_request_endpoint(
    data: DeleteRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    invoice = db.query(Invoice).filter(
        Invoice.id == normalize_invoice_id(data.invoice_id),
        Invoice.deleted_at.is_(None),
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.owner_id == admin.id:
        soft_delete_invoice(db, invoice, admin, data.reason or "Deleted by owner", request)
        db.commit()
        return {"message": "Invoice deleted", "id": invoice.id}

    pending = db.query(DeleteRequest).filter(
        DeleteRequest.invoice_id == invoice.id,
        DeleteRequest.status == "Pending",
    ).first()
    if pending:
        return pending.to_dict()

    delete_request = DeleteRequest(
        invoice_id=invoice.id,
        requested_by=admin.id,
        target_user=invoice.owner_id,
        reason=data.reason,
    )
    db.add(delete_request)
    db.flush()
    create_notification(
        db,
        invoice.owner_id,
        "invoice_delete_request",
        "Invoice deletion request",
        "Admin requested deletion of an invoice.",
        delete_request.id,
    )
    create_audit_log(
        db,
        "invoice.delete_requested",
        actor_id=admin.id,
        target_user_id=invoice.owner_id,
        invoice_id=invoice.id,
        request=request,
        details={"reason": data.reason},
    )
    db.commit()
    db.refresh(delete_request)
    return delete_request.to_dict()


@app.get("/api/delete-requests", tags=["Delete Requests"])
def list_delete_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(DeleteRequest)
    if user.role != "admin":
        query = query.filter(DeleteRequest.target_user == user.id)
    return [item.to_dict() for item in query.order_by(desc(DeleteRequest.created_at)).all()]


@app.post("/api/approve-delete", tags=["Delete Requests"])
def approve_delete_request(
    data: DeleteDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delete_request = db.query(DeleteRequest).filter(DeleteRequest.id == data.request_id).first()
    if not delete_request or delete_request.target_user != user.id:
        raise HTTPException(404, "Delete request not found")
    if delete_request.status != "Pending":
        raise HTTPException(409, "Delete request already resolved")
    invoice = db.query(Invoice).filter(Invoice.id == delete_request.invoice_id).first()
    if invoice:
        soft_delete_invoice(db, invoice, user, delete_request.reason or "Approved deletion request", request)
        permanently_delete_invoice(db, invoice)
    delete_request.status = "Approved"
    create_notification(
        db,
        delete_request.requested_by,
        "invoice_delete_approved",
        "Invoice deletion approved",
        "A user approved your invoice deletion request.",
        delete_request.id,
    )
    create_audit_log(
        db,
        "invoice.delete_approved",
        actor_id=user.id,
        target_user_id=user.id,
        invoice_id=delete_request.invoice_id,
        request=request,
    )
    db.commit()
    return delete_request.to_dict()


@app.post("/api/reject-delete", tags=["Delete Requests"])
def reject_delete_request(
    data: DeleteDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delete_request = db.query(DeleteRequest).filter(DeleteRequest.id == data.request_id).first()
    if not delete_request or delete_request.target_user != user.id:
        raise HTTPException(404, "Delete request not found")
    if delete_request.status != "Pending":
        raise HTTPException(409, "Delete request already resolved")
    delete_request.status = "Rejected"
    create_notification(
        db,
        delete_request.requested_by,
        "invoice_delete_rejected",
        "Invoice deletion rejected",
        "A user rejected your invoice deletion request.",
        delete_request.id,
    )
    create_audit_log(
        db,
        "invoice.delete_rejected",
        actor_id=user.id,
        target_user_id=user.id,
        invoice_id=delete_request.invoice_id,
        request=request,
    )
    db.commit()
    return delete_request.to_dict()


@app.post("/api/delete-user-request", tags=["Delete Requests"])
def create_delete_user_request_endpoint(
    data: DeleteUserRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    target = get_selected_user_or_404(db, data.user_id)
    if target.id == admin.id:
        raise HTTPException(400, "Admins cannot request deletion of their own account")
    pending = db.query(DeleteUserRequest).filter(
        DeleteUserRequest.target_user == target.id,
        DeleteUserRequest.status == "Pending",
    ).first()
    if pending:
        return pending.to_dict()
    delete_request = DeleteUserRequest(
        requested_by=admin.id,
        target_user=target.id,
        reason=data.reason,
    )
    db.add(delete_request)
    db.flush()
    create_notification(
        db,
        target.id,
        "account_delete_request",
        "Account deletion request",
        "Admin requested deletion of your account.",
        delete_request.id,
    )
    create_audit_log(
        db,
        "user.delete_requested",
        actor_id=admin.id,
        target_user_id=target.id,
        request=request,
        details={"reason": data.reason},
    )
    db.commit()
    db.refresh(delete_request)
    return delete_request.to_dict()


@app.get("/api/delete-user-requests", tags=["Delete Requests"])
def list_delete_user_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(DeleteUserRequest)
    if user.role != "admin":
        query = query.filter(DeleteUserRequest.target_user == user.id)
    return [item.to_dict() for item in query.order_by(desc(DeleteUserRequest.created_at)).all()]


@app.post("/api/approve-user-delete", tags=["Delete Requests"])
def approve_user_delete_request(
    data: DeleteUserDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delete_request = db.query(DeleteUserRequest).filter(DeleteUserRequest.id == data.request_id).first()
    if not delete_request or delete_request.target_user != user.id:
        raise HTTPException(404, "Delete user request not found")
    if delete_request.status != "Pending":
        raise HTTPException(409, "Delete user request already resolved")
    requester_id = delete_request.requested_by
    create_notification(
        db,
        requester_id,
        "account_delete_approved",
        "Account deletion approved",
        "A user approved your account deletion request.",
        delete_request.id,
    )
    create_audit_log(db, "user.delete_approved", actor_id=user.id, target_user_id=user.id, request=request)
    permanently_delete_user_data(db, user)
    db.commit()
    return {"message": "User account deleted", "id": user.id}


@app.post("/api/reject-user-delete", tags=["Delete Requests"])
def reject_user_delete_request(
    data: DeleteUserDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delete_request = db.query(DeleteUserRequest).filter(DeleteUserRequest.id == data.request_id).first()
    if not delete_request or delete_request.target_user != user.id:
        raise HTTPException(404, "Delete user request not found")
    if delete_request.status != "Pending":
        raise HTTPException(409, "Delete user request already resolved")
    delete_request.status = "Rejected"
    create_notification(
        db,
        delete_request.requested_by,
        "account_delete_rejected",
        "Account deletion rejected",
        "A user rejected your account deletion request.",
        delete_request.id,
    )
    create_audit_log(db, "user.delete_rejected", actor_id=user.id, target_user_id=user.id, request=request)
    db.commit()
    return delete_request.to_dict()


@app.get("/api/notifications", tags=["Notifications"])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(desc(Notification.created_at))
        .all()
    )
    return [notification.to_dict() for notification in notifications]


@app.get("/api/audit-log", tags=["Audit"])
def list_audit_log(
    target_user_id: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    query = db.query(AuditLog)
    if target_user_id:
        query = query.filter(AuditLog.target_user_id == target_user_id)
    return [log.to_dict() for log in query.order_by(desc(AuditLog.created_at)).limit(limit).all()]


# ──────────────────────────────────────────────────────
# VALIDATE ROUTE
# ──────────────────────────────────────────────────────

@app.get("/api/validate/{invoice_id}", tags=["Validation"])
def validate_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-run validation on an existing invoice."""
    invoice_id = normalize_invoice_id(invoice_id)
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    from models.schemas import InvoiceExtraction
    extraction = InvoiceExtraction(
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        vendor_gstin=invoice.vendor_gstin,
        vendor_vat=invoice.vendor_vat,
        buyer_name=invoice.buyer_name,
        buyer_gstin=invoice.buyer_gstin,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        total_amount=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        payment_method=invoice.payment_method,
        subtotal=invoice.subtotal,
        currency=invoice.currency or "INR",
        line_items=invoice.line_items or [],
    )
    result = validation_engine.validate(extraction, db, invoice_id)

    invoice.validation_status = result.status
    invoice.validation_errors = result.errors + result.warnings
    invoice.is_duplicate = result.is_duplicate
    invoice.duplicate_of = result.duplicate_of
    db.commit()

    issues = result.errors + result.warnings
    return {
        "status": invoice.validation_status,
        "issues": issues,
        **result.dict(),
    }


# ──────────────────────────────────────────────────────
# RAG / CHAT ROUTES
# ──────────────────────────────────────────────────────

@app.post("/api/query", response_model=ChatResponse, tags=["RAG"])
def chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Natural language query over all processed invoices."""
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")

    try:
        result = rag_engine.query(
            request.question,
            db,
            owner_id=user.id,
        )

        history = ChatHistory(
            user_id=user.id,
            question=request.question,
            answer=result["answer"],
            sources=result["sources"],
        )
        db.add(history)
        db.commit()

        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            session_id=request.session_id,
        )
    except Exception as exc:
        logger.exception("Chat query failed: %s", exc)
        db.rollback()
        return ChatResponse(
            answer="I hit a backend issue while answering that question. The system is still running, but chat could not complete the request.",
            sources=[],
            session_id=request.session_id,
        )


@app.get("/api/chat-history", tags=["RAG"])
def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ChatHistory)
    query = query.filter(ChatHistory.user_id == user.id)
    history = query.order_by(desc(ChatHistory.created_at)).limit(limit).all()
    return [
        {
            "id": h.id,
            "question": h.question,
            "answer": h.answer,
            "sources": h.sources,
            "created_at": str(h.created_at),
        }
        for h in history
    ]


# ──────────────────────────────────────────────────────
# AGENT ROUTES
# ──────────────────────────────────────────────────────

@app.get("/api/agent-actions", tags=["Agents"])
def list_agent_actions(
    status: Optional[str] = None,
    invoice_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(AgentAction)
    owned_invoice_ids = scoped_invoice_query(db, user).with_entities(Invoice.id)
    query = query.filter(AgentAction.invoice_id.in_(owned_invoice_ids))
    if status:
        query = query.filter(AgentAction.action_status == status)
    if invoice_id:
        query = query.filter(AgentAction.invoice_id == invoice_id)
    actions = query.order_by(desc(AgentAction.created_at)).limit(100).all()
    return [a.to_dict() for a in actions]


@app.post("/api/agent-action/{action_id}/resolve", tags=["Agents"])
def resolve_action(
    action_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    action = db.query(AgentAction).filter(AgentAction.id == action_id).first()
    if not action:
        raise HTTPException(404, "Action not found")
    invoice = scoped_invoice_query(db, user).filter(Invoice.id == action.invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Action not found")
    result = invoice_agent.resolve_action(action_id, db)
    if not result:
        raise HTTPException(404, "Action not found")
    return result


# ──────────────────────────────────────────────────────
# ANALYTICS ROUTES
# ──────────────────────────────────────────────────────

@app.get("/api/analytics", tags=["Analytics"])
def get_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = scoped_invoice_query(db, user)
    total = query.with_entities(func.count(Invoice.id)).scalar() or 0
    total_amount = query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0.0
    verified = query.filter(Invoice.validation_status.in_([STATUS_VERIFIED, "valid"])).with_entities(func.count(Invoice.id)).scalar() or 0
    complete = query.filter(Invoice.validation_status == STATUS_COMPLETE).with_entities(func.count(Invoice.id)).scalar() or 0
    needs_review = query.filter(Invoice.validation_status.in_([STATUS_NEEDS_REVIEW, "invalid"])).with_entities(func.count(Invoice.id)).scalar() or 0
    failed = query.filter(
        (Invoice.validation_status == STATUS_FAILED) | (Invoice.extraction_status == STATUS_FAILED)
    ).with_entities(func.count(Invoice.id)).scalar() or 0
    duplicates = query.filter(Invoice.is_duplicate == True).with_entities(func.count(Invoice.id)).scalar() or 0
    pending = query.filter(Invoice.validation_status == "pending").with_entities(func.count(Invoice.id)).scalar() or 0

    invoice_rows = query.all()
    summaries = [build_validation_summary(invoice) for invoice in invoice_rows]
    successful_summaries = [
        summary for summary in summaries
        if summary.get("status") != STATUS_FAILED
    ]
    average_extraction_score = round(
        sum(summary["extraction_score"] for summary in successful_summaries) / len(successful_summaries)
    ) if successful_summaries else 0
    average_ai_confidence = round(
        sum(summary["ai_confidence"] for summary in successful_summaries) / len(successful_summaries)
    ) if successful_summaries else 0

    currency_totals_raw = (
        query.with_entities(Invoice.currency, func.sum(Invoice.total_amount).label("total"))
        .filter(Invoice.total_amount.isnot(None))
        .group_by(Invoice.currency)
        .all()
    )
    currency_totals = [
        {"currency": currency or "INR", "total": round(amount or 0, 2)}
        for currency, amount in currency_totals_raw
    ]
    dashboard_currency = currency_totals[0]["currency"] if len(currency_totals) == 1 else "MIXED"

    # Top vendors
    top_vendors_raw = (
        query.with_entities(Invoice.vendor_name, Invoice.currency, func.sum(Invoice.total_amount).label("total"))
        .filter(Invoice.vendor_name.isnot(None))
        .group_by(Invoice.vendor_name, Invoice.currency)
        .order_by(desc("total"))
        .all()
    )
    vendors_by_currency = {}
    for vendor, currency, amount in top_vendors_raw:
        code = currency or "INR"
        vendors_by_currency.setdefault(code, []).append(
            {"vendor": vendor, "currency": code, "total": round(amount or 0, 2)}
        )

    top_vendors = []
    for code in sorted(vendors_by_currency):
        currency_vendors = sorted(
            vendors_by_currency[code],
            key=lambda item: item["total"],
            reverse=True,
        )[:5]
        top_vendors.extend(currency_vendors)

    # Monthly spend (last 6 months). Some older databases have upload_time
    # as VARCHAR, so aggregate in Python instead of relying on DB date functions.
    from datetime import datetime

    monthly_totals = {}
    spend_rows = (
        query.with_entities(Invoice.upload_time, Invoice.total_amount, Invoice.currency)
        .filter(Invoice.total_amount.isnot(None))
        .all()
    )
    for upload_time, amount, currency in spend_rows:
        if not upload_time:
            continue
        if isinstance(upload_time, datetime):
            dt = upload_time
        else:
            try:
                dt = datetime.fromisoformat(str(upload_time))
            except ValueError:
                continue
        key = (dt.year, dt.month, currency or "INR")
        monthly_totals[key] = monthly_totals.get(key, 0.0) + float(amount or 0.0)

    monthly_spend = [
        {"year": year, "month": month, "currency": currency, "total": round(total, 2)}
        for (year, month, currency), total in sorted(monthly_totals.items())[-18:]
    ]

    return {
        "total_invoices": total,
        "total_amount": round(total_amount, 2),
        "currency": dashboard_currency,
        "currency_totals": currency_totals,
        "verified_invoices": verified,
        "complete_invoices": complete,
        "needs_review_invoices": needs_review,
        "failed_invoices": failed,
        "average_extraction_score": average_extraction_score,
        "average_ai_confidence": average_ai_confidence,
        "valid_invoices": verified,
        "invalid_invoices": needs_review,
        "duplicate_invoices": duplicates,
        "pending_invoices": pending,
        "top_vendors": top_vendors,
        "monthly_spend": monthly_spend,
    }


# ──────────────────────────────────────────────────────
# BACKGROUND PROCESSING PIPELINE
# ──────────────────────────────────────────────────────

def legacy_process_invoice(invoice_id: str, file_path: str, db: Session):
    """Full pipeline: OCR → Extract → Validate → Embed → Agent."""
    start = time.time()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return

    try:
        # Step 1: OCR
        logger.info(f"[{invoice_id}] Running OCR...")
        ocr_text = ocr_engine.extract_text(file_path)
        invoice.ocr_text = ocr_text

        # Step 2: Extraction
        logger.info(f"[{invoice_id}] Running LLM extraction...")
        extraction = extraction_engine.extract(ocr_text)
        invoice.invoice_number = extraction.invoice_number
        invoice.vendor_name = extraction.vendor_name
        invoice.vendor_gstin = extraction.vendor_gstin
        invoice.vendor_vat = extraction.vendor_vat
        invoice.buyer_name = extraction.buyer_name
        invoice.buyer_gstin = extraction.buyer_gstin
        invoice.invoice_date = extraction.invoice_date
        invoice.due_date = extraction.due_date
        invoice.total_amount = extraction.total_amount
        invoice.tax_amount = extraction.tax_amount
        invoice.payment_method = extraction.payment_method
        invoice.subtotal = extraction.subtotal
        invoice.currency = extraction.currency
        invoice.line_items = [item.dict() for item in extraction.line_items]
        invoice.raw_extraction = extraction.dict()
        invoice.extraction_status = "success"

        # Step 3: Validation
        logger.info(f"[{invoice_id}] Running validation...")
        validation_result = validation_engine.validate(extraction, db, invoice_id)
        invoice.validation_status = validation_result.status
        invoice.validation_errors = validation_result.errors + validation_result.warnings
        invoice.is_duplicate = validation_result.is_duplicate
        invoice.duplicate_of = validation_result.duplicate_of

        db.commit()

        # Step 4: Embedding
        logger.info(f"[{invoice_id}] Storing embedding...")
        embedded = embedding_store.store_invoice_embedding(invoice_id, invoice.to_dict())
        invoice.embedding_stored = embedded

        # Step 5: Agent Actions
        logger.info(f"[{invoice_id}] Running agent checks...")
        invoice_agent.run(invoice, db)

    except Exception as e:
        logger.error(f"[{invoice_id}] Processing failed: {e}")
        invoice.extraction_status = "failed"
        invoice.validation_status = STATUS_FAILED
        invoice.validation_errors = [str(e)]

    finally:
        invoice.processing_time_ms = int((time.time() - start) * 1000)
        db.commit()
        logger.info(f"[{invoice_id}] Processing complete in {invoice.processing_time_ms}ms")


# ──────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────

def process_invoice_background(invoice_id: str, file_path: str):
    """Open a fresh DB session for FastAPI background processing."""
    db = SessionLocal()
    try:
        process_invoice(invoice_id, file_path, db)
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
    finally:
        db.close()


def process_invoice(invoice_id: str, file_path: str, db: Session):
    """Full pipeline: OCR -> Extract -> Validate -> Embed -> Agent."""
    start = time.time()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return structured_error("Database", "Invoice not found", invoice_id)

    try:
        try:
            logger.debug("[%s] [OCR] Started", invoice_id)
            ocr_text = ocr_engine.extract_text(file_path)
            invoice.ocr_text = ocr_text
            logger.debug("[%s] [OCR] Success", invoice_id)
        except ProcessingStageError:
            raise
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("OCR", "OCR failed", str(e)) from e

        try:
            logger.debug("[%s] [AI] Started", invoice_id)
            extraction = extraction_engine.extract(ocr_text)
            logger.debug("[%s] [AI] Success", invoice_id)
        except ProcessingStageError:
            raise
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("AI Extraction", "AI extraction failed", str(e)) from e

        logger.debug("[%s] [VALIDATION] Started field assignment", invoice_id)
        invoice.invoice_number = extraction.invoice_number
        invoice.vendor_name = extraction.vendor_name
        invoice.vendor_gstin = extraction.vendor_gstin
        invoice.vendor_vat = extraction.vendor_vat
        invoice.buyer_name = extraction.buyer_name
        invoice.buyer_gstin = extraction.buyer_gstin
        invoice.invoice_date = extraction.invoice_date
        invoice.due_date = extraction.due_date
        invoice.total_amount = extraction.total_amount
        invoice.tax_amount = extraction.tax_amount
        invoice.payment_method = extraction.payment_method
        invoice.subtotal = extraction.subtotal
        invoice.currency = extraction.currency
        invoice.line_items = [item.dict() for item in extraction.line_items]
        invoice.raw_extraction = extraction.dict()
        invoice.extraction_status = "success"
        invoice.processing_error = None
        invoice.failed_stage = None
        logger.debug("[%s] [VALIDATION] Success field assignment", invoice_id)

        try:
            logger.debug("[%s] [VALIDATION] Started", invoice_id)
            validation_result = validation_engine.validate(extraction, db, invoice_id)
            invoice.validation_status = validation_result.status
            invoice.validation_errors = validation_result.errors + validation_result.warnings
            invoice.is_duplicate = validation_result.is_duplicate
            invoice.duplicate_of = validation_result.duplicate_of
            logger.debug("[%s] [VALIDATION] Success", invoice_id)
        except ProcessingStageError:
            raise
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("Validation", "Invoice validation failed", str(e)) from e

        try:
            logger.debug("[%s] [DATABASE] Started save", invoice_id)
            db.commit()
            logger.debug("[%s] [DATABASE] Saved", invoice_id)
        except Exception as e:
            db.rollback()
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("Database", "Unable to save invoice", str(e)) from e

        try:
            logger.debug("[%s] [DATABASE] Started embedding save", invoice_id)
            embedded = embedding_store.store_invoice_embedding(invoice_id, invoice.to_dict())
            invoice.embedding_stored = embedded
            db.commit()
            logger.debug("[%s] [DATABASE] Saved embedding", invoice_id)
        except Exception as e:
            db.rollback()
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("Database", "Unable to save invoice", str(e)) from e

        try:
            logger.debug("[%s] [RESPONSE] Started agent checks", invoice_id)
            invoice_agent.run(invoice, db)
            logger.debug("[%s] [RESPONSE] Success agent checks", invoice_id)
        except Exception as e:
            logger.exception("Optional agent processing failed for invoice %s: %s", invoice_id, e)
            traceback.print_exc()

        logger.debug("[%s] [RESPONSE] Processing success response generated", invoice_id)
        return {"success": True, "invoice_id": invoice_id}

    except ProcessingStageError as e:
        logger.exception(e)
        traceback.print_exc()
        error = e.to_dict()
        try:
            persist_invoice_error(db, invoice, error)
        except ProcessingStageError:
            error = structured_error("Database", "Unable to save invoice", e.details)
        return error

    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        error = structured_error("Processing", "Processing failed", str(e))
        try:
            persist_invoice_error(db, invoice, error)
        except ProcessingStageError:
            error = structured_error("Database", "Unable to save invoice", str(e))
        return error

    finally:
        try:
            invoice.processing_time_ms = int((time.time() - start) * 1000)
            db.commit()
            logger.info("[%s] Processing complete in %sms", invoice_id, invoice.processing_time_ms)
        except Exception as e:
            db.rollback()
            logger.exception(e)
            traceback.print_exc()


@app.get("/api/health", tags=["System"])
def health(user: User = Depends(get_current_user)):
    return {
        "status": "ok",
        "version": "1.0.0",
        "openai": bool(settings.openai_api_key),
        "pinecone": bool(settings.pinecone_api_key),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
