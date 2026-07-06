import logging
import os
import traceback

from dotenv import load_dotenv
from groq import Groq

from utils.error_handling import ProcessingStageError

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is missing. Add it to backend/.env.")

client = Groq(api_key=api_key)


def extract_invoice_data(text):
    logger.debug("[LLM] Starting Groq invoice extraction")

    prompt = f"""
    Extract the following details from this invoice:

    - Invoice Number
    - Invoice Date
    - Vendor Name
    - Customer Name
    - Total Amount
    - Items (description, quantity, price)

    Return STRICT JSON format only.

    Invoice Text:
    {text}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        logger.debug("[LLM] Finished Groq invoice extraction")
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise ProcessingStageError("LLM", "LLM request failed", str(e)) from e
