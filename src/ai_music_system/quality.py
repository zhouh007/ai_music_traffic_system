from __future__ import annotations

import json

from PIL import Image

from .models import SongRecord, TopicRecord
from .platform_profiles import audio_constraints, is_music_platform_target


def evaluate_quality(song: SongRecord, topic: TopicRecord) -> dict:
    lyrics = song.lyrics_clean_path.read_text(encoding="utf-8") if song.lyrics_clean_path.exists() else ""
    validation_path = song.song_dir / "audio_validation.json"
    audio_validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    duration = _number(audio_validation.get("duration_seconds"))
    first_vocal = _number(audio_validation.get("first_vocal_second"))
    audio_size = song.audio_path.stat().st_size if song.audio_path.exists() else 0
    cover_size = song.cover_publish_path.stat().st_size if song.cover_publish_path.exists() else 0
    dimensions = _cover_dimensions(song)
    music_target = is_music_platform_target(topic.distribution_target, topic.publish_platform)
    constraints = audio_constraints(topic.distribution_target, topic.publish_platform)

    technical = {
        "lyrics_present": bool(lyrics.strip()),
        "text_integrity_valid": all(_text_is_readable(value) for value in (lyrics, song.title, topic.topic, topic.audience, topic.scene)),
        "audio_present": audio_size > 10_000,
        "cover_present": cover_size > 1_000,
        "cover_dimensions_valid": dimensions == (1440, 1440),
        "audio_duration_valid": duration is not None and constraints["min_duration_seconds"] <= duration <= constraints["max_duration_seconds"],
        "vocal_entry_valid": first_vocal is not None and first_vocal <= constraints["max_intro_seconds"],
        "title_text_valid": bool(song.title.strip()) and _text_is_readable(song.title),
    }
    brief_values = (topic.user_need, topic.core_conflict, topic.unique_observation, topic.emotional_payoff, topic.visual_scene)
    content = {
        "creative_brief_complete": sum(bool(value.strip()) for value in brief_values) >= 4,
        "structure_present": _has_song_structure(lyrics, music_target, topic.creative_mode),
        "concrete_imagery_present": _count_concrete_signals(lyrics) >= 2,
        "abstract_language_controlled": _abstract_word_ratio(lyrics) <= 0.18,
        "repeatable_hook_present": _has_repeatable_hook(lyrics),
    }
    context = {
        "distribution_target_valid": topic.distribution_target in {"short_video", "hybrid", "music_platform"},
        "usage_scene_present": bool((topic.visual_scene or topic.scene).strip()),
        "audience_present": bool(topic.audience.strip()),
    }
    technical_passed = all(technical.values())
    content_passed = all(content.values())
    context_passed = all(context.values())
    all_checks = {**technical, **content, **context}
    length = len(lyrics)
    hook_score = min(5, 2 + int(content["repeatable_hook_present"]) + int(content["concrete_imagery_present"]) + int(content["abstract_language_controlled"])) if lyrics else 0
    return {
        "hard_gate_passed": technical_passed and content_passed and context_passed,
        "gates": technical,
        "quality_layers": {
            "technical": {"passed": technical_passed, "checks": technical},
            "content": {"passed": content_passed, "checks": content},
            "context": {"passed": context_passed, "checks": context},
        },
        "failed_gates": [key for key, value in all_checks.items() if not value],
        "hook_score": hook_score,
        "vocal_score": 5 if technical["audio_present"] and technical["vocal_entry_valid"] else 0,
        "cover_score": 5 if technical["cover_present"] and technical["cover_dimensions_valid"] else 0,
        "total_score": hook_score + (5 if technical["audio_present"] and technical["vocal_entry_valid"] else 0) + (5 if technical["cover_present"] and technical["cover_dimensions_valid"] else 0),
        "notes": "Quality layers: " + ("passed" if technical_passed and content_passed and context_passed else "review required"),
        "evidence": {"lyrics_length": length, "audio_bytes": audio_size, "cover_bytes": cover_size, "cover_dimensions": dimensions, "duration_seconds": duration, "first_vocal_second": first_vocal, "music_platform_target": music_target, "gates": all_checks},
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


def _text_is_readable(value: str) -> bool:
    text = value or ""
    markers = ("\ufffd", "??", "闆", "鏅", "绐", "鍒", "鐨", "淇", "璇", "鎴", "杞", "€", "?鎴", "閿熸", "枻鎷")
    if any(marker in text for marker in markers):
        return False
    # Common UTF-8 decoded as GBK fragments often contain these paired forms.
    mojibake_pairs = ("鍚", "浼", "姣", "鐢", "妫", "懑", "绔", "搴", "闂", "笂")
    return not any(text.count(pair) >= 2 for pair in mojibake_pairs)


def _has_song_structure(lyrics: str, music_target: bool, creative_mode: str = "auto") -> bool:
    lowered = lyrics.lower()
    if not music_target:
        return "[chorus]" in lowered and "[verse" in lowered and len(lyrics) >= 100
    has_hook = "[chorus]" in lowered or "[hook]" in lowered or "[refrain]" in lowered
    if len(lyrics) < 280 or not has_hook:
        return False
    mode = (creative_mode or "auto").strip().lower()
    if mode in {"mood", "healing_gentle"}:
        # Atmosphere songs can use repeating sections and instrumental lifts;
        # a narrative bridge is optional.
        return "[verse" in lowered or "[pre-chorus]" in lowered or "[section" in lowered or "[outro]" in lowered
    if mode == "playful_hook":
        return "[verse" in lowered or "[post-chorus]" in lowered or "[outro]" in lowered
    if mode == "slice_of_life":
        return "[verse" in lowered or "[section" in lowered or "[outro]" in lowered
    if mode == "anthemic":
        return "[final chorus]" in lowered or "[outro]" in lowered
    # Narrative mode keeps the traditional bridge expectation; auto remains
    # backward-compatible for legacy topics that have no explicit mode.
    return "[bridge]" in lowered and "[verse" in lowered


def _count_concrete_signals(lyrics: str) -> int:
    signals = ("\u7a97", "\u8def\u706f", "\u8f66\u7ad9", "\u96e8", "\u98ce", "\u95e8", "\u624b\u673a", "\u6d88\u606f", "\u697c\u9053", "\u676f", "\u5f71\u5b50", "\u978b")
    return sum(1 for signal in signals if signal in lyrics)


def _abstract_word_ratio(lyrics: str) -> float:
    words = ("\u5b64\u72ec", "\u9057\u61be", "\u6210\u957f", "\u6cbb\u6108", "\u60f3\u5ff5", "\u52c7\u6562", "\u68a6\u60f3", "\u5fc3\u788e", "\u81ea\u7531")
    return sum(lyrics.count(word) for word in words) / max(len(lyrics), 1)


def _has_repeatable_hook(lyrics: str) -> bool:
    chorus = _extract_chorus(lyrics)
    lines = [line.strip() for line in chorus.splitlines() if line.strip()]
    return any(2 <= len(line) <= 24 and lines.count(line) >= 2 for line in lines)


def _extract_chorus(lyrics: str) -> str:
    marker = "[chorus]"
    lowered = lyrics.lower()
    start = lowered.find(marker)
    if start < 0:
        return ""
    end = lowered.find("[", start + len(marker))
    return lyrics[start + len(marker):end if end >= 0 else None]
