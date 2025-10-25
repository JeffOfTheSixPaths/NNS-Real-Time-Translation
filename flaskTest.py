from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)

# Basic in-file HTML template with a small real-time UI using fetch()
INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Basic Flask Interface</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        body {font-family: Arial, sans-serif; margin: 2rem; max-width: 800px;}
        textarea {width: 100%; height: 120px; font-size: 1rem; padding: 0.5rem;}
        .row {display:flex; gap:0.5rem; align-items:center; margin:0.5rem 0;}
        select, button {padding:0.4rem 0.6rem; font-size:1rem;}
        #output {white-space:pre-wrap; background:#f7f7f7; padding:0.8rem; border-radius:6px; min-height:3rem;}
        .muted {color:#666; font-size:0.9rem;}
    </style>
</head>
<body>
    <h1>Basic Flask Website Interface</h1>
    <p class="muted">Type text below. A simple "translate" request is sent to the server in real time (debounced).</p>

    <div>
        <label for="input">Input text</label>
        <textarea id="input" placeholder="Enter text to translate..."></textarea>
    </div>

    <div class="row">
        <label for="lang">Target language:</label>
        <select id="lang">
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
        </select>
        <button id="clear">Clear</button>
        <button id="recordBtn">Start Recording</button>
        <div id="status" class="muted" style="margin-left:auto">Idle</div>
    </div>

    <h3>Translated output</h3>
    <div id="output">Nothing yet</div>

<script>
const input = document.getElementById('input');
const lang = document.getElementById('lang');
const output = document.getElementById('output');
const status = document.getElementById('status');
const clearBtn = document.getElementById('clear');

let timer = null;
const DEBOUNCE_MS = 600;

function sendTranslate() {
    const text = input.value;
    const target = lang.value;
    if (!text.trim()) {
        output.textContent = 'Nothing yet';
        status.textContent = 'Idle';
        return;
    }
    status.textContent = 'Translating...';
    fetch('/translate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text, target})
    })
    .then(r => r.json())
    .then(data => {
        output.textContent = data.translated;
        status.textContent = 'Done';
    })
    .catch(err => {
        output.textContent = 'Error: ' + err;
        status.textContent = 'Error';
    });
}

function scheduleTranslate() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(sendTranslate, DEBOUNCE_MS);
}

input.addEventListener('input', scheduleTranslate);
lang.addEventListener('change', scheduleTranslate);
clearBtn.addEventListener('click', () => {
    input.value = '';
    output.textContent = 'Nothing yet';
    status.textContent = 'Idle';
});

// Audio recording logic: press to start, press again to stop and upload
const recordBtn = document.getElementById('recordBtn');
let mediaRecorder = null;
let audioChunks = [];
let localStream = null;

async function startRecording() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(localStream);
        audioChunks = [];
        mediaRecorder.addEventListener('dataavailable', e => audioChunks.push(e.data));
        mediaRecorder.addEventListener('stop', onRecordingStop);
        mediaRecorder.start();
        recordBtn.textContent = 'Stop Recording';
        status.textContent = 'Recording...';
    } catch (err) {
        console.error('Microphone access denied or error:', err);
        status.textContent = 'Microphone error';
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
        localStream = null;
    }
    recordBtn.textContent = 'Start Recording';
}

function onRecordingStop() {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const form = new FormData();
    // Provide a filename; server will sanitize
    form.append('audio_data', blob, 'recording.webm');
    status.textContent = 'Uploading...';
    fetch('/upload_audio', { method: 'POST', body: form })
        .then(r => r.json())
        .then(data => {
            status.textContent = data.success ? ('Saved: ' + data.filename) : 'Upload failed';
            console.log('Upload response', data);
        })
        .catch(err => {
            console.error('Upload error', err);
            status.textContent = 'Upload error';
        });
}

recordBtn.addEventListener('click', () => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        startRecording();
    } else {
        stopRecording();
    }
});
</script>
</body>
</html>
"""

@app.route('/')
def index():
        return render_template_string(INDEX_HTML)

@app.route('/translate', methods=['POST'])
def translate():
        """
        Placeholder translation endpoint.
        Replace the body of translate_text() with real translation logic or an API call.
        """
        data = request.get_json(force=True) or {}
        text = data.get('text', '')
        target = data.get('target', 'en')

        def translate_text(s, tgt):
                # Simple stub: demonstrate different pretend behavior per language
                s = s.strip()
                if not s:
                        return ''
                if tgt == 'en':
                        return s  # no-op for English
                if tgt == 'es':
                        return f"[ES] {s[::-1]}"  # reversed as a stub
                if tgt == 'fr':
                        return f"[FR] {s.upper()}"  # uppercase as a stub
                if tgt == 'de':
                        return f"[DE] {s.split()[::-1].join(' ')}"  # crude word-reverse
                return s

        translated = translate_text(text, target)
        return jsonify({'translated': translated})


@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """Accepts a posted audio blob (multipart/form-data with field 'audio_data') and saves it to uploads/"""
    # Ensure uploads dir exists
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    # Flask provides files for multipart form data
    file = request.files.get('audio_data')
    if not file:
        # Try raw data fallback
        data = request.get_data()
        if not data:
            return jsonify({'success': False, 'error': 'No audio data received'}), 400
        filename = f"recording-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.webm"
        path = os.path.join(uploads_dir, secure_filename(filename))
        with open(path, 'wb') as f:
            f.write(data)
        return jsonify({'success': True, 'filename': os.path.basename(path)})

    filename = secure_filename(file.filename or f"recording-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.webm")
    save_path = os.path.join(uploads_dir, filename)
    file.save(save_path)
    return jsonify({'success': True, 'filename': filename})

if __name__ == '__main__':
        # Run the app: visit http://127.0.0.1:5000/
        app.run(host='0.0.0.0', port=5000, debug=True)