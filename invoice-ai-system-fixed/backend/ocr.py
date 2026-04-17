import json
import pytesseract
from pdf2image import convert_from_path

from modules.agent import invoice_agent
from database.save_invoice import save_invoice_to_db
from modules.agents import InvoiceAgent
from database.db import SessionLocal
from models.schemas import Invoice

# 🔥 RAG IMPORTS
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

print("🚀 OCR STARTED")

# ================= RAG SETUP =================
model = SentenceTransformer("all-MiniLM-L6-v2")
dimension = 384
index = faiss.IndexFlatL2(dimension)
documents = []


def build_index():
    db = SessionLocal()
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

    db.close()


def query_rag(question):
    q_emb = model.encode([question])
    D, I = index.search(np.array(q_emb), k=3)

    # 🔥 remove duplicates
    results = list(set([documents[i] for i in I[0] if i < len(documents)]))

    return results


# ================= OCR SETUP =================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(file_path):
    print(f"📄 Reading file: {file_path}")

    images = convert_from_path(
        file_path,
        poppler_path=r"C:\poppler\poppler-25.12.0\Library\bin",
    )

    print(f"📑 Total pages: {len(images)}")

    text = ""

    for i, img in enumerate(images):
        print(f"🔍 Processing page {i + 1}")
        page_text = pytesseract.image_to_string(img)
        text += page_text

    return text


# ================= MAIN =================
if __name__ == "__main__":
    print("🔥 MAIN RUNNING")

    file_path = "uploads/sample.pdf"

    try:
        # Step 1: OCR
        text = extract_text_from_pdf(file_path)

        print("\n===== OCR OUTPUT =====\n")

        if not text.strip():
            print("❌ No text extracted (try a clearer PDF)")
            exit()

        print(text)

        # Step 2: AI Extraction
        print("\n🤖 CALLING AI...")
        raw_result = invoice_agent("extract invoice data", text)

        print("\n===== RAW AI OUTPUT =====\n")
        print(raw_result)

        # Step 3: Convert to JSON
        try:
            cleaned = raw_result.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned)
        except Exception as e:
            print("❌ JSON PARSE ERROR:", e)
            exit()

        print("\n===== CLEAN JSON =====\n")
        print(result)

        # Step 4: Save to DB
        print("\n💾 Saving to database...")
        saved_invoice = save_invoice_to_db(result)

        # Step 5: Run Automation Agent
        print("\n🤖 Running Automation Agent...")

        db = SessionLocal()
        invoice = saved_invoice

        if invoice is None:
            print("❌ Invoice not saved. Skipping agent.")
        else:
            agent = InvoiceAgent()
            actions = agent.run(invoice, db)

            print("\n===== AGENT ACTIONS =====")
            print(actions)

        db.close()

        # ================= RAG PART =================
        print("\n🔍 Building RAG Index...")
        build_index()

        print("\n💬 Ask something about invoices:")
        query = input("👉 ")

        results = query_rag(query)

        print("\n===== RAG RESULT =====")
        for r in results:
            print("•", r)

        print("\n✅ PROCESS COMPLETED SUCCESSFULLY!")

    except Exception as e:
        print("\n❌ ERROR OCCURRED:")
        print(e)