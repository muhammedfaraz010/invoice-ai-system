"""
Invoice AI System — FastAPI Backend
Main application entry point
"""
import os
import time
import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import (
    FastAPI, File, UploadFile, Depends, HTTPException,
    Query, BackgroundTasks
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from config import settings
from database.db import create_tables, get_db, Invoice, AgentAction, ChatHistory, User
from models.schemas import (
    ChatRequest, ChatResponse, InvoiceResponse,
    AnalyticsSummary, UserCreate, UserLogin, Token
)
from modules.ocr import ocr_engine
from modules.extraction import extraction_engine
from modules.validation import validation_engine
from modules.embeddings import embedding_store
from modules.rag import rag_engine
from modules.agents import invoice_agent
from utils.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, create_demo_admin, require_role
)

# ──────────────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
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


@app.on_event("startup")
def startup():
    create_tables()
    db = next(get_db())
    create_demo_admin(db)
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info("✅ Invoice AI System started.")


# ──────────────────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────────────────

@app.post("/api/auth/register", tags=["Auth"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already exists")
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully", "username": data.username}


@app.post("/api/auth/login", response_model=Token, tags=["Auth"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username, User.is_active == True).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@app.get("/api/auth/me", tags=["Auth"])
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}


# ──────────────────────────────────────────────────────
# INVOICE ROUTES
# ──────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


@app.post("/api/upload", tags=["Invoice"])
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # user: User = Depends(get_current_user),  # Uncomment to require auth
):
    """Upload an invoice file (PDF/image) and trigger background processing."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    if file.size and file.size > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(400, f"File too large. Max size: {settings.max_file_size_mb}MB")

    # Save file
    invoice_id = str(uuid.uuid4())
    save_name = f"{invoice_id}{ext}"
    save_path = os.path.join(settings.upload_dir, save_name)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create DB record
    invoice = Invoice(id=invoice_id, filename=file.filename, file_path=save_path)
    db.add(invoice)
    db.commit()

    # Background processing
    background_tasks.add_task(process_invoice, invoice_id, save_path, db)

    return {
        "invoice_id": invoice_id,
        "filename": file.filename,
        "status": "uploaded",
        "message": "Invoice is being processed. Check /api/invoice/{id} for results.",
    }


@app.post("/api/extract/{invoice_id}", tags=["Invoice"])
def extract_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """Manually trigger extraction for an already-uploaded invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    process_invoice(invoice_id, invoice.file_path, db)
    db.refresh(invoice)
    return invoice.to_dict()


@app.get("/api/invoice/{invoice_id}", tags=["Invoice"])
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
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
):
    query = db.query(Invoice)
    if vendor:
        query = query.filter(Invoice.vendor_name.ilike(f"%{vendor}%"))
    if status:
        query = query.filter(Invoice.validation_status == status)

    total = query.count()
    invoices = query.order_by(desc(Invoice.upload_time)).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "invoices": [inv.to_dict() for inv in invoices],
    }


@app.delete("/api/invoice/{invoice_id}", tags=["Invoice"])
def delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    # user: User = Depends(require_role("admin")),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    # Remove file
    if invoice.file_path and os.path.exists(invoice.file_path):
        os.remove(invoice.file_path)

    # Remove embedding
    embedding_store.delete_embedding(invoice_id)

    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted", "id": invoice_id}


# ──────────────────────────────────────────────────────
# VALIDATE ROUTE
# ──────────────────────────────────────────────────────

@app.get("/api/validate/{invoice_id}", tags=["Validation"])
def validate_invoice(invoice_id: str, db: Session = Depends(get_db)):
    """Re-run validation on an existing invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    from models.schemas import InvoiceExtraction
    extraction = InvoiceExtraction(
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        vendor_gstin=invoice.vendor_gstin,
        buyer_name=invoice.buyer_name,
        buyer_gstin=invoice.buyer_gstin,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        total_amount=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        subtotal=invoice.subtotal,
    )
    result = validation_engine.validate(extraction, db, invoice_id)

    invoice.validation_status = "valid" if result.is_valid else "invalid"
    invoice.validation_errors = result.errors + result.warnings
    invoice.is_duplicate = result.is_duplicate
    invoice.duplicate_of = result.duplicate_of
    db.commit()

    return result.dict()


# ──────────────────────────────────────────────────────
# RAG / CHAT ROUTES
# ──────────────────────────────────────────────────────

@app.post("/api/query", response_model=ChatResponse, tags=["RAG"])
def chat_query(request: ChatRequest, db: Session = Depends(get_db)):
    """Natural language query over all processed invoices."""
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")

    result = rag_engine.query(request.question, db)

    # Save to history
    history = ChatHistory(
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


@app.get("/api/chat-history", tags=["RAG"])
def get_chat_history(limit: int = 50, db: Session = Depends(get_db)):
    history = (
        db.query(ChatHistory)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
        .all()
    )
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
):
    query = db.query(AgentAction)
    if status:
        query = query.filter(AgentAction.action_status == status)
    if invoice_id:
        query = query.filter(AgentAction.invoice_id == invoice_id)
    actions = query.order_by(desc(AgentAction.created_at)).limit(100).all()
    return [a.to_dict() for a in actions]


@app.post("/api/agent-action/{action_id}/resolve", tags=["Agents"])
def resolve_action(action_id: str, db: Session = Depends(get_db)):
    result = invoice_agent.resolve_action(action_id, db)
    if not result:
        raise HTTPException(404, "Action not found")
    return result


# ──────────────────────────────────────────────────────
# ANALYTICS ROUTES
# ──────────────────────────────────────────────────────

@app.get("/api/analytics", tags=["Analytics"])
def get_analytics(db: Session = Depends(get_db)):
    total = db.query(func.count(Invoice.id)).scalar() or 0
    total_amount = db.query(func.sum(Invoice.total_amount)).scalar() or 0.0
    valid = db.query(func.count(Invoice.id)).filter(Invoice.validation_status == "valid").scalar() or 0
    invalid = db.query(func.count(Invoice.id)).filter(Invoice.validation_status == "invalid").scalar() or 0
    duplicates = db.query(func.count(Invoice.id)).filter(Invoice.is_duplicate == True).scalar() or 0
    pending = db.query(func.count(Invoice.id)).filter(Invoice.validation_status == "pending").scalar() or 0

    # Top vendors
    top_vendors_raw = (
        db.query(Invoice.vendor_name, func.sum(Invoice.total_amount).label("total"))
        .filter(Invoice.vendor_name.isnot(None))
        .group_by(Invoice.vendor_name)
        .order_by(desc("total"))
        .limit(5)
        .all()
    )
    top_vendors = [{"vendor": v, "total": round(t or 0, 2)} for v, t in top_vendors_raw]

    # Monthly spend (last 6 months)
    from sqlalchemy import extract
    monthly_raw = (
        db.query(
            extract("year", Invoice.upload_time).label("year"),
            extract("month", Invoice.upload_time).label("month"),
            func.sum(Invoice.total_amount).label("total"),
        )
        .filter(Invoice.total_amount.isnot(None))
        .group_by("year", "month")
        .order_by("year", "month")
        .limit(6)
        .all()
    )
    monthly_spend = [
        {"year": int(y), "month": int(m), "total": round(t or 0, 2)}
        for y, m, t in monthly_raw
    ]

    return {
        "total_invoices": total,
        "total_amount": round(total_amount, 2),
        "valid_invoices": valid,
        "invalid_invoices": invalid,
        "duplicate_invoices": duplicates,
        "pending_invoices": pending,
        "top_vendors": top_vendors,
        "monthly_spend": monthly_spend,
    }


# ──────────────────────────────────────────────────────
# BACKGROUND PROCESSING PIPELINE
# ──────────────────────────────────────────────────────

def process_invoice(invoice_id: str, file_path: str, db: Session):
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
        invoice.buyer_name = extraction.buyer_name
        invoice.buyer_gstin = extraction.buyer_gstin
        invoice.invoice_date = extraction.invoice_date
        invoice.due_date = extraction.due_date
        invoice.total_amount = extraction.total_amount
        invoice.tax_amount = extraction.tax_amount
        invoice.subtotal = extraction.subtotal
        invoice.currency = extraction.currency
        invoice.line_items = [item.dict() for item in extraction.line_items]
        invoice.raw_extraction = extraction.dict()
        invoice.extraction_status = "success"

        # Step 3: Validation
        logger.info(f"[{invoice_id}] Running validation...")
        validation_result = validation_engine.validate(extraction, db, invoice_id)
        invoice.validation_status = "valid" if validation_result.is_valid else "invalid"
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

    finally:
        invoice.processing_time_ms = int((time.time() - start) * 1000)
        db.commit()
        logger.info(f"[{invoice_id}] Processing complete in {invoice.processing_time_ms}ms")


# ──────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "openai": bool(settings.openai_api_key),
        "pinecone": bool(settings.pinecone_api_key),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
