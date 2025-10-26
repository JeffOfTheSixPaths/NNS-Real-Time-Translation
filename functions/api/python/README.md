This folder contains Python versions of the Cloudflare Pages Function endpoints.

Files:
- `stt_elevenlabs.py` - POST /stt, accepts multipart form with `audio` file, optional `lang`, forwards to ElevenLabs STT and returns JSON { transcript }
- `translate_gemini.py` - POST /translate, accepts JSON { text, sourceLang, targetLang } and calls the Gemini generateContent API, returns JSON { translation }
- `tts_elevenlabs.py` - POST /tts, accepts JSON { text, lang } and forwards to ElevenLabs TTS, returns audio/mpeg stream

Quick run (development):

1. Create a virtualenv and install requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
pip install -r functions/api/python/requirements.txt
```

2. Set environment variables (example for Windows cmd):

```cmd
set ELEVENLABS_API_KEY=your_key
set ELEVENLABS_VOICE_ID_EN=voice_en_id
set ELEVENLABS_VOICE_ID_ES=voice_es_id
set GEMINI_API_KEY=your_gemini_key
```

3. Run a server for a specific module, for example the STT endpoint:

```cmd
uvicorn functions.api.python.stt_elevenlabs:app --reload --port 8000
```

Then POST to http://localhost:8000/stt, /translate or /tts depending on the file you run.

Notes:
- These are minimal wrappers to mimic the original TypeScript functions. They use FastAPI + httpx.
- For production you may want to bundle these into a single FastAPI app or adapt to your target hosting platform.
