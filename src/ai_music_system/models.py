from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class TopicRecord(BaseModel):
    topic_id: str
    batch_id: str
    topic: str
    audience: str
    mood: str
    scene: str
    style_hint: str
    publish_platform: str
    status: str = "pending"
    generation_mode: str = "text_to_music"
    reference_audio_url: str = ""
    distribution_target: str = "hybrid"


class SongRecord(BaseModel):
    song_id: str
    topic_id: str
    batch_id: str
    run_id: str = ""
    prompt_version: str = ""
    title: str
    mode: str
    status: str
    generated_at: str = ""
    song_dir: Path
    lyrics_raw_path: Path
    lyrics_clean_path: Path
    audio_path: Path
    cover_raw_path: Path
    cover_publish_path: Path
    cover_hd_path: Path
    meta_path: Path
    caption_path: Path
    review_path: Path
    error_message: str = ""


class ReviewRecord(BaseModel):
    song_id: str
    run_id: str = ""
    prompt_version: str = ""
    hook_score: int = Field(default=0, ge=0, le=5)
    vocal_score: int = Field(default=0, ge=0, le=5)
    cover_score: int = Field(default=0, ge=0, le=5)
    publishable: bool = False
    review_source: str = "system"
    score_evidence: dict = Field(default_factory=dict)
    notes: str = ""
    reviewed_at: str = ""


class PublishJobRecord(BaseModel):
    job_id: str
    song_id: str
    batch_id: str
    run_id: str = ""
    prompt_version: str = ""
    target_platform: str = ""
    review_source: str = ""
    platform: str
    platform_type: str = "video"
    status: str = "pending"
    package_dir: Path
    video_path: Path | None = None
    cover_path: Path
    audio_path: Path
    caption_path: Path
    lyrics_path: Path | None = None
    meta_path: Path | None = None
    publish_url: str
    title: str
    caption: str
    scheduled_at: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    external_post_id: str = ""
    automation_summary: dict = Field(default_factory=dict)
    status_history: list[dict] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if normalized.get("video_path") in {".", "", "null"}:
            normalized["video_path"] = None

        legacy_status_map = {
            "launched": "browser_opened",
            "automation_ran": "saved_for_review",
        }
        status = normalized.get("status")
        if status in legacy_status_map:
            normalized["status"] = legacy_status_map[status]
        return normalized


class AppConfig(BaseModel):
    root_dir: Path
    data_dir: Path
    songs_dir: Path
    exports_dir: Path
    topics_dir: Path
    queue_dir: Path
    publish_dir: Path
    cover_publish_size: int = 1440
    cover_hd_size: int = 3000
    music_platform_intro_max_seconds: float = 15.0
    music_platform_min_duration_seconds: float = 165.0
    music_platform_preferred_min_duration_seconds: float = 180.0
    music_platform_max_duration_seconds: float = 240.0
    music_platform_retry_target_vocal_seconds: float = 8.0
    music_platform_retry_target_duration_seconds: float = 180.0
    skip_existing_steps: bool = True
    target_platform: str = "douyin"
    prompt_version: str = "v1"
    lyrics_provider: "LyricsProviderConfig"
    music_provider: "MusicProviderConfig"
    image_provider: "ImageProviderConfig"


class PerformanceRecord(BaseModel):
    song_id: str
    platform: str
    captured_at: str
    window: str = "manual"
    external_post_id: str = ""
    views: int = Field(default=0, ge=0)
    complete_rate: float | None = Field(default=None, ge=0, le=1)
    likes: int = Field(default=0, ge=0)
    favorites: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    followers_gained: int = Field(default=0, ge=0)
    revenue: float = Field(default=0, ge=0)
    notes: str = ""


class ExperimentRecord(BaseModel):
    experiment_id: str
    name: str
    hypothesis: str
    variable: str
    control_prompt_version: str
    variant_prompt_version: str
    primary_metric: str
    minimum_sample_size: int = Field(default=5, ge=1)
    status: str = "draft"
    created_at: str
    song_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class ProviderBaseConfig(BaseModel):
    name: str
    api_key: str
    timeout_seconds: int = 120


class LyricsProviderConfig(ProviderBaseConfig):
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    temperature: float = 0.9


class MusicProviderConfig(ProviderBaseConfig):
    base_url: str = "https://api.minimaxi.com/v1"
    model: str = "music-2.6-free"
    cover_model: str = "music-cover-free"
    output_format: str = "hex"
    sample_rate: int = 44100
    bitrate: int = 256000
    audio_format: str = "mp3"


class ImageProviderConfig(ProviderBaseConfig):
    base_url: str = "https://apihub.agnes-ai.com/v1"
    model: str = "agnes-image-2.0-flash"
    size: str = "1024x1024"
    return_base64: bool = False
