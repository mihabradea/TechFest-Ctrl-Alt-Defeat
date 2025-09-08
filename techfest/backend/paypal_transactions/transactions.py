import logging
from typing import Dict, Generator, Iterable, Tuple
from datetime import datetime, timedelta, timezone
import requests
from .config import paypal_base_url
from .auth import fetch_paypal_token
from .storage import ingest_to_sqlite, export_csv, DB_PATH_DEFAULT

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


OUTPUT_CSV = "out/txns_last90d.csv"


def save_transactions(token):
    # 90-day window (the fetcher handles 31-day chunking/pagination)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=90)

    log.info("Fetching PayPal transactions for last 90 days: %s → %s",
             start_time.isoformat(), end_time.isoformat())



    # Fetch iterator
    txns_iter = fetch_transactions(
        start_dt=start_time,
        end_dt=end_time,
        access_token=token,
        page_size=500,
        balance_affecting_only=True,
    )

    # Ingest into a fresh SQLite (scoped to this 90d window), then export CSV
    rows = ingest_to_sqlite(txns_iter, db_path=DB_PATH_DEFAULT)
    log.info("Ingested/updated %d transactions into %s", rows, DB_PATH_DEFAULT)

    exported = export_csv(DB_PATH_DEFAULT, OUTPUT_CSV)
    log.info("Exported %d rows to %s", exported, OUTPUT_CSV)

    print(f"Done. CSV at: {OUTPUT_CSV}")