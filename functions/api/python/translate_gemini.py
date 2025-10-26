from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import os
import httpx
from dotenv import load_dotenv

# Load local .env for development (no-op if variables already in environment)
load_dotenv()

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


@app.post("/translate")
async def translate(request: Request):
    payload = await request.json()
    text = payload.get("text")
    sourceLang = payload.get("sourceLang")
    targetLang = payload.get("targetLang")

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY")
    if not text or not sourceLang or not targetLang:
        raise HTTPException(status_code=400, detail="Missing fields")

    prompt = f"Translate the following from {sourceLang} to {targetLang}.\n- Preserve names, numbers, URLs, punctuation.\n- Keep idioms natural.\n- Return ONLY the translation.\n\nText: \"\"\"{text}\"\"\""

    body = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=body, headers={"Content-Type": "application/json"})

    if r.status_code >= 400:
        detail = r.text
        raise HTTPException(status_code=500, detail={"error": "Gemini failed", "detail": detail})

    data = r.json()
    translation = ""
    try:
        translation = data.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "").strip()
    except Exception:
        translation = ""

    return JSONResponse({"translation": translation})
