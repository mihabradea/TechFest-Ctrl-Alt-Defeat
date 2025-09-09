from __future__ import annotations
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from techfest.backend.paypal_transactions.auth import fetch_paypal_token_for_issuer
from techfest.backend.paypal_transactions.invoicing import (
    _list_unpaid_invoices,
    build_pay_link_for_invoice,
    show_invoice,
)



# ---------- response models ----------
class Recipient(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class UnpaidInvoice(BaseModel):
    id: str
    number: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    amount_value: Optional[str] = None
    amount_currency: Optional[str] = None
    recipient: Optional[Recipient] = None
    pay_url: Optional[str] = None


class UnpaidInvoicesResponse(BaseModel):
    count: int
    items: List[UnpaidInvoice]


# ---------- mapping helpers ----------
def _recipient_from_item(it: dict) -> Recipient:
    pr = (it.get("primary_recipients") or [])
    if not pr:
        return Recipient()
    billing = (pr[0].get("billing_info") or {})
    nm = (billing.get("name") or {})
    full_name = nm.get("full_name") or " ".join([p for p in [nm.get("given_name"), nm.get("surname")] if p])
    return Recipient(name=(full_name or None), email=billing.get("email_address"))


def _map_invoice_with_link(token: str, it: dict) -> UnpaidInvoice:
    inv_id = it.get("id")
    detail = (it.get("detail") or {})
    number = detail.get("invoice_number") or inv_id
    status = (detail.get("status") or it.get("status"))
    amount = (detail.get("amount") or {})  # sometimes present if you asked for fields; otherwise skip
    note_memo = detail.get("note") or detail.get("memo")

    used_id, pay_url = build_pay_link_for_invoice(token, inv_id)
    # enrich (optional) by refetching full invoice to read description if missing
    if not note_memo:
        try:
            inv_json, _, _ = show_invoice(token, inv_id)
            d2 = (inv_json.get("detail") or {})
            note_memo = d2.get("note") or d2.get("memo")
        except Exception:
            pass

    return UnpaidInvoice(
        id=used_id,
        number=number,
        status=status,
        description=note_memo,
        amount_value=(amount.get("value") if isinstance(amount, dict) else None),
        amount_currency=(amount.get("currency_code") if isinstance(amount, dict) else None),
        recipient=_recipient_from_item(it),
        pay_url=pay_url,
    )
