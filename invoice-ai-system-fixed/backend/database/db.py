import logging
import traceback

from sqlalchemy import (
    create_engine, Column, String, Float, DateTime,
    Boolean, Text, Integer, JSON, ForeignKey, inspect, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid

from config import settings

logger = logging.getLogger(__name__)


def utc_iso(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    return str(value)

# SQLite needs check_same_thread=False; timeout reduces transient lock failures under TestClient/dev reloads.
connect_args = {"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {}
try:
    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
except ModuleNotFoundError as exc:
    fallback_url = "sqlite:///./invoice_ai.db"
    logger.warning(
        "Database driver missing for %s; falling back to %s. Error: %s",
        settings.database_url,
        fallback_url,
        exc,
    )
    engine = create_engine(
        fallback_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────────────────────────
# DB Models
# ──────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    owner_role = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String)
    upload_time = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    deleted_reason = Column(Text, nullable=True)

    # Extracted fields
    invoice_number = Column(String, index=True)
    vendor_name = Column(String, index=True)
    vendor_gstin = Column(String)
    vendor_vat = Column(String)
    buyer_name = Column(String)
    buyer_gstin = Column(String)
    invoice_date = Column(String)
    due_date = Column(String)
    total_amount = Column(Float)
    tax_amount = Column(Float)
    payment_method = Column(String)
    subtotal = Column(Float)
    currency = Column(String, default="INR")
    line_items = Column(JSON)

    # Status
    ocr_text = Column(Text)
    extraction_status = Column(String, default="pending")
    validation_status = Column(String, default="pending")
    validation_errors = Column(JSON)
    processing_error = Column(JSON)
    failed_stage = Column(String)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String, nullable=True)
    embedding_stored = Column(Boolean, default=False)

    # Metadata
    raw_extraction = Column(JSON)
    processing_time_ms = Column(Integer)

    owner = relationship("User", back_populates="invoices", foreign_keys=[owner_id])

    def to_dict(self):
        try:
            from modules.validation import build_validation_summary
            validation_summary = build_validation_summary(self)
        except Exception:
            logger.exception("Unable to build validation summary for invoice %s", self.id)
            validation_summary = None

        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "owner_role": self.owner_role,
            "created_by": self.created_by,
            "filename": self.filename,
            "upload_time": utc_iso(self.upload_time),
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
            "deleted_at": utc_iso(self.deleted_at),
            "deleted_by": self.deleted_by,
            "deleted_reason": self.deleted_reason,
            "invoice_number": self.invoice_number,
            "vendor_name": self.vendor_name,
            "vendor_gstin": self.vendor_gstin,
            "vendor_vat": self.vendor_vat,
            "buyer_name": self.buyer_name,
            "buyer_gstin": self.buyer_gstin,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "total_amount": self.total_amount,
            "tax_amount": self.tax_amount,
            "payment_method": self.payment_method,
            "subtotal": self.subtotal,
            "currency": self.currency,
            "line_items": self.line_items,
            "extraction_status": self.extraction_status,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "validation_summary": validation_summary,
            "missing_required_fields": validation_summary.get("missing_required", []) if validation_summary else [],
            "missing_optional_fields": validation_summary.get("missing_optional", []) if validation_summary else [],
            "required_score": validation_summary.get("required_score", 0) if validation_summary else 0,
            "optional_score": validation_summary.get("optional_score", 0) if validation_summary else 0,
            "extraction_score": validation_summary.get("extraction_score", 0) if validation_summary else 0,
            "ai_confidence": validation_summary.get("ai_confidence", 0) if validation_summary else 0,
            "processing_error": self.processing_error,
            "failed_stage": self.failed_stage,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "embedding_stored": self.embedding_stored,
            "processing_time_ms": self.processing_time_ms,
        }


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False, default="")
    password_hash = Column(String, nullable=False)
    legacy_hashed_password = Column("hashed_password", String, nullable=True)
    role = Column(String, default="user")
    status = Column(String, default="Active")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="owner", foreign_keys="Invoice.owner_id")

    @property
    def hashed_password(self):
        return self.password_hash or self.legacy_hashed_password

    @hashed_password.setter
    def hashed_password(self, value):
        self.password_hash = value
        self.legacy_hashed_password = value

    def to_profile(self):
        status = self.status or ("Active" if self.is_active else "Inactive")
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "status": status,
            "is_active": self.is_active,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String)
    action_type = Column(String)
    action_status = Column(String, default="triggered")
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "action_type": self.action_type,
            "action_status": self.action_status,
            "message": self.message,
            "created_at": utc_iso(self.created_at),
            "resolved_at": utc_iso(self.resolved_at),
        }


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    sources = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeleteRequest(Base):
    __tablename__ = "delete_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False, index=True)
    requested_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    target_user = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="Pending", index=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "requested_by": self.requested_by,
            "target_user": self.target_user,
            "status": self.status,
            "reason": self.reason,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }


class DeleteUserRequest(Base):
    __tablename__ = "delete_user_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requested_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    target_user = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="Pending", index=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "requested_by": self.requested_by,
            "target_user": self.target_user,
            "status": self.status,
            "reason": self.reason,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    reference_id = Column(String, nullable=True, index=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "reference_id": self.reference_id,
            "is_read": self.is_read,
            "created_at": utc_iso(self.created_at),
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    target_user_id = Column(String, nullable=True, index=True)
    invoice_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    ip_address = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "target_user_id": self.target_user_id,
            "invoice_id": self.invoice_id,
            "action": self.action,
            "ip_address": self.ip_address,
            "details": self.details,
            "created_at": utc_iso(self.created_at),
        }


# ──────────────────────────────────────────────
# DB Utilities
# ──────────────────────────────────────────────

def _repair_postgres_schema():
    dialect = engine.dialect.name
    inspector = inspect(engine)
    if not inspector.has_table("invoices"):
        return

    columns = {column["name"]: str(column["type"]).lower() for column in inspector.get_columns("invoices")}
    statements = []

    if dialect == "postgresql" and columns.get("id", "").startswith("integer"):
        statements.append("ALTER TABLE invoices ALTER COLUMN id DROP DEFAULT")
        statements.append("ALTER TABLE invoices ALTER COLUMN id TYPE VARCHAR USING id::text")

    if dialect == "postgresql" and columns.get("duplicate_of", "").startswith("integer"):
        statements.append("ALTER TABLE invoices ALTER COLUMN duplicate_of TYPE VARCHAR USING duplicate_of::text")

    if "vendor_vat" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN vendor_vat VARCHAR")

    if "payment_method" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN payment_method VARCHAR")

    if "processing_error" not in columns:
        column_type = "JSONB" if dialect == "postgresql" else "JSON"
        statements.append(f"ALTER TABLE invoices ADD COLUMN processing_error {column_type}")

    if "failed_stage" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN failed_stage VARCHAR")

    if "owner_id" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN owner_id VARCHAR")

    if "owner_role" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN owner_role VARCHAR")

    if "created_by" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN created_by VARCHAR")

    if "created_at" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN created_at TIMESTAMP")

    if "updated_at" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN updated_at TIMESTAMP")

    if "deleted_at" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN deleted_at TIMESTAMP")

    if "deleted_by" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN deleted_by VARCHAR")

    if "deleted_reason" not in columns:
        statements.append("ALTER TABLE invoices ADD COLUMN deleted_reason TEXT")

    if not statements:
        return

    try:
        with engine.begin() as connection:
            for statement in statements:
                logger.debug("[Database] Running schema repair: %s", statement)
                connection.execute(text(statement))
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise

    try:
        with engine.begin() as connection:
            if dialect == "postgresql":
                connection.execute(text(
                    "UPDATE invoices SET created_at = upload_time::timestamp WHERE created_at IS NULL AND upload_time IS NOT NULL"
                ))
                connection.execute(text(
                    "UPDATE invoices SET updated_at = upload_time::timestamp WHERE updated_at IS NULL AND upload_time IS NOT NULL"
                ))
            else:
                connection.execute(text("UPDATE invoices SET created_at = upload_time WHERE created_at IS NULL"))
                connection.execute(text("UPDATE invoices SET updated_at = upload_time WHERE updated_at IS NULL"))
    except Exception as e:
        logger.warning("[Database] Non-critical backfill of created_at/updated_at failed: %s", e)


def _repair_user_schema():
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    dialect = engine.dialect.name
    columns = {column["name"]: str(column["type"]).lower() for column in inspector.get_columns("users")}
    statements = []

    if "full_name" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR")

    if "password_hash" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR")

    if "hashed_password" in columns and "password_hash" not in columns:
        statements.append("UPDATE users SET password_hash = hashed_password WHERE password_hash IS NULL")

    if dialect == "postgresql" and "hashed_password" in columns:
        statements.append("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")

    if "updated_at" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP")

    if "status" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN status VARCHAR")

    if "role" in columns:
        statements.append("UPDATE users SET role = 'user' WHERE role IN ('viewer', 'employee')")

    try:
        with engine.begin() as connection:
            for statement in statements:
                logger.debug("[Database] Running user schema repair: %s", statement)
                connection.execute(text(statement))

            timestamp_expr = "CURRENT_TIMESTAMP"
            connection.execute(text(f"UPDATE users SET full_name = username WHERE full_name IS NULL OR full_name = ''"))
            if "hashed_password" in columns:
                connection.execute(text("UPDATE users SET password_hash = hashed_password WHERE password_hash IS NULL"))
                connection.execute(text("UPDATE users SET hashed_password = password_hash WHERE hashed_password IS NULL"))
            connection.execute(text("UPDATE users SET status = CASE WHEN is_active THEN 'Active' ELSE 'Inactive' END WHERE status IS NULL OR status = ''"))
            connection.execute(text(f"UPDATE users SET updated_at = {timestamp_expr} WHERE updated_at IS NULL"))
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise


def create_tables():
    try:
        logger.debug("[Database] Creating tables")
        Base.metadata.create_all(bind=engine)
        _repair_user_schema()
        _repair_postgres_schema()
        logger.debug("[Database] Tables ready")
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise


def get_db():
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()