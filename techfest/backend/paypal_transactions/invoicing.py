# backend/paypal_transactions/invoicing.py
from typing import Optional, Tuple, List, Dict
import requests
from datetime import datetime, timezone

from techfest.backend.paypal_transactions import config  # absolute module import

# ----------------- headers -----------------
def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

# ----------------- listing unpaid/sent -----------------
def _list_unpaid_invoices(token: str, page: int = 1, page_size: int = 50) -> dict:
    base_url = config.paypal_base_url()
    url = f"{base_url}/v2/invoicing/search-invoices"
    params = {"page": page, "page_size": page_size, "total_required": True}
    body = {"status": ["UNPAID", "SENT"]}
    r = requests.post(url, headers=_headers(token), params=params, json=body, timeout=40)
    r.raise_for_status()
    return r.json()

def _pick_latest_invoice_id(items: List[dict]) -> Optional[str]:
    def parse_date(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    def key(inv: dict) -> Optional[datetime]:
        d = (inv.get("detail") or {})
        return parse_date(d.get("invoice_date")) or parse_dt((d.get("metadata") or {}).get("create_time"))

    if not items:
        return None
    items_sorted = sorted(items, key=key, reverse=True)
    return items_sorted[0].get("id")

# ----------------- show/send invoice -----------------
def show_invoice(token: str, invoice_id: str):
    base_url = config.paypal_base_url()
    resp = requests.get(f"{base_url}/v2/invoicing/invoices/{invoice_id}",
                        headers=_headers(token), timeout=40)
    resp.raise_for_status()
    data = resp.json()
    meta = (data.get("detail") or {}).get("metadata") or {}
    return data, meta.get("recipient_view_url"), meta.get("invoicer_view_url")

def send_invoice(token: str, invoice_id: str, share_link_only: bool = True):
    base_url = config.paypal_base_url()
    r = requests.post(f"{base_url}/v2/invoicing/invoices/{invoice_id}/send",
                      headers=_headers(token),
                      json={"send_to_recipient": not share_link_only}, timeout=40)
    r.raise_for_status()

# ----------------- PUBLIC: build pay link for a known invoice -----------------
def build_pay_link_for_invoice(token: str, invoice_id: str) -> Tuple[str, Optional[str]]:
    """
    Always returns exactly (used_invoice_id, pay_url_or_None).
    No duplication of paid invoices here; it only handles UNPAID/SENT/DRAFT.
    """
    inv_json, pay_url, _ = show_invoice(token, invoice_id)
    detail = inv_json.get("detail") or {}
    status = (detail.get("status") or inv_json.get("status") or "").upper()

    if status in ("UNPAID", "SENT"):
        # Ensure a link exists; if absent, send and re-fetch
        if not pay_url:
            send_invoice(token, invoice_id, share_link_only=True)
            _, pay_url, _ = show_invoice(token, invoice_id)
        result = (invoice_id, pay_url)
    elif status in ("DRAFT",):
        # Send then fetch link
        send_invoice(token, invoice_id, share_link_only=True)
        _, pay_url, _ = show_invoice(token, invoice_id)
        result = (invoice_id, pay_url)
    else:
        # PAID/VOID/CANCELLED/etc. -> no link in this minimal flow
        result = (invoice_id, None)

    # hard-guard against accidental return-shape drift
    assert isinstance(result, tuple) and len(result) == 2, f"Unexpected return: {result!r}"
    return result

# ----------------- PUBLIC: newest unpaid/sent -> pay link -----------------
def build_pay_link_for_last_unpaid(token: str) -> Tuple[Optional[str], Optional[str]]:
    listing = _list_unpaid_invoices(token, page=1, page_size=50)
    items = listing.get("items") or []
    inv_id = _pick_latest_invoice_id(items)
    if not inv_id:
        return None, None
    used_id, url = build_pay_link_for_invoice(token, inv_id)
    assert isinstance(used_id, str) or used_id is None
    return used_id, url

# ----------------- PUBLIC: other-business credentials -> pay link -----------------
# If you use a helper like fetch_paypal_token_for, import it here:
try:
    from techfest.backend.paypal_transactions.auth import fetch_paypal_token_for  # your earlier helper
except Exception:
    fetch_paypal_token_for = None  # optional

def pay_link_for_other_business_last_unpaid(
    issuer_client_id: str,
    issuer_client_secret: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Authenticate as the issuing business, pick the newest UNPAID/SENT invoice,
    and return (invoice_id, recipient_view_url). Returns (None, None) if none found.
    """
    if fetch_paypal_token_for is None:
        raise RuntimeError("fetch_paypal_token_for not available; import or implement it in auth.py")
    token = fetch_paypal_token_for(issuer_client_id, issuer_client_secret)
    used_id, url = build_pay_link_for_last_unpaid(token)
    assert (used_id is None) or isinstance(used_id, str)
    return used_id, url
