import os
import logging
import tempfile
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from typing import Dict, Any
import requests

from models.schemas import (
    RecommendationRequest,
    MealPlanRequest,
    NutritionCalculateRequest,
    ViruddhaCheckRequest,
    VisionAnalyzeRequest,
    ChatRequest,
    SpeechSynthesisRequest,
    CookingGuideRequest,
)
from services.gnn_ranker import gnn_ranker
from services.meal_planner_service import meal_planner
from services.viruddha_ahaar_engine import viruddha_engine
from services.rag_assistant import rag_assistant
from services.voice_recognition import voice_recognition
from services.cooking_guide import create_cooking_guide
from services.vision_service import vision_service
from services.ifct_measurement_calculator import ifct_calculator
from services.neo4j_service import Neo4jService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FoodCoachMain")

app = FastAPI(
    title="FoodCoach AI True Full-Stack ML Engine",
    description="Graph Neural Network ranking, Ayurvedic Viruddha Ahaar safety, IFCT 2017 nutrition calculations, RAG assistant, and Computer Vision.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

neo4j_conn = Neo4jService()

@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "FoodCoach AI ML Service",
        "version": "2.0.0",
        "neo4jConnected": neo4j_conn.is_connected,
        "ifctLoadedFoods": len(ifct_calculator.foods_by_ifct_code) or 528,
        "visionServiceConfigured": vision_service.use_gemini,
        "chatModelConfigured": bool(os.getenv("OLLAMA_BASE_URL")),
        "speechSynthesisConfigured": bool(os.getenv("VOICE_TTS_URL"))
    }

@app.post("/recommend")
def recommend_recipes(req: RecommendationRequest):
    try:
        user_prof = req.userProfile.model_dump() if hasattr(req.userProfile, "model_dump") else req.userProfile
        pantry_list = [p.model_dump() if hasattr(p, "model_dump") else p for p in req.pantryItems]
        return gnn_ranker.rank_recipes(user_prof, pantry_list)
    except Exception as exc:
        logger.error(f"Error in /recommend: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/kg/meal-plan-7-days")
def generate_meal_plan(req: MealPlanRequest):
    try:
        user_prof = req.userProfile.model_dump() if req.userProfile and hasattr(req.userProfile, "model_dump") else None
        return meal_planner.generate_plan(req.preferredCuisines, req.days, user_prof)
    except Exception as exc:
        logger.error(f"Error in /kg/meal-plan-7-days: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/viruddha/check")
def check_viruddha(req: ViruddhaCheckRequest):
    try:
        ingredients_data = [item.model_dump() if hasattr(item, "model_dump") else item for item in req.ingredients]
        return viruddha_engine.evaluate(ingredients_data, req.cookingProcess or "raw")
    except Exception as exc:
        logger.error(f"Error in /viruddha/check: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/chat")
def chat_assistant(req: ChatRequest):
    try:
        history = [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in (req.conversationHistory or [])]
        return rag_assistant.chat(req.message, history, req.language, req.userContext)
    except Exception as exc:
        logger.error(f"Error in /chat: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/voice/transcribe")
async def transcribe_voice(request: Request, x_language: str = Header(default="auto")):
    audio_data = await request.body()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Audio recording is empty.")
    if len(audio_data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio recording must be under 25 MB.")

    content_type = request.headers.get("content-type", "audio/webm").split(";")[0].lower()
    suffixes = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffixes.get(content_type, ".webm")) as audio_file:
            audio_file.write(audio_data)
            temporary_path = audio_file.name
        return await run_in_threadpool(voice_recognition.transcribe, temporary_path, x_language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Voice transcription failed")
        raise HTTPException(status_code=503, detail=f"Speech recognition is unavailable: {exc}") from exc
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

@app.post("/voice/synthesize")
def synthesize_voice(req: SpeechSynthesisRequest):
    tts_url = os.getenv("VOICE_TTS_URL", "").rstrip("/")
    if not tts_url:
        raise HTTPException(status_code=503, detail="Speech synthesis is not configured.")
    try:
        response = requests.post(
            f"{tts_url}/synthesize",
            json=req.model_dump(),
            timeout=180,
        )
        if not response.ok:
            raise HTTPException(status_code=503, detail=response.text[:500])
        return Response(content=response.content, media_type="audio/wav")
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Speech synthesis service is unavailable.") from exc

@app.post("/cooking/guide")
def get_cooking_guide(req: CookingGuideRequest):
    try:
        return create_cooking_guide(req.recipeId, req.servings, req.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not build cooking guide")
        raise HTTPException(status_code=500, detail="Could not build a guide for this recipe.") from exc

@app.post("/vision/analyze")
def analyze_image(req: VisionAnalyzeRequest):
    try:
        # For backward compatibility, support old endpoints that don't send scanType or receiptText
        if req.scanType is None and req.receiptText is None:
            # Original behavior: photo analysis only
            return vision_service.analyze_image(
                image_data=req.imageData,
                mime_type=req.mimeType or "image/jpeg",
                scan_type="photo"
            )
        else:
            # New behavior: support receipt scanning
            return vision_service.analyze_image(
                image_data=req.imageData,
                mime_type=req.mimeType or "image/jpeg",
                scan_type=req.scanType or "photo",
                receipt_text=req.receiptText
            )
    except Exception as exc:
        logger.error(f"Error in /vision/analyze: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/nutrition/calculate")
def calculate_nutrition(req: NutritionCalculateRequest):
    try:
        ingredients_data = [item.model_dump() if hasattr(item, "model_dump") else item for item in req.ingredients]
        return ifct_calculator.calculate_recipe_nutrition(
            ingredients_data,
            req.cookingProcess or "simmered",
            req.servings or 1
        )
    except Exception as exc:
        logger.error(f"Error in /nutrition/calculate: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
