# FoodCoach AI - True Full-Stack v3
**Complete Architecture: React (Vite) + Node.js (Express) + Python (FastAPI) + Neo4j + MongoDB**

## Features:
- **Frontend**: React UI with Pantry Scanning, Viruddha Aahara Sandbox, KG Recommendations, multilingual voice chat, and step-by-step guided cooking.
- **Node.js Gateway**: Handles profiles, pantry state, gamification, and proxies ML requests.
- **Python ML Service**: 
  - `ifct_measurement_calculator.py` (Full IFCT 2017 math engine)
  - `viruddha_ahaar_engine.py` (Ayurvedic rule engine)
  - `gnn_ranker.py` (Constraint + Expiry + GNN ranking)
  - `meal_planner_service.py` (7-day multi-cuisine fusion planner)
  - `vision_service.py`, multilingual `rag_assistant.py`, and Whisper speech recognition
- **Local language model**: Ollama with Qwen3 for conversational English, Hindi, and Marathi responses.
- **Optional speech output**: Indic Parler-TTS for English, Hindi, and Marathi.
- **Guided cooking**: Recipe-specific steps, step timers, read-aloud, pantry availability, and confirmed ingredient deduction.
- **Accounts and profiles**: MongoDB-backed registration/login, JWT sessions, protected user data, and editable ML recommendation preferences.
- **Databases**: Neo4j (Graph data, historical recipes, IFCT) & MongoDB (User states).

## How to Run:
```bash
docker compose up --build -d
```
- **Frontend**: http://localhost:5173
- **Node API**: http://localhost:5000
- **Python API**: http://localhost:8000/docs
- **Neo4j**: http://localhost:7474

## Authentication and Profile Setup
Create a local environment file from the template before starting the services:

```powershell
Copy-Item .env.example .env
```

Set unique `JWT_ACCESS_SECRET` and `JWT_REFRESH_SECRET` values in `.env` before exposing the app outside your machine. Never copy secrets from `Smart_Kitchen_AI/.env` into source control.

Open the frontend and register an account. Sign in with that account on later visits. The old seeded demo users have no passwords and are not login accounts. After registration, open **My Profile** and set diet type, allergies, health conditions, cuisine preferences, macro targets, and Ayurvedic constraints. The recommendation API reads this saved profile; each account's pantry is isolated by its authenticated user ID.

## Chat Model Setup
The first start builds the services but does not automatically download the Qwen model. In PowerShell, pull it once:

```powershell
docker compose exec ollama ollama pull qwen3:4b
```

The model download is about 2.5 GB. The first chat response may take longer while the model loads. Ollama is bound to localhost and is only used internally by the ML service.

## Voice Chat Setup
Speech recognition uses faster-whisper and downloads the configured Whisper model (`small` by default) on the first recording. Select Auto, English, Hindi, or Marathi in the chat language menu; Auto lets Whisper detect the spoken language.

For spoken replies, first accept the model terms on the [Indic Parler-TTS model page](https://huggingface.co/ai4bharat/indic-parler-tts) and create a Hugging Face read token. Then set the token in PowerShell and start the optional TTS service:

```powershell
$env:HF_TOKEN = "YOUR_HUGGING_FACE_READ_TOKEN"
docker compose --profile voice up --build -d voice_tts
```

Do not commit the token. The TTS model downloads on the first playback request and is cached in the `tts_model_cache` volume. Without the voice profile, text chat and speech recognition still work; playback uses an available browser voice or reports that no voice is available.

## Guided Cooking and Pantry Usage
Choose **Start guided cooking** on a recommendation to load recipe steps, serving-scaled ingredient quantities, and the current pantry allocation. Each step can be read aloud and timed. Missing quantities are shown but are not taken from pantry stock.

Pantry stock is unchanged while a guide is open. On the final step, check **I finished cooking this recipe** and choose **Finish and update pantry**. The gateway rechecks stock, deducts only quantities allocated to pantry items, removes items that reach zero, and awards cooking points once. If stock changed during cooking, completion is rejected so the user can refresh the pantry and recommendations before retrying.
