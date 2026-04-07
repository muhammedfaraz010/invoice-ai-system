"""
Agent Automation Layer
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
    Rule-based agent that fires actions after invoice processing:
    - Duplicate alert
    - Missing GST flag
    - High-value approval request
    """

    HIGH_VALUE_THRESHOLD = 100_000  # ₹1,00,000

    # ──────────────────────────────────────────
    # Main Dispatcher
    # ──────────────────────────────────────────

    def run(self, invoice: Invoice, db: Session) -> list[dict]:
        """Evaluate all rules and trigger appropriate actions."""
        actions_fired = []

        # Rule 1: Duplicate Invoice
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

        # Rule 2: Missing GST
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

        # Rule 3: High-Value Approval
        if invoice.total_amount and invoice.total_amount >= self.HIGH_VALUE_THRESHOLD:
            action = self._trigger(
                invoice_id=invoice.id,
                action_type="high_value_approval",
                message=(
                    f"High-value invoice detected: ₹{invoice.total_amount:,.2f} "
                    f"from '{invoice.vendor_name}'. Approval required."
                ),
                db=db,
            )
            actions_fired.append(action)
            self._send_email_alert(
                subject=f"[APPROVAL NEEDED] High-Value Invoice: ₹{invoice.total_amount:,.2f}",
                body=(
                    f"Invoice {invoice.invoice_number} from {invoice.vendor_name} "
                    f"amounts to ₹{invoice.total_amount:,.2f}.\n"
                    f"Please review and approve."
                ),
            )

        # Rule 4: Validation Failures
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

    # ──────────────────────────────────────────
    # Action Trigger
    # ──────────────────────────────────────────

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
        logger.info(f"[AGENT] {action_type}: {message}")
        return action.to_dict()

    # ──────────────────────────────────────────
    # Email Alert
    # ──────────────────────────────────────────

    def _send_email_alert(self, subject: str, body: str):
        if not all([settings.smtp_user, settings.smtp_password, settings.alert_email]):
            logger.info(f"Email not configured – skipping alert: {subject}")
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

            logger.info(f"Alert email sent: {subject}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    # ──────────────────────────────────────────
    # Resolve Action
    # ──────────────────────────────────────────

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
