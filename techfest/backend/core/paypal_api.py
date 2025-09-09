
import requests
import time
import dotenv
import os


class Invoice:
    def __init__(self, invoice_number, status, amount, currency, due_date):
        self.invoice_number = invoice_number
        self.status = status
        self.amount = amount
        self.currency = currency
        self.due_date = due_date


class PayPalAPI:
    def __init__(self):
        dotenv.load_dotenv()

        self.base_url = "https://api-m.sandbox.paypal.com"

        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")

        self.access_token = None
        self.access_token_expires_in = None

    def authenticate(self):
        """
        Authenticate with PayPal API and store access token and expiration
        """
        response = requests.post(
            url=f"{self.base_url}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json"
            },
        )

        if response.status_code != 200:
            raise Exception("Failed to authenticate with PayPal API")

        data = response.json()
        self.access_token = data.get("access_token")
        expires_in = data.get("expires_in", 0)
        self.access_token_expires_in = time.time() + expires_in - 60  # refresh 1 min before expiry

    def get_token(self):
        if not self.access_token or not self.access_token_expires_in or time.time() >= self.access_token_expires_in:
            self.authenticate()
        return self.access_token

    def get_invoices(self):
        """
        Fetch a list of invoices from PayPal API
        """
        access_token = self.get_token()
        invoices_response = requests.get(
            f"{self.base_url}/v2/invoicing/invoices",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        )

        if invoices_response.status_code != 200:
            raise Exception("Failed to fetch invoices from PayPal API")

        return invoices_response.json().get("items", [])

    def create_invoice(self, invoice_data):
        """
        Create a new invoice in PayPal API
        """
        access_token = self.get_token()
        create_response = requests.post(
            f"{self.base_url}/v2/invoicing/invoices",
            json=invoice_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Prefer": "return=representation"
            }
        )

        if create_response.status_code != 201:
            raise Exception(f"Failed to create invoice draft in PayPal API: {create_response.text}")

        send_response = requests.post(
            f"{self.base_url}/v2/invoicing/invoices/{create_response.json().get('id')}/send",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json={}
        )

        if send_response.status_code != 200:
            raise Exception(f"Failed to send invoice in PayPal API: {send_response.text}")

        return create_response.json()
