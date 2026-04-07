from sqlalchemy import (
    create_engine, Column, String, Float, DateTime,
    Boolean, Text, Integer, JSON, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

from config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────────────────────────
# DB Models
# ──────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String)
    upload_time = Column(DateTime, default=datetime.utcnow)

    # Extracted fields
    invoice_number = Column(String, index=True)
    vendor_name = Column(String, index=True)
    vendor_gstin = Column(String)
    buyer_name = Column(String)
    buyer_gstin = Column(String)
    invoice_date = Column(String)
    due_date = Column(String)
    total_amount = Column(Float)
    tax_amount = Column(Float)
    subtotal = Column(Float)
    currency = Column(String, default="INR")
    line_items = Column(JSON)

    # Status
    ocr_text = Column(Text)
    extraction_status = Column(String, default="pending")  # pending/success/failed
    validation_status = Column(String, default="pending")  # pending/valid/invalid
    validation_errors = Column(JSON)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String, ForeignKey("invoices.id"), nullable=True)
    embedding_stored = Column(Boolean, default=False)

    # Metadata
    raw_extraction = Column(JSON)
    processing_time_ms = Column(Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "upload_time": str(self.upload_time),
            "invoice_number": self.invoice_number,
            "vendor_name": self.vendor_name,
            "vendor_gstin": self.vendor_gstin,
            "buyer_name": self.buyer_name,
            "buyer_gstin": self.buyer_gstin,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "total_amount": self.total_amount,
            "tax_amount": self.tax_amount,
            "subtotal": self.subtotal,
            "currency": self.currency,
            "line_items": self.line_items,
            "extraction_status": self.extraction_status,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "embedding_stored": self.embedding_stored,
            "processing_time_ms": self.processing_time_ms,
        }


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="viewer")  # admin/finance/viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String, ForeignKey("invoices.id"))
    action_type = Column(String)          # duplicate_alert / missing_gst / high_value_approval
    action_status = Column(String, default="triggered")   # triggered/resolved/dismissed
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "action_type": self.action_type,
            "action_status": self.action_status,
            "message": self.message,
            "created_at": str(self.created_at),
        }


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    sources = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# DB Utilities
# ──────────────────────────────────────────────

def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
