from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import uuid
from jose import jwt, JWTError
import os as os
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-prod")  # set env var in prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# OAuth2 bearer (used only to read Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo user store (replace with DB). Password here is "password123".
_fake_users_db = {
    "alice": {
        "username": "alice",
        "hashed_password": pwd_context.hash("password123"),
        "disabled": False,
    }
}

# In-memory blacklist for JWTs (use Redis/DB in production)
BLACKLISTED_JTIS: set[str] = set()

def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def _authenticate_user(username: str, password: str):
    user = _fake_users_db.get(username)
    if not user:
        return None
    if not _verify_password(password, user["hashed_password"]):
        return None
    return user

def _create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
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
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_active_token(token: str = Depends(oauth2_scheme)) -> dict:
    payload = _decode_token(token)
    jti = payload.get("jti")
    if not jti or jti in BLACKLISTED_JTIS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is revoked or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload