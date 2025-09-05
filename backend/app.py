from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import json
import bcrypt
import jwt
import datetime
import os
from dotenv import load_dotenv
from mathview.mathUI import MathUI


SECRET_KEY = "my_super_secret_key"
app = Flask(__name__)
CORS(app)
# Load users from JSON file
def load_users():
    try:
        with open("users.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    print(f"🔍 Primit email: {email}")
    print(f"🔍 Primit parolă: {password}")

    # Email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"status": "fail", "message": "Invalid email format"}), 400

    users = load_users()
    user = users.get(email)

    print(f"📂 Găsit în users.json: {user}")

    if user:
        if bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            # ✅ Generare token JWT
            payload = {
                "email": email,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
            return jsonify({"status": "success", "token": token}), 200

    return jsonify({"status": "fail", "message": "Unauthorized"}), 401

@app.route('/protected', methods=['GET'])
def protected():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"message": "Token missing or invalid"}), 401

    token = auth_header.split(" ")[1]

    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return jsonify({"message": f"Access granted to {decoded['email']}!"}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"message": "Invalid token"}), 401


if __name__ == '__main__':
    app.run(debug=True)