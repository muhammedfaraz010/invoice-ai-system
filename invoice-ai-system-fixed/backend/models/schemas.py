from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


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
    vendor_vat: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_gstin: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    payment_method: Optional[str] = None
    subtotal: Optional[float] = None
    currency: str = "INR"
    line_items: List[LineItem] = Field(default_factory=list)


class ValidationResult(BaseModel):
    is_valid: bool
    status: str = "needs_review"
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    missing_optional: List[str] = Field(default_factory=list)
    required_score: int = 0
    optional_score: int = 0
    extraction_score: int = 0
    ai_confidence: int = 98
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: str
    filename: Optional[str]
    upload_time: Optional[str]
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[float]
    currency: str
    extraction_status: Optional[str]
    validation_status: Optional[str]
    validation_summary: Optional[dict] = None
    missing_required_fields: List[str] = Field(default_factory=list)
    missing_optional_fields: List[str] = Field(default_factory=list)
    required_score: int = 0
    optional_score: int = 0
    extraction_score: int = 0
    ai_confidence: int = 0
    is_duplicate: bool
    embedding_stored: bool


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict] = Field(default_factory=list)
    session_id: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_invoices: int
    total_amount: float
    verified_invoices: int = 0
    complete_invoices: int = 0
    needs_review_invoices: int = 0
    failed_invoices: int = 0
    average_extraction_score: int = 0
    average_ai_confidence: int = 0
    valid_invoices: int
    invalid_invoices: int
    duplicate_invoices: int
    pending_invoices: int
    top_vendors: List[dict]
    monthly_spend: List[dict]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1)
    email: EmailStr
    full_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str
    role: str
    status: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


class UserAdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserStatusUpdate(BaseModel):
    status: str


class DeleteRequestCreate(BaseModel):
    invoice_id: str
    reason: Optional[str] = None


class DeleteDecision(BaseModel):
    request_id: str


class DeleteUserRequestCreate(BaseModel):
    user_id: str
    reason: Optional[str] = None


class DeleteUserDecision(BaseModel):
    request_id: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserProfile
