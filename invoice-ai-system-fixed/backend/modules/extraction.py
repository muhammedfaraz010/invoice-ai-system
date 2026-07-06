"""
NLP / LLM Extraction Engine.
Uses Groq to extract structured invoice data from raw OCR text.
"""
import json
import logging
import re
import traceback
from typing import Optional

from config import settings
from models.schemas import InvoiceExtraction, LineItem
from utils.error_handling import ProcessingStageError, log_stage

logger = logging.getLogger(__name__)

try:
    from groq import Groq
except ImportError:  # pragma: no cover - depends on local environment
    Groq = None


EXTRACTION_PROMPT = """
You are a highly intelligent invoice extraction system.

Your task:
Extract correct invoice details from OCR text of ANY invoice. The text may be
messy, scanned, unstructured, or contain multiple values.

Return JSON:
{
  "invoice_number": null,
  "vendor_name": null,
  "invoice_date": null,
  "total_amount": null,
  "currency": null
}

Strict extraction rules:
1. invoice_number:
   Look for Invoice ID, Invoice No, Invoice #, Bill No, or Receipt No.
2. vendor_name:
   Usually the first meaningful line. Use the company, shop, or hospital name.
   Ignore phone numbers, emails, customer names, and generic labels.
3. invoice_date:
   Use invoice/bill date only. Ignore pickup, return, due, booking, delivery,
   and service dates.
4. total_amount:
   Choose only one value. Prefer TOTAL PAYABLE, GRAND TOTAL, or NET AMOUNT.
   Ignore PAID AMOUNT, BALANCE, BALANCE DUE, SUBTOTAL, PRODUCT COST, TAX,
   and deposit lines.
5. currency:
   Map rupee symbols, Rs, and INR to INR; dollar symbols and USD to USD; AED to
   AED.

Logic rules:
- If multiple amounts exist, choose the final payable amount.
- If multiple dates exist, choose invoice date.
- If no vendor label exists, take the first meaningful top line.
- Clean numbers by removing commas and currency symbols.
- Never return an empty object.
- If a field is missing, return null.
- Return only valid JSON. Do not include markdown or explanation.

OCR text:
{ocr_text}
"""


class ExtractionEngine:
    def __init__(self):
        if settings.groq_api_key and Groq:
            self.client = Groq(api_key=settings.groq_api_key)
        else:
            self.client = None
            logger.warning("Groq client unavailable; extraction will use fallback regex.")

    @log_stage("LLM")
    def extract(self, ocr_text: str) -> InvoiceExtraction:
        if not ocr_text or not ocr_text.strip():
            raise ProcessingStageError("OCR", "No readable text found in invoice.")

        if self.client:
            try:
                return self._extract_with_llm(ocr_text)
            except ProcessingStageError as exc:
                logger.exception("LLM extraction failed; falling back to regex extraction: %s", exc)
                traceback.print_exc()
        return self._extract_with_regex(ocr_text)

    @log_stage("LLM", "LLM request failed")
    def _extract_with_llm(self, ocr_text: str) -> InvoiceExtraction:
        prompt = EXTRACTION_PROMPT.replace("{ocr_text}", ocr_text[:4000])

        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return valid JSON only. Never return an empty object.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_completion_tokens=800,
                response_format={"type": "json_object"},
            )

            raw_json = response.choices[0].message.content
            extraction = self._parse_json_to_schema(raw_json, source_text=ocr_text)
        except Exception as exc:
            logger.exception(exc)
            traceback.print_exc()
            raise ProcessingStageError("LLM", "LLM request failed", str(exc)) from exc

        fallback = self._extract_with_regex(ocr_text)
        return self._merge_extractions(extraction, fallback)

    @log_stage("AI extraction")
    def _extract_with_regex(self, text: str) -> InvoiceExtraction:
        logger.info("Using regex fallback extraction.")

        invoice_number = self._find(
            [
                r"(?:invoice|bill|receipt)\s*(?:id|no|number|#)[:\s]*([A-Z0-9\-/]+)",
                r"inv\s*(?:no|#)[:\s]*([A-Z0-9\-/]+)",
            ],
            text,
        )
        vendor_name = self._clean_vendor_name(self._find(
            [
                r"(?:from|seller|vendor|billed by)[: \t]*([A-Za-z0-9 \t&.,'-]+?)(?:\n|GSTIN|GST|VAT|TRN)",
                r"^[ \t]*([A-Z][A-Za-z0-9 \t&.,'-]{3,60})[ \t]*$",
            ],
            text,
        ))
        gstin = self._find(
            [r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b"],
            text,
        )
        vendor_vat = self._find(
            [
                r"(?:TRN|VAT\s*(?:TRN|No|Number)?)[:\s]*([0-9]{10,20})",
                r"\b([0-9]{15})\b",
            ],
            text,
        )
        invoice_date = self._find_invoice_date(text)

        currency = self._detect_currency(text)
        currency_pattern = r"(?:Rs\.?|INR|USD|US\$|\$|AED|Dhs\.?|Dirhams?|EUR|GBP|\u20b9)?"
        total = self._find_total_amount(text, currency_pattern)
        tax = self._find_tax_amount(text, currency_pattern)
        payment_method = self._find_payment_method(text)

        return InvoiceExtraction(
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            vendor_gstin=gstin,
            vendor_vat=vendor_vat,
            invoice_date=self._normalize_date(invoice_date),
            total_amount=self._to_float(total),
            tax_amount=self._to_float(tax),
            payment_method=payment_method,
            currency=currency,
        )

    @log_stage("AI extraction", "Unable to parse invoice data")
    def _parse_json_to_schema(self, raw_json: str, source_text: str = "") -> InvoiceExtraction:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.exception(exc)
            traceback.print_exc()
            raise ValueError(f"LLM returned invalid JSON: {exc}")

        if not isinstance(data, dict) or not data:
            raise ValueError("LLM returned empty or non-object JSON.")

        line_items = []
        raw_items = data.get("items") or data.get("line_items") or []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = self._pick(item, "name", "description", default="")
            line_items.append(
                LineItem(
                    description=name or "",
                    quantity=self._to_float(item.get("quantity")),
                    unit_price=self._to_float(item.get("unit_price")),
                    amount=self._to_float(self._pick(item, "price", "amount")),
                    tax_rate=self._to_float(item.get("tax_rate")),
                )
            )

        return InvoiceExtraction(
            invoice_number=self._clean_text(data.get("invoice_number")),
            vendor_name=self._clean_vendor_name(data.get("vendor_name")),
            vendor_gstin=self._clean_text(data.get("vendor_gstin")),
            vendor_vat=self._clean_text(data.get("vendor_vat")),
            buyer_name=self._clean_text(data.get("buyer_name")),
            buyer_gstin=self._clean_text(data.get("buyer_gstin")),
            invoice_date=self._normalize_date(data.get("invoice_date")),
            due_date=self._normalize_date(data.get("due_date")),
            total_amount=self._to_float(data.get("total_amount")),
            tax_amount=self._to_float(data.get("tax_amount")),
            payment_method=self._clean_payment_method(data.get("payment_method")),
            subtotal=self._to_float(data.get("subtotal")),
            currency=self._normalize_currency(data.get("currency")) or self._detect_currency(source_text or raw_json),
            line_items=line_items,
        )

    @log_stage("AI extraction")
    def _merge_extractions(self, primary: InvoiceExtraction, fallback: InvoiceExtraction) -> InvoiceExtraction:
        data = primary.dict()
        fallback_data = fallback.dict()
        for field in (
            "invoice_number",
            "vendor_name",
            "invoice_date",
            "total_amount",
            "currency",
            "tax_amount",
            "payment_method",
            "vendor_gstin",
            "vendor_vat",
        ):
            if data.get(field) in (None, "", []):
                data[field] = fallback_data.get(field)

        if not any(data.get(field) not in (None, "", []) for field in ("invoice_number", "vendor_name", "invoice_date", "total_amount")):
            logger.warning("LLM returned no core fields; using regex fallback extraction.")
            return fallback

        return InvoiceExtraction(**data)

    def _find(self, patterns: list[str], text: str) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None

    def _find_invoice_date(self, text: str) -> Optional[str]:
        date_value = r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})"
        preferred = re.search(
            rf"(?:invoice\s*date|bill\s*date|issued\s*date|receipt\s*date|^date)[:\s]*{date_value}",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if preferred:
            return preferred.group(1)

        ignored_labels = re.compile(r"\b(pickup|return|due|booking|delivery|service)\b", re.IGNORECASE)
        for line in text.splitlines():
            if ignored_labels.search(line):
                continue
            match = re.search(date_value, line)
            if match:
                return match.group(1)
        return None

    def _find_total_amount(self, text: str, currency_pattern: str) -> Optional[str]:
        preferred_labels = r"total\s*payable|grand\s*total|net\s*amount"
        preferred = self._amounts_for_labels(text, preferred_labels, currency_pattern)
        if preferred:
            return preferred[-1]

        secondary_labels = r"amount\s*payable|amount\s*due|total\s*due|total\s*amount|total"
        secondary = self._amounts_for_labels(text, secondary_labels, currency_pattern)
        if secondary:
            return secondary[-1]

        ignored = re.compile(
            r"\b(paid\s*amount|balance(?:\s*due)?|subtotal|sub\s*total|product\s*cost|tax|gst|vat|deposit)\b",
            re.IGNORECASE,
        )
        candidates = []
        for line in text.splitlines():
            if ignored.search(line):
                continue
            amounts = re.findall(rf"{currency_pattern}\s*([\d,]+(?:\.\d+)?)", line, re.IGNORECASE)
            candidates.extend(amounts)

        parsed = [(amount, self._to_float(amount)) for amount in candidates]
        parsed = [(amount, value) for amount, value in parsed if value is not None]
        if not parsed:
            return None

        return max(parsed, key=lambda item: item[1])[0]

    def _amounts_for_labels(self, text: str, labels: str, currency_pattern: str) -> list[str]:
        amount_pattern = r"([\d,]+(?:\.\d+)?)"
        patterns = [
            rf"(?:{labels})[:\s]*{currency_pattern}\s*{amount_pattern}",
            rf"(?:{labels})[:\s]*{amount_pattern}\s*{currency_pattern}",
        ]
        amounts = []
        for pattern in patterns:
            amounts.extend(re.findall(pattern, text, re.IGNORECASE))
        return [amount for amount in amounts if amount]

    def _find_tax_amount(self, text: str, currency_pattern: str) -> Optional[str]:
        tax_labels = r"tax|gst|vat|cgst|sgst|igst"
        matches = re.findall(
            rf"(?:{tax_labels})[:\s]*{currency_pattern}\s*([\d,]+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if matches:
            return matches[-1]
        return None

    def _find_payment_method(self, text: str) -> Optional[str]:
        labelled = self._find(
            [
                r"(?:payment\s*method|mode\s*of\s*payment|payment\s*mode|paid\s*via)[:\s]*([A-Za-z0-9\s\-_/]+)",
            ],
            text,
        )
        cleaned = self._clean_payment_method(labelled)
        if cleaned:
            return cleaned

        return self._find(
            [
                r"\b(cash|credit card|debit card|card|upi|gpay|google pay|phonepe|paytm|wallet|net banking|bank transfer|cheque)\b",
            ],
            text,
        )

    def _pick(self, data: dict, *keys: str, default=None):
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        return default

    def _clean_text(self, value) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _clean_vendor_name(self, value) -> Optional[str]:
        cleaned = self._clean_text(value)
        if not cleaned:
            return None

        generic_headers = {
            "invoice",
            "tax invoice",
            "bill",
            "receipt",
            "click to edit",
            "original",
            "duplicate",
        }
        normalized = re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()
        if normalized in generic_headers or "click to edit" in normalized:
            return None
        return cleaned

    def _clean_payment_method(self, value) -> Optional[str]:
        cleaned = self._clean_text(value)
        if not cleaned:
            return None
        if not re.search(
            r"\b(cash|card|credit|debit|upi|gpay|google pay|phonepe|paytm|wallet|net banking|bank transfer|cheque)\b",
            cleaned,
            re.IGNORECASE,
        ):
            return None
        return cleaned

    def _to_float(self, value) -> Optional[float]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "")
        matches = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
        if not matches:
            return None
        try:
            return float(matches[-1])
        except ValueError:
            return None

    def _detect_currency(self, text: str) -> str:
        upper = text.upper()
        if re.search(r"\b(AED|DIRHAM|DIRHAMS|DHS)\b", upper):
            return "AED"
        if re.search(r"\b(USD|US DOLLAR|DOLLARS?)\b|US\$|\$", upper):
            return "USD"
        if re.search(r"\b(EUR|EURO)\b", upper):
            return "EUR"
        if re.search(r"\b(GBP|POUND|POUNDS)\b", upper):
            return "GBP"
        if re.search(r"\b(INR|RUPEE|RUPEES|RS\.?)\b|\bGSTIN\b|\bPAN\b|\u20b9", upper):
            return "INR"
        return "INR"

    def _normalize_currency(self, currency: Optional[str]) -> Optional[str]:
        if not currency:
            return None
        value = str(currency).strip().upper()
        aliases = {
            "RS": "INR",
            "RS.": "INR",
            "₹": "INR",
            "RUPEE": "INR",
            "RUPEES": "INR",
            "$": "USD",
            "US$": "USD",
            "DOLLAR": "USD",
            "DOLLARS": "USD",
            "DIRHAM": "AED",
            "DIRHAMS": "AED",
            "DHS": "AED",
            "EURO": "EUR",
            "POUND": "GBP",
            "POUNDS": "GBP",
        }
        return aliases.get(value, value if len(value) == 3 else None)

    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%y"):
            try:
                from datetime import datetime

                return datetime.strptime(str(date_str), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return str(date_str)


extraction_engine = ExtractionEngine()
