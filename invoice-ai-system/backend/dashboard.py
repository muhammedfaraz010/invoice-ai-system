import streamlit as st
import os
import json

from database.db import SessionLocal
from models.schemas import Invoice

from modules.agent import invoice_agent
from modules.agents import InvoiceAgent
from modules.rag import build_index, query_rag

from database.save_invoice import save_invoice_to_db

import pytesseract
from pdf2image import convert_from_path
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(page_title="Invoice AI System", layout="wide")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

st.title("🤖 Invoice AI System")

# ================= FILE UPLOAD =================
st.subheader("📄 Upload Invoice PDF")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success(f"✅ Uploaded: {uploaded_file.name}")

    # ================= OCR =================
    st.write("🔍 Running OCR...")

    try:
        images = convert_from_path(
            file_path,
            poppler_path=r"C:\poppler\poppler-25.12.0\Library\bin",
        )

        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)

        st.text_area("📜 OCR Output", text[:1000])

    except Exception as e:
        st.error(f"OCR Error: {e}")
        text = ""

    # ================= AI EXTRACTION =================
    if text:
        st.write("🤖 Extracting invoice data...")

        raw_result = invoice_agent("extract invoice data", text)

        try:
            cleaned = raw_result.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned)

            st.json(result)

        except Exception as e:
            st.error(f"JSON Error: {e}")
            result = None

        # ================= SAVE + AGENT =================
        if result:
            db = SessionLocal()

            saved_invoice = save_invoice_to_db(result)

            if saved_invoice:
                agent = InvoiceAgent()
                actions = agent.run(saved_invoice, db)

                st.subheader("⚙️ Agent Actions")
                st.write(actions)

            db.close()

# ================= DASHBOARD =================
st.divider()
st.subheader("📊 Dashboard")

db = SessionLocal()
invoices = db.query(Invoice).all()

# ================= METRICS =================
col1, col2 = st.columns(2)

col1.metric("📄 Total Invoices", len(invoices))
col2.metric("💰 Total Amount", sum([i.total_amount or 0 for i in invoices]))

# ================= INSIGHTS PANEL (🔥 NEW) =================
st.subheader("📊 Insights")

if invoices:
    amounts = [i.total_amount or 0 for i in invoices]

    st.write(f"🔹 Highest Invoice: ₹{max(amounts)}")
    st.write(f"🔹 Lowest Invoice: ₹{min(amounts)}")
    st.write(f"🔹 Average Invoice: ₹{round(sum(amounts)/len(amounts), 2)}")
else:
    st.info("No invoices available")

# ================= TABLE =================
st.subheader("📋 Invoice List")

seen = set()
data = []

for i in invoices:
    key = (i.invoice_number, i.vendor_name)
    if key not in seen:
        seen.add(key)
        data.append({
            "Invoice": i.invoice_number,
            "Vendor": i.vendor_name,
            "Amount": i.total_amount,
            "Status": "⚠️ Issue" if not i.vendor_name else "✅ OK"
        })

st.dataframe(data, use_container_width=True)

# ================= CHART =================
st.subheader("📈 Invoice Amount Distribution")

amounts = [i.total_amount or 0 for i in invoices]

if amounts:
    fig, ax = plt.subplots()
    ax.hist(amounts)
    st.pyplot(fig)

# ================= RAG CHATBOT =================
st.divider()
st.subheader("🤖 AI Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask about invoices...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    build_index()
    answer = query_rag(user_input)

    st.session_state.messages.append({"role": "assistant", "content": answer})

    with st.chat_message("assistant"):
        st.write(answer)

# ================= SUGGESTIONS =================
st.write("💡 Try:")
st.write("- Total amount")
st.write("- Highest invoice")
st.write("- Vendor summary")

db.close()