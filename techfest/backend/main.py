import os
import logging

from backend.paypal_transactions.transactions import save_transactions
from paypal_transactions.auth import fetch_paypal_token
from paypal_transactions.notify import notify_same_day_last_month, notify_about_last_unpaid_invoice
from paypal_transactions.notify import show_recurring_same_day_last_3_months
from paypal_transactions.invoicing import list_unpaid_or_sent, list_any_invoices

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)
log = logging.getLogger("main")

OUTPUT_CSV = "out/txns_last90d.csv"

def debug_list_invoices(token: str):
    data = list_unpaid_or_sent(token, days=365)
    print("unpaid/sent count:", len(data.get("items", [])))

    # 2) If still empty, list *any* invoices visible to this token
    all_data = list_any_invoices(token)
    items = all_data.get("items", [])
    print("visible invoices:", len(items))
    print({(it.get("detail") or {}).get("status") for it in items})  # which statuses?



def main():
    # OAuth
    token = fetch_paypal_token()
    save_transactions(token)
    notify_about_last_unpaid_invoice(token)
    notify_same_day_last_month(OUTPUT_CSV)

    show_recurring_same_day_last_3_months("out/txns_last90d.csv")



if __name__ == "__main__":
    main()
