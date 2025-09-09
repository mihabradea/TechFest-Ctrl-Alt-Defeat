from __future__ import annotations
import os, csv
from datetime import datetime, timedelta, timezone
from typing import Tuple, Iterable, Dict

from techfest.backend.paypal_transactions.auth import fetch_paypal_token
from techfest.backend.paypal_transactions.transactions import fetch_transactions

FIELDS = [
    "transaction_id",
    "transaction_initiation_date",
    "transaction_status",
    "description",
    "transaction_subject",
    "invoice_id",
    "sender_name",
    "payer_email",
    "amount_value",
    "amount_currency",
]


def _row_from_txn(txn: Dict) -> Dict:
    info = (txn.get("transaction_info") or {})
    payer = (txn.get("payer_info") or {})
    cart = (txn.get("cart_info") or {})

    amount = (info.get("transaction_amount") or {}) or {}
    # Try to pull a human description: prefer item name(s), else subject
    desc = None
    items = cart.get("item_details") or []
    if items:
        names = [i.get("item_name") for i in items if i.get("item_name")]
        if names:
            desc = ", ".join(names)
    if not desc:
        desc = info.get("transaction_subject")

    # Invoice id can live in a few places
    invoice_id = (
            info.get("invoice_id") or
            cart.get("paypal_invoice_id") or
            cart.get("cart_invoice_id")
    )

    sender_name = (
            (payer.get("payer_name") or {}).get("alternate_full_name")
            or (payer.get("payer_name") or {}).get("given_name")
            or (payer.get("payer_name") or {}).get("surname")
            or payer.get("payer_name")
    )

    return {
        "transaction_id": info.get("transaction_id"),
        "transaction_initiation_date": info.get("transaction_initiation_date"),
        "transaction_status": info.get("transaction_status"),
        "description": desc,
        "transaction_subject": info.get("transaction_subject"),
        "invoice_id": invoice_id,
        "sender_name": sender_name,
        "payer_email": payer.get("email_address") or payer.get("payer_email"),
        "amount_value": (amount.get("value") if isinstance(amount, dict) else None),
        "amount_currency": (amount.get("currency_code") if isinstance(amount, dict) else None),
    }


def export_transactions_csv(days: int = 90, csv_path: str = "out/txns_last90d.csv") -> Tuple[int, str]:
    """
    Fetch last `days` of balance-affecting transactions and write them to CSV.
    Returns (rows_written, csv_path).
    """
    token = fetch_paypal_token()
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)

    tx_iter: Iterable[Dict] = fetch_transactions(
        start_dt=start_dt,
        end_dt=end_dt,
        access_token=token,
        page_size=500,
        balance_affecting_only=True,
    )

    rows = [_row_from_txn(txn) for txn in tx_iter]

    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    return len(rows), csv_path


def ensure_csv(csv_path: str = "out/txns_last90d.csv", days: int = 90, refresh: bool = False) -> str:
    """
    If `csv_path` is missing or `refresh=True`, (re)generate it.
    Returns the path.
    """
    if refresh or not os.path.exists(csv_path):
        export_transactions_csv(days=days, csv_path=csv_path)
    return csv_path