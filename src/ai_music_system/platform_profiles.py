from __future__ import annotations


SHORT_VIDEO_PLATFORMS = {
    "douyin",
    "kuaishou",
    "xiaohongshu",
    "bilibili",
}

MUSIC_PLATFORMS = {
    "fanqie_music",
    "qishui_music",
}


def infer_distribution_target(distribution_target: str, publish_platform: str) -> str:
    candidate = (distribution_target or "").strip().lower()
    if candidate in {"short_video", "hybrid", "music_platform"}:
        return candidate

    platform = (publish_platform or "").strip().lower()
    if platform in MUSIC_PLATFORMS:
        return "music_platform"
    if platform in SHORT_VIDEO_PLATFORMS:
        return "short_video"
    return "hybrid"


def is_music_platform_target(distribution_target: str, publish_platform: str) -> bool:
    return infer_distribution_target(distribution_target, publish_platform) == "music_platform"
