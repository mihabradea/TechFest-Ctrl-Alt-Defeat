from openai import OpenAI

client = OpenAI()

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