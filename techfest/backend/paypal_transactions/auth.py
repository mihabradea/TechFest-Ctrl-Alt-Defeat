import base64
import logging
import os

import httpx

from .config import require_env, paypal_base_url

client_id = os.getenv("CLIENT_ID", "AUwDbh92cYpOxREvA3aeugMEfJdMH5U-HwMvLi0z-ABQQ0puDUd1ijGzFsh6s7ugl2zisrqI4tZGYRAT")

log = logging.getLogger("paypalx.auth")

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