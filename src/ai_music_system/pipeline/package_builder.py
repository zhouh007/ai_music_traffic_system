from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from ..models import ReviewRecord, SongRecord, TopicRecord


def build_song_metadata(song: SongRecord, topic: TopicRecord) -> dict:
    return {
        "song_id": song.song_id,
        "topic_id": song.topic_id,
        "batch_id": song.batch_id,
        "title": song.title,
        "topic": topic.topic,
        "audience": topic.audience,
        "mood": topic.mood,
        "scene": topic.scene,
        "style_hint": topic.style_hint,
        "publish_platform": topic.publish_platform,
        "mode": song.mode,
        "status": song.status,
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
        "song_id",
        "title",
        "batch_id",
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


def build_publish_manifest_entry(song: SongRecord, review: ReviewRecord, exported_dir: Path) -> dict:
    return {
        "song_id": song.song_id,
        "title": song.title,
        "batch_id": song.batch_id,
        "publishable": review.publishable,
        "hook_score": review.hook_score,
        "vocal_score": review.vocal_score,
        "cover_score": review.cover_score,
        "notes": review.notes,
        "audio_path": str(exported_dir / "audio.mp3"),
        "cover_path": str(exported_dir / "cover_publish.png"),
        "caption_path": str(exported_dir / "caption.txt"),
    }
