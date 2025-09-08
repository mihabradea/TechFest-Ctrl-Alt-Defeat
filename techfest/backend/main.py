from fastapi import FastAPI, Request, Response, HTTPException, Body
import secrets
import httpx
# For securely signing/verifying state values
from itsdangerous import URLSafeSerializer
from fastapi import UploadFile, File, HTTPException, FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os
from pydantic import BaseModel, EmailStr
from fastapi.responses import FileResponse
from techfest.backend.text_speech.speech_to_text import transcribe_wav_file
from techfest.backend.text_speech.text_to_speech import text_to_mp3
from techfest.backend.db import models
from techfest.backend.db.database import engine, get_db
from sqlalchemy.orm import Session

from techfest.backend.auth.jwt_auth import (
    require_active_token,
    create_access_token_db,
    revoke_current_token,
    get_or_create_user_by_email,
)

#run command for testing: uvicorn techfest.backend.main:app --reload

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

protected = APIRouter(dependencies=[Depends(require_active_token)])
app.include_router(protected)

class LoginRequest(BaseModel):
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --- PayPal and app configuration from environment ---
client_id = os.getenv("CLIENT_ID", "AUwDbh92cYpOxREvA3aeugMEfJdMH5U-HwMvLi0z-ABQQ0puDUd1ijGzFsh6s7ugl2zisrqI4tZGYRAT")
client_secret = os.getenv("CLIENT_SECRET","EL9UjcK_RLn94hX6HaDKhGfLXPh4L-_RAU-kUtVJZdlQGRbT2re1iiTTjFccDKczOjUZjLyAKUckTERG")
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
    print("Received callback with query params:", request.query_params)
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
    # cookie_state = request.cookies.get("pp_state")
    # print("Cookie state:", cookie_state, "Received state:", state)

    # if not cookie_state or cookie_state != state:
    #     raise HTTPException(status_code=403, detail="Invalid state")
    # try:
    #     signer.loads(state)  # verifies signature
    # except Exception:
    #     raise HTTPException(status_code=403, detail="Invalid state signature")

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
    print("Received tokens:", tokens)

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




@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Accepts an already verified email from a third-party identity provider.
    Stores only the email, issues an API access token, and persists token status in DB.
    """
    user = get_or_create_user_by_email(db, req.email)
    jwt_token = create_access_token_db(db, subject=user.email, user_id=user.id)
    return TokenResponse(access_token=jwt_token)

@app.post("/logout")
def logout(payload: dict = Depends(require_active_token), db: Session = Depends(get_db)):
    revoke_current_token(payload, db)
    return {"status": "logged_out"}

# Optional: protected demo route
@app.get("/me")
def me(payload: dict = Depends(require_active_token), db: Session = Depends(get_db)):
    email = payload.get("sub")
    user = db.query(models.User).filter(models.User.email == email).first()
    return {"user": {"email": email}}

@app.post("/stt")
async def stt(file: UploadFile = File(...), payload: dict = Depends(require_active_token)):
    """
    Receives a .wav file from the frontend and returns a JSON { "text": "<transcript>" }.
    Requires login (Bearer token).
    """
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise HTTPException(status_code=400, detail="Please upload a WAV file.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            contents = await file.read()
            if not contents:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            tmp.write(contents)

        text = transcribe_wav_file(tmp_path)
        return {"text": text}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

class TTSRequest(BaseModel):
    text: str
    filename: str | None = None
    download: bool = False

@app.post("/tts")
def tts(req: TTSRequest, payload: dict = Depends(require_active_token)):
    """
    Receives text and returns an MP3 file as the response body.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    try:
        path, name = text_to_mp3(req.text.strip(), req.filename)
        disposition = "attachment" if req.download else "inline"
        headers = {"Content-Disposition": f'{disposition}; filename="{name}"'}
        # Return the actual MP3 file
        return FileResponse(path, media_type="audio/mpeg", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")