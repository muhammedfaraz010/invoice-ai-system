"""
Agent automation layer.
Triggers automated actions based on invoice analysis results.
"""
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.db import AgentAction, Invoice

logger = logging.getLogger(__name__)


class InvoiceAgent:
    """
    Rule-based automation for processed invoices.
    """

    HIGH_VALUE_THRESHOLD = 100_000

    def run(self, invoice: Invoice, db: Session) -> list[dict]:
        actions_fired = []

        if invoice.is_duplicate:
            action = self._trigger(
                invoice_id=invoice.id,
                action_type="duplicate_alert",
                message=(
                    f"Duplicate invoice detected: '{invoice.invoice_number}' "
                    f"from vendor '{invoice.vendor_name}' already exists."
                ),
                db=db,
            )
            actions_fired.append(action)
            self._send_email_alert(
                subject=f"[ALERT] Duplicate Invoice: {invoice.invoice_number}",
                body=(
                    f"Invoice {invoice.invoice_number} from {invoice.vendor_name} "
                    f"appears to be a duplicate of invoice {invoice.duplicate_of}.\n"
                    f"Please review immediately."
                ),
            )

        if not invoice.vendor_gstin and invoice.total_amount and invoice.total_amount > 0:
            action = self._trigger(
                invoice_id=invoice.id,
                action_type="missing_gst",
                message=(
                    f"Invoice '{invoice.invoice_number}' from '{invoice.vendor_name}' "
                    f"is missing vendor GSTIN. Flagged for compliance review."
                ),
                db=db,
            )
            actions_fired.append(action)

        if invoice.total_amount and invoice.total_amount >= self.HIGH_VALUE_THRESHOLD:
            action = self._trigger(
                invoice_id=invoice.id,
                action_type="high_value_approval",
                message=(
                    f"High-value invoice detected: Rs. {invoice.total_amount:,.2f} "
                    f"from '{invoice.vendor_name}'. Approval required."
                ),
                db=db,
            )
            actions_fired.append(action)
            self._send_email_alert(
                subject=f"[APPROVAL NEEDED] High-Value Invoice: Rs. {invoice.total_amount:,.2f}",
                body=(
                    f"Invoice {invoice.invoice_number} from {invoice.vendor_name} "
                    f"amounts to Rs. {invoice.total_amount:,.2f}.\n"
                    f"Please review and approve."
                ),
            )

        if invoice.validation_status == "invalid" and invoice.validation_errors:
            errors_text = ", ".join(invoice.validation_errors)
            action = self._trigger(
                invoice_id=invoice.id,
                action_type="validation_failure",
                message=f"Invoice validation failed: {errors_text}",
                db=db,
            )
            actions_fired.append(action)

        return actions_fired

    def _trigger(
        self,
        invoice_id: str,
        action_type: str,
        message: str,
        db: Session,
    ) -> dict:
        action = AgentAction(
            invoice_id=invoice_id,
            action_type=action_type,
            message=message,
            action_status="triggered",
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        logger.info("[AGENT] %s: %s", action_type, message)
        return action.to_dict()

    def _send_email_alert(self, subject: str, body: str):
        if not all([settings.smtp_user, settings.smtp_password, settings.alert_email]):
            logger.info("Email not configured; skipping alert: %s", subject)
            return

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.smtp_user
            msg["To"] = settings.alert_email
            msg.set_content(body)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info("Alert email sent: %s", subject)
        except Exception as exc:
            logger.error("Email send failed: %s", exc)

    def resolve_action(self, action_id: str, db: Session) -> Optional[dict]:
        from datetime import datetime

        action = db.query(AgentAction).filter(AgentAction.id == action_id).first()
        if not action:
            return None

        action.action_status = "resolved"
        action.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(action)
        return action.to_dict()


invoice_agent = InvoiceAgent()
