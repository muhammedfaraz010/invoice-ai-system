"""
Lightweight Groq-backed invoice helper agent.
Used by OCR scripts for extraction and summarization tasks.
"""
import os

from dotenv import load_dotenv
from groq import Groq

from extractor import extract_invoice_data

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to backend/.env before running the agent."
        )
    return Groq(api_key=api_key)


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
        print("Agent: Extracting invoice data...")
        return extract_invoice_data(ocr_text)

    if "summary" in normalized_input or "summarize" in normalized_input:
        print("Agent: Summarizing invoice...")
        client = _get_groq_client()
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize invoice data clearly and briefly. "
                        "Highlight vendor, invoice number, date, amount, and key line items."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this invoice:\n\n{ocr_text}",
                },
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content

    return "Agent: I do not understand the request."
