<div align="center">

# 🎬 YouClip AI — AI Video Shorts Generator

A FastAPI + Next.js portfolio application for converting authorized YouTube videos or uploaded media files into AI-selected short clips with transcription and LLM-assisted highlight selection.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Frontend-Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/UI-React%2019-61dafb?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/Types-TypeScript-3178c6?style=for-the-badge&logo=typescript&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-46%20Automated-22c55e?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-f97316?style=for-the-badge)

</div>

---

## 📌 Project Overview

**YouClip AI** is a local-first portfolio application designed to automatically generate short, engaging video clips from long-form YouTube videos or local media uploads. 

The application pairs a **FastAPI backend** with a **Next.js 16 studio**. A Python pipeline manages video transcription, strict LLM-assisted highlight selection, and deterministic media cropping, while the API adapter provides bounded background jobs to the frontend.

**Project integration, repairs, API, studio, tests, and documentation:** Muhammad Ali Nawaz 2026.
*Note: The media pipeline incorporates MIT-licensed code from [SamurAIGPT's AI YouTube Shorts Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator). Its license and provenance notices are preserved. See [`docs/UPSTREAM_CHANGES.md`](docs/UPSTREAM_CHANGES.md).*

---

## ✨ Features

### 🎞️ Media Workspace
- 📤 **Streamed uploads** with byte, signature, ffprobe duration, and resolution limits
- 🔗 **Canonical YouTube-only URL handling** rejecting lookalikes, IP literals, and unsupported schemes
- 🔄 **Status polling** and explicit processing modes (`API` vs `Local`)
- 📥 **Protected media loading** and per-job isolated output directories
- 🧹 **Retention cleanup** to remove terminal job files and records after a configured period

### 🧠 AI Video Intelligence
- 🗣️ **Transcription** chunking with relative timestamps and absolute offsets (faster-whisper)
- 🤖 **LLM-assisted highlight selection** mapping engaging moments using OpenAI, Gemini, or MuAPI
- ✂️ **Deterministic overlap removal** and strict LLM output validation
- 🎬 **Automated cropping** and rendering via FFmpeg and OpenCV
- 📊 **Scoring system** providing LLM opinions to rank candidate clips

### 🛡️ Reliability and Security Controls
- 🔐 **Local and fail-closed hosted modes** (`WEB_ACCESS_MODE=local` by default)
- 🔑 **Session-based authentication** storing the `X-YouClip-Key` only in browser session storage
- 🚦 **Bounded execution** enforcing maximum workers and queued jobs (`429` retry guidance)
- 📁 **Safe media path checks** preventing directory traversal
- 🧾 **Sanitized public errors** masking provider and media-tool failures behind stable messages
- 🛑 **No arbitrary remote URLs accepted** outside of strictly verified YouTube domains

### 🖥️ Next.js Studio
- 📱 **Responsive React 19 interface** built with TypeScript and custom CSS
- 📤 **XMLHttpRequest upload progress** feedback
- 📋 **Failure state handling** and continuous job status polling
- 👨‍💻 Developer attribution for Muhammad Ali Nawaz 2026

---

## 🖼️ Screenshots

| YouClip AI |
| --- |
| ![Homepage](docs/screenshots/homepage.png) |

---

## 🧰 Tech Stack

### Frontend
- Next.js 16
- React 19
- TypeScript
- Native Fetch API and responsive custom CSS

### Backend
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic Settings

### Media & AI Processing
- yt-dlp
- faster-whisper
- OpenAI / Gemini clients
- FFmpeg & FFprobe
- OpenCV

### Quality Assurance
- pytest and pytest-asyncio
- ESLint and TypeScript checks
- Next.js production build checks
- GitHub Actions CI

---

## 📁 Folder Structure

```text
youclip-ai/
├── .github/workflows/ci.yml
├── backend_api/
│   ├── app.py
│   ├── config.py
│   ├── routes.py
│   └── job_store.py
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
├── shorts_generator/
│   ├── pipeline.py
│   ├── transcribe.py
│   └── crop.py
├── docs/
│   ├── UPSTREAM_CHANGES.md
│   ├── VALIDATION_REPORT.md
│   └── original-backend-sha256.txt
├── scripts/
│   └── verify-backend-unchanged.py
├── tests/
├── .env.example
├── main.py
├── requirements-dev.txt
├── requirements-local.txt
├── LICENSE
└── README.md
```

---

## 🔐 Environment Variables

Never commit a real `.env` file. Copy `.env.example` to `.env` in both root and `frontend` directories.

### Recommended Local Configuration (Root `.env`)
```env
WEB_ACCESS_MODE=local
WEB_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
WEB_MAX_WORKERS=1
WEB_MAX_QUEUED_JOBS=2
WEB_MAX_UPLOAD_MB=500
WEB_MAX_VIDEO_SECONDS=14400
WEB_MAX_VIDEO_WIDTH=1920
WEB_MAX_VIDEO_HEIGHT=1080
WEB_RETENTION_SECONDS=3600

# Required for Local Mode:
OPENAI_API_KEY=your_openai_key_here
# OR GEMINI_API_KEY=your_gemini_key_here
```

### Hosted Configuration
```env
WEB_ACCESS_MODE=hosted
YOUCLIP_ACCESS_KEY=<generate_a_long_random_value_for_hosted_mode>
# Required for API Mode:
MUAPI_API_KEY=your_muapi_key_here
```
*Never put `YOUCLIP_ACCESS_KEY` in a `NEXT_PUBLIC_*` variable.*

---

## 🚀 Getting Started on Windows

### Prerequisites
- Windows 10 or 11
- Python 3.11 or newer
- Node.js 20.9 or newer and npm 10 or newer
- **FFmpeg and FFprobe** installed and added to system PATH

---

## ▶️ Run the Complete Project

Use **Windows PowerShell** or CMD from the project root.

### 1. Create a Clean Virtual Environment
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
```

### 2. Install Backend and Media Dependencies
```powershell
py -m pip install -r requirements-dev.txt
# Install local AI/Media dependencies for Local Mode:
py -m pip install -r requirements-local.txt
```

### 3. Create the Local Environment File
```powershell
Copy-Item .env.example .env
```
*Edit `.env` to add your `OPENAI_API_KEY` or `GEMINI_API_KEY`.*

### 4. Start the FastAPI Backend
```powershell
py -m uvicorn backend_api.app:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Install and Start the Next.js Frontend
Open a second PowerShell window:
```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```
Open `http://localhost:3000`.

---

## 🧪 Test the Project

No live provider, public download, model download, or media render is required by the automated checks.

### Complete Backend Quality Check
```powershell
.\.venv\Scripts\Activate.ps1
py scripts/verify-backend-unchanged.py
py -m compileall -q main.py shorts_generator backend_api
py -m pytest -q
```

### Complete Frontend Quality Check
```powershell
cd frontend
npm ci
npm run lint
npm test
npx tsc --noEmit
npm run build
```

---

## 📜 Available Commands

| Command | Description |
| --- | --- |
| `py -m uvicorn backend_api.app:app --host 127.0.0.1 --port 8000 --reload` | Start the FastAPI backend |
| `npm run dev` | Start the Next.js studio from `frontend` |
| `py scripts/verify-backend-unchanged.py` | Verify upstream code provenance |
| `py -m pytest -q` | Run mocked Python workflow tests |
| `npm test` | Run frontend HTTP-state tests |
| `npm run build` | Validate Next.js production build |

---

## 🔌 Main API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | View limits and provider readiness |
| `POST` | `/api/uploads` | Validate and stage an uploaded local source |
| `POST` | `/api/jobs` | Admit a bounded generation job |
| `GET` | `/api/jobs/{job_id}` | Read an owned job until expiry |
| `GET` | `/api/media/{job_id}/{filename}` | Read a referenced, owned result |

*Note: There is intentionally no global job-list endpoint. In hosted mode, add `X-YouClip-Key` to each request.*

---

## 🎯 Project Flow

```text
User provides YouTube URL or Media Upload
└── FastAPI handles request via Next.js Studio
    ├── Validates media format, resolution, and URL shape
    ├── Admits job if within WEB_MAX_QUEUED_JOBS limit
    └── Places job in ThreadPoolExecutor
        ├── Creates unique local runtime directory
        ├── Routes to 'Local' or 'API' processing mode
        ├── Executes Python Video Pipeline
        └── Marks job completed or failed
            └── Next.js polls status and displays safe media URLs
```

---

## 🎥 Media Processing Flow

```text
Source Video (Upload or yt-dlp)
└── Bounded Pipeline Processing
    ├── Audio Extraction (FFmpeg)
    ├── Transcription & Chunking (faster-whisper)
    │   └── Relative timestamps & absolute offset generation
    ├── Highlight Selection (OpenAI/Gemini/MuAPI)
    │   └── Strict LLM validation & ranking score
    ├── Overlap Removal (Deterministic deduplication)
    └── Media Cropping (OpenCV & FFmpeg)
        ├── Subject tracking / centering
        ├── 9:16 aspect ratio framing
        └── Final short-form video generation
```

---

## ⚠️ Scope and Limitations

- **Portfolio Context:** This remains a single-process portfolio application. It does not claim distributed or unrestricted public-service scalability. 
- **Durability:** Job state is an in-memory store and is not durable across restarts. Running jobs are not cancellable.
- **LLM Scoring:** The displayed score is an LLM opinion used to rank candidates. It is not a measured prediction of views, retention, engagement, or virality.
- **Copyright:** Only process media you own or have permission to transform. Review applicable platform terms and copyright requirements. Real provider calls may cost money.

---

## 🧑‍💻 Author

**Muhammad Ali Nawaz**  
Python Developer

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). The required MIT notices for incorporated upstream work (SamurAIGPT) and project-owned work are preserved.
