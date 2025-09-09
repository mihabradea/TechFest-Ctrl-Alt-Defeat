from flask import Flask
from flask import request
from core.paypal_service import PayPalService
from core.paypal_api import PayPalAPI
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

    print(f"Received messages: {messages}")

    res = paypal_service.call_model(messages)

    return {"reply": res}
