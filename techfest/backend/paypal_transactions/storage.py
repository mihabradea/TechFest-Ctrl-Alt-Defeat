import sqlite3
import json
import csv
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DB_PATH_DEFAULT = "out/paypal_txn_last90d.db"  # recreated each run by default

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions(
    transaction_id          TEXT PRIMARY KEY,
    initiation_time         TEXT,
    updated_time            TEXT,
    status                  TEXT,
    event_code              TEXT,

    amount_value            REAL,
    amount_currency         TEXT,
    fee_value               REAL,
    fee_currency            TEXT,

    -- Sender (payer) details
    sender_name             TEXT,
    payer_given_name        TEXT,
    payer_surname           TEXT,
    payer_email             TEXT,
    payer_id                TEXT,
    payer_country_code      TEXT,
    payer_phone             TEXT,

    -- Invoice/cart enrichment
    invoice_id              TEXT,   -- from transaction_info (kept)
    cart_invoice_id         TEXT,   -- from cart_info when present
    item_count              INTEGER,
    item_names              TEXT,   -- semicolon-joined item titles
    item_skus               TEXT,   -- semicolon-joined item codes/SKUs
    item_json               TEXT,   -- raw cart_info.item_details JSON
    description             TEXT,   -- human-friendly summary built from items

    raw_json                TEXT
);
"""

def init_db(db_path: str = DB_PATH_DEFAULT, wipe: bool = True) -> sqlite3.Connection:
    """
    Create (and optionally wipe) the DB so schema changes apply cleanly each run.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if wipe and os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA_SQL)
    conn.commit()
    return conn

def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _name_from_payer(payer: Dict) -> Tuple[str, str, str]:
    """
    Build (full, given, surname) from payer_info.payer_name;
    prefer alternate_full_name if present.
    """
    name = (payer or {}).get("payer_name") or {}
    given = name.get("given_name")
    sur   = name.get("surname")
    full  = name.get("alternate_full_name") or " ".join([p for p in [given, sur] if p])
    return (full or None, given, sur)

def _cart_aggregates(cart_info: Dict) -> Tuple[int, str, str, str, str]:
    """
    Build counts & descriptions from cart_info.item_details.
    Returns (item_count, item_names, item_skus, item_json, description)
    """
    items: List[Dict] = (cart_info or {}).get("item_details") or []
    names: List[str] = []
    skus:  List[str] = []
    parts: List[str] = []

    for it in items:
        name = it.get("item_name") or it.get("name")
        code = it.get("item_code") or it.get("sku")
        qty  = it.get("item_quantity") or it.get("quantity")
        # Compose a friendly piece like: "Widget x2"
        if name and qty:
            parts.append(f"{name} x{qty}")
        elif name:
            parts.append(name)
        if name:
            names.append(name)
        if code:
            skus.append(code)

    item_json = json.dumps(items, separators=(",", ":"), ensure_ascii=False) if items else None
    desc = "; ".join(parts) if parts else None
    return (len(items), "; ".join(names) if names else None, "; ".join(skus) if skus else None, item_json, desc)

def _flatten_txn(txn: Dict) -> Dict:
    info  = txn.get("transaction_info", {}) or {}
    payer = txn.get("payer_info", {}) or {}
    cart  = txn.get("cart_info", {}) or {}

    amt   = info.get("transaction_amount", {}) or {}
    fee   = info.get("fee_amount", {}) or {}

    sender_full, given, sur = _name_from_payer(payer)
    item_count, item_names, item_skus, item_json, cart_desc = _cart_aggregates(cart)

    # Prefer any explicit subject/note if present; else fall back to cart summary
    # (Transaction Search sometimes includes only items; invoice memo requires Invoicing API for full detail.)
    description = info.get("transaction_subject") or info.get("transaction_note") or cart_desc

    # cart invoice id may appear as invoice_id or paypal_invoice_id depending on flow
    cart_invoice_id = cart.get("invoice_id") or cart.get("paypal_invoice_id")

    return {
        "transaction_id": info.get("transaction_id"),
        "initiation_time": info.get("transaction_initiation_date"),
        "updated_time": info.get("transaction_updated_date"),
        "status": info.get("transaction_status"),
        "event_code": info.get("transaction_event_code"),

        "amount_value": _safe_float(amt.get("value")),
        "amount_currency": amt.get("currency_code"),
        "fee_value": _safe_float(fee.get("value")),
        "fee_currency": fee.get("currency_code"),

        "sender_name": sender_full,
        "payer_given_name": given,
        "payer_surname": sur,
        "payer_email": payer.get("email_address"),
        "payer_id": payer.get("account_id"),
        "payer_country_code": payer.get("country_code"),
        "payer_phone": ((payer.get("primary_phone") or {}).get("national_number")
                        or (payer.get("primary_phone") or {}).get("phone_number")),

        "invoice_id": info.get("invoice_id"),
        "cart_invoice_id": cart_invoice_id,
        "item_count": item_count,
        "item_names": item_names,
        "item_skus": item_skus,
        "item_json": item_json,
        "description": description,

        "raw_json": json.dumps(txn, separators=(",", ":"), ensure_ascii=False),
    }

def upsert_txn(cur: sqlite3.Cursor, row: Dict) -> None:
    cur.execute("""
    INSERT INTO transactions(
        transaction_id, initiation_time, updated_time, status, event_code,
        amount_value, amount_currency, fee_value, fee_currency,
        sender_name, payer_given_name, payer_surname, payer_email, payer_id, payer_country_code, payer_phone,
        invoice_id, cart_invoice_id, item_count, item_names, item_skus, item_json, description,
        raw_json
    ) VALUES(?,?,?,?,?,?,?,?,?,
             ?,?,?,?,?,?,?,
             ?,?,?,?,?,?,?,
             ?)
    ON CONFLICT(transaction_id) DO UPDATE SET
        initiation_time=excluded.initiation_time,
        updated_time=excluded.updated_time,
        status=excluded.status,
        event_code=excluded.event_code,
        amount_value=excluded.amount_value,
        amount_currency=excluded.amount_currency,
        fee_value=excluded.fee_value,
        fee_currency=excluded.fee_currency,
        sender_name=excluded.sender_name,
        payer_given_name=excluded.payer_given_name,
        payer_surname=excluded.payer_surname,
        payer_email=excluded.payer_email,
        payer_id=excluded.payer_id,
        payer_country_code=excluded.payer_country_code,
        payer_phone=excluded.payer_phone,
        invoice_id=excluded.invoice_id,
        cart_invoice_id=excluded.cart_invoice_id,
        item_count=excluded.item_count,
        item_names=excluded.item_names,
        item_skus=excluded.item_skus,
        item_json=excluded.item_json,
        description=excluded.description,
        raw_json=excluded.raw_json;
    """, (
        row["transaction_id"], row["initiation_time"], row["updated_time"], row["status"], row["event_code"],
        row["amount_value"], row["amount_currency"], row["fee_value"], row["fee_currency"],
        row["sender_name"], row["payer_given_name"], row["payer_surname"], row["payer_email"], row["payer_id"], row["payer_country_code"], row["payer_phone"],
        row["invoice_id"], row["cart_invoice_id"], row["item_count"], row["item_names"], row["item_skus"], row["item_json"], row["description"],
        row["raw_json"]
    ))

def ingest_to_sqlite(txns: Iterable[Dict], db_path: str = DB_PATH_DEFAULT) -> int:
    conn = init_db(db_path, wipe=True)  # recreate to apply new schema each run
    cur = conn.cursor()
    count = 0
    for txn in txns:
        row = _flatten_txn(txn)
        if not row["transaction_id"]:
            continue
        upsert_txn(cur, row)
        count += 1
    conn.commit()
    conn.close()
    return count

def export_csv(db_path: str, out_csv: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            transaction_id, initiation_time, updated_time, status, event_code,
            amount_value, amount_currency, fee_value, fee_currency,
            sender_name, payer_given_name, payer_surname, payer_email, payer_id, payer_country_code, payer_phone,
            invoice_id, cart_invoice_id, item_count, item_names, item_skus, description
        FROM transactions
        ORDER BY initiation_time DESC
    """)
    rows = cur.fetchall()
    conn.close()

    headers = [
        "transaction_id","initiation_time","updated_time","status","event_code",
        "amount_value","amount_currency","fee_value","fee_currency",
        "sender_name","payer_given_name","payer_surname","payer_email","payer_id","payer_country_code","payer_phone",
        "invoice_id","cart_invoice_id","item_count","item_names","item_skus","description"
    ]
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return len(rows)
