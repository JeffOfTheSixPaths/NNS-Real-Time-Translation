# Simple TTS helper using ElevenLabs
from elevenlabs.client import ElevenLabs
import os

elevenlabs = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

def synthesize_audio_bytes(text: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb", model_id: str = "eleven_multilingual_v2") -> bytes:
    """Synthesize `text` to audio bytes (mp3) using ElevenLabs streaming API.

    Returns raw bytes which can be written to a file or sent as a response.
    """
    audio_stream = elevenlabs.text_to_speech.stream(
        text=text,
        voice_id=voice_id,
        model_id=model_id
    )

    chunks = []
    for chunk in audio_stream:
        if isinstance(chunk, bytes):
            chunks.append(chunk)

    return b"".join(chunks)


if __name__ == "__main__":
    # quick local test (requires ELEVEN_API_KEY env var set)
    sample = "This is a quick ElevenLabs TTS test."
    out = synthesize_audio_bytes(sample)
    with open("tts_test_output.mp3", "wb") as f:
        f.write(out)
    print("Wrote tts_test_output.mp3 (bytes:", len(out), ")")