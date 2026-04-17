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

    def query(self, question: str, db: Session) -> dict:
        """Answer a natural language question about invoices."""
        from database.db import Invoice

        invoices = (
            db.query(Invoice)
            .filter(Invoice.extraction_status == "success")
            .order_by(desc(Invoice.upload_time))
            .limit(20)
            .all()
        )

        if not invoices:
            return {
                "answer": "No processed invoices found yet. Upload and process some invoices first.",
                "sources": [],
            }

        context_lines = []
        sources = []
        for inv in invoices:
            line = (
                f"Invoice #{inv.invoice_number} | Vendor: {inv.vendor_name} | "
                f"Amount: {inv.currency or 'INR'} {inv.total_amount} | "
                f"Date: {inv.invoice_date} | Status: {inv.validation_status}"
            )
            context_lines.append(line)
            sources.append({
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "vendor_name": inv.vendor_name,
            })

        context = "\n".join(context_lines)

        if self.client:
            try:
                answer = self._ask_groq(question, context)
                return {"answer": answer, "sources": sources[:5]}
            except Exception as e:
                logger.error("Groq query failed: %s", e)

        answer = self._db_fallback_answer(question, invoices)
        return {"answer": answer, "sources": sources[:5]}

    def _ask_groq(self, question: str, context: str) -> str:
        prompt = f"""You are a financial AI assistant for an Invoice Management System.

Invoice Data:
{context}

Question: {question}

Answer clearly and professionally. Use currency symbols (Rs. for INR).
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
        total = sum(inv.total_amount or 0 for inv in invoices)
        vendors = list({inv.vendor_name for inv in invoices if inv.vendor_name})
        return (
            f"Found {len(invoices)} invoice(s). Total value: Rs.{total:,.2f}. "
            f"Vendors: {', '.join(vendors[:5]) if vendors else 'N/A'}. "
            f"(Set GROQ_API_KEY in backend/.env for AI-powered answers.)"
        )


rag_engine = RAGEngine()
