import io
import os
from threading import Lock

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from transformers import AutoTokenizer
from parler_tts import ParlerTTSForConditionalGeneration

MODEL_ID = "ai4bharat/indic-parler-tts"
VOICE_DESCRIPTIONS = {
    "en": "Mary speaks in clear Indian English at a moderate pace, with a friendly conversational tone.",
    "hi": "Divya speaks Hindi clearly at a moderate pace, with a friendly conversational tone.",
    "mr": "Sunita speaks Marathi clearly at a moderate pace, with a friendly conversational tone.",
}

app = FastAPI(title="FoodCoach Indic Speech Service")
model = None
tokenizer = None
description_tokenizer = None
model_lock = Lock()


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(pattern="^(en|hi|mr)$")


def load_model():
    global model, tokenizer, description_tokenizer
    if model is not None:
        return
    with model_lock:
        if model is not None:
            return
        from huggingface_hub import get_token

        token = os.getenv("HF_TOKEN") or get_token()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        loaded_model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL_ID, token=token).to(device)
        loaded_tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=token)
        loaded_description_tokenizer = AutoTokenizer.from_pretrained(
            loaded_model.config.text_encoder._name_or_path,
            token=token,
        )
        model = loaded_model
        tokenizer = loaded_tokenizer
        description_tokenizer = loaded_description_tokenizer


@app.get("/health")
def health():
    return {"status": "healthy", "modelLoaded": model is not None}


@app.post("/synthesize")
def synthesize(request: SynthesisRequest):
    try:
        load_model()
        device = next(model.parameters()).device
        description = VOICE_DESCRIPTIONS[request.language]
        prompt_inputs = tokenizer(request.text, return_tensors="pt").to(device)
        description_inputs = description_tokenizer(description, return_tensors="pt").to(device)
        with torch.inference_mode():
            audio = model.generate(
                input_ids=description_inputs.input_ids,
                attention_mask=description_inputs.attention_mask,
                prompt_input_ids=prompt_inputs.input_ids,
                prompt_attention_mask=prompt_inputs.attention_mask,
            )
        audio_data = audio.detach().cpu().numpy().squeeze()
        output = io.BytesIO()
        sf.write(output, audio_data, model.config.sampling_rate, format="WAV")
        return Response(content=output.getvalue(), media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Speech synthesis is unavailable. Check Hugging Face model access and service logs: {exc}",
        ) from exc