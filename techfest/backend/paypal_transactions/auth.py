import base64
import logging
import os
from datetime import timedelta

import httpx
from fastapi import Depends
from select import select
from sqlalchemy import desc

from .config import require_env, paypal_base_url
from sqlalchemy.orm import Session

from ..db.database import SessionLocal, get_db
from ..db.models import now_utc, PayPalToken

client_id = os.getenv("CLIENT_ID", "AUwDbh92cYpOxREvA3aeugMEfJdMH5U-HwMvLi0z-ABQQ0puDUd1ijGzFsh6s7ugl2zisrqI4tZGYRAT")

log = logging.getLogger("paypalx.auth")

"""
def fetch_paypal_token() -> str:
    client_id = os.getenv("CLIENT_ID", "AUwDbh92cYpOxREvA3aeugMEfJdMH5U-HwMvLi0z-ABQQ0puDUd1ijGzFsh6s7ugl2zisrqI4tZGYRAT")
    secret = os.getenv("CLIENT_SECRET","EL9UjcK_RLn94hX6HaDKhGfLXPh4L-_RAU-kUtVJZdlQGRbT2re1iiTTjFccDKczOjUZjLyAKUckTERG")


    base_url = paypal_base_url()
    basic = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    try:
        log.info("POST %s/v1/oauth2/token", base_url)
        with httpx.Client(timeout=20.0) as client:
            r = client.post(f"{base_url}/v1/oauth2/token",
                            headers=headers,
                            data={"grant_type": "client_credentials"})
            log.debug("OAuth response status: %s", r.status_code)
            r.raise_for_status()
            data = r.json()
            token = data.get("access_token")
            if not token:
                log.error("No access_token found in OAuth response.")
                raise SystemExit(4)
            return token
    except httpx.HTTPStatusError as e:
        log.error("PayPal OAuth failed (%s): %s", e.response.status_code, e.response.text)
        raise SystemExit(2)
"""
class NoValidPayPalToken(Exception):
    """Raised when no valid (non-expired) PayPal access token is found."""

def fetch_paypal_token(
    db: Session = Depends(get_db),
    *,
    leeway_seconds: int = 60,
    allow_expired_fallback: bool = False,
) -> str:
    """
    Return the latest non-expired PayPal access token from DB.

    - leeway_seconds: subtract this from expiry to be conservative about edge-of-expiry tokens.
    - allow_expired_fallback: if True and no valid token exists, return the most recent token
      even if expired (NOT recommended unless your caller will immediately refresh/re-auth).

    Raises:
        NoValidPayPalToken if no suitable token is found.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        now_with_leeway = now_utc() + timedelta(seconds=leeway_seconds)

        # 1) Try to get a still-valid token (latest first)
        stmt_valid = (
            select(PayPalToken)
            .where(PayPalToken.expires_at > now_with_leeway)
            .order_by(desc(PayPalToken.expires_at), desc(PayPalToken.created_at))
            .limit(1)
        )
        result = db.execute(stmt_valid).scalars().first()
        if result and result.access_token:
            return result.access_token

        # 2) Optionally, fall back to the latest token regardless of expiry
        if allow_expired_fallback:
            stmt_any = (
                select(PayPalToken)
                .order_by(desc(PayPalToken.expires_at), desc(PayPalToken.created_at))
                .limit(1)
            )
            any_token = db.execute(stmt_any).scalars().first()
            if any_token and any_token.access_token:
                return any_token.access_token

        # 3) Nothing suitable found
        raise NoValidPayPalToken("No valid PayPal access token found in database.")

    finally:
        if owns_session and db is not None:
            db.close()



############################# Invoicing-related auth #############################

import base64
import logging
import httpx
from .config import paypal_base_url

log = logging.getLogger("paypalx.auth")

def fetch_paypal_token_for_issuer() -> str:
    """
    Get an OAuth token using explicit credentials (for a *different* business).
    Uses the same PAYPAL_ENV as your app (sandbox/live).
    """

    client_id = require_env("ISSUER_CLIENT_ID")
    secret = require_env("ISSUER_CLIENT_SECRET")

    base_url = paypal_base_url()
    basic = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.post(f"{base_url}/v1/oauth2/token",
                        headers=headers,
                        data={"grant_type": "client_credentials"})
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("No access_token in OAuth response for issuer business.")
        return token