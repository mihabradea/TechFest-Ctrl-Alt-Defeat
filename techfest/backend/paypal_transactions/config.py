import os
import logging

log = logging.getLogger("paypalx.config")

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        log.error("Missing required env var: %s", name)
        raise SystemExit(1)
    return val

def paypal_base_url() -> str:
    env = os.getenv("PAYPAL_ENV", "sandbox").lower()
    if env not in ("sandbox", "live"):
        env = "sandbox"
    base_url = "https://api-m.paypal.com" if env == "live" else "https://api-m.sandbox.paypal.com"
    log.debug("Resolved PAYPAL_ENV=%s -> base_url=%s", env, base_url)
    return base_url
