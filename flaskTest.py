from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import sys

# Import STT module directly since it's in the same directory
from STT import transcribe_audio
from gemini import translate_text
from TTS import synthesize_audio_bytes

app = Flask(__name__)

# Basic in-file HTML template with a small real-time UI using fetch()
INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>NNH Real Time Translation</title>
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
            font-size: 0.95rem;
            font-weight: 600;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            background: var(--panel-bg);
            color: var(--text);
            cursor: pointer;
            position: relative;
            z-index: 2;
        }

        /* Select Styles */
        select {
            padding: 10px 36px 10px 16px;
            font-size: 15px;
            font-weight: 500;
            border: 2px solid var(--border);
            background-color: var(--panel-bg);
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%23FF7940' viewBox='0 0 16 16'%3E%3Cpath d='M8 10.5l4-4H4z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            transition: all 0.2s ease;
        }

    select:not(:disabled) {
        border: 2px solid var(--border);
    }

    select:not(:disabled):hover {
        border-color: var(--accent);
        transform: translateY(-1px);
        box-shadow: 
            0 4px 12px rgba(255, 121, 64, 0.15),
            0 1px 3px rgba(0,0,0,0.05);
    }

    select:not(:disabled):focus {
        outline: none;
        border-color: var(--accent);
        box-shadow: 
            0 0 0 3px var(--accent-glow),
            0 4px 12px rgba(255, 121, 64, 0.15);
    }

    select:disabled {
        background: var(--disabled);
        color: var(--text-light);
        cursor: not-allowed;
        opacity: 0.7;
        border-color: var(--border);
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

    /* Button Styles */
    button {
        padding: 10px 20px;
        font-size: 15px;
        font-weight: 600;
        border: none;
        border-radius: 12px;
        background: var(--panel-bg);
        color: var(--text);
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
        z-index: 1;
    }

    button:not(:disabled) {
        box-shadow: 
            0 2px 4px rgba(0,0,0,0.05),
            0 1px 2px rgba(0,0,0,0.1);
    }

    button:not(#recordBtn):not(:disabled) {
        border: 2px solid var(--border);
    }

    button:not(:disabled):hover {
        transform: translateY(-1px);
        box-shadow: 
            0 4px 8px rgba(0,0,0,0.1),
            0 2px 4px rgba(0,0,0,0.05);
    }

    button:not(:disabled):active {
        transform: translateY(1px);
        box-shadow: 
            0 2px 4px rgba(0,0,0,0.05),
            0 1px 2px rgba(0,0,0,0.1);
    }

    button:disabled {
        background: var(--disabled);
        color: var(--text-light);
        cursor: not-allowed;
        opacity: 0.7;
    }

    /* Record Button Specific Styles */
    #recordBtn:not(:disabled) {
        background: linear-gradient(135deg, var(--accent), var(--accent-dark));
        color: white;
        padding: 12px 24px;
        box-shadow: 
            0 2px 4px rgba(0,0,0,0.1),
            0 6px 12px rgba(255, 121, 64, 0.2);
        text-shadow: 0 1px 1px rgba(0,0,0,0.1);
    }

    #recordBtn:not(:disabled):hover {
        background: linear-gradient(135deg, var(--accent-light), var(--accent));
        box-shadow: 
            0 4px 8px rgba(0,0,0,0.15),
            0 8px 16px rgba(255, 121, 64, 0.3);
    }

    #recordBtn.recording {
        background: linear-gradient(135deg, #e64040, #c01010) !important;
        animation: pulse 2s infinite;
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
    /* Transcription box shown below the record button */
    .transcription-box {
        width: 100%;
        max-width: 520px;
        color: var(--text);
        background: var(--panel-bg);
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        font-size: 0.98rem;
        line-height: 1.4;
        text-align: left;
    }
    /* Clear styles and fix layout */
    .controls-panel,
    .output-panel {
        flex: 0 0 calc((100% - 10px) / 2);
        min-height: 0;
        padding: 24px;
        border-radius: 16px;
    }

    .controls-panel {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 1.5rem;
        background: var(--control-bg);
        border: 1px solid rgba(255, 121, 64, 0.15);
        box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.6);
    }

    .output-panel {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        background: var(--input-bg);
        border: 1px solid var(--border);
    }

    .row {
        display: flex;
        align-items: center;
        gap: 1rem;
        width: 100%;
        justify-content: center;
    }
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
    <h1>NNS Real Time Translation</h1>
    <p class="muted">Use the record button to capture audio. Press once to start and again to stop and upload.</p>

    <div class="controls-panel">
        <div class="row">
            <label for="inputLang">Input language:</label>
            <select id="inputLang" title="Language spoken into the microphone">
                <option value="es">Spanish</option>
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="zh">Chinese</option>
            </select>
        </div>

        <div class="row">
            <button id="recordBtn">Start Recording</button>
        </div>

        <!-- Transcription display shown below the record button -->
        <div class="row">
            <div id="transcribed" class="transcription-box">Nothing yet</div>
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
                <option value="zh">Chinese</option>
            </select>
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
const transcriptionBox = document.getElementById('transcribed');

// Clear Output button removed; use page refresh to reset UI or implement another control if needed.

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
    // Show immediate listening state in the transcription box
    try { if (transcriptionBox) transcriptionBox.textContent = 'Listening...'; } catch(e) {}
        
    // Disable controls immediately
    inputLang.disabled = true;
    lang.disabled = true;
        
        // Start countdown from 2
        let countdown = 2;
        recordBtn.textContent = `Starting in ${countdown}...`;
        
        const countdownInterval = setInterval(() => {
            countdown--;
            if (countdown > 0) {
                recordBtn.textContent = `Starting in ${countdown}...`;
            } else {
                clearInterval(countdownInterval);
                recordBtn.textContent = 'Stop Recording';
                recordBtn.classList.add('recording');
                status.textContent = 'Recording...';
            }
        }, 1000);
        
    } catch (err) {
        console.error('Microphone access denied or error:', err);
        status.textContent = 'Microphone error';
        recordBtn.classList.remove('recording');
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
    
    // Clear any potential countdown styles
    recordBtn.style.animation = 'none';
    recordBtn.textContent = 'Start Recording';
    recordBtn.classList.remove('recording');
    
    // Re-enable controls
    inputLang.disabled = false;
    lang.disabled = false;
}

function onRecordingStop() {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const form = new FormData();
    // Provide a filename; server will sanitize
    form.append('audio_data', blob, 'recording.webm');
    // include the selected input language (spoken language) if present
    try { 
        form.append('input_lang', inputLang ? inputLang.value : 'auto');
        form.append('target_lang', lang ? lang.value : 'en');
    } catch(e) {}
    status.textContent = 'Uploading...';
    fetch('/upload_audio', { method: 'POST', body: form })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                status.textContent = 'Transcription complete';
                // Show transcription under the record button
                if (transcriptionBox) transcriptionBox.textContent = data.transcription || 'No transcription available';
                // Show only the translated text in the translation output area
                output.textContent = data.translated || 'Translation not available';
                
                // Swap input and output languages to prep for the other person's response
                if (inputLang && lang) {
                    const tempLang = inputLang.value;
                    inputLang.value = lang.value;
                    lang.value = tempLang;
                }
                
                // If server returned an audio URL, play it
                try {
                    if (data.audio_url) {
                        // Add cache-busting parameter to ensure we get the latest audio
                        const audioUrlWithCacheBust = data.audio_url + '?t=' + Date.now();
                        const audio = new Audio(audioUrlWithCacheBust);
                        // allow autoplay in browsers that permit it; otherwise user gesture already occurred
                        audio.play().catch(err => console.warn('Audio playback failed', err));
                    }
                } catch (err) {
                    console.error('Failed to play returned audio', err);
                }
            } else {
                // Server returned an error
                if (transcriptionBox) transcriptionBox.textContent = data.transcription || 'No transcription available';
                output.textContent = '';
                status.textContent = 'Error: ' + (data.error || 'Unknown error');
                console.error('Upload failed:', data);
            }
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
        Endpoint that uses Gemini to translate text
        """
        data = request.get_json(force=True) or {}
        text = data.get('text', '')
        target_lang = data.get('target', 'en')
        input_lang = data.get('input_lang', 'auto')

        if not text:
            return jsonify({'translated': ''})

        # Use Gemini's translation function
        translated = translate_text(text, target_lang=target_lang, input_lang=input_lang)
        return jsonify({'translated': translated})


@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """Accepts a posted audio blob (multipart/form-data with field 'audio_data') and saves it to uploads/"""
    # Ensure uploads dir exists
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    try:
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
        else:
            filename = secure_filename(file.filename or f"recording-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.webm")
            path = os.path.join(uploads_dir, filename)
            file.save(path)

        # Get the input language from form data
        input_lang = request.form.get('input_lang') or request.args.get('input_lang')
        
        # Convert 'auto' to None for language detection
        lang_code = None if input_lang == 'auto' else input_lang
        
        # Convert language codes to ElevenLabs format
        lang_map = {
            'en': 'eng',
            'es': 'spa',
            'fr': 'fra',
            'de': 'deu',
            'zh' : 'cmn'
        }
        if lang_code in lang_map:
            lang_code = lang_map[lang_code]
        
        # Transcribe the audio using our STT module
        transcription = transcribe_audio(path, language_code=lang_code)
        
        # Get the target language from form data
        target_lang = request.form.get('target_lang', 'en')
        
        # Translate the transcription using Gemini
        translated_text = translate_text(
            input_text=transcription,
            target_lang=target_lang,
            input_lang=input_lang if input_lang != 'auto' else 'auto'
        )

        # Synthesize translated text to audio (mp3 bytes)
        try:
            audio_bytes = synthesize_audio_bytes(translated_text)
            audio_filename = secure_filename(f"{os.path.splitext(filename)[0]}_translated.mp3")
            audio_path = os.path.join(uploads_dir, audio_filename)
            with open(audio_path, 'wb') as af:
                af.write(audio_bytes)
            audio_url = f"/audio/{audio_filename}"
        except Exception as e:
            # If TTS fails, don't block the response; return transcription/translation without audio
            audio_url = None
            print("TTS error:", e)

        return jsonify({
            'success': True,
            'filename': filename,
            'input_lang': input_lang,
            'transcription': transcription,
            'translated': translated_text,
            'audio_url': audio_url
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve generated audio files from uploads/"""
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    return send_from_directory(uploads_dir, filename)

if __name__ == '__main__':
        # Run the app: visit http://127.0.0.1:5000/
        app.run(host='0.0.0.0', port=5000, debug=True)