# paypalx/notify.py
import csv
import os
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Optional, Tuple, List
from techfest.backend.paypal_transactions.auth import fetch_paypal_token_for_issuer
from techfest.backend.paypal_transactions.invoicing import _list_unpaid_invoices, build_pay_link_for_invoice, \
    _pick_latest_invoice_id


def _norm(s: str) -> str:
    return s.strip().lower().replace(" ", "_")

def _parse_iso8601_utc(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        d = datetime.fromisoformat(s2)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        else:
            d = d.astimezone(timezone.utc)
        return d
    except Exception:
        return None

def _columns_map(header) -> Dict[str, str]:
    """Map normalized names to actual CSV columns."""
    return {_norm(h): h for h in header}

def _pick(cols_map: Dict[str, str], candidates) -> Optional[str]:
    for c in candidates:
        if c in cols_map:
            return cols_map[c]
    return None

def _last_month_same_day_or_prev_friday(today_utc: datetime) -> date:
    """Same day last month; if weekend, roll back to previous Friday (stays in last month)."""
    y = today_utc.year
    m = today_utc.month
    # compute previous month
    if m == 1:
        pm_y, pm_m = y - 1, 12
    else:
        pm_y, pm_m = y, m - 1

    # find last day of previous month
    if pm_m == 12:
        next_y, next_m = pm_y + 1, 1
    else:
        next_y, next_m = pm_y, pm_m + 1
    first_of_next = date(next_y, next_m, 1)
    last_day_prev = first_of_next - timedelta(days=1)

    # clamp day
    day = min(today_utc.day, last_day_prev.day)
    d = date(pm_y, pm_m, day)
    # roll back to Friday if weekend
    while d.weekday() >= 5:  # 5=Sat,6=Sun
        d = d - timedelta(days=1)
    return d




def notify_same_day_last_month(csv_path: str) -> Tuple[str, Optional[Dict]]:
    """
    Returns (message, row_dict_or_None). If no matching transaction, row is None.
    """
    if not os.path.exists(csv_path):
        return ("No recurring payment (CSV not found).", None)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            return ("No recurring payment (CSV empty).", None)
        cols_map = _columns_map(reader.fieldnames)

    time_col = _pick(cols_map, ["initiation_time","time","transaction_time","transaction_initiation_date"])
    desc_col = _pick(cols_map, ["description","item_names","transaction_subject","note","memo"])
    payer_col= _pick(cols_map, ["sender_name","payer_email","payer_name","payer"])
    val_col  = _pick(cols_map, ["amount_value","amount","transaction_amount_value","value"])
    ccy_col  = _pick(cols_map, ["amount_currency","currency","transaction_amount_currency","currency_code"])

    if not time_col:
        return ("No recurring payment (no timestamp column).", None)

    target_date = _last_month_same_day_or_prev_friday(datetime.now(timezone.utc))

    # collect candidates for that target date
    candidates = []
    for r in rows:
        ts = _parse_iso8601_utc(r.get(time_col, ""))
        if ts and ts.date() == target_date:
            candidates.append((ts, r))

    if not candidates:
        return ("No recurring payment", None)

    # pick latest that day
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, row = candidates[0]

    desc = row.get(desc_col) if desc_col else None
    payer = row.get(payer_col) if payer_col else None
    val = row.get(val_col) if val_col else None
    ccy = row.get(ccy_col) if ccy_col else None

    parts = [f"You paid an invoice on {target_date.isoformat()}"]
    if payer: parts.append(f"from {payer}")
    if desc:  parts.append(f"— {desc}")
    if val and ccy: parts.append(f"({val} {ccy})")
    message = " ".join(parts) + ". Do you want to pay it again? (Y/N)"

    return (message, row)

def build_pay_link_for_last_unpaid(token: str) -> Tuple[Optional[str], Optional[str]]:
    listing = _list_unpaid_invoices(token, page=1, page_size=50)
    items = listing.get("items") or []
    inv_id = _pick_latest_invoice_id(items)
    if not inv_id:
        return None, None
    used_id, url = build_pay_link_for_invoice(token, inv_id)
    assert isinstance(used_id, str) or used_id is None
    return used_id, url

def _same_day_k_months_ago_or_prev_friday(today_utc: datetime, k: int) -> date:
    """Same calendar day k months ago; if weekend, roll back to previous Friday (stays in that month)."""
    y, m, d = today_utc.year, today_utc.month, today_utc.day
    # subtract k months
    new_m = m - k
    new_y = y
    while new_m <= 0:
        new_m += 12
        new_y -= 1
    # last day of target month
    nm_y, nm_m = (new_y + (1 if new_m == 12 else 0), 1 if new_m == 12 else new_m + 1)
    last_day = (date(nm_y, nm_m, 1) - timedelta(days=1)).day
    day = min(d, last_day)
    target = date(new_y, new_m, day)
    # weekend → previous Friday
    while target.weekday() >= 5:  # 5=Sat,6=Sun
        target -= timedelta(days=1)
    return target

def _classify(has1: bool, has2: bool, has3: bool) -> str:
    if has1 and not has2 and not has3:
        return "recurring: last month only"
    if has1 and has2 and not has3:
        return "recurring: last 2 months"
    if has1 and has2 and has3:
        return "recurring: last 3 months"
    if not has1 and has2 and not has3:
        return "recurring: 2 months ago only"
    if not has1 and not has2 and has3:
        return "recurring: 3 months ago only"
    if not has1 and has2 and has3:
        return "recurring: skipped last month (2–3 months ago)"
    return "recurring: irregular pattern"

# --- main detection & display ---
def show_recurring_same_day_last_3_months(csv_path: str) -> List[Dict]:
    """
    Reads the CSV and prints all same-day recurring payments across the last 3 months.
    Returns a structured list with details for further processing if needed.
    """
    if not os.path.exists(csv_path):
        print("No recurring payment (CSV not found).")
        return []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            print("No recurring payment (CSV empty).")
            return []
        cols_map = _columns_map(reader.fieldnames)

    # Column guesses (robust to different headers)
    time_col = _pick(cols_map, ["initiation_time","time","transaction_time","transaction_initiation_date"])
    desc_col = _pick(cols_map, ["description","item_names","transaction_subject","note","memo"])
    inv_col  = _pick(cols_map, ["invoice_id","cart_invoice_id","paypal_invoice_id"])
    payer_col= _pick(cols_map, ["sender_name","payer_email","payer_name","payer"])
    val_col  = _pick(cols_map, ["amount_value","amount","transaction_amount_value","value"])
    ccy_col  = _pick(cols_map, ["amount_currency","currency","transaction_amount_currency","currency_code"])

    if not time_col:
        print("No recurring payment (no timestamp column).")
        return []

    # Targets: same “effective” day 1, 2, and 3 months ago
    today_utc = datetime.now(timezone.utc)
    targets = {
        1: _same_day_k_months_ago_or_prev_friday(today_utc, 1),
        2: _same_day_k_months_ago_or_prev_friday(today_utc, 2),
        3: _same_day_k_months_ago_or_prev_friday(today_utc, 3),
    }

    # Grouping key: prefer description → invoice_id → payer → fallback
    key_choice = desc_col or inv_col or payer_col
    def _norm_key(v: Optional[str]) -> str:
        return (str(v).strip().lower()) if v is not None else "__unknown__"

    # presence[k][key] = list of rows on target date k months ago
    presence: Dict[int, Dict[str, List[Dict]]] = {1:{}, 2:{}, 3:{}}

    for r in rows:
        ts = _parse_iso8601_utc(r.get(time_col, ""))
        if not ts:
            continue
        r_date = ts.date()
        for k, tgt in targets.items():
            if r_date == tgt:
                gkey = _norm_key(r.get(key_choice)) if key_choice else "__all__"
                presence[k].setdefault(gkey, []).append(r)

    all_keys = set(presence[1].keys()) | set(presence[2].keys()) | set(presence[3].keys())
    if not all_keys:
        print("No recurring payment")
        return []

    def _sample(vals: List[Dict], col: Optional[str]) -> Optional[str]:
        if not vals or not col: return None
        v = vals[0].get(col)
        return str(v) if v is not None else None

    results: List[Dict] = []
    # Print each recurring series with description
    for k in sorted(all_keys):
        rows1 = presence[1].get(k, [])
        rows2 = presence[2].get(k, [])
        rows3 = presence[3].get(k, [])

        has1, has2, has3 = bool(rows1), bool(rows2), bool(rows3)
        label = _classify(has1, has2, has3)

        desc = _sample(rows1 or rows2 or rows3, desc_col) or "(no description)"
        payer = _sample(rows1 or rows2 or rows3, payer_col)
        val = _sample(rows1 or rows2 or rows3, val_col)
        ccy = _sample(rows1 or rows2 or rows3, ccy_col)

        dates_str = f"[dates: {targets[1].isoformat() if has1 else '—'}, {targets[2].isoformat() if has2 else '—'}, {targets[3].isoformat() if has3 else '—'}]"
        parts = [label, f"— {desc}"]
        if payer: parts.append(f"(from {payer})")
        if val and ccy: parts.append(f"amount ~ {val} {ccy}")
        parts.append(dates_str)

        print(" ".join(parts))

        results.append({
            "key": k,
            "pattern": label,
            "description": desc if desc != "(no description)" else None,
            "payer": payer,
            "amount": val,
            "currency": ccy,
            "dates": {
                "last_month": targets[1].isoformat() if has1 else None,
                "two_months_ago": targets[2].isoformat() if has2 else None,
                "three_months_ago": targets[3].isoformat() if has3 else None,
            },
            "rows_last_month": rows1,
            "rows_two_months_ago": rows2,
            "rows_three_months_ago": rows3,
        })

    return results


def unpaid_invoice_notification():
    token = fetch_paypal_token_for_issuer()

    page = 1
    page_size = 50
    total_found = 0

    while True:
        data = _list_unpaid_invoices(token, page=page, page_size=page_size)
        items = data.get("items") or []

        if page == 1 and not items:
            print("No unpaid/sent invoices found.")
            return
        print("Here are your unpaid/sent invoices with payment links:")
        for it in items:
            inv_id = it.get("id")
                # Build/ensure a payer link using your existing helper
            used_id, pay_url = build_pay_link_for_invoice(token, inv_id)
                # Try to show a nicer label if available
            detail = (it.get("detail") or {})
            number = detail.get("invoice_number") or used_id
            print(f"- {number}: {pay_url or '(no payer link yet)'}")
            total_found += 1

            # Simple pagination: stop if fewer than page_size returned
        if len(items) < page_size:
            break
        page += 1

    if total_found == 0:
        print("No unpaid/sent invoices found.")