import os
import logging
from datetime import datetime, timedelta, timezone

# (Optional) your agent import stays — not used here, but harmless to keep.
# from agents import Runner
# from backend.tools_paypal_agent.agents_class import agent

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)
log = logging.getLogger("main")

# Our package
from paypal_transactions.auth import fetch_paypal_token
from paypal_transactions.transactions import fetch_transactions
from paypal_transactions.storage import ingest_to_sqlite, export_csv, DB_PATH_DEFAULT

OUTPUT_CSV = "out/txns_last90d.csv"

def main():
    # 90-day window (the fetcher handles 31-day chunking/pagination)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=90)

    log.info("Fetching PayPal transactions for last 90 days: %s → %s",
             start_time.isoformat(), end_time.isoformat())

    # OAuth
    token = fetch_paypal_token()

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

if __name__ == "__main__":
    main()
