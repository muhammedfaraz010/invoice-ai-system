import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is missing. Add it to backend/.env.")

client = Groq(api_key=api_key)


def extract_invoice_data(text):
    print("INSIDE AI FUNCTION")

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

    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    return response.choices[0].message.content
