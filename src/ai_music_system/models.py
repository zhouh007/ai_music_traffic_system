from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


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


class SongRecord(BaseModel):
    song_id: str
    topic_id: str
    batch_id: str
    title: str
    mode: str
    status: str
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
    hook_score: int = Field(default=0, ge=0, le=5)
    vocal_score: int = Field(default=0, ge=0, le=5)
    cover_score: int = Field(default=0, ge=0, le=5)
    publishable: bool = False
    notes: str = ""
    reviewed_at: str = ""


class PublishJobRecord(BaseModel):
    job_id: str
    song_id: str
    batch_id: str
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
    notes: str = ""


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
    skip_existing_steps: bool = True
    lyrics_provider: "LyricsProviderConfig"
    music_provider: "MusicProviderConfig"
    image_provider: "ImageProviderConfig"


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
