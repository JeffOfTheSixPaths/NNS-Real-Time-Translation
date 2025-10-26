# 🌐 NNS Real-Time Translation

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-Backend-lightgrey?logo=flask)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Workers-orange?logo=cloudflare)
![License](https://img.shields.io/badge/License-MIT-green)

A **real-time speech translation web app** built with **Flask (Python)** and **Cloudflare Workers (Wrangler)**.  
It performs live **Speech → Text → Translation → Speech** for instant multilingual communication.

---

## ⚙️ Tech Stack
- **Backend:** Flask (Python)
- **Edge / Hosting:** Cloudflare Wrangler
- **Frontend:** HTML, CSS, JS
- **APIs:** Gemini / Google Translate / Speech-to-Text
- **Env:** Python 3.11+, Node.js 18+

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR-USERNAME/NNS-Real-Time.git
cd NNS-Real-Time

# 2. Python setup
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 3. Run Flask
python flaskTest
# → http://127.0.0.1:5000

# 4. Deploy (Cloudflare)
wrangler login
wrangler publish
