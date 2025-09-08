import os
import logging

from backend.paypal_transactions.transactions import save_transactions
from backend.paypal_transactions.auth import fetch_paypal_token, fetch_paypal_token_for_issuer
from backend.paypal_transactions.notify import notify_same_day_last_month
from backend.paypal_transactions.notify import show_recurring_same_day_last_3_months
from backend.paypal_transactions.invoicing import build_pay_link_for_last_unpaid
from backend.paypal_transactions.invoicing import pay_link_for_other_business_last_unpaid
from backend.paypal_transactions.auth import fetch_paypal_token_for_issuer
from backend.paypal_transactions.invoicing import _list_unpaid_invoices, build_pay_link_for_invoice


# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)
log = logging.getLogger("main")

OUTPUT_CSV = "out/txns_last90d.csv"

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

def main():
    # OAuth
    # token = fetch_paypal_token()
    # save_transactions(token)
    # notify_same_day_last_month(OUTPUT_CSV)
    # show_recurring_same_day_last_3_months("out/txns_last90d.csv")
    unpaid_invoice_notification()

if __name__ == "__main__":
    main()
