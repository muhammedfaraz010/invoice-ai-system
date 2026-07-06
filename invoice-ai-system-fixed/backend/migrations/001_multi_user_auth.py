"""
SQLAlchemy migration for multi-user authentication and invoice ownership.

Run from backend/:
    python migrations/001_multi_user_auth.py

The migration preserves existing invoices and assigns invoices without an
owner_id to the configured admin account.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text

from config import settings
from database.db import Base, Invoice, SessionLocal, User, engine
from utils.auth import create_admin_user


def _run_schema_updates():
    inspector = inspect(engine)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        if inspector.has_table("users"):
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "full_name" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
            if "password_hash" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
            if "hashed_password" in user_columns and "password_hash" not in user_columns:
                connection.execute(text("UPDATE users SET password_hash = hashed_password WHERE password_hash IS NULL"))
            if engine.dialect.name == "postgresql" and "hashed_password" in user_columns:
                connection.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"))
            if "updated_at" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP"))
            connection.execute(text("UPDATE users SET full_name = username WHERE full_name IS NULL OR full_name = ''"))
            if "hashed_password" in user_columns:
                connection.execute(text("UPDATE users SET password_hash = hashed_password WHERE password_hash IS NULL"))
                connection.execute(text("UPDATE users SET hashed_password = password_hash WHERE hashed_password IS NULL"))
            connection.execute(text("UPDATE users SET role = 'user' WHERE role IN ('viewer', 'employee')"))

        if inspector.has_table("invoices"):
            invoice_columns = {column["name"] for column in inspector.get_columns("invoices")}
            invoice_columns_to_add = {
                "owner_id": "VARCHAR",
                "owner_role": "VARCHAR",
                "created_by": "VARCHAR",
                "created_at": "TIMESTAMP",
                "updated_at": "TIMESTAMP",
                "deleted_at": "TIMESTAMP",
                "deleted_by": "VARCHAR",
                "deleted_reason": "TEXT",
            }
            for column_name, column_type in invoice_columns_to_add.items():
                if column_name not in invoice_columns:
                    connection.execute(text(f"ALTER TABLE invoices ADD COLUMN {column_name} {column_type}"))
            connection.execute(text("UPDATE invoices SET created_at = upload_time WHERE created_at IS NULL"))
            connection.execute(text("UPDATE invoices SET updated_at = upload_time WHERE updated_at IS NULL"))


def upgrade():
    _run_schema_updates()
    db = SessionLocal()
    try:
        admin = create_admin_user(db)
        db.query(Invoice).filter(Invoice.owner_id.is_(None)).update(
            {
                Invoice.owner_id: admin.id,
                Invoice.owner_role: "admin",
                Invoice.created_by: admin.id,
            },
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
    print(f"Multi-user auth migration complete. Admin username: {settings.admin_username}")
