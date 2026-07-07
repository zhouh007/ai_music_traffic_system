from __future__ import annotations

from pathlib import Path

from .models import TopicRecord
from .platform_profiles import infer_distribution_target


PROMPT_FILE_MAP = {
    "short_video": "lyrics_prompt_short_video.txt",
    "hybrid": "lyrics_prompt_hybrid.txt",
    "music_platform": "lyrics_prompt_music_platform.txt",
}


def load_lyrics_prompt(project_root: Path, topic: TopicRecord) -> tuple[str, str]:
    target = normalize_distribution_target(topic.distribution_target, topic.publish_platform)
    prompt_path = project_root / "src" / "ai_music_system" / "prompts" / PROMPT_FILE_MAP[target]
    return prompt_path.read_text(encoding="utf-8"), target


def normalize_distribution_target(value: str, publish_platform: str = "") -> str:
    candidate = infer_distribution_target(value, publish_platform)
    if candidate in PROMPT_FILE_MAP:
        return candidate
    return "hybrid"
