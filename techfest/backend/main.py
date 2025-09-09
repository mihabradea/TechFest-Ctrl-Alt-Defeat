from flask import Flask
from flask import request
from paypal_service import PayPalService
from paypal_api import PayPalAPI

app = Flask(__name__)

paypal_api = PayPalAPI()
paypal_service = PayPalService(paypal_api)


@app.route('/hello_world')
def hello_world():
    return "Hello, World!"


@app.route('/test', methods=['GET'])
def get_invoices():
    invoices = paypal_api.get_invoices()
    return {"invoices": invoices}


@app.route('/chat', methods=['POST'])
def chat():
    messages = request.get_json()

    res = paypal_service.call_model(messages)

    return f"Received message: {res}"
