# SENTINEL — Conversational Safety Intelligence
## AssemblyAI Voice Agent Hackathon 2026

> When something goes wrong, don't stop to fill out a form. Just speak.

SENTINEL is a real-time conversational safety agent. A worker reports a hazard by voice. SENTINEL investigates, evaluates risk, and responds — adapting its behavior as the situation evolves.

**LISTEN → INVESTIGATE → UNDERSTAND → ASSESS → ACT → VERIFY**

---

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- An [AssemblyAI API key](https://www.assemblyai.com/dashboard/api-keys)
- Chrome or Edge (Chromium-based browser)

---

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env and add your ASSEMBLYAI_API_KEY

# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend starts at `http://localhost:8000`.

On first startup, calling `GET /api/token` will:
1. Create the SENTINEL agent on AssemblyAI
2. Print the agent ID to the console
3. Return a session token to the browser

**Save the printed agent ID to `SENTINEL_AGENT_ID` in your `.env`** to reuse it across restarts.

---

### 2. Frontend

```bash
cd frontend

# Configure environment
copy .env.example .env.local
# (default: NEXT_PUBLIC_BACKEND_URL=http://localhost:8000)

# Install and run
npm install
npm run dev
```

The frontend starts at `http://localhost:3000`.

---

### 3. Test the Voice Agent

1. Open `http://localhost:3000` in **Chrome or Edge**
2. Click the **SPEAK** button
3. Allow microphone access when prompted
4. Say something like:

   > "Machine four is behaving strangely."

5. SENTINEL should respond with an investigative question (not a generic acknowledgement)
6. Continue the conversation — notice how SENTINEL adapts as you provide more information

---

## Architecture (Phase 1 Prototype)

```
Browser (Chrome/Edge)
  ├── WebSocket → wss://agents.assemblyai.com/v1/ws  (voice: mic + audio)
  └── HTTP      → http://localhost:8000/api/token     (token minting)

SENTINEL Backend (FastAPI)
  ├── GET /api/token   → mints AssemblyAI session token
  ├── GET /api/agent   → returns SENTINEL agent ID
  └── GET /health      → health check
```

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Required | Description |
|----------|----------|-------------|
| `ASSEMBLYAI_API_KEY` | ✅ | Your AssemblyAI API key |
| `SENTINEL_AGENT_ID` | After first run | Saved agent ID (auto-printed on first run) |
| `BACKEND_PORT` | No | Default: 8000 |
| `CORS_ORIGINS` | No | Default: http://localhost:3000 |

### Frontend (`frontend/.env.local`)
| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | No | Default: http://localhost:8000 |

---

## Project Structure

```
sentinel/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app entry point
│   │   ├── config.py            Settings (reads from .env)
│   │   ├── api/
│   │   │   └── voice.py         Token + agent endpoints
│   │   └── agents/
│   │       └── sentinel_agent.py  SENTINEL agent creation + system prompt
│   └── requirements.txt
│
└── frontend/
    ├── app/
    │   ├── worker/page.tsx      Worker voice interface
    │   ├── hooks/
    │   │   └── useVoiceAgent.ts  AssemblyAI WS + audio pipeline
    │   ├── components/
    │   │   ├── Waveform.tsx
    │   │   └── StatusBadge.tsx
    │   └── types/
    │       └── voice.ts         TypeScript types
    └── public/
        └── pcm-processor.js     AudioWorklet (mic capture + resampling)
```

---

## What This Prototype Demonstrates

- ✅ Full-duplex voice conversation via AssemblyAI Voice Agent API
- ✅ Real-time microphone capture (PCM16, 24kHz, cross-browser resampling)
- ✅ Agent audio playback with interruption support (barge-in)
- ✅ Live transcript streaming (`transcript.user.delta` + `transcript.agent.delta`)
- ✅ SENTINEL investigative system prompt (not a voice form)
- ✅ API key never exposed to browser (server-side token minting)

---

## Hackathon: AssemblyAI Voice Agent Hackathon 2026

Category: Conversational Safety Intelligence

> SENTINEL is not a voice reporting app.
> SENTINEL is a conversational safety intelligence system that investigates incidents in real time and adapts its response as risk evolves.
