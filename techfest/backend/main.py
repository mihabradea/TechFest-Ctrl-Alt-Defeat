from datetime import timedelta

import dotenv

from techfest.backend.db.models import now_utc, PayPalToken

dotenv.load_dotenv()

from typing import List, Dict

from fastapi import FastAPI, Request, Response, HTTPException, Body, Query
import secrets
import httpx
# For securely signing/verifying state values
from itsdangerous import URLSafeSerializer
from fastapi import UploadFile, File, HTTPException, FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os
from pydantic import BaseModel, EmailStr
from fastapi.responses import FileResponse

from techfest.backend.core.paypal_api import PayPalAPI
from techfest.backend.core.paypal_service import PayPalService
from techfest.backend.paypal_transactions.csv_export import ensure_csv
from techfest.backend.paypal_transactions.invoicing import _list_unpaid_invoices
from techfest.backend.paypal_transactions.recurring_api import RecurringResponse
from techfest.backend.paypal_transactions.unpaid_invoices_api import UnpaidInvoicesResponse, _map_invoice_with_link
from techfest.backend.text_speech.speech_to_text import transcribe_wav_file, WAV_TYPES, ALLOWED, save_upload_to_tmp, \
    ffmpeg_to_wav, CONTENT_SUFFIX
from techfest.backend.text_speech.text_to_speech import text_to_mp3
from techfest.backend.db import models
from techfest.backend.db.database import engine, get_db
from sqlalchemy.orm import Session
from techfest.backend.paypal_transactions.transactions import save_transactions
from techfest.backend.paypal_transactions.auth import fetch_paypal_token, fetch_paypal_token_for_issuer
from techfest.backend.paypal_transactions.notify import notify_same_day_last_month
from techfest.backend.paypal_transactions.notify import show_recurring_same_day_last_3_months



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
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:8081")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

protected = APIRouter(dependencies=[Depends(require_active_token)])
app.include_router(protected)

paypal_api = PayPalAPI()
paypal_service = PayPalService(paypal_api)

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
@app.post("/callback")
async def paypal_callback(request: Request, db: Session = Depends(get_db)):
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
            data={
                "grant_type": "authorization_code",
                "code": code,
            },
        )
    if token_res.status_code != 200:
        detail = token_res.text
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {detail}")

    tokens = token_res.json()
    # Parse & compute expiry
    try:
        expires_in = int(tokens.get("expires_in") or 0)
    except ValueError:
        expires_in = 0
    expires_at = now_utc() + timedelta(seconds=expires_in)

    # Persist to DB
    ppt = PayPalToken(
        scope=tokens.get("scope"),
        access_token=tokens.get("access_token"),
        token_type=tokens.get("token_type"),
        expires_in=expires_in,
        expires_at=expires_at,
        refresh_token=tokens.get("refresh_token"),  # stored server-side; not returned to client
        nonce=tokens.get("nonce"),
        state=state,
        auth_code=code,
        # user_id=...  # Optional: set if you know who initiated (via signed state)
    )

    db.add(ppt)
    db.commit()
    db.refresh(ppt)

    # Return ONLY what you want the frontend to have (no refresh token)
    return {
        "access_token": tokens.get("access_token"),
        "token_type": tokens.get("token_type"),
        "expires_in": expires_in,
        "scope": tokens.get("scope"),
        "nonce": tokens.get("nonce"),
        # deliberately omit refresh_token from response
    }

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
async def stt(file: UploadFile = File(...), payload: Dict = Depends(require_active_token)):
    """
    Accepts .wav, .mp4 (audio/video), or .webm (audio/video).
    If not WAV, converts to 16 kHz mono WAV before transcribing.
    Returns: { "text": "<transcript>" }
    """
    # Normalize content type (strip parameters like "; codecs=opus")
    ctype = (file.content_type or "").split(";")[0].strip().lower()

    if ctype not in ALLOWED:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Please upload a WAV, MP4, or WEBM file."
        )

    tmp_input = None
    tmp_wav = None
    try:
        # Choose suffix based on content type (fallback to filename extension if needed)
        suffix = CONTENT_SUFFIX.get(ctype)
        if not suffix:
            _, ext = os.path.splitext(file.filename or "")
            suffix = ext if ext else ".bin"

        tmp_input = await save_upload_to_tmp(file, suffix=suffix)

        # If it's already WAV, transcribe directly; else convert → WAV first
        if ctype in WAV_TYPES:
            wav_path = tmp_input
            tmp_input = None  # we'll delete in finally via wav_path cleanup
        else:
            tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            ffmpeg_to_wav(tmp_input, tmp_wav, sr=16000)
            wav_path = tmp_wav

        text = transcribe_wav_file(wav_path)
        return {"text": text}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp files
        for p in (tmp_input, tmp_wav):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
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



@app.get("/unpaid-invoices", response_model=UnpaidInvoicesResponse)
def get_unpaid_invoices(page_size: int = 50, page: int = 1, payload: dict = Depends(require_active_token)):
    """
    Returns unpaid/sent invoices for the ISSUING business (sandbox/live per PAYPAL_ENV),
    including a ready-to-use pay_url for each invoice.
    """
    try:
        token = fetch_paypal_token_for_issuer()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issuer token: {e}")

    try:
        data = _list_unpaid_invoices(token, page=page, page_size=page_size)
        items = data.get("items") or []
        mapped = [_map_invoice_with_link(token, it) for it in items]
        return UnpaidInvoicesResponse(count=len(mapped), items=mapped)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list unpaid invoices: {e}")


@app.post("/unpaid-invoices/notify", response_model=UnpaidInvoicesResponse)
def notify_unpaid_invoices(payload: dict = Depends(require_active_token)):
    """
    'Notification' variant – same payload as GET but intended to be called by a scheduler.
    You can wire a real notifier (email/Slack) here later.
    """
    resp = get_unpaid_invoices()
    if resp.count == 0:
        # replace with your notifier of choice
        print("No unpaid/sent invoices found.")
    else:
        print("Unpaid/Sent invoices:")
        for it in resp.items:
            print(f"- {it.number}: {it.pay_url or '(no payer link)'}")
    return resp


@app.get("/recurring/same-day", response_model=RecurringResponse)
def get_recurring_same_day(
        csv_path: str = Query("/techfest/backend/out/txns_last90d.csv"),
        days: int = Query(90, ge=1, le=365),
        refresh: bool = Query(False),
        payload: dict = Depends(require_active_token)
):
    """
    Ensures the CSV exists (or regenerates it when refresh=true), then returns recurring payments.
    """
    try:
        path = ensure_csv(csv_path=csv_path, days=days, refresh=refresh)
        items: List[Dict] = show_recurring_same_day_last_3_months(path)
        return RecurringResponse(count=len(items), items=items)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"CSV not found at {csv_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute recurring payments: {e}")


@app.post("/recurring/same-day/notify")  # tolerate trailing slash
def notify_recurring_same_day(
        csv_path: str = Query("out/txns_last90d.csv"),
        days: int = Query(90, ge=1, le=365),
        refresh: bool = Query(False),
        payload: dict = Depends(require_active_token)
):
    """
    Convenience action: regenerates CSV if requested, prints a short summary, returns JSON.
    """
    try:
        path = ensure_csv(csv_path=csv_path, days=days, refresh=refresh)
        items: List[Dict] = show_recurring_same_day_last_3_months(path)
        if not items:
            print("No recurring payment.")
        else:
            print("Recurring payments (same day over last 3 months):")
            for it in items:
                human = f"{it['pattern']} — {it.get('description') or '(no description)'}"
                print(f"- {human}")
        return {"count": len(items), "items": items}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"CSV not found at {csv_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute recurring payments: {e}")

@app.post('/chat')
def chat(messages: List[Dict] = Body(...)):

    print(f"Received messages: {messages}")
    res = paypal_service.call_model(messages)
    return {"reply": res}