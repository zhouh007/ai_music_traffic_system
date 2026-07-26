from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import subprocess

from imageio_ffmpeg import get_ffmpeg_exe

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


def find_lyric_window(audio_path: Path, lyric_text: str, language: str = "zh") -> dict:
    """Find the first ASR segment matching a lyric line and its next segments."""
    target = "".join(char for char in lyric_text if char.isalnum())
    if len(target) < 4:
        return {"found": False, "reason": "lyric line too short"}
    model = _load_model()
    segments, _ = model.transcribe(str(audio_path), language=language, vad_filter=True, beam_size=1, condition_on_previous_text=False)
    items = list(segments)
    for index, segment in enumerate(items):
        text = "".join(char for char in segment.text if char.isalnum())
        if len(text) < 4 or not (target[:4] in text or text[:4] in target):
            continue
        end_index = min(len(items) - 1, index + 7)
        return {"found": True, "start_seconds": round(float(segment.start), 2), "end_seconds": round(float(items[end_index].end), 2), "matched_text": segment.text.strip()}
    return {"found": False, "reason": "no matching ASR segment"}


def measure_audio_signal(audio_path: Path) -> dict:
    """Read inexpensive FFmpeg loudness/peak metrics for release diagnostics."""
    try:
        result = subprocess.run(
            [get_ffmpeg_exe(), "-hide_banner", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stderr
        mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", output)
        max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", output)
        clipped_match = re.search(r"(\d+) clipped samples", output)
        mean_db = float(mean_match.group(1)) if mean_match else None
        max_db = float(max_match.group(1)) if max_match else None
        clipped_samples = int(clipped_match.group(1)) if clipped_match else 0
        return {
            "analyzer": "ffmpeg_volumedetect",
            "available": mean_db is not None or max_db is not None,
            "mean_volume_db": mean_db,
            "max_volume_db": max_db,
            "clipped_samples": clipped_samples,
            "signal_quality_valid": bool(max_db is None or max_db < 0.0) and clipped_samples == 0,
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"analyzer": "ffmpeg_volumedetect", "available": False, "signal_quality_valid": True}
