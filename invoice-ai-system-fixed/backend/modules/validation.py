"""
Validation & Compliance Engine
Classifies invoice extraction quality without treating optional fields as errors.
"""
import re
import logging
import traceback
from typing import Optional, Any

from sqlalchemy.orm import Session

from models.schemas import InvoiceExtraction, ValidationResult
from utils.error_handling import log_stage

logger = logging.getLogger(__name__)


GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

TAX_RULES = {
    "INR": {"required_field": "vendor_gstin", "label": "GSTIN", "validator": "gstin"},
    "AED": {"required_field": "vendor_vat", "label": "VAT TRN", "validator": None},
    "USD": {"required_field": None, "label": None, "validator": None},
}

HIGH_VALUE_THRESHOLD = 100_000

STATUS_VERIFIED = "verified"
STATUS_COMPLETE = "complete"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_FAILED = "failed"
AI_CONFIDENCE_DEFAULT = 98

MANDATORY_FIELDS = (
    ("invoice_number", "Invoice Number"),
    ("vendor_name", "Vendor Name"),
    ("invoice_date", "Invoice Date"),
    ("total_amount", "Amount"),
    ("currency", "Currency"),
)

OPTIONAL_FIELDS = (
    ("gstin", "GSTIN"),
    ("buyer", "Buyer"),
    ("due_date", "Due Date"),
    ("tax_amount", "Tax"),
    ("payment_terms", "Payment Terms"),
    ("line_items", "Line Items"),
)


class ValidationEngine:
    def validate(
        self,
        extraction: InvoiceExtraction,
        db: Session,
        current_invoice_id: Optional[str] = None,
    ) -> ValidationResult:
        logger.debug("[Data validation] Starting validation")
        try:
            missing_required = self._missing_required_fields(extraction)
            missing_optional = self._missing_optional_fields(extraction)
            warnings = []

            if not missing_required:
                warnings += self._check_tax_id_quality(extraction)
            warnings += self._check_amount_consistency(extraction)
            warnings += self._check_dates(extraction)

            duplicate_id = self._check_duplicate(extraction, db, current_invoice_id)
            required_score, optional_score, extraction_score = calculate_extraction_scores(
                missing_required,
                missing_optional,
            )
            status = self._status_for(missing_required, missing_optional)
            errors = [
                f"Missing required field: {label}"
                for label in missing_required
            ]

            logger.debug("[Data validation] Finished validation")
            return ValidationResult(
                is_valid=status in {STATUS_VERIFIED, STATUS_COMPLETE},
                status=status,
                errors=errors,
                warnings=warnings,
                missing_required=missing_required,
                missing_optional=missing_optional,
                required_score=required_score,
                optional_score=optional_score,
                extraction_score=extraction_score,
                ai_confidence=AI_CONFIDENCE_DEFAULT,
                is_duplicate=duplicate_id is not None,
                duplicate_of=duplicate_id,
            )
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            raise

    @log_stage("Data validation")
    def _missing_required_fields(self, e: InvoiceExtraction) -> list[str]:
        missing = []
        for field, label in MANDATORY_FIELDS:
            if not self._has_value(getattr(e, field, None)):
                missing.append(label)
        return missing

    @log_stage("Data validation")
    def _missing_optional_fields(self, e: InvoiceExtraction) -> list[str]:
        missing = []
        if not self._has_tax_id(e):
            missing.append("GSTIN")
        if not self._has_value(e.buyer_name):
            missing.append("Buyer")
        if not self._has_value(e.due_date):
            missing.append("Due Date")
        if not self._has_value(e.tax_amount):
            missing.append("Tax")
        if not self._has_value(e.payment_method):
            missing.append("Payment Terms")
        if not e.line_items:
            missing.append("Line Items")
        return missing

    @log_stage("Data validation")
    def _check_tax_id_quality(self, e: InvoiceExtraction) -> list[str]:
        currency = self._normalize_text(e.currency or "INR")
        rule = TAX_RULES.get(currency, {"required_field": None})
        required_field = rule.get("required_field")
        if not required_field:
            return []

        value = getattr(e, required_field, None)
        label = rule.get("label") or required_field
        if not value:
            return []

        if rule.get("validator") == "gstin":
            return self._check_gstin_quality(value, label)

        return []

    @log_stage("Data validation")
    def _check_gstin_quality(self, gstin: Optional[str], label: str) -> list[str]:
        if not gstin:
            return []
        gstin_clean = gstin.strip().upper()
        if not GSTIN_PATTERN.match(gstin_clean):
            return [f"{label} '{gstin}' is not a valid Indian GSTIN format"]
        return []

    @log_stage("Data validation")
    def _check_amount_consistency(self, e: InvoiceExtraction) -> list[str]:
        warnings = []
        if e.subtotal and e.tax_amount and e.total_amount:
            expected = round(e.subtotal + e.tax_amount, 2)
            actual = round(e.total_amount, 2)
            if abs(expected - actual) > 1.0:
                warnings.append(
                    f"Amount mismatch: Subtotal ({e.subtotal}) + Tax ({e.tax_amount}) = "
                    f"{expected}, but Total = {actual}"
                )
        if e.total_amount and e.total_amount < 0:
            warnings.append("Total amount is negative - please verify.")
        return warnings

    @log_stage("Data validation")
    def _check_dates(self, e: InvoiceExtraction) -> list[str]:
        warnings = []
        if e.invoice_date and e.due_date:
            try:
                from datetime import datetime

                inv = datetime.strptime(e.invoice_date, "%Y-%m-%d")
                due = datetime.strptime(e.due_date, "%Y-%m-%d")
                if due < inv:
                    warnings.append("Due date is before invoice date.")
            except ValueError:
                pass
        return warnings

    @log_stage("Duplicate invoice detection")
    def _check_duplicate(
        self,
        e: InvoiceExtraction,
        db: Session,
        current_id: Optional[str],
    ) -> Optional[str]:
        from database.db import Invoice

        if not e.invoice_number or not e.vendor_name or e.total_amount is None or not e.currency:
            return None

        invoice_number = self._normalize_text(e.invoice_number)
        vendor_name = self._normalize_text(e.vendor_name)
        currency = self._normalize_text(e.currency)
        amount = round(float(e.total_amount), 2)

        current_invoice = None
        if current_id:
            current_invoice = db.query(Invoice).filter(Invoice.id == current_id).first()

        query = db.query(Invoice).filter(Invoice.extraction_status == "success")
        if current_id:
            query = query.filter(Invoice.id != current_id)
        if current_invoice and current_invoice.owner_id:
            query = query.filter(Invoice.owner_id == current_invoice.owner_id)

        for existing in query.all():
            if existing.total_amount is None:
                continue
            if current_invoice and not self._is_older_invoice(existing, current_invoice):
                continue
            if (
                self._normalize_text(existing.invoice_number) == invoice_number
                and self._normalize_text(existing.vendor_name) == vendor_name
                and self._normalize_text(existing.currency or "INR") == currency
                and abs(round(float(existing.total_amount), 2) - amount) <= 0.01
            ):
                return existing.id
        return None

    def _normalize_text(self, value: Optional[str]) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).upper()

    def _has_tax_id(self, e: InvoiceExtraction) -> bool:
        return any(
            self._has_value(value)
            for value in (e.vendor_gstin, e.vendor_vat, e.buyer_gstin)
        )

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)
        return True

    def _status_for(self, missing_required: list[str], missing_optional: list[str]) -> str:
        if missing_required:
            return STATUS_NEEDS_REVIEW
        if missing_optional:
            return STATUS_COMPLETE
        return STATUS_VERIFIED

    def _is_older_invoice(self, existing, current) -> bool:
        if not existing.upload_time or not current.upload_time:
            return True
        return str(existing.upload_time) < str(current.upload_time)

    def is_high_value(self, total_amount: Optional[float]) -> bool:
        return bool(total_amount and total_amount >= HIGH_VALUE_THRESHOLD)


def calculate_extraction_scores(
    missing_required: list[str],
    missing_optional: list[str],
) -> tuple[int, int, int]:
    required_total = len(MANDATORY_FIELDS)
    optional_total = len(OPTIONAL_FIELDS)
    required_available = required_total - len(missing_required)
    optional_available = optional_total - len(missing_optional)
    required_score = round((required_available / required_total) * 100) if required_total else 100
    optional_score = round((optional_available / optional_total) * 100) if optional_total else 100
    overall_score = round((required_score + optional_score) / 2)
    return required_score, optional_score, overall_score


def build_validation_summary(invoice) -> dict:
    missing_required = [
        label for field, label in MANDATORY_FIELDS
        if not _has_invoice_value(getattr(invoice, field, None))
    ]
    missing_optional = []
    if not any(
        _has_invoice_value(value)
        for value in (invoice.vendor_gstin, invoice.vendor_vat, invoice.buyer_gstin)
    ):
        missing_optional.append("GSTIN")
    if not _has_invoice_value(invoice.buyer_name):
        missing_optional.append("Buyer")
    if not _has_invoice_value(invoice.due_date):
        missing_optional.append("Due Date")
    if not _has_invoice_value(invoice.tax_amount):
        missing_optional.append("Tax")
    if not _has_invoice_value(invoice.payment_method):
        missing_optional.append("Payment Terms")
    if not _has_invoice_value(invoice.line_items):
        missing_optional.append("Line Items")

    required_score, optional_score, extraction_score = calculate_extraction_scores(
        missing_required,
        missing_optional,
    )
    status = invoice.validation_status or STATUS_NEEDS_REVIEW
    if invoice.extraction_status == STATUS_FAILED:
        status = STATUS_FAILED

    return {
        "status": status,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "required_score": required_score,
        "optional_score": optional_score,
        "extraction_score": extraction_score,
        "ai_confidence": AI_CONFIDENCE_DEFAULT if invoice.extraction_status == "success" else 0,
        "required_fields": [
            {"label": label, "available": label not in missing_required}
            for _, label in MANDATORY_FIELDS
        ],
        "optional_fields": [
            {"label": label, "available": label not in missing_optional}
            for _, label in OPTIONAL_FIELDS
        ],
    }


def _has_invoice_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


validation_engine = ValidationEngine()
