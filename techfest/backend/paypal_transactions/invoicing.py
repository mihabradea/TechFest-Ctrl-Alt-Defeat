# paypalx/invoicing.py
import requests
from .config import paypal_base_url

def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}

from datetime import datetime, timedelta, timezone
import requests

def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def list_unpaid_or_sent(token: str, days: int = 365, page: int = 1, page_size: int = 50) -> dict:
    """
    Finds UNPAID/SENT within an explicit created_time window.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    url = f"{paypal_base_url()}/v2/invoicing/search-invoices"
    params = {"page": page, "page_size": page_size, "total_required": True}  # boolean, not string
    body = {
        "status": ["UNPAID", "SENT"],
        "created_time": {"start": _iso_utc(start), "end": _iso_utc(now)},
    }
    r = requests.post(url, headers=_headers(token), params=params, json=body, timeout=40)
    r.raise_for_status()
    return r.json()

def list_any_invoices(token: str, page: int = 1, page_size: int = 20) -> dict:
    """
    GET list without status filter to inspect what's visible to this token.
    """
    url = f"{paypal_base_url()}/v2/invoicing/invoices"
    params = {"page": page, "page_size": page_size, "total_required": True}
    r = requests.get(url, headers=_headers(token), params=params, timeout=40)
    r.raise_for_status()
    return r.json()

def _pick_latest_invoice_id(items: list[dict]) -> str | None:
    """
    Choose the 'latest' invoice by detail.invoice_date (YYYY-MM-DD),
    with a fallback to detail.metadata.create_time (RFC3339).
    """
    from datetime import datetime, timezone

    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def parse_dt(s):
        try:
            # sample: 2018-11-12T08:00:20Z
            s2 = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s2)
        except Exception:
            return None

    def key(inv):
        d = (inv.get("detail") or {})
        invoice_date = parse_date(d.get("invoice_date", ""))
        created = parse_dt((d.get("metadata") or {}).get("create_time", ""))
        return invoice_date or created

    if not items:
        return None
    items_sorted = sorted(items, key=key, reverse=True)
    return items_sorted[0].get("id")

def show_invoice(token: str, invoice_id: str):
    resp = requests.get(f"{paypal_base_url()}/v2/invoicing/invoices/{invoice_id}",
                        headers=_headers(token), timeout=40)
    resp.raise_for_status()
    data = resp.json()
    meta = (data.get("detail") or {}).get("metadata") or {}
    # URL the customer uses to pay:
    return data, meta.get("recipient_view_url"), meta.get("invoicer_view_url")


def send_invoice(token: str, invoice_id: str, share_link_only: bool = True):
    # share_link_only=True -> don't email; you’ll fetch the link and send it yourself
    r = requests.post(f"{paypal_base_url()}/v2/invoicing/invoices/{invoice_id}/send",
                      headers=_headers(token),
                      json={"send_to_recipient": not share_link_only}, timeout=40)
    r.raise_for_status()


def build_pay_link_for_invoice(token: str, invoice_id: str) -> str | None:
    """
    Returns recipient payer URL for an UNPAID/SENT invoice.
    (No duplication of paid invoices in this trimmed version.)
    """
    inv_json, pay_url, _ = show_invoice(token, invoice_id)
    detail = inv_json.get("detail") or {}
    status = (detail.get("status") or inv_json.get("status") or "").upper()

    if status in ("UNPAID", "SENT"):

        if not pay_url:
            try:
                send_invoice(token, invoice_id, share_link_only=True)
                _, pay_url, _ = show_invoice(token, invoice_id)
            except Exception:
                pass
        return pay_url

    return None



def build_pay_link_for_last_unpaid(token: str) -> tuple[str | None, str | None]:
    """
    Find the most recent payable invoice (UNPAID or SENT) and return its pay link.

    Returns (invoice_id, pay_url) or (None, None) if none found.
    Internally reuses your build_pay_link_for_invoice() so headers/scopes are correct.
    """
    listing = _list_unpaid_invoices(token, page=1, page_size=50)
    items = listing.get("items") or []
    inv_id = _pick_latest_invoice_id(items)
    if not inv_id:
        return None, None

    # This will:
    # - return recipient_view_url for UNPAID/SENT,
    # - send drafts if somehow returned,
    # - NOT duplicate since it's unpaid/sent (allow_duplicate_if_paid=False).
    used_id, url = build_pay_link_for_invoice(token, inv_id, allow_duplicate_if_paid=False)
    return used_id, url