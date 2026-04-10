# ================== Pydantic Models ==================

from pydantic import BaseModel
from typing import Optional, List, Any


class LineItem(BaseModel):
    description: str = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    tax_rate: Optional[float] = None


class InvoiceExtraction(BaseModel):
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_gstin: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_gstin: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    currency: str = "INR"
    line_items: List[LineItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    is_duplicate: bool = False
    duplicate_of: Optional[int] = None   # ✅ FIXED TYPE


class InvoiceResponse(BaseModel):
    id: int
    filename: Optional[str]
    upload_time: Optional[str]
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[float]
    currency: str
    extraction_status: Optional[str]
    validation_status: Optional[str]
    is_duplicate: bool
    embedding_stored: bool


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict] = []
    session_id: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_invoices: int
    total_amount: float
    valid_invoices: int
    invalid_invoices: int
    duplicate_invoices: int
    pending_invoices: int
    top_vendors: List[dict]
    monthly_spend: List[dict]


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ================== SQLAlchemy Model ==================

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON
from database.db import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String)
    file_path = Column(String)
    upload_time = Column(String)

    invoice_number = Column(String)
    vendor_name = Column(String)
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

    ocr_text = Column(String)

    extraction_status = Column(String, default="pending")
    validation_status = Column(String, default="pending")

    validation_errors = Column(JSON)

    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(Integer)   # ✅ FIXED HERE

    embedding_stored = Column(Boolean, default=False)
    raw_extraction = Column(JSON)

    processing_time_ms = Column(Integer)