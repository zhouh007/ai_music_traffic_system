from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    return WhisperModel("tiny", device="cpu", compute_type="int8")


def detect_first_vocal_entry(audio_path: Path, language: str = "zh") -> dict:
    model = _load_model()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        beam_size=1,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    first_word_seconds = None
    transcript_preview: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            transcript_preview.append(text)
        if segment.words:
            for word in segment.words:
                token = (word.word or "").strip()
                if not token:
                    continue
                first_word_seconds = round(float(word.start), 2)
                break
        if first_word_seconds is not None:
            break
    return {
        "analyzer": "faster_whisper_tiny",
        "language": getattr(info, "language", language),
        "audio_duration_seconds": round(float(getattr(info, "duration", 0.0) or 0.0), 2),
        "first_vocal_second": first_word_seconds,
        "transcript_preview": transcript_preview[:3],
    }
