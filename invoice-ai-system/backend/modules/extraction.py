"""
NLP / LLM Extraction Engine
Uses xAI Grok to extract structured invoice data from OCR text.
"""
import json
import logging
import re
from typing import Optional

from openai import OpenAI
from config import settings
from models.schemas import InvoiceExtraction, LineItem

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are an expert invoice parser. Extract structured data from the invoice text below.

Return ONLY a valid JSON object with these exact fields:
{
  "invoice_number": "string or null",
  "vendor_name": "string or null",
  "vendor_gstin": "string or null (15-char Indian GST number)",
  "buyer_name": "string or null",
  "buyer_gstin": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "tax_amount": number or null,
  "subtotal": number or null,
  "currency": "INR",
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null,
      "tax_rate": number or null
    }
  ]
}

Rules:
- For Indian invoices, currency is almost always INR.
- GSTIN format: 2 digits + 10 char PAN + 1 digit + Z + 1 char (e.g., 27AAPFU0939F1ZV).
- Normalize dates to YYYY-MM-DD.
- Convert amounts to float (remove ₹, commas, etc.).
- If a field is not found, use null.
- Return only the JSON object — no explanation, no markdown.

INVOICE TEXT:
{ocr_text}
"""


class ExtractionEngine:
    def __init__(self):
        if settings.xai_api_key:
            self.client = OpenAI(
                api_key=settings.xai_api_key,
                base_url="https://api.x.ai/v1"
            )
        else:
            self.client = None
            logger.warning("xAI API key not set – extraction will use fallback regex.")

    # ──────────────────────────────────────────
    # Main Extraction
    # ──────────────────────────────────────────

    def extract(self, ocr_text: str) -> InvoiceExtraction:
        """Extract structured data from OCR text."""
        if not ocr_text or len(ocr_text.strip()) < 10:
            raise ValueError("OCR text is too short or empty.")

        if self.client:
            return self._extract_with_llm(ocr_text)
        else:
            return self._extract_with_regex(ocr_text)

    # ──────────────────────────────────────────
    # LLM Extraction
    # ──────────────────────────────────────────

    def _extract_with_llm(self, ocr_text: str) -> InvoiceExtraction:
        prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text[:4000])  # token limit

        response = self.client.chat.completions.create(
            model=settings.grok_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise invoice data extraction assistant. Always return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        raw_json = response.choices[0].message.content
        return self._parse_json_to_schema(raw_json)

    # ──────────────────────────────────────────
    # Regex Fallback (no API key)
    # ──────────────────────────────────────────

    def _extract_with_regex(self, text: str) -> InvoiceExtraction:
        """Basic regex extraction as fallback when no LLM is available."""
        logger.info("Using regex fallback extraction.")

        def find(patterns, txt):
            for p in patterns:
                m = re.search(p, txt, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return None

        invoice_number = find(
            [r"invoice\s*(?:no|number|#)[:\s]*([A-Z0-9\-/]+)",
             r"inv\s*(?:no|#)[:\s]*([A-Z0-9\-/]+)"],
            text,
        )

        vendor_name = find(
            [r"(?:from|seller|vendor|billed by)[:\s]*([A-Za-z\s&.,]+?)(?:\n|GSTIN|GST)",
             r"^([A-Z][A-Za-z\s&.,]{3,50})\n"],
            text,
        )

        gstin = find(
            [r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b"],
            text,
        )

        invoice_date = find(
            [r"(?:invoice\s*date|date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
             r"(\d{2}/\d{2}/\d{4})"],
            text,
        )

        total = find(
            [r"(?:total|grand total|amount due)[:\s]*(?:₹|Rs\.?|INR)?\s*([\d,]+\.?\d*)",
             r"(?:₹|Rs\.?)\s*([\d,]+\.?\d*)"],
            text,
        )

        total_amount = None
        if total:
            try:
                total_amount = float(total.replace(",", ""))
            except ValueError:
                pass

        return InvoiceExtraction(
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            vendor_gstin=gstin,
            invoice_date=self._normalize_date(invoice_date),
            total_amount=total_amount,
        )

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _parse_json_to_schema(self, raw_json: str) -> InvoiceExtraction:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nRaw: {raw_json[:200]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        line_items = []
        for item in data.get("line_items", []):
            line_items.append(
                LineItem(
                    description=item.get("description", ""),
                    quantity=item.get("quantity"),
                    unit_price=item.get("unit_price"),
                    amount=item.get("amount"),
                    tax_rate=item.get("tax_rate"),
                )
            )

        return InvoiceExtraction(
            invoice_number=data.get("invoice_number"),
            vendor_name=data.get("vendor_name"),
            vendor_gstin=data.get("vendor_gstin"),
            buyer_name=data.get("buyer_name"),
            buyer_gstin=data.get("buyer_gstin"),
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            total_amount=data.get("total_amount"),
            tax_amount=data.get("tax_amount"),
            subtotal=data.get("subtotal"),
            currency=data.get("currency", "INR"),
            line_items=line_items,
        )

    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                from datetime import datetime
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str


extraction_engine = ExtractionEngine()
