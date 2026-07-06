"""
Authentication Utilities
JWT-based auth with role-based access control.
"""
import logging
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config import settings
from database.db import get_db, User

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        logger.exception("Password verification failed")
        return False


def create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    payload = data.copy()
    if "sub" in payload:
        payload["sub"] = str(payload["sub"])
    payload.update({"exp": datetime.utcnow() + expires_delta, "type": token_type})
    logger.debug("Creating %s JWT for subject=%s role=%s", token_type, payload.get("sub"), payload.get("role"))
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(data: dict) -> str:
    return create_token(
        data,
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(data: dict) -> str:
    return create_token(
        data,
        timedelta(days=settings.refresh_token_expire_days),
        "refresh",
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        logger.exception("JWT decode failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != expected_type:
        logger.warning("JWT token type mismatch: expected=%s actual=%s", expected_type, payload.get("type"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    logger.debug("JWT validated subject=%s role=%s type=%s", payload.get("sub"), payload.get("role"), expected_type)
    return payload


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    """Dependency factory: ensure user has one of the given roles."""
    def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return user
    return _check


def create_admin_user(db: Session) -> User:
    """Create or repair the default admin account and attach legacy invoices."""
    from database.db import Invoice

    admin = db.query(User).filter(User.username == settings.admin_username).first()
    if not admin:
        password_hash = hash_password(settings.admin_password)
        admin = User(
            username=settings.admin_username,
            email=settings.admin_email,
            full_name=settings.admin_full_name,
            password_hash=password_hash,
            legacy_hashed_password=password_hash,
            role="admin",
            status="Active",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Default admin created: username=%s", settings.admin_username)
    else:
        changed = False
        if verify_password("admin12345", admin.hashed_password) and not verify_password(settings.admin_password, admin.hashed_password):
            password_hash = hash_password(settings.admin_password)
            admin.password_hash = password_hash
            admin.legacy_hashed_password = password_hash
            changed = True
            logger.info("Repaired default admin password to documented credentials.")
        if admin.role != "admin":
            admin.role = "admin"
            changed = True
        if not admin.is_active or admin.status != "Active":
            admin.is_active = True
            admin.status = "Active"
            changed = True
        if not admin.full_name:
            admin.full_name = settings.admin_full_name
            changed = True
        if changed:
            db.commit()
            db.refresh(admin)

    updated = db.query(Invoice).filter(Invoice.owner_id.is_(None)).update(
        {
            Invoice.owner_id: admin.id,
            Invoice.owner_role: "admin",
            Invoice.created_by: admin.id,
        },
        synchronize_session=False,
    )
    if updated:
        db.commit()
        logger.info("Assigned %s legacy invoice(s) to admin.", updated)
    return admin


create_demo_admin = create_admin_user
