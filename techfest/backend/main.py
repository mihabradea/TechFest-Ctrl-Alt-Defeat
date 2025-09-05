from fastapi import UploadFile, File, HTTPException, FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os
from pydantic import BaseModel
from fastapi.responses import FileResponse
from techfest.backend.text_speech.speech_to_text import transcribe_wav_file
from techfest.backend.text_speech.text_to_speech import text_to_mp3

from techfest.backend.auth.jwt_auth import (
    _authenticate_user,
    _create_access_token,
    require_active_token,
    BLACKLISTED_JTIS,
)

#run command for testing: uvicorn techfest.backend.main:app --reload

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
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """
    Authenticate user and return a JWT access token.
    Body (JSON): { "username": "alice", "password": "password123" }
    """
    user = _authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.", headers={"WWW-Authenticate": "Bearer"})
    token = _create_access_token(subject=req.username)
    return TokenResponse(access_token=token)

@app.post("/logout")
def logout(payload: dict = Depends(require_active_token)):
    """
    Blacklist the current access token so it can’t be used again.
    Requires Authorization: Bearer <access_token>
    """
    jti = payload.get("jti")
    if jti:
        BLACKLISTED_JTIS.add(jti)
    return {"status": "logged_out"}

# Optional: protected demo route
@app.get("/me")
def me(payload: dict = Depends(require_active_token)):
    return {"user": payload.get("sub")}

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