from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

from .models import AppConfig, ImageProviderConfig, LyricsProviderConfig, MusicProviderConfig


def load_app_config(project_root: Path) -> AppConfig:
    _load_env_file(project_root / ".env")
    pipeline = _load_json_with_override(
        project_root / "config" / "pipeline.example.json",
        project_root / "config" / "pipeline.local.json",
    )
    providers = _load_json_with_override(
        project_root / "config" / "providers.example.json",
        project_root / "config" / "providers.local.json",
    )
    data_dir = project_root / "data"
    return AppConfig(
        root_dir=project_root,
        data_dir=data_dir,
        songs_dir=data_dir / "songs",
        exports_dir=data_dir / "exports",
        topics_dir=data_dir / "topics",
        queue_dir=data_dir / "queue",
        publish_dir=data_dir / "publish",
        cover_publish_size=pipeline.get("cover_publish_size", 1440),
        cover_hd_size=pipeline.get("cover_hd_size", 3000),
        music_platform_intro_max_seconds=pipeline.get("music_platform_intro_max_seconds", 15),
        music_platform_min_duration_seconds=pipeline.get("music_platform_min_duration_seconds", 165),
        music_platform_preferred_min_duration_seconds=pipeline.get("music_platform_preferred_min_duration_seconds", 180),
        music_platform_max_duration_seconds=pipeline.get("music_platform_max_duration_seconds", 240),
        music_platform_retry_target_vocal_seconds=pipeline.get("music_platform_retry_target_vocal_seconds", 8),
        music_platform_retry_target_duration_seconds=pipeline.get("music_platform_retry_target_duration_seconds", 180),
        douyin_clip_max_seconds=pipeline.get("douyin_clip_max_seconds", 60),
        skip_existing_steps=pipeline.get("skip_existing_steps", True),
        target_platform=pipeline.get("target_platform", pipeline.get("default_publish_platform", "douyin")),
        prompt_version=pipeline.get("prompt_version", "v1"),
        lyrics_provider=_build_lyrics_provider_config(providers["lyrics_provider"]),
        music_provider=_build_music_provider_config(providers["music_provider"]),
        image_provider=_build_image_provider_config(providers["image_provider"]),
    )


def _load_json_with_override(default_path: Path, local_path: Path) -> dict:
    payload = json.loads(default_path.read_text(encoding="utf-8"))
    if local_path.exists():
        local_payload = json.loads(local_path.read_text(encoding="utf-8"))
        payload = _deep_merge(payload, local_payload)
    return payload


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _build_lyrics_provider_config(payload: dict) -> LyricsProviderConfig:
    return LyricsProviderConfig(
        name=payload["name"],
        api_key=_resolve_api_key_from_payload(payload),
        base_url=payload.get("base_url", "https://api.deepseek.com"),
        model=payload.get("model", "deepseek-v4-flash"),
        temperature=payload.get("temperature", 0.9),
        timeout_seconds=payload.get("timeout_seconds", 120),
    )


def _build_music_provider_config(payload: dict) -> MusicProviderConfig:
    return MusicProviderConfig(
        name=payload["name"],
        api_key=_resolve_api_key_from_payload(payload),
        base_url=payload.get("base_url", "https://api.minimaxi.com/v1"),
        model=payload.get("model", "music-2.6-free"),
        cover_model=payload.get("cover_model", "music-cover-free"),
        output_format=payload.get("output_format", "hex"),
        sample_rate=payload.get("sample_rate", 44100),
        bitrate=payload.get("bitrate", 256000),
        audio_format=payload.get("audio_format", "mp3"),
        timeout_seconds=payload.get("timeout_seconds", 360),
    )


def _build_image_provider_config(payload: dict) -> ImageProviderConfig:
    return ImageProviderConfig(
        name=payload["name"],
        api_key=_resolve_api_key_from_payload(payload),
        base_url=payload.get("base_url", "https://www.codex2api.com"),
        api_proxy_url=payload.get("api_proxy_url", ""),
        use_api_proxy=payload.get("use_api_proxy", False),
        model=payload.get("model", "gpt-image-1.5"),
        size=payload.get("size", "1024x1024"),
        output_format=payload.get("output_format", "png"),
        quality=payload.get("quality", "auto"),
        moderation=payload.get("moderation", "auto"),
        return_base64=payload.get("return_base64", False),
        timeout_seconds=payload.get("timeout_seconds", 180),
    )


def _resolve_api_key_from_payload(payload: dict) -> str:
    direct_value = str(payload.get("api_key", "")).strip()
    if direct_value:
        return direct_value
    env_name = str(payload.get("api_key_env", "")).strip()
    if not env_name and payload.get("name") == "codex2api":
        return _resolve_codex_api_key()
    if not env_name:
        raise RuntimeError("Provider config requires either api_key or api_key_env.")
    value = os.getenv(env_name, "").strip()
    if value:
        return value
    if payload.get("name") == "codex2api":
        return _resolve_codex_api_key()
    return _resolve_api_key(env_name)


def _resolve_codex_api_key() -> str:
    config_path = Path(os.getenv("CODEX_CONFIG_PATH", str(Path.home() / ".codex" / "config.toml")))
    if not config_path.exists():
        raise RuntimeError(f"Codex config not found: {config_path}")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    provider_name = config.get("model_provider", "custom")
    provider = config.get("model_providers", {}).get(provider_name, {})
    token = str(provider.get("experimental_bearer_token") or provider.get("api_key") or "").strip()
    if not token:
        raise RuntimeError(f"Codex provider has no bearer token: {provider_name}")
    return token


def _resolve_api_key(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required API key environment variable: {env_name}")
    return value


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_name = key.strip()
        env_value = value.strip()
        if not env_name:
            continue
        if len(env_value) >= 2 and env_value[0] == env_value[-1] and env_value[0] in {"'", '"'}:
            env_value = env_value[1:-1]
        os.environ.setdefault(env_name, env_value)
