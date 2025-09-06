# main.py
import sys
import base64
import logging
import traceback
import httpx
import os
import requests
from datetime import datetime

# --- Agents SDK + your agent ---
from agents import Runner                  # pip install openai-agents
# from pydantic.mypy import BASEMODEL_FULLNAME

from tools_paypal_agent.agents_class import agent     # <-- keep this import path as in your project

# -------- Logging setup --------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)
log = logging.getLogger("main")

# -------- Helpers --------
def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        log.error("Missing required env var: %s", name)
        sys.exit(1)
    return val

def paypal_base_url() -> str:
    env = os.getenv("PAYPAL_ENV", "sandbox").lower()
    if env not in ("sandbox", "live"):
        env = "sandbox"
    base_url = "https://api-m.paypal.com" if env == "live" else "https://api-m.sandbox.paypal.com"
    log.debug("Resolved PAYPAL_ENV=%s -> base_url=%s", env, base_url)
    return base_url

# -------- Step 1: fetch PayPal OAuth token (and print only the token) --------
def fetch_paypal_token() -> str:
    client_id = require_env("PAYPAL_CLIENT_ID")
    secret = require_env("PAYPAL_CLIENT_SECRET")

    # Masked debug for creds presence (not values)
    log.info("Starting PayPal OAuth (sandbox/live decided by PAYPAL_ENV).")
    log.debug("PAYPAL_CLIENT_ID present: %s", "yes" if client_id else "no")
    log.debug("PAYPAL_CLIENT_SECRET present: %s", "yes" if secret else "no")

    base_url = paypal_base_url()

    basic = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
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
                sys.exit(4)
            return token
    except httpx.HTTPStatusError as e:
        log.error("PayPal OAuth failed (%s): %s", e.response.status_code, e.response.text)
        sys.exit(2)
    except Exception as e:
        log.error("Unexpected error during OAuth: %s", e)
        log.debug("Traceback:\n%s", traceback.format_exc())
        sys.exit(3)

# -------- Step 2: run the agent once --------
# def run_agent_once(user_msg: str):
#     # OPENAI key needed for the agent thought+tool selection
#     require_env("OPENAI_API_KEY")
#
#     log.info("Initializing Runner and invoking the agent…")
#     log.debug("User message: %s", user_msg)
#
#     try:
#         # Synchronous, one-shot
#         result = Runner.run_sync(agent, user_msg)
#         # Try to pull a friendly message; otherwise dump the object
#         final_text = getattr(result, "final_output", None)
#         if final_text:
#             log.info("Agent completed successfully.")
#             print("\n=== Agent output ===\n" + final_text)
#         else:
#             log.warning("Agent returned no final_output; printing raw result.")
#             print("\n=== Agent raw result ===\n", result)
#     except Exception as e:
#         log.error("Agent run failed: %s", e)
#         log.debug("Traceback:\n%s", traceback.format_exc())
#         # If your Agents SDK nests tool errors, you can try to surface more detail:
#         tool_err = getattr(e, "tool_error", None)
#         if tool_err:
#             log.error("Nested tool error: %s", tool_err)
#         # Exit non-zero to make failures obvious in CI/runner
#         sys.exit(5)



# ==== PayPal Transactions Helpers ============================================
from typing import Dict, Generator, Iterable, Tuple

def _iso(ts: datetime) -> str:
    """PayPal requires UTC ISO8601 with seconds + Z."""
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

def _chunked_windows(start: datetime, end: datetime, max_days: int = 31
                    ) -> Generator[Tuple[str, str], None, None]:
    """
    Yield [start,end] ISO8601 windows no longer than max_days (PayPal limit).
    Both inputs must be timezone-agnostic UTC datetimes (as you're doing with utcnow()).
    """
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=max_days), end)
        yield _iso(cursor), _iso(nxt)
        cursor = nxt

def _request_transactions_page(
    access_token: str,
    start_iso: str,
    end_iso: str,
    page: int,
    page_size: int = 500,
    balance_affecting_only: bool = True,
) -> Dict:
    """
    Request one page from /v1/reporting/transactions.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "start_date": start_iso,
        "end_date": end_iso,
        "fields": "all",
        "page_size": page_size,
        "page": page,
        "balance_affecting_records_only": "Y" if balance_affecting_only else "N",
    }
    base_url = paypal_base_url()
    resp = requests.get(f"{base_url}/v1/reporting/transactions",
                        headers=headers, params=params, timeout=40)
    resp.raise_for_status()
    return resp.json()

def fetch_transactions(
    start_dt: datetime,
    end_dt: datetime,
    access_token: str,
    page_size: int = 500,
    balance_affecting_only: bool = True,
) -> Iterable[Dict]:
    """
    Fetch ALL transactions between start_dt and end_dt (any span),
    handling 31-day windowing and pagination under the hood.
    Yields individual transaction dicts (items in 'transaction_details').
    """
    if start_dt >= end_dt:
        return

    for start_iso, end_iso in _chunked_windows(start_dt, end_dt, max_days=31):
        page = 1
        while True:
            data = _request_transactions_page(
                access_token, start_iso, end_iso, page,
                page_size=page_size,
                balance_affecting_only=balance_affecting_only,
            )

            for txn in data.get("transaction_details", []) or []:
                yield txn

            # Pagination handling
            total_pages = data.get("total_pages")
            if total_pages is None:
                # Fall back to link rel=next if total_pages missing
                links = {lk.get("rel"): lk.get("href") for lk in data.get("links", [])}
                if "next" in links:
                    page += 1
                    continue
                break
            else:
                if page >= int(total_pages):
                    break
                page += 1

def print_transaction_summary(txn: Dict) -> None:
    """
    Pretty-print a single transaction row (safe lookups).
    """
    info = txn.get("transaction_info", {})
    payer = txn.get("payer_info", {})
    amt = info.get("transaction_amount", {}) or {}
    print(
        "ID: {id} | Time: {time} | Status: {status} | "
        "Amount: {val} {ccy} | Payer: {email}".format(
            id=info.get("transaction_id", "-"),
            time=info.get("transaction_initiation_date", "-"),
            status=info.get("transaction_status", "-"),
            val=amt.get("value", "-"),
            ccy=amt.get("currency_code", "-"),
            email=payer.get("email_address", "-"),
        )
    )
# ============================================================================

# -------- Main --------
##


# if __name__ == "__main__":
#
#     token = fetch_paypal_token()
#     print(token)  # <- keep as the first line of stdout, as requested
#     log.info("Successfully obtained PayPal access token (not logged).")
#
#     # 2) Call the agent with a precise, schema-shaped request
#     #    Tip: include application_context to get an approval link back.
#     user_msg = (
#         "Use create_order with this JSON: "
#         '{"intent":"CAPTURE","purchase_units":[{"amount":{"currency_code":"USD","value":"10.00"}}],'
#         '"application_context":{"return_url":"https://example.com/return","cancel_url":"https://example.com/cancel"}}. '
#         "Then give me the approval link."
#     )
#
#     run_agent_once(user_msg)

def get_transactions(start_date, end_date, access_token):
    """Fetch transactions between start_date and end_date (ISO 8601 format)"""
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "fields": "all",
        "page_size": 100
    }
    BASE_URL = paypal_base_url()
    resp = requests.get(f"{BASE_URL}/v1/reporting/transactions", headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

from datetime import datetime, timedelta, timezone
#
if __name__ == "__main__":
    # Example: fetch the last 7 days (you can expand to months/years)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)
    # 1) OAuth
    token = fetch_paypal_token()

    # 2) Fetch + print
    txns = fetch_transactions(
        start_dt=start_time,
        end_dt=end_time,
        access_token=token,
        page_size=500,                 # max allowed; reduce if you prefer
        balance_affecting_only=True,   # set False to include non-balance records
    )

    count = 0
    for t in txns:
        print_transaction_summary(t)
        count += 1

    print(f"\nTotal transactions: {count}")