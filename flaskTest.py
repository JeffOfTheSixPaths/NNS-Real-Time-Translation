from flask import Flask, request, jsonify, render_template_string, send_from_directory, redirect
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from datetime import datetime
import sys
import uuid
import threading
import json
import array
import logging

# Configure basic logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Import STT module directly since it's in the same directory
from STT import transcribe_audio
from gemini import translate_text
from TTS import synthesize_audio_bytes

# Vosk realtime STT globals (lazy-load model)
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except Exception as e:
    Model = None
    KaldiRecognizer = None
    VOSK_AVAILABLE = False
    print('Vosk import failed (install vosk to enable realtime STT):', e, file=sys.stderr)

MODEL = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model_english')
RECOGNIZERS = {}
RECOGNIZERS_LOCK = threading.Lock()
RECOGNIZER_LOCKS = {}

MODEL_LOCK = threading.Lock()

def find_model_for_language(lang_code: str):
    """Try common locations for a language-specific Vosk model directory.
    Returns the path if found, otherwise None.
    """
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, f"model-{lang_code}"),
        os.path.join(base, f"model_{lang_code}"),
        os.path.join(base, 'models', lang_code),
        os.path.join(base, 'models', f"model-{lang_code}"),
        os.path.join(base, 'models', f"model_{lang_code}"),
        os.path.join(base, 'model')  # fallback to default
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return None

def load_model_at_path(path: str):
    """Load a Vosk model from path and replace the global MODEL. Clears existing recognizers."""
    global MODEL, MODEL_PATH
    if not VOSK_AVAILABLE:
        raise RuntimeError('Vosk not available')
    if not os.path.isdir(path):
        raise RuntimeError(f'Model path not found: {path}')

    with MODEL_LOCK:
        # Load new model (may take time)
        new_model = Model(path)
        MODEL = new_model
        MODEL_PATH = path

    # Clear existing recognizers safely
    with RECOGNIZERS_LOCK:
        RECOGNIZERS.clear()
        # Release and clear per-session locks
        for k, lk in list(RECOGNIZER_LOCKS.items()):
            try:
                # best-effort release if locked
                if lk.locked():
                    try:
                        lk.release()
                    except Exception:
                        pass
            except Exception:
                pass
        RECOGNIZER_LOCKS.clear()

def ensure_model_loaded():
    global MODEL
    if MODEL is not None:
        return
    if not VOSK_AVAILABLE:
        raise RuntimeError('Vosk package not available in this Python environment')
    if not os.path.isdir(MODEL_PATH):
        raise RuntimeError(f'Vosk model directory not found at: {MODEL_PATH}')
    # Load the model (can take time)
    MODEL = Model(MODEL_PATH)
    print('Vosk model loaded from', MODEL_PATH)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
@app.before_request
def enforce_https():
    # Cloudflare sets this header
    if request.headers.get("X-Forwarded-Proto") == "http":
        return redirect(request.url.replace("http://", "https://", 1), code=301)

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
// Elements
const inputLang = document.getElementById('inputLang');
const lang = document.getElementById('lang');
const output = document.getElementById('output');
const status = document.getElementById('status');
const transcriptionBox = document.getElementById('transcribed');
const recordBtn = document.getElementById('recordBtn');

// Realtime streaming variables
let audioContext = null;
let processor = null;
let mediaStream = null;
let sessionId = null;
let isStarting = false;
// Queue for finalized text to be translated periodically
let finalizedQueue = [];

function flushTranslationQueue() {
    if (!finalizedQueue.length) return;
    const text = finalizedQueue.join(' ');
    finalizedQueue.length = 0;
    translateAndShow(text);
}

// Flush every 2 seconds (reduced from 6s to speed up translation batching)
setInterval(flushTranslationQueue, 2000);

// Utility: convert Float32 [-1,1] buffer -> 16-bit PCM ArrayBuffer
function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
}

function downsampleBuffer(buffer, inputSampleRate, outSampleRate) {
    if (outSampleRate === inputSampleRate) {
        return buffer;
    }
    if (outSampleRate > inputSampleRate) {
        console.warn('downsampling rate should be smaller than original sample rate');
        return buffer;
    }
    const sampleRateRatio = inputSampleRate / outSampleRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
        const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
        // Use average value between the current and next offset
        let accum = 0, count = 0;
        for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
            accum += buffer[i];
            count++;
        }
        result[offsetResult] = accum / count;
        offsetResult++;
        offsetBuffer = nextOffsetBuffer;
    }
    return result;
}

async function startRecording() {
    try {
        // Create session on server
        const startResp = await fetch('/stt_start', { method: 'POST' });
        const startJson = await startResp.json();
        sessionId = startJson.session_id;
        if (!sessionId) throw new Error('Failed to create STT session');

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(mediaStream);

        // ScriptProcessor is deprecated but widely supported; buffer size 4096 is a reasonable tradeoff
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (evt) => {
            const inputData = evt.inputBuffer.getChannelData(0);
            const downsampled = downsampleBuffer(inputData, audioContext.sampleRate, 16000);
            if (!downsampled) return;
            const pcm16 = floatTo16BitPCM(downsampled);

            // POST the raw PCM16 bytes to /stt_chunk
            fetch('/stt_chunk?session_id=' + encodeURIComponent(sessionId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/octet-stream' },
                body: pcm16
            }).then(r => r.json()).then(j => {
                // Vosk returns { partial: '...' } for partials and { text: '...' } or {result:[...], text:'...'} for finals
                if (!j) return;
                if (j.partial) {
                    transcriptionBox.textContent = j.partial;
                } else if (j.text) {
                    transcriptionBox.textContent = j.text;
                    // Queue final text for periodic translation (flushed every 6s)
                    finalizedQueue.push(j.text);
                }
            }).catch(err => {
                // Don't spam console on transient errors
                console.debug('stt_chunk error', err);
            });
        };

        source.connect(processor);
        processor.connect(audioContext.destination);

        // UI updates
        inputLang.disabled = true;
        lang.disabled = true;
        recordBtn.textContent = 'Stop Recording';
        recordBtn.classList.add('recording');
        status.textContent = 'Recording...';
        transcriptionBox.textContent = 'Listening...';
    } catch (err) {
        console.error('startRecording error', err);
        status.textContent = 'Microphone error';
    }
}

async function stopRecording() {
    try {
        // Stop audio nodes
        if (processor) {
            processor.disconnect();
            processor.onaudioprocess = null;
            processor = null;
        }
        if (audioContext) {
            try { audioContext.close(); } catch(e) {}
            audioContext = null;
        }
        if (mediaStream) {
            mediaStream.getTracks().forEach(t => t.stop());
            mediaStream = null;
        }

        // Tell server to finalize and get last result
        if (sessionId) {
            const r = await fetch('/stt_stop?session_id=' + encodeURIComponent(sessionId), { method: 'POST' });
            try {
                const j = await r.json();
                if (j && j.text) {
                    transcriptionBox.textContent = j.text;
                    // Queue final text and flush immediately on stop for lower latency
                    finalizedQueue.push(j.text);
                    flushTranslationQueue();
                }
            } catch (e) {
                console.debug('stt_stop parse error', e);
            }
            sessionId = null;
        }

        // UI updates
        recordBtn.textContent = 'Start Recording';
        recordBtn.classList.remove('recording');
        inputLang.disabled = false;
        lang.disabled = false;
        status.textContent = 'Idle';
    } catch (err) {
        console.error('stopRecording error', err);
    }
}

async function translateAndShow(text) {
    if (!text || !text.trim()) return;
    output.textContent = 'Translating...';
    try {
        const resp = await fetch('/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, target: lang.value || 'en', input_lang: inputLang.value || 'auto', synthesize: true })
        });
        const j = await resp.json();
        output.textContent = j.translated || '';
        if (j && j.audio_url) {
            // Play synthesized audio (add cache-bust)
            const url = j.audio_url + '?t=' + Date.now();
            const audio = new Audio(url);
            const fname = (j.audio_url || '').split('/').pop();
            const tryDelete = () => {
                if (!fname) return;
                fetch('/audio_delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: fname })
                }).catch(() => {});
            };

            audio.play().then(() => {
                // Remove the file once playback ends
                audio.addEventListener('ended', tryDelete);
                audio.addEventListener('error', tryDelete);
            }).catch(err => {
                console.warn('Audio playback failed', err);
                // If playback is blocked, delete after a short delay to avoid leftover files
                setTimeout(tryDelete, 3000);
            });
        }
    } catch (e) {
        console.error('translate error', e);
        output.textContent = 'Translation error';
    }
}

// Toggle recording on button press with immediate UI feedback to avoid perceived delay
recordBtn.addEventListener('click', () => {
    if (!mediaStream && !isStarting) {
        // Provide instant visual feedback while getUserMedia / AudioContext initialize
        isStarting = true;
        recordBtn.textContent = 'Stop Recording';
        recordBtn.classList.add('recording');
        inputLang.disabled = true;
        lang.disabled = true;
        status.textContent = 'Initializing...';
        transcriptionBox.textContent = 'Starting...';

        // Start recording asynchronously; update status when ready or revert on error
        startRecording().then(() => {
            isStarting = false;
            status.textContent = 'Recording...';
        }).catch(err => {
            console.error('startRecording failed', err);
            isStarting = false;
            // Revert UI
            recordBtn.textContent = 'Start Recording';
            recordBtn.classList.remove('recording');
            inputLang.disabled = false;
            lang.disabled = false;
            status.textContent = 'Microphone error';
            transcriptionBox.textContent = 'Nothing yet';
        });
    } else {
        // Immediate feedback for stopping
        status.textContent = 'Stopping...';
        stopRecording();
    }
});

// When the input language changes, request the server to load an appropriate Vosk model.
inputLang.addEventListener('change', async () => {
    const newLang = inputLang.value;
    // If currently recording, stop first to avoid switching mid-stream
    if (mediaStream) {
        status.textContent = 'Stopping to switch model...';
        try { await stopRecording(); } catch (e) { console.warn('stopRecording failed during model switch', e); }
    }

    recordBtn.disabled = true;
    status.textContent = 'Loading model for ' + newLang + '...';
    transcriptionBox.textContent = 'Loading model...';

    try {
        const resp = await fetch('/stt_set_language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lang: newLang })
        });
        const j = await resp.json();
        if (j && j.success) {
            status.textContent = 'Model loaded: ' + (j.model_path || newLang);
            transcriptionBox.textContent = 'Model ready (' + newLang + ')';
        } else {
            status.textContent = 'Model load failed';
            transcriptionBox.textContent = 'Model load failed: ' + (j && j.error ? j.error : 'unknown');
        }
    } catch (e) {
        console.error('stt_set_language error', e);
        status.textContent = 'Model load error';
        transcriptionBox.textContent = 'Model load error';
    } finally {
        recordBtn.disabled = false;
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
        synthesize = bool(data.get('synthesize', False))

        if not text:
            return jsonify({'translated': ''})

        # Use Gemini's translation function
        translated = translate_text(text, target_lang=target_lang, input_lang=input_lang)

        audio_url = None
        if synthesize and translated:
            try:
                uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                audio_bytes = synthesize_audio_bytes(translated)
                audio_filename = secure_filename(f"translated_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.mp3")
                audio_path = os.path.join(uploads_dir, audio_filename)
                with open(audio_path, 'wb') as af:
                    af.write(audio_bytes)
                audio_url = f"/audio/{audio_filename}"
            except Exception:
                logging.exception('translate: TTS failed')
                audio_url = None

        return jsonify({'translated': translated, 'audio_url': audio_url})


@app.route('/stt_start', methods=['POST'])
def stt_start():
    """Start a Vosk recognizer session and return a session_id."""
    try:
        ensure_model_loaded()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    session_id = request.args.get('session_id') or str(uuid.uuid4())
    sample_rate = 16000
    with RECOGNIZERS_LOCK:
        # Create a new recognizer for this session
        rec = KaldiRecognizer(MODEL, sample_rate)
        RECOGNIZERS[session_id] = rec
        # Per-session lock to serialize access to the recognizer (Flask may handle requests concurrently)
        RECOGNIZER_LOCKS[session_id] = threading.Lock()
    return jsonify({'session_id': session_id})


@app.route('/stt_set_language', methods=['POST'])
def stt_set_language():
    """Switch the Vosk model to match the requested language code.
    Expects JSON {"lang": "en"} or form/query param 'lang'.
    """
    data = request.get_json(silent=True) or {}
    lang_code = data.get('lang') or request.form.get('lang') or request.args.get('lang')
    if not lang_code:
        return jsonify({'success': False, 'error': 'lang required'}), 400

    # Stop any active recognizers and load the model if found
    model_path = find_model_for_language(lang_code)
    if not model_path:
        return jsonify({'success': False, 'error': f'No model found for lang {lang_code}'}), 404

    try:
        load_model_at_path(model_path)
        logging.info('stt_set_language: loaded model for %s at %s', lang_code, model_path)
        return jsonify({'success': True, 'model_path': model_path})
    except Exception as e:
        logging.exception('stt_set_language failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/stt_chunk', methods=['POST'])
def stt_chunk():
    """Accept raw PCM16 bytes for the given session_id and return partial or final JSON result from Vosk."""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    data = request.get_data()
    logging.debug('stt_chunk called: session=%s, bytes=%d', session_id, len(data) if data is not None else 0)
    if not data:
        # Tolerate empty chunks (can happen); respond with an empty partial instead of an error
        logging.debug('stt_chunk: empty body for session %s', session_id)
        return jsonify({'partial': ''})

    with RECOGNIZERS_LOCK:
        rec = RECOGNIZERS.get(session_id)
    if rec is None:
        logging.warning('stt_chunk: unknown session_id %s', session_id)
        return jsonify({'error': 'unknown session_id'}), 400

    try:
        # Defensive checks: Vosk expects 16-bit little-endian PCM. Ensure even number of bytes.
        if len(data) % 2 != 0:
            # Drop the trailing byte to keep pairs intact
            logging.debug('stt_chunk: odd-length chunk received (%d), dropping last byte', len(data))
            data = data[:-1]

        # Ignore trivially small chunks
        if len(data) < 4:
            return jsonify({'partial': ''})

        # Convert to array of int16 to validate format (will raise if bytes length mismatched)
        try:
            a = array.array('h')
            a.frombytes(data)
            # Ensure native byteorder is little-endian for Vosk; if system is big-endian, byteswap
            if sys.byteorder == 'big':
                a.byteswap()
            pcm_bytes = a.tobytes()
        except Exception as e:
            logging.exception('stt_chunk: failed to parse incoming audio bytes as int16')
            return jsonify({'error': 'invalid audio data'}), 400

        # Acquire per-recognizer lock to prevent concurrent calls into Vosk C++ decoder
        lock = None
        with RECOGNIZERS_LOCK:
            lock = RECOGNIZER_LOCKS.get(session_id)
        if lock is None:
            logging.warning('stt_chunk: missing per-session lock for %s', session_id)
            return jsonify({'error': 'session lock missing'}), 500

        lock.acquire()
        try:
            accepted = rec.AcceptWaveform(pcm_bytes)
        finally:
            lock.release()
        if accepted:
            # Final chunk produced a final result
            res = rec.Result()
            # Result is already JSON string; return as JSON
            return app.response_class(res, mimetype='application/json')
        else:
            # Partial result
            pres = rec.PartialResult()
            return app.response_class(pres, mimetype='application/json')
    except Exception as e:
        logging.exception('stt_chunk exception')
        return jsonify({'error': str(e)}), 500


@app.route('/stt_stop', methods=['POST'])
def stt_stop():
    """Finalize a recognizer session and return the final text."""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    with RECOGNIZERS_LOCK:
        rec = RECOGNIZERS.pop(session_id, None)
        lock = RECOGNIZER_LOCKS.pop(session_id, None)
    if rec is None:
        return jsonify({'error': 'unknown session_id'}), 400
    try:
        # Acquire the per-session lock before finalizing to ensure no in-flight AcceptWaveform calls
        if lock:
            lock.acquire()
        try:
            final = rec.FinalResult()
        finally:
            if lock:
                lock.release()
        return app.response_class(final, mimetype='application/json')
    except Exception as e:
        logging.exception('stt_stop exception')
        return jsonify({'error': str(e)}), 500


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


@app.route('/audio_delete', methods=['POST'])
def audio_delete():
    """Delete a generated audio file from uploads/ after playback."""
    data = request.get_json(force=True) or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'success': False, 'error': 'filename required'}), 400
    filename = secure_filename(filename)
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    path = os.path.join(uploads_dir, filename)
    # Ensure the resolved path is inside uploads_dir
    try:
        abs_path = os.path.abspath(path)
        abs_uploads = os.path.abspath(uploads_dir)
        if not abs_path.startswith(abs_uploads + os.sep) and abs_path != abs_uploads:
            return jsonify({'success': False, 'error': 'invalid filename'}), 400
        if os.path.exists(abs_path):
            os.remove(abs_path)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'not found'}), 404
    except Exception as e:
        logging.exception('audio_delete failed')
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
        # Run the app: visit http://127.0.0.1:5000/
        app.run(host='0.0.0.0', port=5000, debug=True)