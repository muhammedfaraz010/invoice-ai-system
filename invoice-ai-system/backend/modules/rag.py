from sentence_transformers import SentenceTransformer
import numpy as np
from database.db import SessionLocal
from models.schemas import Invoice
from groq import Groq
import os

# ================= INIT =================
model = SentenceTransformer("all-MiniLM-L6-v2")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

embeddings = []
invoice_objects = []


# ================= BUILD INDEX =================
def build_index():
    global embeddings, invoice_objects

    db = SessionLocal()
    invoices = db.query(Invoice).all()

    embeddings = []
    invoice_objects = []

    for inv in invoices:
        text = f"""
        Invoice {inv.invoice_number}
        Vendor {inv.vendor_name}
        Amount {inv.total_amount} {inv.currency}
        Date {inv.invoice_date}
        """

        emb = model.encode(text)

        embeddings.append(emb)
        invoice_objects.append(inv)

    db.close()


# ================= CURRENCY SYMBOL =================
def get_symbol(currency):
    return {
        "INR": "₹",
        "AED": "AED",
        "USD": "$"
    }.get(currency, currency)


# ================= QUERY =================
def query_rag(query):
    global embeddings, invoice_objects

    if not embeddings:
        return "❌ No invoice data available."

    query_emb = model.encode(query)

    scores = np.dot(embeddings, query_emb)
    top_indices = np.argsort(scores)[-3:][::-1]

    # ================= BUILD CONTEXT =================
    context_lines = []
    amounts = []

    for i in top_indices:
        inv = invoice_objects[i]

        symbol = get_symbol(inv.currency)

        context_lines.append(
            f"Invoice {inv.invoice_number} from {inv.vendor_name} is {symbol}{inv.total_amount}"
        )

        if inv.total_amount:
            amounts.append(inv.total_amount)

    context = "\n".join(context_lines)

    # ================= SMART INSIGHTS =================
    insight_text = ""

    if amounts:
        total = sum(amounts)
        highest = max(amounts)
        lowest = min(amounts)
        avg = round(total / len(amounts), 2)

        insight_text = f"""
        Summary:
        - Total Amount: {total}
        - Highest Invoice: {highest}
        - Lowest Invoice: {lowest}
        - Average: {avg}
        """

    # ================= LLM PROMPT =================
    prompt = f"""
    You are a professional financial AI assistant.

    Context:
    {context}

    {insight_text}

    Question:
    {query}

    Instructions:
    - Answer clearly and professionally
    - Use correct currency symbols (₹, AED, $)
    - If multiple invoices exist, summarize totals
    - Highlight insights (highest, lowest, trends)
    - Keep answer concise but intelligent

    Answer:
    """

    # ================= LLM CALL =================
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content