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
    <!-- Use Inter from Google Fonts for a modern look -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
    :root { 
        --side-width: 220px; 
        --accent: #FF7940;
        --accent-light: #FF9866;
        --accent-dark: #E65D20;
        --page-bg: #F0F2F5;
        --panel-bg: #FFFFFF;
        --text: #2C3E50;
        --text-light: #516173;
        --muted: #94A3B8;
        --border: #E2E8F0;
        --accent-glow: rgba(255, 121, 64, 0.15);
        --input-bg: #F8FAFC;
        --control-bg: #EDF2F7;
        --disabled: #CBD5E1;
    }
        /* include border-box so padding is counted into flex sizes */
        *, *:before, *:after { box-sizing: border-box; }
        body { 
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; 
            margin: 0; 
            min-height: 100vh; 
            background: 
                radial-gradient(circle at 0% 0%, rgba(255, 121, 64, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 100% 0%, rgba(255, 121, 64, 0.1) 0%, transparent 40%),
                radial-gradient(circle at 100% 100%, rgba(255, 121, 64, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 0% 100%, rgba(255, 121, 64, 0.1) 0%, transparent 40%),
                linear-gradient(135deg, var(--page-bg), #E5E9EF);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text);
            line-height: 1.5;
            font-size: 16px;
            position: relative;
            overflow: hidden;
        }
        body::before {
            content: '';
            position: absolute;
            width: 200%;
            height: 200%;
            top: -50%;
            left: -50%;
            background: 
                radial-gradient(circle at center, transparent 0%, transparent 40%, rgba(255, 121, 64, 0.03) 50%, transparent 60%),
                radial-gradient(circle at center, transparent 0%, transparent 35%, rgba(255, 121, 64, 0.03) 45%, transparent 55%);
            animation: rotate 60s linear infinite;
            z-index: 1;
        }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        /* Modern Select and Button Base Styles */
        select, button {
            border-radius: 12px;
            padding: 0.75rem 1.25rem;
            font-size: 0.95rem;
            font-weight: 600;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid transparent;
            background: var(--panel-bg);
            color: var(--text);
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        select {
            background: var(--panel-bg);
            border: 2px solid var(--border, rgba(0,0,0,0.1));
            padding-right: 2.5rem;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%23FF7940' viewBox='0 0 16 16'%3E%3Cpath d='M8 10.5l4-4H4z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 1rem center;
        }
        select:hover, button:hover {
            border-color: var(--accent);
            transform: translateY(-1px);
            box-shadow: 
                0 4px 12px rgba(255, 121, 64, 0.15),
                0 1px 3px rgba(0,0,0,0.05);
        }
        select:focus, button:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 
                0 0 0 3px var(--accent-glow, rgba(255, 121, 64, 0.2)),
                0 4px 12px rgba(255, 121, 64, 0.15);
        }
        /* Fancy Record Button */
        #recordBtn {
            background: linear-gradient(135deg, var(--accent), var(--accent-dark));
            color: white;
            font-weight: 600;
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            text-shadow: 0 1px 1px rgba(0,0,0,0.1);
            box-shadow: 
                0 2px 4px rgba(0,0,0,0.1),
                0 6px 12px rgba(255, 121, 64, 0.2),
                inset 0 1px 1px rgba(255,255,255,0.2);
            transform: translateY(0);
        }
        #recordBtn:hover {
            transform: translateY(-1px);
            box-shadow: 
                0 4px 8px rgba(0,0,0,0.15),
                0 8px 16px rgba(255, 121, 64, 0.3),
                inset 0 1px 1px rgba(255,255,255,0.2);
            background: linear-gradient(135deg, var(--accent-light), var(--accent));
        }
        #recordBtn:active {
            transform: translateY(1px);
            box-shadow: 
                0 2px 4px rgba(0,0,0,0.1),
                0 4px 8px rgba(255, 121, 64, 0.2),
                inset 0 1px 1px rgba(255,255,255,0.1);
        }
        #recordBtn.recording {
            background: linear-gradient(135deg, #e64040, #c01010);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(230, 64, 64, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(230, 64, 64, 0); }
            100% { box-shadow: 0 0 0 0 rgba(230, 64, 64, 0); }
        }
        /* dark gray vertical bars on the left and right */
        .side-rect { position: fixed; top: 0; bottom: 0; width: var(--side-width); background: var(--side-color); z-index: 0; }
        .side-rect.left { left: 0; }
        .side-rect.right { right: 0; }
        /* content container sits above the side bars */
    /* larger overall card and split layout: top and bottom halves equal height */
        .content { 
    .content { 
        position: relative; 
        z-index: 2; 
        width: 100%; 
        max-width: 900px; 
        margin: 24px;
        background: var(--panel-bg); 
        padding: 32px 24px 16px; 
        border-radius: 20px; 
        border: 1px solid rgba(255, 121, 64, 0.2);
        box-shadow: 
            0 8px 24px rgba(0,0,0,0.1),
            0 1px 2px rgba(0,0,0,0.08),
            0 24px 48px rgba(255, 121, 64, 0.15),
            inset 0 0 0 1px rgba(255, 255, 255, 0.5);
        display: flex; 
        flex-direction: column; 
        gap: 0; 
        min-height: 640px;
        backdrop-filter: blur(20px);
        position: relative;
    }
    .content::before {
        content: '';
        position: absolute;
        top: -2px;
        left: -2px;
        right: -2px;
        bottom: -2px;
        background: linear-gradient(135deg, var(--accent), transparent 50%);
        border-radius: 22px;
        z-index: -1;
        opacity: 0.1;
    }
    /* Title centered with fancy gradient */
    .content h1 { 
        text-align: center; 
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, var(--accent), var(--accent-dark));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    /* Fancy divider with gradient and glow */
    .divider { 
        height: 4px; 
        background: linear-gradient(to right, transparent, var(--accent), transparent);
        border-radius: 2px; 
        margin: 0; 
        position: relative;
    }
    .divider::after {
        content: '';
        position: absolute;
        top: 0;
        left: 25%;
        right: 25%;
        height: 100%;
        background: inherit;
        filter: blur(4px);
        opacity: 0.7;
    }
    /* force controls and output to occupy exactly half of the internal content height each
       subtracting the divider height (10px) by using calc((100% - 10px)/2) as flex-basis */
    .controls-panel { 
        display:flex; 
        flex-direction: column;
        justify-content: space-evenly;
        padding: 24px; 
        background: var(--control-bg);
        border-radius: 16px; 
        border: 1px solid rgba(255, 121, 64, 0.15);
        flex: 0 0 calc((100% - 10px) / 2); 
        min-height:0; 
        color: var(--text);
        box-shadow: 
            inset 0 1px 0 0 rgba(255, 255, 255, 0.6),
            0 0 0 1px rgba(255, 121, 64, 0.05);
        position: relative;
        overflow: hidden;
    }
    .controls-panel::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(255, 121, 64, 0.08), transparent);
        opacity: 0.5;
    }
    .controls-panel .row {
        display: flex;
        align-items: center;
        gap: 1rem;
        width: 100%;
        justify-content: center;
    }
    .output-panel { 
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
        padding: 24px;
        border-radius: 16px; 
        background: var(--input-bg);
        border: 1px solid var(--border);
        flex: 0 0 calc((100% - 10px) / 2); 
        min-height:0; 
        color: var(--text);
    }
    .output-panel .row {
        display: flex;
        align-items: center;
        gap: 1rem;
        width: 100%;
        margin-bottom: 1rem;
        color: var(--text-light);
    }
    .output-section {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        background: var(--panel-bg);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    /* Add styles for text elements */
    p, label, select, input {
        color: var(--text);
        margin: 0;
    }
    label {
        font-weight: 500;
        color: var(--text-light);
        margin-bottom: 0.5rem;
    }
    .output-text {
        color: var(--text);
        font-size: 1.1rem;
        line-height: 1.6;
        background: var(--panel-bg);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    /* controls and output now flex equally within the content area */
    .controls-panel { display:flex; align-items:center; gap:0.75rem; padding: 18px; background: linear-gradient(180deg, rgba(240,242,245,0.6), rgba(250,250,250,0.6)); border-radius:8px; border:1px solid rgba(220,224,228,0.7); flex:1 1 0; min-height:0; }
     /* divider between sections - zero margin so it sits exactly between halves */
     .divider { height: 1px; background: #e6e9ec; border-radius: 1px; margin: 0; }
     /* force controls and output to occupy exactly half of the internal content height each
         subtracting the divider height (1px) by using calc((100% - 1px)/2) as flex-basis */
     .controls-panel { display:flex; align-items:center; gap:0.75rem; padding: 18px; background: linear-gradient(180deg, rgba(240,242,245,0.6), rgba(250,250,250,0.6)); border-radius:8px; border:1px solid rgba(220,224,228,0.7); flex: 0 0 calc((100% - 1px) / 2); min-height:0; }
     .output-panel { padding: 20px; border-radius:8px; background: transparent; flex: 0 0 calc((100% - 1px) / 2); min-height:0; }
    /* clearly assign halves: keep controls visually prominent on top */
    .controls-panel { flex: 0 0 auto; }
    .output-panel { flex: 0 0 auto; }
    .row {display:flex; gap:0.5rem; align-items:center; margin:0;}
    select, button {padding:0.5rem 0.75rem; font-size:1rem; border-radius:6px; border:1px solid #e0e3e8; background:#fff}
        #output {white-space:pre-wrap; background:#f7f7f7; padding:0.8rem; border-radius:6px; min-height:3rem;}
        .muted {color:#666; font-size:0.9rem;}
        @media (max-width: 900px) {
            :root { --side-width: 0px; }
            .side-rect { display:none; }
            .content { margin: 16px; min-height: 580px; }
            /* on small screens let the panels stack naturally (remove rigid half-split) */
            .controls-panel, .output-panel { flex: 0 0 auto; padding: 20px; }
            .divider { margin: 12px 0; height: 10px; }
        }
    </style>
</head>
<body>
    <div class="side-rect left" aria-hidden="true"></div>
    <div class="side-rect right" aria-hidden="true"></div>
    <div class="content">
    <h1>Basic Flask Website Interface</h1>
    <p class="muted">Use the record button to capture audio. Press once to start and again to stop and upload.</p>

    <div class="controls-panel">
        <div class="row">
            <label for="inputLang">Input language:</label>
            <select id="inputLang" title="Language spoken into the microphone">
                <option value="auto">Detect (auto)</option>
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
            </select>
        </div>

        <div class="row">
            <button id="recordBtn">Start Recording</button>
        </div>

        <div class="row">
            <div id="status" class="muted">Idle</div>
        </div>
    </div>

    <div class="divider" aria-hidden="true"></div>

    <div class="output-panel">
        <div class="row">
            <label for="lang">Target language:</label>
            <select id="lang">
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
            </select>
            <button id="clear">Clear Output</button>
        </div>
        
        <div class="output-section">
            <h3>Translated output</h3>
            <div id="output">Nothing yet</div>
        </div>
    </div>

<script>
const inputLang = document.getElementById('inputLang');
const lang = document.getElementById('lang');
const output = document.getElementById('output');
const status = document.getElementById('status');
const clearBtn = document.getElementById('clear');

clearBtn.addEventListener('click', () => {
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
    // include the selected input language (spoken language) if present
    try { form.append('input_lang', inputLang ? inputLang.value : 'auto'); } catch(e) {}
    status.textContent = 'Uploading...';
    fetch('/upload_audio', { method: 'POST', body: form })
        .then(r => r.json())
        .then(data => {
            status.textContent = data.success ? ('Saved: ' + data.filename + (data.input_lang ? (' — input: ' + data.input_lang) : '')) : 'Upload failed';
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
</div>
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
        # read optional input language from form data (may be empty for raw fallback)
        input_lang = request.form.get('input_lang') or request.args.get('input_lang') or None
        return jsonify({'success': True, 'filename': os.path.basename(path), 'input_lang': input_lang})

    filename = secure_filename(file.filename or f"recording-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.webm")
    save_path = os.path.join(uploads_dir, filename)
    file.save(save_path)
    # capture the declared input language (spoken language)
    input_lang = request.form.get('input_lang') or request.args.get('input_lang') or None
    return jsonify({'success': True, 'filename': filename, 'input_lang': input_lang})

if __name__ == '__main__':
        # Run the app: visit http://127.0.0.1:5000/
        app.run(host='0.0.0.0', port=5000, debug=True)