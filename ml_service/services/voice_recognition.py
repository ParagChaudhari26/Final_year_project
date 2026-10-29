import os
from typing import Optional


class VoiceRecognitionService:
    def __init__(self):
        self._model = None

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        if language not in {None, "auto", "en", "hi", "mr"}:
            raise ValueError("Language must be auto, en, hi, or mr.")

        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                os.getenv("WHISPER_MODEL", "small"),
                device=os.getenv("WHISPER_DEVICE", "cpu"),
                compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            )

        segments, info = self._model.transcribe(
            audio_path,
            language=None if language in {None, "auto"} else language,
            beam_size=3,
            vad_filter=True,
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        return {"text": transcript, "language": info.language}


voice_recognition = VoiceRecognitionService()