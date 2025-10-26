from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import os
import httpx
import io
from dotenv import load_dotenv

# Load local .env for development (no-op if variables already in environment)
load_dotenv()

app = FastAPI()

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN")
ELEVENLABS_VOICE_ID_ES = os.environ.get("ELEVENLABS_VOICE_ID_ES")


@app.post("/tts")
async def tts(request: Request):
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID_EN or not ELEVENLABS_VOICE_ID_ES:
        raise HTTPException(status_code=500, detail="Missing ElevenLabs env vars")

    payload = await request.json()
    text = payload.get("text")
    lang = payload.get("lang")

    if not text or not lang:
        raise HTTPException(status_code=400, detail="Missing fields")

    voice_id = ELEVENLABS_VOICE_ID_ES if str(lang).lower().startswith("es") else ELEVENLABS_VOICE_ID_EN

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.7}
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body, headers=headers)

    if r.status_code >= 400 or r.content is None:
        detail = r.text
        raise HTTPException(status_code=500, detail={"error": "TTS failed", "detail": detail})

    # Stream back the audio/mpeg content
    return StreamingResponse(io.BytesIO(r.content), media_type="audio/mpeg")
