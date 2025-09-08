# --- Imports ---
# FastAPI and related modules for API server and request handling
from fastapi import FastAPI, Request, Response, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os
from urllib.parse import urlencode
import uvicorn
import secrets
import httpx
# For securely signing/verifying state values
from itsdangerous import URLSafeSerializer

# --- Load environment variables from .env file ---
load_dotenv(override=True)

# --- Initialize FastAPI app ---
app = FastAPI()

# --- Enable CORS for frontend communication ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- PayPal and app configuration from environment ---
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
pp_env = os.getenv("PP_ENV", "sandbox")  # "sandbox" or "live"
paypal_base = os.getenv("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
return_url = os.getenv("RETURN_URL", "http://localhost:8000/callback")

# --- PayPal OAuth2 token endpoint and state signer ---
url = f"{paypal_base}/v1/oauth2/token"
signer = URLSafeSerializer(secrets.token_urlsafe(32), salt="paypal-oidc")

# --- Endpoint to generate a random OAuth state and set it as a secure cookie ---
@app.get("/api/state")
async def get_state():
    state = secrets.token_urlsafe(16)  # Generate a random state string
    response = Response(content=state)
    print("Setting state cookie:", state)
    response.set_cookie("pp_state", state, httponly=True, secure=False)  
    return response

# --- OAuth callback endpoint: handles PayPal redirect after user login ---
@app.get("/callback")
async def paypal_callback(request: Request):
    params = dict(request.query_params)  # Extract query parameters from PayPal
    error = params.get("error")
    if error:
        # If PayPal returned an error, abort
        raise HTTPException(status_code=400, detail=f"PayPal returned error: {error}")

    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        # Both code and state are required
        raise HTTPException(status_code=400, detail="Missing code/state")

    # Validate 'state' for CSRF protection (uncomment for production)
    cookie_state = request.cookies.get("pp_state")
    print("Cookie state:", cookie_state, "Received state:", state)

    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=403, detail="Invalid state")
    try:
        signer.loads(state)  # verifies signature
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid state signature")

    # Exchange authorization code for tokens (server-to-server)
    basic_auth = httpx.BasicAuth(client_id, client_secret)
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            f"{paypal_base}/v1/oauth2/token",
            auth=basic_auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
            },
        )
    if token_res.status_code != 200:
        detail = token_res.text
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {detail}")

    tokens = token_res.json()

    # Build response in requested format
    response_data = {
        "scope": tokens.get("scope"),
        "access_token": tokens.get("access_token"),
        "token_type": tokens.get("token_type"),
        "expires_in": tokens.get("expires_in"),
        "refresh_token": tokens.get("refresh_token"),
        "nonce": tokens.get("nonce")
    }
    return response_data

# --- Endpoint to exchange refresh token for access token ---
@app.post("/api/refresh_token")
async def exchange_refresh_token(refresh_token: str = Body(..., embed=True)):
    basic_auth = httpx.BasicAuth(client_id, client_secret)
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            f"{paypal_base}/v1/oauth2/token",
            auth=basic_auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
        )
    if token_res.status_code != 200:
        detail = token_res.text
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {detail}")

    tokens = token_res.json()
    # Build response in requested format
    response_data = {
        "scope": tokens.get("scope"),
        "token_type": tokens.get("token_type"),
        "expires_in": tokens.get("expires_in"),
        "access_token": tokens.get("access_token"),
        "nonce": tokens.get("nonce")
    }
    return response_data

# --- Run the FastAPI app with Uvicorn when executed directly ---
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)