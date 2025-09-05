from flask import Flask
from flask import request
from paypal_service import PayPalService

app = Flask(__name__)

paypal_service = PayPalService()


@app.route('/hello_world')
def hello_world():
    return "Hello, World!"


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message') if data else None

    res = paypal_service.process_query(message)

    return f"Received message: {res}"
