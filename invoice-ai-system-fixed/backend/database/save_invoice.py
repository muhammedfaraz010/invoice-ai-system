import json
import logging
import traceback

from database.db import Invoice, SessionLocal

logger = logging.getLogger(__name__)


def save_invoice_to_db(invoice_json, owner_id=None, owner_role=None, created_by=None):
    db = SessionLocal()

    try:
        if isinstance(invoice_json, str):
            data = json.loads(invoice_json)
        else:
            data = invoice_json

        currency = data.get("Currency")
        if not currency:
            amount_text = str(data.get("Total Amount", ""))

            if "AED" in amount_text:
                currency = "AED"
            elif "$" in amount_text:
                currency = "USD"
            else:
                currency = "INR"

        invoice = Invoice(
            owner_id=owner_id,
            owner_role=owner_role,
            created_by=created_by or owner_id,
            invoice_number=data.get("Invoice Number"),
            vendor_name=data.get("Vendor Name"),
            invoice_date=data.get("Invoice Date"),
            total_amount=data.get("Total Amount"),
            tax_amount=data.get("Tax Amount"),
            subtotal=data.get("Subtotal"),
            currency=currency,
        )

        logger.debug("[Database] Saving invoice")
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        logger.debug("[Database] Invoice saved")
        logger.info("Invoice saved. Currency: %s", currency)

        return invoice

    except Exception as e:
        db.rollback()
        logger.exception(e)
        traceback.print_exc()
        return None

    finally:
        db.close()
