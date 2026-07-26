from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from .audio_review import detect_first_vocal_entry, find_lyric_window


def extract_douyin_clip_lyrics(lyrics: str) -> tuple[str, str]:
    lines = lyrics.splitlines()
    chorus_index = next(
        (index for index, line in enumerate(lines) if line.strip().lower() == "[chorus]"),
        None,
    )
    section = "first_chorus"
    if chorus_index is None:
        chorus_index = next(
            (index for index, line in enumerate(lines) if line.strip().lower() == "[final chorus]"),
            None,
        )
        section = "final_chorus"
    if chorus_index is None:
        singable = [line.strip() for line in lines if line.strip() and not line.strip().startswith("[")]
        return "\n".join(singable[:8]).strip() + ("\n" if singable[:8] else ""), "first_lines_fallback"

    chorus_end = next(
        (index for index in range(chorus_index + 1, len(lines)) if lines[index].strip().startswith("[")),
        len(lines),
    )
    clip_lyrics = "\n".join(lines[chorus_index:chorus_end]).strip()
    return clip_lyrics + ("\n" if clip_lyrics else ""), section


def select_douyin_clip_selection(
    lyrics: str,
    first_vocal_second: float,
    duration_seconds: float,
    max_duration_seconds: float = 60.0,
) -> dict:
    """Estimate the first chorus from lyric structure without modifying the full-song master.

    This is only a first-pass cut point. Before delivering a short-video hook,
    validate the rendered clip by ASR segment timing or listening, then override
    clip_start_seconds/clip_duration_seconds when the estimate includes a
    pre-chorus lead-in or spills into the next verse.
    """
    lines = lyrics.splitlines()
    chorus_index = next(
        (index for index, line in enumerate(lines) if line.strip().lower() in {"[chorus]", "[final chorus]"}),
        None,
    )
    if chorus_index is None:
        return {
            "start_seconds": round(first_vocal_second, 2),
            "recommended_duration_seconds": min(45.0, max_duration_seconds),
            "selection_method": "first_vocal_fallback",
            "selection_reason": "No chorus section label was found in the lyrics.",
        }

    def singable_characters(items: list[str]) -> int:
        return sum(len(re.findall(r"[\u4e00-\u9fffA-Za-z]", line)) for line in items)

    total_characters = singable_characters(lines)
    pre_chorus_characters = singable_characters(lines[:chorus_index])
    if total_characters <= 0 or pre_chorus_characters <= 0:
        return {
            "start_seconds": round(first_vocal_second, 2),
            "recommended_duration_seconds": min(45.0, max_duration_seconds),
            "selection_method": "first_vocal_fallback",
            "selection_reason": "Lyrics did not contain enough singable text to estimate a chorus position.",
        }

    vocal_span = max(0.0, duration_seconds - first_vocal_second)
    estimated_start = first_vocal_second + vocal_span * pre_chorus_characters / total_characters
    chorus_end = next(
        (index for index in range(chorus_index + 1, len(lines)) if lines[index].strip().startswith("[")),
        len(lines),
    )
    chorus_characters = singable_characters(lines[chorus_index:chorus_end])
    estimated_chorus_seconds = vocal_span * chorus_characters / total_characters
    # Leave a small resolving tail after the hook, while keeping the clip concise.
    recommended_duration = max(
        min(25.0, max_duration_seconds),
        min(max_duration_seconds, estimated_chorus_seconds + 10.0),
    )
    return {
        "start_seconds": round(estimated_start, 2),
        "recommended_duration_seconds": round(recommended_duration, 2),
        "selection_method": "first_chorus_lyrics_estimate",
        "selection_reason": "Estimated the first chorus from the lyric section structure and vocal timeline.",
    }


def create_douyin_audio_variant(
    *,
    source_path: Path,
    output_path: Path,
    lyrics: str,
    clip_max_duration_seconds: float = 60.0,
    clip_duration_seconds: float | None = None,
    clip_start_seconds: float | None = None,
) -> dict:
    """Create a short-video audio asset while leaving the release master untouched."""
    if not source_path.exists():
        raise FileNotFoundError(f"Source audio not found: {source_path}")
    if clip_max_duration_seconds <= 0:
        raise ValueError("Douyin clip maximum duration must be greater than zero.")
    if clip_duration_seconds is not None and clip_duration_seconds <= 0:
        raise ValueError("Douyin clip duration must be greater than zero.")

    analysis = detect_first_vocal_entry(source_path)
    source_duration = float(analysis.get("audio_duration_seconds") or 0.0)
    first_vocal_second = analysis.get("first_vocal_second")
    if source_duration <= 0:
        raise RuntimeError(f"Could not determine source duration: {source_path}")
    if first_vocal_second is None:
        first_vocal_second = 0.0

    selection = select_douyin_clip_selection(
        lyrics,
        float(first_vocal_second),
        source_duration,
        clip_max_duration_seconds,
    )
    # Replace the proportional estimate with actual ASR timing when possible.
    chorus_text, _ = extract_douyin_clip_lyrics(lyrics)
    chorus_lines = [line.strip() for line in chorus_text.splitlines() if line.strip() and not line.strip().startswith("[")]
    if chorus_lines:
        window = find_lyric_window(source_path, chorus_lines[0])
        if window.get("found"):
            selection.update(
                {
                    "start_seconds": window["start_seconds"],
                    "recommended_duration_seconds": min(
                        clip_max_duration_seconds,
                        max(20.0, window["end_seconds"] - window["start_seconds"] + 0.5),
                    ),
                    "selection_method": "whisper_lyric_window",
                    "selection_reason": "Matched the first chorus lyric line to Whisper timestamps.",
                }
            )
        else:
            selection["selection_method"] = "needs_review_estimate"
            selection["selection_reason"] = "ASR could not match the chorus lyric line; proportional estimate requires review."
    if clip_start_seconds is None:
        requested_start = float(selection["start_seconds"])
    else:
        requested_start = float(clip_start_seconds)
        selection.update(
            {
                "start_seconds": round(requested_start, 2),
                "selection_method": "verified_manual_hook",
                "selection_reason": "Start time verified from the generated performance; duration adapts to the chorus structure.",
            }
        )
    selected_duration = clip_duration_seconds or float(selection["recommended_duration_seconds"])
    actual_duration = min(selected_duration, source_duration)
    start_seconds = max(0.0, min(requested_start, max(0.0, source_duration - actual_duration)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_path,
        "-y",
        "-ss",
        f"{start_seconds:.2f}",
        "-i",
        str(source_path),
        "-t",
        f"{actual_duration:.2f}",
        "-vn",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "256k",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Failed to create Douyin audio variant: {details}") from exc
    if not output_path.exists() or output_path.stat().st_size < 10_000:
        raise RuntimeError("Douyin audio variant was not created or is unexpectedly small.")

    return {
        "status": "ready",
        "source_path": str(source_path),
        "output_path": str(output_path),
        "start_seconds": round(start_seconds, 2),
        "duration_seconds": round(actual_duration, 2),
        "source_duration_seconds": round(source_duration, 2),
        "first_vocal_second": round(float(first_vocal_second), 2),
        **selection,
    }
