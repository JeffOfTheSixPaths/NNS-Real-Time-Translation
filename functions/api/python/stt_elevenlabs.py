from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import httpx
from dotenv import load_dotenv

# Load local .env for development (no-op if variables already in environment)
load_dotenv()

app = FastAPI()

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_STT_MODEL = os.environ.get("ELEVENLABS_STT_MODEL")


@app.post("/stt")
async def stt(
    audio: UploadFile = File(...),
    lang: str = Form("auto"),
    model_id: str | None = Form(None),
):
    """Accepts multipart/form-data with field `audio` and optional `lang`.
    Forwards the file to ElevenLabs Speech-to-Text and returns a JSON transcript.
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="Missing ELEVENLABS_API_KEY")

    # Build multipart payload
    files = {"file": (audio.filename or "clip.webm", await audio.read(), audio.content_type)}
    data = {}
    if lang and lang != "auto":
        data["language_code"] = lang

    # model resolution: prefer explicit form field, fall back to env var
    model = model_id or ELEVENLABS_STT_MODEL
    if not model:
        raise HTTPException(
            status_code=500,
            detail=(
                "Missing ElevenLabs STT model id. Set ELEVENLABS_STT_MODEL in your environment "
                "or include 'model_id' as a form field in the POST."
            ),
        )
    data["model_id"] = model

    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post("https://api.elevenlabs.io/v1/speech-to-text", headers=headers, files=files, data=data)

    if r.status_code >= 400:
        detail = r.text
        raise HTTPException(status_code=500, detail={"error": "STT failed", "detail": detail})

    data = r.json()
    # try multiple fields for transcript for compatibility with previous implementation
    transcript = data.get("text") or data.get("transcript") or (data.get("results") or [{}])[0].get("text", "")
    return JSONResponse({"transcript": transcript})
