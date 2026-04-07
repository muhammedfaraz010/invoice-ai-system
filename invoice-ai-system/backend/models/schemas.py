from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


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
    duplicate_of: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: str
    filename: str
    upload_time: str
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    vendor_gstin: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[float]
    tax_amount: Optional[float]
    currency: str
    extraction_status: str
    validation_status: str
    validation_errors: Optional[Any]
    is_duplicate: bool
    embedding_stored: bool
    processing_time_ms: Optional[int]


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
