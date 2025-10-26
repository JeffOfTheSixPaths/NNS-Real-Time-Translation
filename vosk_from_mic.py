import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer

# Load the model
model = Model("model")
recognizer = KaldiRecognizer(model, 16000)

# Create a queue to hold audio data
q = queue.Queue()

def callback(indata, frames, time, status):
    """Callback that receives audio data from sounddevice."""
    if status:
        print(status, flush=True)
    q.put(bytes(indata))

# Open the microphone stream
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):
    print("🎙️ Speak into the microphone...")
    while True:
        data = q.get()
        if recognizer.AcceptWaveform(data):
            result = recognizer.Result()
            text = json.loads(result)['text']
            if text.strip():
                print("You said:", text)
        else:
            partial = recognizer.PartialResult()
            partial_text = json.loads(partial).get('partial', '')
            if partial_text:
                print("...", partial_text, end='\r')
