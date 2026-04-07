"""
RAG (Retrieval-Augmented Generation) Engine
Answers natural language queries about invoices using vector search + LLM.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from config import settings
from modules.embeddings import embedding_store
from database.db import Invoice

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """
You are an intelligent invoice assistant for a financial document management system.
You have access to invoice data retrieved from a vector database.

Your job:
- Answer questions about invoices accurately and concisely.
- Use the provided context (retrieved invoice records) to answer.
- If the answer is not in the context, say "I don't have enough data to answer that."
- Format currency as ₹ (Indian Rupees) with commas (e.g., ₹1,25,000).
- For lists, use bullet points.
- Be factual — do not guess.

Context (Retrieved Invoice Records):
{context}
"""


class RAGEngine:
    def __init__(self):
        self.client = None
        if settings.xai_api_key:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.xai_api_key,
                base_url="https://api.x.ai/v1"
            )

    # ──────────────────────────────────────────
    # Main Query
    # ──────────────────────────────────────────

    def query(self, question: str, db: Session) -> dict:
        """Full RAG pipeline: retrieve → augment → generate."""

        # Step 1: Retrieve relevant invoice chunks from vector DB
        matches = embedding_store.search(question, top_k=5)

        # Step 2: Augment with structured DB data for richer context
        context_parts = []
        sources = []

        if matches:
            invoice_ids = [m["invoice_id"] for m in matches]
            invoices = db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
            inv_map = {inv.id: inv for inv in invoices}

            for match in matches:
                inv = inv_map.get(match["invoice_id"])
                if inv:
                    context_parts.append(self._format_invoice_context(inv))
                    sources.append(
                        {
                            "invoice_id": inv.id,
                            "invoice_number": inv.invoice_number,
                            "vendor_name": inv.vendor_name,
                            "relevance_score": match["score"],
                        }
                    )
        else:
            # Fallback: keyword-based DB search
            invoices = self._keyword_search(question, db)
            for inv in invoices:
                context_parts.append(self._format_invoice_context(inv))
                sources.append(
                    {
                        "invoice_id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "vendor_name": inv.vendor_name,
                        "relevance_score": 0.5,
                    }
                )

        # Step 3: Generate answer
        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant invoices found."

        if not self.client:
            return {
                "answer": f"LLM not configured. Based on search, I found {len(sources)} relevant invoice(s).",
                "sources": sources,
            }

        answer = self._generate_answer(question, context)
        return {"answer": answer, "sources": sources}

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _generate_answer(self, question: str, context: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=settings.grok_model,
                messages=[
                    {
                        "role": "system",
                        "content": RAG_SYSTEM_PROMPT.format(context=context),
                    },
                    {"role": "user", "content": question},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"Error generating answer: {str(e)}"

    def _format_invoice_context(self, inv: Invoice) -> str:
        lines = [
            f"Invoice ID: {inv.id}",
            f"Invoice Number: {inv.invoice_number or 'N/A'}",
            f"Vendor: {inv.vendor_name or 'N/A'}",
            f"Vendor GSTIN: {inv.vendor_gstin or 'N/A'}",
            f"Buyer: {inv.buyer_name or 'N/A'}",
            f"Date: {inv.invoice_date or 'N/A'}",
            f"Total Amount: ₹{inv.total_amount or 'N/A'}",
            f"Tax Amount: ₹{inv.tax_amount or 'N/A'}",
            f"Currency: {inv.currency}",
            f"Validation: {inv.validation_status}",
            f"Duplicate: {'Yes' if inv.is_duplicate else 'No'}",
        ]
        if inv.line_items:
            lines.append(f"Line Items: {len(inv.line_items)} items")
        return "\n".join(lines)

    def _keyword_search(self, question: str, db: Session, limit: int = 5) -> list:
        """Simple text-based fallback search on vendor name and invoice number."""
        words = question.lower().split()
        invoices = db.query(Invoice).filter(Invoice.extraction_status == "success").all()
        scored = []
        for inv in invoices:
            score = 0
            text = f"{inv.vendor_name or ''} {inv.invoice_number or ''}".lower()
            for word in words:
                if word in text:
                    score += 1
            if score > 0:
                scored.append((score, inv))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [inv for _, inv in scored[:limit]]


rag_engine = RAGEngine()
