"""
Lightweight Groq-backed invoice helper agent.
Used by OCR scripts for extraction and summarization tasks.
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Ensure backend root is in path so extractor can be imported
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def invoice_agent(user_input, ocr_text=None):
    """
    Simple invoice agent for OCR workflows.
    Supported actions:
    - extract invoice data
    - summary / summarize invoice
    """
    if not user_input:
        return "Agent: Please provide a request."

    normalized_input = user_input.lower().strip()

    if not ocr_text or not ocr_text.strip():
        return "Agent: No OCR text was provided."

    if "extract" in normalized_input:
        try:
            from extractor import extract_invoice_data
            logger.info("Agent: Extracting invoice data...")
            return extract_invoice_data(ocr_text)
        except Exception as e:
            logger.error("Extraction failed: %s", e)
            return f"Agent: Extraction failed - {e}"

    if "summary" in normalized_input or "summarize" in normalized_input:
        try:
            from config import settings
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": "Summarize invoice data briefly."},
                    {"role": "user", "content": f"Summarize this invoice:\n\n{ocr_text}"},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Summary failed: %s", e)
            return f"Agent: Summary failed - {e}"

    return "Agent: I do not understand the request."
