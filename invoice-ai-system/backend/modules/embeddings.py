"""
Embeddings Module
Converts invoice text to vector embeddings and stores in Pinecone.
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _build_invoice_text(invoice_data: dict) -> str:
    """Create a rich text representation of the invoice for embedding."""
    parts = [
        f"Invoice Number: {invoice_data.get('invoice_number', 'N/A')}",
        f"Vendor: {invoice_data.get('vendor_name', 'N/A')}",
        f"Vendor GSTIN: {invoice_data.get('vendor_gstin', 'N/A')}",
        f"Buyer: {invoice_data.get('buyer_name', 'N/A')}",
        f"Date: {invoice_data.get('invoice_date', 'N/A')}",
        f"Due Date: {invoice_data.get('due_date', 'N/A')}",
        f"Total Amount: ₹{invoice_data.get('total_amount', 'N/A')}",
        f"Tax Amount: ₹{invoice_data.get('tax_amount', 'N/A')}",
        f"Currency: {invoice_data.get('currency', 'INR')}",
        f"Filename: {invoice_data.get('filename', '')}",
    ]
    line_items = invoice_data.get("line_items") or []
    if line_items:
        parts.append("Line Items:")
        for item in line_items:
            desc = item.get("description", "")
            amt = item.get("amount", "")
            parts.append(f"  - {desc}: ₹{amt}")

    return "\n".join(parts)


class EmbeddingStore:
    def __init__(self):
        self.openai_client = None
        self.pinecone_index = None
        self._init_clients()

    def _init_clients(self):
        try:
            from openai import OpenAI
            if settings.xai_api_key:
                self.openai_client = OpenAI(
                    api_key=settings.xai_api_key,
                    base_url="https://api.x.ai/v1"
                )
        except Exception as e:
            logger.warning(f"xAI client init failed: {e}")

        try:
            if settings.pinecone_api_key:
                from pinecone import Pinecone
                pc = Pinecone(api_key=settings.pinecone_api_key)
                # Create index if not exists (dim=1536 for text-embedding-ada-002)
                existing = [idx.name for idx in pc.list_indexes()]
                if settings.pinecone_index_name not in existing:
                    pc.create_index(
                        name=settings.pinecone_index_name,
                        dimension=1536,
                        metric="cosine",
                    )
                self.pinecone_index = pc.Index(settings.pinecone_index_name)
                logger.info("Pinecone index connected.")
        except Exception as e:
            logger.warning(f"Pinecone init failed: {e}")

    # ──────────────────────────────────────────
    # Store embedding
    # ──────────────────────────────────────────

    def store_invoice_embedding(self, invoice_id: str, invoice_data: dict) -> bool:
        """Generate and store embedding for an invoice."""
        if not self.openai_client or not self.pinecone_index:
            logger.warning("Embedding store not available – skipping.")
            return False

        try:
            text = _build_invoice_text(invoice_data)
            embedding = self._embed(text)

            metadata = {
                "invoice_id": invoice_id,
                "invoice_number": invoice_data.get("invoice_number") or "",
                "vendor_name": invoice_data.get("vendor_name") or "",
                "invoice_date": invoice_data.get("invoice_date") or "",
                "total_amount": invoice_data.get("total_amount") or 0.0,
                "filename": invoice_data.get("filename") or "",
                "text_preview": text[:500],
            }

            self.pinecone_index.upsert(
                vectors=[{"id": invoice_id, "values": embedding, "metadata": metadata}]
            )
            logger.info(f"Embedding stored for invoice {invoice_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return False

    # ──────────────────────────────────────────
    # Search (for RAG)
    # ──────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search for relevant invoices."""
        if not self.openai_client or not self.pinecone_index:
            return []

        try:
            query_embedding = self._embed(query)
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )
            matches = []
            for match in results.get("matches", []):
                matches.append(
                    {
                        "invoice_id": match["id"],
                        "score": round(match["score"], 4),
                        "metadata": match.get("metadata", {}),
                    }
                )
            return matches
        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return []

    def delete_embedding(self, invoice_id: str):
        if self.pinecone_index:
            try:
                self.pinecone_index.delete(ids=[invoice_id])
            except Exception as e:
                logger.error(f"Failed to delete embedding: {e}")

    # ──────────────────────────────────────────
    # Core embed call
    # ──────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        response = self.openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text[:8000],
        )
        return response.data[0].embedding


embedding_store = EmbeddingStore()
