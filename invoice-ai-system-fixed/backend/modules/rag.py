"""
RAG (Retrieval-Augmented Generation) Engine
Answers natural-language questions about invoices using Groq LLM + DB context.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self):
        self.client = None
        self._init_groq()

    def _init_groq(self):
        try:
            if settings.groq_api_key:
                from groq import Groq
                self.client = Groq(api_key=settings.groq_api_key)
                logger.info("Groq client initialized for RAG.")
            else:
                logger.warning("GROQ_API_KEY not set; RAG will use DB-only answers.")
        except Exception as e:
            logger.warning("Groq init failed: %s", e)

    def query(self, question: str, db: Session, owner_id: str | None = None) -> dict:
        """Answer a natural language question about invoices."""
        from database.db import Invoice

        query = db.query(Invoice).filter(
            Invoice.extraction_status == "success",
            Invoice.deleted_at.is_(None),
        )
        if owner_id:
            query = query.filter(Invoice.owner_id == owner_id)
        invoices = query.order_by(desc(Invoice.upload_time)).limit(20).all()

        if not invoices:
            return {
                "answer": "No processed invoices found yet. Upload and process some invoices first.",
                "sources": [],
            }

        filtered_invoices = self._filter_invoices(question, invoices)

        context_lines = []
        for inv in filtered_invoices:
            line = (
                f"Invoice #{inv.invoice_number} | Vendor: {inv.vendor_name} | "
                f"Amount: {inv.currency or 'INR'} {inv.total_amount} | "
                f"Date: {inv.invoice_date} | Status: {inv.validation_status} | "
                f"Duplicate: {'yes' if inv.is_duplicate else 'no'} | "
                f"Issues: {', '.join(inv.validation_errors or []) if inv.validation_errors else 'none'}"
            )
            context_lines.append(line)

        sources = self._build_sources(filtered_invoices)

        context = "\n".join(context_lines)

        if self.client:
            try:
                answer = self._ask_groq(question, context)
                return {"answer": answer, "sources": sources[:5]}
            except Exception as e:
                logger.error("Groq query failed: %s", e)

        answer = self._db_fallback_answer(question, filtered_invoices)
        return {"answer": answer, "sources": sources}

    def _filter_invoices(self, question: str, invoices: list) -> list:
        q = question.lower()

        if "duplicate" in q:
            return [inv for inv in invoices if inv.is_duplicate]

        if "invalid" in q or "failed validation" in q or "validation issue" in q:
            return [inv for inv in invoices if inv.validation_status == "invalid"]

        if "valid" in q and "invalid" not in q:
            return [inv for inv in invoices if inv.validation_status == "valid"]

        if "gstin" in q and ("missing" in q or "issue" in q):
            return [
                inv for inv in invoices
                if any("gstin" in issue.lower() for issue in (inv.validation_errors or []))
            ]

        if ("vat" in q or "trn" in q) and ("missing" in q or "issue" in q):
            return [
                inv for inv in invoices
                if any(("vat" in issue.lower() or "trn" in issue.lower()) for issue in (inv.validation_errors or []))
            ]

        if "high value" in q or "high-value" in q or "above" in q or "greater than" in q:
            threshold = self._extract_threshold(q) or 100000
            return [inv for inv in invoices if (inv.total_amount or 0) >= threshold]

        return invoices

    def _build_sources(self, invoices: list) -> list[dict]:
        sources = []
        seen = set()
        for inv in invoices:
            if inv.id in seen:
                continue
            seen.add(inv.id)
            sources.append({
                "invoice_id": inv.invoice_number or inv.id,
                "row_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": inv.total_amount,
                "vendor": inv.vendor_name,
                "vendor_name": inv.vendor_name,
            })
            if len(sources) >= 5:
                break
        return sources

    def _extract_threshold(self, question: str) -> float | None:
        import re

        match = re.search(r"(?:above|greater than|over|more than)\s+(?:rs\.?|inr|aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)", question)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    def _ask_groq(self, question: str, context: str) -> str:
        prompt = f"""You are a financial AI assistant for an Invoice Management System.

Invoice Data:
{context}

Question: {question}

Answer clearly and professionally. Use the invoice currency code/symbol (INR/Rs., USD/$, AED).
Answer:"""
        response = self.client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a financial invoice assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content

    def _db_fallback_answer(self, question: str, invoices: list) -> str:
        totals_by_currency = {}
        for inv in invoices:
            currency = inv.currency or "INR"
            totals_by_currency[currency] = totals_by_currency.get(currency, 0.0) + (inv.total_amount or 0.0)
        totals_text = ", ".join(f"{currency} {amount:,.2f}" for currency, amount in totals_by_currency.items())
        vendors = list({inv.vendor_name for inv in invoices if inv.vendor_name})
        return (
            f"Found {len(invoices)} invoice(s). Total value: {totals_text}. "
            f"Vendors: {', '.join(vendors[:5]) if vendors else 'N/A'}. "
            f"(Set GROQ_API_KEY in backend/.env for AI-powered answers.)"
        )


rag_engine = RAGEngine()
