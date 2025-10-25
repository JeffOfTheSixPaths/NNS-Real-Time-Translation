# %%

import os
from io import BytesIO
import requests



# %%
from elevenlabs import stream
from elevenlabs.client import ElevenLabs

# %%

# 1. Load your API key from environment (you can also hard-code for quick test, but not recommended)
API_KEY = os.getenv("ELEVEN_API_KEY")
print(API_KEY)
if API_KEY is None:
    raise ValueError("Please set the ELEVENLABS_API_KEY environment variable")

# 2. Instantiate the client
client = ElevenLabs(api_key=API_KEY)

# %%
# 3. Read the audio file (you can also pass it via URL)
file_path = "chinese.mp3"   # adjust file name / path
with open(file_path, "rb") as f:
    audio_bytes = f.read()

#

# %%
# 4. Call the convert endpoint
response = client.speech_to_text.convert(
    file=BytesIO(audio_bytes),
    model_id="scribe_v1",          # current model
    language_code="eng",           # optional; set if you know the language; else null
    tag_audio_events=True,         # e.g., tag laughter/applause
    diarize=True                   # optional: speaker diarization
)



# %%
# 5. Handle the result
print("Transcription result:")
print(response.text)



