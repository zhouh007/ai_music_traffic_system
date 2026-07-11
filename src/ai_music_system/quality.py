from __future__ import annotations

import json

from PIL import Image

from .models import SongRecord, TopicRecord
from .platform_profiles import is_music_platform_target


def evaluate_quality(song: SongRecord, topic: TopicRecord) -> dict:
    lyrics = song.lyrics_clean_path.read_text(encoding="utf-8") if song.lyrics_clean_path.exists() else ""
    validation_path = song.song_dir / "audio_validation.json"
    quality = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    duration = _number(quality.get("duration_seconds"))
    first_vocal = _number(quality.get("first_vocal_second"))
    audio_size = song.audio_path.stat().st_size if song.audio_path.exists() else 0
    cover_size = song.cover_publish_path.stat().st_size if song.cover_publish_path.exists() else 0
    dimensions = _cover_dimensions(song)
    music_target = is_music_platform_target(topic.distribution_target, topic.publish_platform)
    gates = {
        "lyrics_present": bool(lyrics.strip()),
        "audio_present": audio_size > 10_000,
        "cover_present": cover_size > 1_000,
        "cover_dimensions_valid": dimensions == (1440, 1440),
        "music_duration_valid": not music_target or duration is not None and 165 <= duration <= 240,
        "music_vocal_entry_valid": not music_target or first_vocal is not None and first_vocal <= 15,
        "title_text_valid": bool(song.title.strip()) and "�" not in song.title,
    }
    length = len(lyrics)
    structure = 5 if (180 <= length <= 900 if music_target else 80 <= length <= 800) else 2 if lyrics else 0
    hook_score = min(5, structure + (1 if "[chorus]" in lyrics.lower() or "副歌" in lyrics else 0))
    vocal_score = 5 if gates["audio_present"] and gates["music_vocal_entry_valid"] else 0
    cover_score = 5 if gates["cover_present"] and gates["cover_dimensions_valid"] else 0
    return {
        "hard_gate_passed": all(gates.values()),
        "gates": gates,
        "failed_gates": [key for key, value in gates.items() if not value],
        "hook_score": hook_score,
        "vocal_score": vocal_score,
        "cover_score": cover_score,
        "total_score": hook_score + vocal_score + cover_score,
        "notes": "Hard gates: " + ("passed" if all(gates.values()) else ", ".join(key for key, value in gates.items() if not value)),
        "evidence": {"lyrics_length": length, "audio_bytes": audio_size, "cover_bytes": cover_size, "cover_dimensions": dimensions, "duration_seconds": duration, "first_vocal_second": first_vocal, "music_platform_target": music_target, "gates": gates},
    }


def _cover_dimensions(song: SongRecord) -> tuple[int, int] | None:
    if not song.cover_publish_path.exists():
        return None
    try:
        with Image.open(song.cover_publish_path) as image:
            return image.size
    except OSError:
        return None


def _number(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
