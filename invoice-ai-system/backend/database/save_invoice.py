import json
from database.db import SessionLocal
from models.schemas import Invoice


def save_invoice_to_db(invoice_json):
    db = SessionLocal()

    try:
        # ================= HANDLE INPUT =================
        if isinstance(invoice_json, str):
            data = json.loads(invoice_json)
        else:
            data = invoice_json  # already dict

        # ================= CURRENCY HANDLING =================
        currency = data.get("Currency")

        # 🔥 fallback detection (simple logic)
        if not currency:
            amount_text = str(data.get("Total Amount", ""))

            if "AED" in amount_text:
                currency = "AED"
            elif "$" in amount_text:
                currency = "USD"
            else:
                currency = "INR"  # default

        # ================= CREATE OBJECT =================
        invoice = Invoice(
            invoice_number=data.get("Invoice Number"),
            vendor_name=data.get("Vendor Name"),
            invoice_date=data.get("Invoice Date"),
            total_amount=data.get("Total Amount"),
            tax_amount=data.get("Tax Amount"),
            subtotal=data.get("Subtotal"),
            currency=currency,   # ✅ NEW FIELD
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        print(f"✅ Invoice saved! Currency: {currency}")

        return invoice  # 🔥 important for agent

    except Exception as e:
        print("❌ DB ERROR:", e)
        return None

    finally:
        db.close()