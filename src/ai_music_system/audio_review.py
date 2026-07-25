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
    soft_vocal_candidate = None
    transcript_preview: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        no_speech_probability = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
        average_log_probability = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
        reliable_segment = bool(text) and no_speech_probability <= 0.65 and average_log_probability >= -1.5
        if text and len(transcript_preview) < 3:
            transcript_preview.append(text)
        # Singing can be transcribed clearly while Whisper still assigns a high
        # no-speech score. Keep an early textual candidate for that case.
        if (
            text
            and soft_vocal_candidate is None
            and len("".join(text.split())) >= 4
            and no_speech_probability <= 0.8
            and average_log_probability >= -1.0
        ):
            soft_vocal_candidate = (segment, no_speech_probability, average_log_probability)
        if not reliable_segment:
            continue
        selected_segment, selected_no_speech, selected_avg_logprob = soft_vocal_candidate or (
            segment,
            no_speech_probability,
            average_log_probability,
        )
        first_segment_seconds = round(float(selected_segment.start), 2)
        first_vocal_confidence = {
            "no_speech_prob": round(selected_no_speech, 4),
            "avg_logprob": round(selected_avg_logprob, 4),
        }
        if selected_segment.words:
            for word in selected_segment.words:
                token = (word.word or "").strip()
                if not token:
                    continue
                first_word_seconds = round(float(word.start), 2)
                break
        break
    if first_segment_seconds is None and soft_vocal_candidate is not None:
        selected_segment, selected_no_speech, selected_avg_logprob = soft_vocal_candidate
        first_segment_seconds = round(float(selected_segment.start), 2)
        first_vocal_confidence = {
            "no_speech_prob": round(selected_no_speech, 4),
            "avg_logprob": round(selected_avg_logprob, 4),
        }
        if selected_segment.words:
            for word in selected_segment.words:
                token = (word.word or "").strip()
                if token:
                    first_word_seconds = round(float(word.start), 2)
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
