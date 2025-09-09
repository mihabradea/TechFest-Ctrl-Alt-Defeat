# Minimal user model: store email only
from datetime import datetime, timezone
import uuid
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from .database import Base

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def gen_uuid_str() -> str:
    # 36-char UUID string with hyphens
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    # Store UUID as a 36-char string for SQLite
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Token(Base):
    __tablename__ = "tokens"

    # JWT ID (jti) as UUID4 hex (32) or 36 with hyphens; we’ll keep 32-hex from your code
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4 string ok here

    subject: Mapped[str] = mapped_column(String(320), index=True, nullable=False)  # email
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
