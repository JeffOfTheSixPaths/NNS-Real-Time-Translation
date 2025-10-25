import os
from io import BytesIO
import requests
from elevenlabs import stream
from elevenlabs.client import ElevenLabs

def init_client():
    """Initialize the ElevenLabs client with API key"""
    API_KEY = os.getenv("ELEVEN_API_KEY")
    if API_KEY is None:
        raise ValueError("Please set the ELEVEN_API_KEY environment variable")
    return ElevenLabs(api_key=API_KEY)

def transcribe_audio(audio_file_path, language_code=None):
    """
    Transcribe an audio file using ElevenLabs API
    
    Args:
        audio_file_path (str): Path to the audio file
        language_code (str, optional): Language code for the audio (e.g., 'eng', 'spa')
        
    Returns:
        str: Transcribed text
    """
    try:
        client = init_client()
        
        # Read the audio file
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()
        
        # Call the convert endpoint
        response = client.speech_to_text.convert(
            file=BytesIO(audio_bytes),
            model_id="scribe_v1",
            language_code=language_code,
            tag_audio_events=True,
            diarize=True
        )
        
        return response.text
        
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage
    file_path = "chinese.mp3"
    result = transcribe_audio(file_path, "eng")
    print("Transcription result:")
    print(result)



