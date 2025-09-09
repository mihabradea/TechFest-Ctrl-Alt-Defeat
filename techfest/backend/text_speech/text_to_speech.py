import os
import uuid
from pathlib import Path
from gtts import gTTS


AUDIO_DIR = Path(__file__).resolve().parent / "audio"

def text_to_mp3(text: str, filename: str | None = None) -> tuple[str, str]:
    """
    Convert text to an MP3 file using gTTS. Returns (absolute_path, filename).
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = filename or f"tts_{uuid.uuid4().hex}.mp3"
    path = AUDIO_DIR / name

    tts = gTTS(text=text, lang="en")
    tts.save(str(path))  # gTTS needs a str path

    return str(path), name