"""
Validation & Compliance Engine
Checks: required fields, GST format, amount consistency, duplicates
"""
import re
import logging
from typing import Optional
from sqlalchemy.orm import Session

from models.schemas import InvoiceExtraction, ValidationResult

logger = logging.getLogger(__name__)

# Indian GSTIN regex: 2 digits + 5 alpha + 4 digits + 1 alpha + 1 alphanumeric + Z + 1 alphanumeric
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

HIGH_VALUE_THRESHOLD = 100_000  # ₹1 lakh


class ValidationEngine:

    # ──────────────────────────────────────────
    # Main Validate
    # ──────────────────────────────────────────

    def validate(
        self,
        extraction: InvoiceExtraction,
        db: Session,
        current_invoice_id: Optional[str] = None,
    ) -> ValidationResult:
        errors = []
        warnings = []

        # 1. Required fields
        errors += self._check_required_fields(extraction)

        # 2. GSTIN format
        errors += self._check_gstin(extraction.vendor_gstin, "Vendor GSTIN")
        if extraction.buyer_gstin:
            errors += self._check_gstin(extraction.buyer_gstin, "Buyer GSTIN")

        # 3. Amount consistency
        warnings += self._check_amount_consistency(extraction)

        # 4. Date validity
        warnings += self._check_dates(extraction)

        # 5. Duplicate detection
        duplicate_id = self._check_duplicate(extraction, db, current_invoice_id)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            is_duplicate=duplicate_id is not None,
            duplicate_of=duplicate_id,
        )

    # ──────────────────────────────────────────
    # Validators
    # ──────────────────────────────────────────

    def _check_required_fields(self, e: InvoiceExtraction) -> list[str]:
        errors = []
        required = {
            "invoice_number": e.invoice_number,
            "vendor_name": e.vendor_name,
            "invoice_date": e.invoice_date,
            "total_amount": e.total_amount,
        }
        for field, value in required.items():
            if not value:
                errors.append(f"Missing required field: {field.replace('_', ' ').title()}")
        return errors

    def _check_gstin(self, gstin: Optional[str], label: str) -> list[str]:
        if not gstin:
            return [f"{label} is missing"]
        gstin_clean = gstin.strip().upper()
        if not GSTIN_PATTERN.match(gstin_clean):
            return [f"{label} '{gstin}' is not a valid Indian GSTIN format"]
        return []

    def _check_amount_consistency(self, e: InvoiceExtraction) -> list[str]:
        warnings = []
        if e.subtotal and e.tax_amount and e.total_amount:
            expected = round(e.subtotal + e.tax_amount, 2)
            actual = round(e.total_amount, 2)
            if abs(expected - actual) > 1.0:  # tolerance of ₹1
                warnings.append(
                    f"Amount mismatch: Subtotal ({e.subtotal}) + Tax ({e.tax_amount}) = "
                    f"{expected}, but Total = {actual}"
                )
        if e.total_amount and e.total_amount < 0:
            warnings.append("Total amount is negative – please verify.")
        return warnings

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

    def _check_duplicate(
        self,
        e: InvoiceExtraction,
        db: Session,
        current_id: Optional[str],
    ) -> Optional[str]:
        """Check for duplicate invoice based on invoice_number + vendor_name."""
        from database.db import Invoice

        if not e.invoice_number or not e.vendor_name:
            return None

        query = (
            db.query(Invoice)
            .filter(
                Invoice.invoice_number == e.invoice_number,
                Invoice.vendor_name == e.vendor_name,
                Invoice.extraction_status == "success",
            )
        )
        if current_id:
            query = query.filter(Invoice.id != current_id)

        existing = query.first()
        return existing.id if existing else None

    # ──────────────────────────────────────────
    # High-Value Check (for agent trigger)
    # ──────────────────────────────────────────

    def is_high_value(self, total_amount: Optional[float]) -> bool:
        return bool(total_amount and total_amount >= HIGH_VALUE_THRESHOLD)


validation_engine = ValidationEngine()
