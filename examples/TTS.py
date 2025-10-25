# %%
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
import os

elevenlabs = ElevenLabs(
    api_key= os.getenv("ELEVEN_API_KEY")
)

audio_stream = elevenlabs.text_to_speech.stream(
    text="This is a test",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2"
)


# option 2: process the audio bytes manually
with open("output_streamed.mp3", "wb") as f:
    f.write(b"".join(chunk for chunk in audio_stream if isinstance(chunk, bytes)))



