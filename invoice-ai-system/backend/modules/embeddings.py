"""
Embeddings Module
Creates deterministic local embeddings and stores them in Pinecone.
"""
import hashlib
import logging
import math

from config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1536


def _build_invoice_text(invoice_data: dict) -> str:
    parts = [
        f"Invoice Number: {invoice_data.get('invoice_number', 'N/A')}",
        f"Vendor: {invoice_data.get('vendor_name', 'N/A')}",
        f"Vendor GSTIN: {invoice_data.get('vendor_gstin', 'N/A')}",
        f"Buyer: {invoice_data.get('buyer_name', 'N/A')}",
        f"Date: {invoice_data.get('invoice_date', 'N/A')}",
        f"Due Date: {invoice_data.get('due_date', 'N/A')}",
        f"Total Amount: Rs. {invoice_data.get('total_amount', 'N/A')}",
        f"Tax Amount: Rs. {invoice_data.get('tax_amount', 'N/A')}",
        f"Currency: {invoice_data.get('currency', 'INR')}",
        f"Filename: {invoice_data.get('filename', '')}",
    ]

    line_items = invoice_data.get("line_items") or []
    if line_items:
        parts.append("Line Items:")
        for item in line_items:
            desc = item.get("description", "")
            amt = item.get("amount", "")
            parts.append(f"- {desc}: Rs. {amt}")

    return "\n".join(parts)


class EmbeddingStore:
    def __init__(self):
        self.pinecone_index = None
        self._init_clients()

    def _init_clients(self):
        try:
            if settings.pinecone_api_key:
                from pinecone import Pinecone

                pc = Pinecone(api_key=settings.pinecone_api_key)
                existing = [idx.name for idx in pc.list_indexes()]
                if settings.pinecone_index_name not in existing:
                    pc.create_index(
                        name=settings.pinecone_index_name,
                        dimension=EMBEDDING_DIMENSION,
                        metric="cosine",
                    )
                self.pinecone_index = pc.Index(settings.pinecone_index_name)
                logger.info("Pinecone index connected.")
        except Exception as exc:
            logger.warning("Pinecone init failed: %s", exc)

    def store_invoice_embedding(self, invoice_id: str, invoice_data: dict) -> bool:
        if not self.pinecone_index:
            logger.warning("Embedding store not available; skipping.")
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
            logger.info("Embedding stored for invoice %s", invoice_id)
            return True
        except Exception as exc:
            logger.error("Failed to store embedding: %s", exc)
            return False

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.pinecone_index:
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
                metadata = match.get("metadata", {})
                matches.append(
                    {
                        "invoice_id": metadata.get("invoice_id") or match["id"],
                        "score": round(match["score"], 4),
                        "metadata": metadata,
                    }
                )
            return matches
        except Exception as exc:
            logger.error("Pinecone search failed: %s", exc)
            return []

    def delete_embedding(self, invoice_id: str):
        if self.pinecone_index:
            try:
                self.pinecone_index.delete(ids=[invoice_id])
            except Exception as exc:
                logger.error("Failed to delete embedding: %s", exc)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        tokens = text.lower().split()

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


embedding_store = EmbeddingStore()
