import json
import logging
import traceback

import faiss
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from sentence_transformers import SentenceTransformer

from database.db import Invoice, SessionLocal
from database.save_invoice import save_invoice_to_db
from modules.agent import invoice_agent
from modules.agents import InvoiceAgent
from utils.error_handling import ProcessingStageError

logger = logging.getLogger(__name__)
logger.info("OCR script started")

model = SentenceTransformer("all-MiniLM-L6-v2")
dimension = 384
index = faiss.IndexFlatL2(dimension)
documents = []


def build_index():
    logger.debug("[Database] Starting RAG index build")
    db = SessionLocal()
    try:
        invoices = db.query(Invoice).all()

        global documents
        documents = []

        vectors = []
        for inv in invoices:
            text = f"{inv.vendor_name} {inv.invoice_number} {inv.total_amount}"
            emb = model.encode([text])[0]
            vectors.append(emb)
            documents.append(text)

        if vectors:
            index.reset()
            index.add(np.array(vectors))
        logger.debug("[Database] Finished RAG index build")
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise
    finally:
        db.close()


def query_rag(question):
    try:
        logger.debug("[Response generation] Starting RAG query")
        q_emb = model.encode([question])
        _, result_indexes = index.search(np.array(q_emb), k=3)
        results = list(set([documents[i] for i in result_indexes[0] if i < len(documents)]))
        logger.debug("[Response generation] Finished RAG query")
        return results
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(file_path):
    logger.debug("[PDF to image conversion] Reading file: %s", file_path)
    try:
        images = convert_from_path(
            file_path,
            poppler_path=r"C:\poppler\poppler-25.12.0\Library\bin",
        )
        logger.debug("[PDF to image conversion] Total pages: %s", len(images))

        text = ""
        for i, image in enumerate(images):
            logger.debug("[OCR] Processing page %s", i + 1)
            page_text = pytesseract.image_to_string(image)
            text += page_text

        if not text.strip():
            raise ProcessingStageError("OCR", "No readable text found in invoice.")
        logger.debug("[OCR] Finished PDF OCR")
        return text
    except ProcessingStageError:
        raise
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise ProcessingStageError("OCR", "OCR extraction failed", str(e)) from e


if __name__ == "__main__":
    logger.info("OCR script main running")
    file_path = "uploads/sample.pdf"

    try:
        text = extract_text_from_pdf(file_path)
        logger.info("OCR output:\n%s", text)

        logger.debug("[LLM] Calling invoice agent")
        raw_result = invoice_agent("extract invoice data", text)
        logger.info("Raw AI output:\n%s", raw_result)

        try:
            cleaned = raw_result.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned)
        except Exception as e:
            logger.exception(e)
            traceback.print_exc()
            raise ProcessingStageError("LLM", "Unable to parse invoice data", str(e)) from e

        logger.info("Clean JSON:\n%s", result)

        logger.debug("[Database] Saving to database")
        saved_invoice = save_invoice_to_db(result)

        logger.debug("[Response generation] Running automation agent")
        db = SessionLocal()
        invoice = saved_invoice

        try:
            if invoice is None:
                logger.error("Invoice not saved. Skipping agent.")
            else:
                agent = InvoiceAgent()
                actions = agent.run(invoice, db)
                logger.info("Agent actions: %s", actions)
        finally:
            db.close()

        logger.debug("[Database] Building RAG index")
        build_index()

        query = input("Ask something about invoices: ")
        results = query_rag(query)
        logger.info("RAG result: %s", results)
        logger.info("Process completed successfully")

    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
