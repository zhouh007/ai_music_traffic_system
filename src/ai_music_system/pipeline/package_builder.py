from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from ..models import AppConfig, ReviewRecord, SongRecord, TopicRecord


def build_song_metadata(song: SongRecord, topic: TopicRecord, config: AppConfig) -> dict:
    music_release_profile = ""
    if topic.distribution_target == "music_platform":
        music_release_profile = "full_song_emotion_release"
    return {
        "run_id": song.run_id,
        "song_id": song.song_id,
        "topic_id": song.topic_id,
        "batch_id": song.batch_id,
        "prompt_version": song.prompt_version or config.prompt_version,
        "target_platform": config.target_platform,
        "title": song.title,
        "topic": topic.topic,
        "audience": topic.audience,
        "mood": topic.mood,
        "scene": topic.scene,
        "style_hint": topic.style_hint,
        "publish_platform": topic.publish_platform,
        "distribution_target": topic.distribution_target,
        "music_release_profile": music_release_profile,
        "mode": song.mode,
        "status": song.status,
        "generated_at": song.generated_at,
        "provider_lyrics": {
            "name": config.lyrics_provider.name,
            "model": config.lyrics_provider.model,
            "base_url": config.lyrics_provider.base_url,
        },
        "provider_music": {
            "name": config.music_provider.name,
            "model": config.music_provider.model,
            "cover_model": config.music_provider.cover_model,
            "base_url": config.music_provider.base_url,
        },
        "provider_image": {
            "name": config.image_provider.name,
            "model": config.image_provider.model,
            "base_url": config.image_provider.base_url,
        },
        "paths": {
            "song_dir": str(song.song_dir),
            "lyrics_raw_path": str(song.lyrics_raw_path),
            "lyrics_clean_path": str(song.lyrics_clean_path),
            "audio_path": str(song.audio_path),
            "cover_raw_path": str(song.cover_raw_path),
            "cover_publish_path": str(song.cover_publish_path),
            "cover_hd_path": str(song.cover_hd_path),
            "caption_path": str(song.caption_path),
            "review_path": str(song.review_path),
        },
    }


def build_caption(song: SongRecord, topic: TopicRecord) -> str:
    return (
        f"{topic.topic}，是不是也像你心里那句一直没说出口的话。\n"
        f"《{song.title}》\n"
        "#AI音乐 #情绪歌曲 #短视频BGM"
    )


def export_approved_song(song: SongRecord, review: ReviewRecord, export_root: Path) -> Path:
    target_dir = export_root / song.song_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for path in [
        song.audio_path,
        song.lyrics_clean_path,
        song.cover_publish_path,
        song.cover_hd_path,
        song.meta_path,
        song.caption_path,
        song.review_path,
    ]:
        if path.exists():
            shutil.copy2(path, target_dir / path.name)

    (target_dir / "review_summary.json").write_text(
        review.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return target_dir


def write_export_manifest(export_root: Path, entries: list[dict]) -> tuple[Path, Path]:
    manifest_json = export_root / "publish_manifest.json"
    manifest_csv = export_root / "publish_manifest.csv"
    manifest_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    fieldnames = [
        "run_id",
        "song_id",
        "title",
        "batch_id",
        "prompt_version",
        "target_platform",
        "review_source",
        "publishable",
        "hook_score",
        "vocal_score",
        "cover_score",
        "notes",
        "audio_path",
        "cover_path",
        "caption_path",
    ]
    with manifest_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({name: entry.get(name, "") for name in fieldnames})
    return manifest_json, manifest_csv


def write_export_summary(export_root: Path, summary: dict) -> Path:
    summary_path = export_root / "export_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def build_publish_manifest_entry(song: SongRecord, review: ReviewRecord, exported_dir: Path) -> dict:
    target_platform = ""
    if song.meta_path.exists():
        target_platform = json.loads(song.meta_path.read_text(encoding="utf-8")).get("target_platform", "")
    return {
        "run_id": song.run_id,
        "song_id": song.song_id,
        "title": song.title,
        "batch_id": song.batch_id,
        "prompt_version": song.prompt_version,
        "target_platform": target_platform,
        "review_source": review.review_source,
        "publishable": review.publishable,
        "hook_score": review.hook_score,
        "vocal_score": review.vocal_score,
        "cover_score": review.cover_score,
        "notes": review.notes,
        "audio_path": str(exported_dir / "audio.mp3"),
        "cover_path": str(exported_dir / "cover_publish.png"),
        "caption_path": str(exported_dir / "caption.txt"),
    }
