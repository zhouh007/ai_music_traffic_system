from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import PublishJobRecord
from .storage.file_store import ensure_dir, write_json, write_text
from .storage.run_log import log_step
from .video_builder import build_cover_video


PLATFORM_PRESETS = {
    "douyin": {
        "platform_type": "video",
        "publish_url": "https://creator.douyin.com/creator-micro/content/upload",
        "caption_limit": 55,
        "hashtags": ["#AI音乐", "#情绪歌曲", "#短视频BGM"],
        "video_size": (1080, 1920),
        "requires_video": True,
    },
    "kuaishou": {
        "platform_type": "video",
        "publish_url": "https://cp.kuaishou.com/article/publish/video",
        "caption_limit": 80,
        "hashtags": ["#AI音乐", "#情绪短片", "#氛围感"],
        "video_size": (1080, 1920),
        "requires_video": True,
    },
    "bilibili": {
        "platform_type": "video",
        "publish_url": "https://member.bilibili.com/platform/upload/video/frame",
        "caption_limit": 100,
        "hashtags": ["#AI音乐", "#原创音乐", "#短片配乐"],
        "video_size": (1080, 1920),
        "requires_video": True,
    },
    "xiaohongshu": {
        "platform_type": "video",
        "publish_url": "https://creator.xiaohongshu.com/publish/publish",
        "caption_limit": 120,
        "hashtags": ["#AI音乐", "#情绪文案", "#治愈BGM"],
        "video_size": (1080, 1920),
        "requires_video": True,
    },
    "fanqie_music": {
        "platform_type": "music",
        "publish_url": "https://music.douyin.com/",
        "caption_limit": 120,
        "hashtags": ["#AI音乐", "#原创歌曲", "#情绪流行"],
        "video_size": (1080, 1920),
        "requires_video": False,
    },
    "qishui_music": {
        "platform_type": "music",
        "publish_url": "https://music.douyin.com/",
        "caption_limit": 120,
        "hashtags": ["#AI音乐", "#原创音乐", "#氛围感"],
        "video_size": (1080, 1920),
        "requires_video": False,
    },
}


class PublishManager:
    def __init__(self, project_root: Path, config) -> None:
        self.project_root = project_root
        self.config = config

    def prepare_publish_jobs(
        self,
        export_dir: Path,
        platforms: list[str],
        schedule_at: str | None = None,
    ) -> list[PublishJobRecord]:
        manifest_path = export_dir / "publish_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        packages_root = ensure_dir(self.config.publish_dir / "packages")
        jobs_root = ensure_dir(self.config.publish_dir / "jobs")
        created_jobs: list[PublishJobRecord] = []

        for entry in manifest:
            audio_source_path = Path(entry["audio_path"])
            cover_source_path = Path(entry["cover_path"])
            caption_source_path = Path(entry["caption_path"])
            song_export_dir = audio_source_path.parent
            lyrics_source_path = song_export_dir / "lyrics_clean.txt"
            meta_source_path = song_export_dir / "meta.json"
            if not _is_publish_source_valid(audio_source_path, cover_source_path, caption_source_path):
                log_step(f"Skipped publish prep for {entry['song_id']} due to invalid source assets")
                continue

            for platform in platforms:
                preset = _get_platform_preset(platform)
                package_dir = ensure_dir(packages_root / entry["song_id"] / platform)
                copied_audio = package_dir / audio_source_path.name
                copied_cover = package_dir / cover_source_path.name
                copied_caption = package_dir / caption_source_path.name
                copied_lyrics = package_dir / lyrics_source_path.name if lyrics_source_path.exists() else None
                copied_meta = package_dir / meta_source_path.name if meta_source_path.exists() else None

                _copy_if_needed(audio_source_path, copied_audio)
                _copy_if_needed(cover_source_path, copied_cover)
                _copy_if_needed(caption_source_path, copied_caption)
                if copied_lyrics:
                    _copy_if_needed(lyrics_source_path, copied_lyrics)
                if copied_meta:
                    _copy_if_needed(meta_source_path, copied_meta)

                title = _truncate_text(entry["title"], 30)
                caption_text = copied_caption.read_text(encoding="utf-8")
                adapted_caption = _adapt_caption(caption_text, preset["hashtags"], preset["caption_limit"])
                publish_text_path = package_dir / "publish_text.txt"
                write_text(publish_text_path, adapted_caption)

                video_path: Path | None = package_dir / "publish_video.mp4"
                if preset["requires_video"]:
                    width, height = preset["video_size"]
                    build_cover_video(
                        image_path=copied_cover,
                        audio_path=copied_audio,
                        output_path=video_path,
                        width=width,
                        height=height,
                    )
                else:
                    video_path = None

                job_id = f"pub_{platform}_{entry['song_id']}_{datetime.now():%Y%m%d_%H%M%S}"
                job = PublishJobRecord(
                    job_id=job_id,
                    song_id=entry["song_id"],
                    batch_id=entry["batch_id"],
                    platform=platform,
                    platform_type=preset["platform_type"],
                    status="pending",
                    package_dir=package_dir,
                    video_path=video_path,
                    cover_path=copied_cover,
                    audio_path=copied_audio,
                    caption_path=publish_text_path,
                    lyrics_path=copied_lyrics,
                    meta_path=copied_meta,
                    publish_url=preset["publish_url"],
                    title=title,
                    caption=adapted_caption,
                    scheduled_at=schedule_at or "",
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    notes="Prepared from approved export manifest",
                )
                self._save_job(jobs_root / f"{job_id}.json", job)
                write_json(package_dir / "publish_payload.json", _build_publish_payload(job))
                created_jobs.append(job)

        log_step(f"Prepared {len(created_jobs)} publish jobs from {export_dir}")
        return created_jobs

    def list_jobs(self, status: str | None = None, platform: str | None = None) -> list[dict]:
        jobs_root = ensure_dir(self.config.publish_dir / "jobs")
        rows: list[dict] = []
        for job_path in sorted(jobs_root.glob("pub_*.json")):
            job = PublishJobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))
            if status and job.status != status:
                continue
            if platform and job.platform != platform:
                continue
            rows.append(
                {
                    "job_id": job.job_id,
                    "song_id": job.song_id,
                    "batch_id": job.batch_id,
                    "platform": job.platform,
                    "platform_type": job.platform_type,
                    "status": job.status,
                    "scheduled_at": job.scheduled_at,
                    "created_at": job.created_at,
                    "completed_at": job.completed_at,
                }
            )
        return rows

    def run_job(self, job_id: str, launch_browser: bool = False) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = PublishJobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))
        _validate_publish_assets(job)
        job.status = "ready" if not launch_browser else "launched"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        if launch_browser:
            subprocess.run(["cmd", "/c", "start", "", job.publish_url], check=True)
            log_step(f"Launched browser for publish job {job.job_id} -> {job.publish_url}")
        else:
            log_step(f"Validated publish job {job.job_id}")
        self._save_job(job_path, job)
        return job

    def run_music_job_automation(
        self,
        job_id: str,
        manual_login_ms: int = 60000,
        dry_run: bool = False,
        submit: bool = False,
        keep_open: bool = False,
    ) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = PublishJobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))
        if job.platform_type != "music":
            raise RuntimeError(f"Automation skeleton currently supports music jobs only: {job.platform}")
        _validate_publish_assets(job)
        script_path = self.project_root / "scripts" / "music_publish_playwright.mjs"
        command = [
            "node",
            str(script_path),
            "--job-file",
            str(job_path),
            "--manual-login-ms",
            str(manual_login_ms),
        ]
        if dry_run:
            command.append("--dry-run")
        if submit:
            command.append("--submit")
        if keep_open:
            command.append("--keep-open")
        subprocess.run(command, check=True)
        job.status = "automation_ran"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        self._save_job(job_path, job)
        log_step(f"Executed music automation skeleton for {job.job_id}")
        return job

    def complete_job(self, job_id: str, external_post_id: str = "") -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = PublishJobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))
        job.status = "completed"
        job.completed_at = datetime.now().isoformat(timespec="seconds")
        job.external_post_id = external_post_id
        self._save_job(job_path, job)
        log_step(f"Completed publish job {job.job_id}")
        return job

    def fail_job(self, job_id: str, reason: str) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = PublishJobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))
        job.status = "failed"
        job.notes = reason
        self._save_job(job_path, job)
        log_step(f"Marked publish job {job.job_id} failed: {reason}")
        return job

    def _find_job_path(self, job_id: str) -> Path:
        job_path = self.config.publish_dir / "jobs" / f"{job_id}.json"
        if not job_path.exists():
            raise FileNotFoundError(f"Publish job not found: {job_id}")
        return job_path

    def _save_job(self, job_path: Path, job: PublishJobRecord) -> None:
        write_json(job_path, job.model_dump(mode="json"))


def _build_publish_payload(job: PublishJobRecord) -> dict:
    return {
        "job_id": job.job_id,
        "platform": job.platform,
        "platform_type": job.platform_type,
        "title": job.title,
        "caption": job.caption,
        "video_path": str(job.video_path) if job.video_path else "",
        "cover_path": str(job.cover_path),
        "audio_path": str(job.audio_path),
        "lyrics_path": str(job.lyrics_path) if job.lyrics_path else "",
        "meta_path": str(job.meta_path) if job.meta_path else "",
        "publish_url": job.publish_url,
    }


def _adapt_caption(caption_text: str, hashtags: list[str], caption_limit: int) -> str:
    clean = " ".join(caption_text.split())
    existing_tags = {word for word in clean.split() if word.startswith("#")}
    merged_tags: list[str] = []
    for tag in hashtags:
        if tag not in existing_tags and tag not in merged_tags:
            merged_tags.append(tag)
    suffix = f" {' '.join(merged_tags)}" if merged_tags else ""
    base_limit = max(caption_limit - len(suffix), 10)
    trimmed = _truncate_text(clean, base_limit)
    return f"{trimmed}{suffix}"


def _truncate_text(text: str, max_length: int) -> str:
    compact = text.strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "..."


def _get_platform_preset(platform: str) -> dict:
    key = platform.strip().lower()
    if key not in PLATFORM_PRESETS:
        raise RuntimeError(f"Unsupported platform: {platform}")
    return PLATFORM_PRESETS[key]


def _validate_publish_assets(job: PublishJobRecord) -> None:
    required_paths = [job.cover_path, job.audio_path, job.caption_path]
    if job.platform_type == "video" and job.video_path is not None:
        required_paths.append(job.video_path)
    if job.platform_type == "music" and job.lyrics_path is not None:
        required_paths.append(job.lyrics_path)
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing publish asset: {path}")
        if path.stat().st_size <= 0:
            raise RuntimeError(f"Invalid empty publish asset: {path}")


def _copy_if_needed(source_path: Path, target_path: Path) -> None:
    if source_path.resolve() == target_path.resolve():
        return
    shutil.copy2(source_path, target_path)


def _is_publish_source_valid(audio_path: Path, cover_path: Path, caption_path: Path) -> bool:
    if not audio_path.exists() or audio_path.stat().st_size < 100_000:
        return False
    if not cover_path.exists() or cover_path.stat().st_size < 5_000:
        return False
    if not caption_path.exists() or caption_path.stat().st_size <= 0:
        return False
    return True
