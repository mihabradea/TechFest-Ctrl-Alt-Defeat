import os
import subprocess
import tempfile

from fastapi import UploadFile, HTTPException
from openai import OpenAI
from imageio_ffmpeg import get_ffmpeg_exe

client = OpenAI()

WAV_TYPES = {"audio/wav", "audio/x-wav", "audio/wave"}
MP4_TYPES = {"video/mp4", "audio/mp4"}  # some browsers send audio/mp4
WEBM_TYPES = {"audio/webm", "video/webm"}
ALLOWED    = WAV_TYPES | MP4_TYPES | WEBM_TYPES

CONTENT_SUFFIX = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "video/mp4": ".mp4",
    "audio/mp4": ".mp4",
    "audio/webm": ".webm",
    "video/webm": ".webm",
}

FFMPEG_BIN = get_ffmpeg_exe()

async def save_upload_to_tmp(upload: UploadFile, *, suffix: str) -> str:
    """
    Streams the UploadFile to a real temp file on disk (chunked; avoids loading into RAM).
    Returns the temp file path. Caller must delete it.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    try:
        with tmp:
            await upload.seek(0)
            while True:
                chunk = await upload.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                tmp.write(chunk)
        if os.path.getsize(tmp_path) == 0:
            os.remove(tmp_path)
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        return tmp_path
    finally:
        try:
            await upload.seek(0)
        except Exception:
            pass

def ffmpeg_to_wav(src_path: str, dst_wav: str, *, sr: int = 16000, stream_logs: bool = True) -> None:
    cmd = [
        FFMPEG_BIN, "-y", "-hide_banner", "-nostdin",
        "-i", src_path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", dst_wav,
    ]

    if stream_logs:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.strip()
        rc = proc.wait()
        if rc != 0:
            raise HTTPException(status_code=500, detail=f"ffmpeg exited with code {rc}")
    else:
        subprocess.run(cmd, check=True)

def transcribe_wav_file(local_wav_path: str) -> str:
    """
    Takes the path to a local .wav file and returns the transcription string.
    """
    try:
        with open(local_wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        return result.text
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")