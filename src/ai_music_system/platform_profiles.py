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


AUDIO_PROFILE_CONSTRAINTS = {
    "short_video": {
        "max_intro_seconds": 3.0,
        "min_duration_seconds": 20.0,
        "max_duration_seconds": 120.0,
    },
    "hybrid": {
        "max_intro_seconds": 5.0,
        "min_duration_seconds": 30.0,
        "max_duration_seconds": 180.0,
    },
    "music_platform": {
        "max_intro_seconds": 15.0,
        "min_duration_seconds": 165.0,
        "max_duration_seconds": 240.0,
    },
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


def audio_constraints(distribution_target: str, publish_platform: str) -> dict[str, float]:
    target = infer_distribution_target(distribution_target, publish_platform)
    return dict(AUDIO_PROFILE_CONSTRAINTS[target])
