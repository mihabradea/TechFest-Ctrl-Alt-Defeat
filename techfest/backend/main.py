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
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

protected = APIRouter(dependencies=[Depends(require_active_token)])
app.include_router(protected)

class LoginRequest(BaseModel):
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

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