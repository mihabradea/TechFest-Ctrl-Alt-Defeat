from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import uuid
from jose import jwt, JWTError
import os as os
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from techfest.backend.db.database import get_db
from techfest.backend.db import models
from typing import Optional, Dict, Any

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-prod")  # set env var in prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# OAuth2 bearer (used only to read Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_or_create_user_by_email(db: Session, email: str) -> models.User:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        return user

    # Create a new minimal user
    user = models.User(email=email, last_login=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_access_token_db(
    db: Session,
    subject: str,
    user_id: Optional[str] = None,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    jti = uuid.uuid4().hex

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "jti": jti,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # persist token record
    db_token = models.Token(
        jti=jti,
        subject=subject,
        user_id=user_id,
        issued_at=now,
        expires_at=expire,
        revoked=False,
        revoked_at=None,
    )
    db.add(db_token)
    db.commit()
    return token

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def _as_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # interpret naive timestamps from SQLite as UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def require_active_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_token = db.get(models.Token, jti)
    if not db_token or db_token.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is revoked or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at_aware = _as_aware_utc(db_token.expires_at)
    now_aware = datetime.now(timezone.utc)
    if expires_at_aware <= now_aware:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def revoke_current_token(payload: Dict[str, Any], db: Session) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    db_token = db.get(models.Token, jti)
    if db_token and not db_token.revoked:
        db_token.revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        db.add(db_token)
        db.commit()