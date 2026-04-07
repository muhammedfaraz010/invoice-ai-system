import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)
def extract_invoice_data(text):
    print("🔥 INSIDE AI FUNCTION")
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
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content