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
    first_segment_seconds = None
    first_vocal_confidence = None
    transcript_preview: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        no_speech_probability = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
        average_log_probability = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
        reliable_segment = bool(text) and no_speech_probability <= 0.65 and average_log_probability >= -1.5
        if text and len(transcript_preview) < 3:
            transcript_preview.append(text)
        if not reliable_segment:
            continue
        first_segment_seconds = round(float(segment.start), 2)
        first_vocal_confidence = {
            "no_speech_prob": round(no_speech_probability, 4),
            "avg_logprob": round(average_log_probability, 4),
        }
        if segment.words:
            for word in segment.words:
                token = (word.word or "").strip()
                if not token:
                    continue
                first_word_seconds = round(float(word.start), 2)
                break
        break
    return {
        "analyzer": "faster_whisper_tiny",
        "language": getattr(info, "language", language),
        "audio_duration_seconds": round(float(getattr(info, "duration", 0.0) or 0.0), 2),
        "first_vocal_second": first_segment_seconds,
        "first_word_second": first_word_seconds,
        "first_vocal_confidence": first_vocal_confidence,
        "transcript_preview": transcript_preview[:3],
    }
