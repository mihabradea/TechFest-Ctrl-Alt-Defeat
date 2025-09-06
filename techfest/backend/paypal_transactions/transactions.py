import logging
from typing import Dict, Generator, Iterable, Tuple
from datetime import datetime, timedelta, timezone
import requests
from .config import paypal_base_url

log = logging.getLogger("paypalx.transactions")

def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

def _chunked_windows(start: datetime, end: datetime, max_days: int = 31
                    ) -> Generator[Tuple[str, str], None, None]:
    if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:   end = end.replace(tzinfo=timezone.utc)
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
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
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
    if resp.status_code >= 400:
        try:
            log.error("Transactions API %s: %s", resp.status_code, resp.json())
        except Exception:
            log.error("Transactions API %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()

def fetch_transactions(
    start_dt: datetime,
    end_dt: datetime,
    access_token: str,
    page_size: int = 500,
    balance_affecting_only: bool = True,
) -> Iterable[Dict]:
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

            total_pages = data.get("total_pages")
            if total_pages is not None:
                if page >= int(total_pages):
                    break
                page += 1
            else:
                links = {lk.get("rel"): lk.get("href") for lk in data.get("links", [])}
                if "next" in links:
                    page += 1
                    continue
                break

def print_transaction_summary(txn: Dict) -> None:
    info = txn.get("transaction_info", {}) or {}
    payer = txn.get("payer_info", {}) or {}
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
