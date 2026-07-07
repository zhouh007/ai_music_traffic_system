from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import PublishJobRecord
from .storage.file_store import ensure_dir, write_json, write_text
from .storage.run_log import log_step
from .video_builder import build_cover_video


PUBLISH_JOB_STATUSES = {
    "pending",
    "ready",
    "browser_opened",
    "saved_for_review",
    "under_review",
    "completed",
    "failed",
}

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
        "hashtags": ["#原创歌曲", "#情绪流行"],
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

STATUS_REASONS = {
    "job_prepared": "job_prepared",
    "assets_validated": "assets_validated",
    "browser_launched": "browser_launched",
    "music_automation_executed": "music_automation_executed",
    "marked_completed": "marked_completed",
    "marked_under_review": "marked_under_review",
    "marked_failed": "marked_failed",
    "batch_marked_under_review": "batch_marked_under_review",
    "batch_marked_completed": "batch_marked_completed",
    "batch_marked_failed": "batch_marked_failed",
    "legacy_job_imported": "legacy_job_imported",
    "legacy_job_without_timestamp": "legacy_job_without_timestamp",
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
                meta_payload = _safe_read_json(copied_meta)
                adapted_caption = _build_publish_text(
                    platform=platform,
                    title=title,
                    caption_text=caption_text,
                    meta_payload=meta_payload,
                    hashtags=preset["hashtags"],
                    caption_limit=preset["caption_limit"],
                )
                publish_text_path = package_dir / "publish_text.txt"
                write_text(publish_text_path, adapted_caption)
                if platform == "fanqie_music":
                    write_json(
                        package_dir / "release_brief.json",
                        _build_fanqie_release_brief(title, meta_payload, adapted_caption),
                    )
                    write_text(
                        package_dir / "operator_checklist.txt",
                        _build_fanqie_operator_checklist(title, package_dir),
                    )

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

                timestamp = datetime.now().isoformat(timespec="seconds")
                job_id = f"pub_{platform}_{entry['song_id']}_{datetime.now():%Y%m%d_%H%M%S}"
                job = PublishJobRecord(
                    job_id=job_id,
                    song_id=entry["song_id"],
                    batch_id=entry["batch_id"],
                    run_id=entry.get("run_id", ""),
                    prompt_version=entry.get("prompt_version", ""),
                    target_platform=entry.get("target_platform", ""),
                    review_source=entry.get("review_source", ""),
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
                    created_at=timestamp,
                    status_history=[
                        {
                            "status": "pending",
                            "timestamp": timestamp,
                            "reason": STATUS_REASONS["job_prepared"],
                        }
                    ],
                    notes="Prepared from approved export manifest",
                )
                self._save_job(jobs_root / f"{job_id}.json", job)
                write_json(package_dir / "publish_payload.json", _build_publish_payload(job))
                created_jobs.append(job)

        log_step(f"Prepared {len(created_jobs)} publish jobs from {export_dir}")
        return created_jobs

    def list_jobs(
        self,
        status: str | None = None,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        traceability_state: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        rows: list[dict] = []
        for job_path in self._iter_job_paths():
            job = self._load_job(job_path)
            if status and job.status != status:
                continue
            if platform and job.platform != platform:
                continue
            if batch_id and job.batch_id != batch_id:
                continue
            if run_id and job.run_id != run_id:
                continue
            if traceability_state and _job_traceability_state(job) != traceability_state:
                continue
            if active_only and not _is_active_workflow_job(job, self.config.target_platform):
                continue
            last_history = job.status_history[-1] if job.status_history else {}
            rows.append(
                {
                    "job_id": job.job_id,
                    "song_id": job.song_id,
                    "batch_id": job.batch_id,
                    "run_id": job.run_id,
                    "prompt_version": job.prompt_version,
                    "target_platform": job.target_platform,
                    "review_source": job.review_source,
                    "platform": job.platform,
                    "platform_type": job.platform_type,
                    "status": job.status,
                    "scheduled_at": job.scheduled_at,
                    "created_at": job.created_at,
                    "last_status_at": last_history.get("timestamp", ""),
                    "last_status_reason": last_history.get("reason", ""),
                    "history_count": len(job.status_history),
                    "traceability_state": _job_traceability_state(job),
                    "completed_at": job.completed_at,
                }
            )
        return rows

    def summarize_jobs(
        self,
        platform: str | None = None,
        batch_id: str | None = None,
        traceability_state: str | None = None,
        active_only: bool = False,
    ) -> dict:
        status_counts: Counter[str] = Counter()
        platform_counts: Counter[str] = Counter()
        platform_status_counts: dict[str, Counter[str]] = {}
        traceability_counts: Counter[str] = Counter()
        due_pending_count = 0
        now = datetime.now()
        for job_path in self._iter_job_paths():
            job = self._load_job(job_path)
            if platform and job.platform != platform:
                continue
            if batch_id and job.batch_id != batch_id:
                continue
            if traceability_state and _job_traceability_state(job) != traceability_state:
                continue
            if active_only and not _is_active_workflow_job(job, self.config.target_platform):
                continue
            status_counts[job.status] += 1
            platform_counts[job.platform] += 1
            platform_status_counts.setdefault(job.platform, Counter())[job.status] += 1
            traceability_counts[_job_traceability_state(job)] += 1
            if job.status == "pending" and _is_job_due(job, now):
                due_pending_count += 1
        backlog = {
            "action_required": status_counts.get("pending", 0)
            + status_counts.get("ready", 0)
            + status_counts.get("saved_for_review", 0)
            + status_counts.get("under_review", 0),
            "due_pending": due_pending_count,
            "ready_to_open": status_counts.get("ready", 0),
            "awaiting_platform_review": status_counts.get("under_review", 0),
            "awaiting_manual_submit_review": status_counts.get("saved_for_review", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
        }
        return {
            "platform_filter": platform or "",
            "batch_id_filter": batch_id or "",
            "traceability_filter": traceability_state or "",
            "active_only": active_only,
            "status_counts": dict(status_counts),
            "platform_counts": dict(platform_counts),
            "platform_status_counts": {
                platform_key: dict(counts)
                for platform_key, counts in sorted(platform_status_counts.items())
            },
            "traceability_counts": dict(traceability_counts),
            "backlog": backlog,
            "job_count": sum(status_counts.values()),
        }

    def get_job(self, job_id: str) -> PublishJobRecord:
        return self._load_job(self._find_job_path(job_id))

    def normalize_jobs(
        self,
        *,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        traceability_state: str | None = None,
        active_only: bool = False,
    ) -> list[PublishJobRecord]:
        normalized: list[PublishJobRecord] = []
        for job_path, _ in self._select_jobs(
            platform=platform,
            batch_id=batch_id,
            run_id=run_id,
            traceability_state=traceability_state,
            active_only=active_only,
        ):
            normalized.append(self._load_job(job_path))
        log_step(f"Normalized {len(normalized)} publish jobs for traceability")
        return normalized

    def run_job(self, job_id: str, launch_browser: bool = False) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = self._load_job(job_path)
        return self._run_job_from_path(job_path, job, launch_browser=launch_browser)

    def run_due_jobs(
        self,
        launch_browser: bool = False,
        platform: str | None = None,
        limit: int | None = None,
    ) -> list[PublishJobRecord]:
        now = datetime.now()
        executed: list[PublishJobRecord] = []
        for job_path in self._iter_job_paths():
            job = self._load_job(job_path)
            if platform and job.platform != platform:
                continue
            if job.status != "pending":
                continue
            if not _is_job_due(job, now):
                continue
            executed.append(self._run_job_from_path(job_path, job, launch_browser=launch_browser))
            if limit is not None and len(executed) >= limit:
                break
        log_step(
            f"Processed {len(executed)} due publish jobs"
            f"{f' for {platform}' if platform else ''}"
            f" | launch_browser={launch_browser}"
        )
        return executed

    def run_music_job_automation(
        self,
        job_id: str,
        manual_login_ms: int = 60000,
        dry_run: bool = False,
        submit: bool = False,
        keep_open: bool = False,
        simulate_session: bool = False,
    ) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = self._load_job(job_path)
        if job.platform_type != "music":
            raise RuntimeError(f"Automation skeleton currently supports music jobs only: {job.platform}")
        _validate_publish_assets(job)
        if simulate_session:
            _write_simulated_music_automation(job)
        else:
            command = [
                "node",
                str(self.project_root / "scripts" / "music_publish_playwright.mjs"),
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
        automation_summary = _safe_read_json(job.package_dir / "automation_last_run.json")
        job.status = "saved_for_review"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        job.automation_summary = automation_summary
        job.notes = _build_music_automation_note(job.platform, automation_summary)
        _append_status_history(job, "saved_for_review", STATUS_REASONS["music_automation_executed"])
        self._save_job(job_path, job)
        log_step(f"Executed music automation flow for {job.job_id}")
        return job

    def complete_job(self, job_id: str, external_post_id: str = "") -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = self._load_job(job_path)
        job.status = "completed"
        job.completed_at = datetime.now().isoformat(timespec="seconds")
        job.external_post_id = external_post_id
        _append_status_history(job, "completed", STATUS_REASONS["marked_completed"])
        self._save_job(job_path, job)
        log_step(f"Completed publish job {job.job_id}")
        return job

    def complete_jobs(
        self,
        *,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        job_ids: list[str] | None = None,
        from_statuses: set[str] | None = None,
    ) -> list[PublishJobRecord]:
        jobs = self._select_jobs(
            platform=platform,
            batch_id=batch_id,
            run_id=run_id,
            job_ids=job_ids,
            statuses=from_statuses,
        )
        updated: list[PublishJobRecord] = []
        for job_path, job in jobs:
            if job.status == "completed":
                continue
            job.status = "completed"
            job.completed_at = datetime.now().isoformat(timespec="seconds")
            _append_status_history(job, "completed", STATUS_REASONS["batch_marked_completed"])
            self._save_job(job_path, job)
            updated.append(job)
        log_step(f"Marked {len(updated)} publish jobs completed")
        return updated

    def mark_job_under_review(self, job_id: str, external_post_id: str = "", notes: str = "") -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = self._load_job(job_path)
        job.status = "under_review"
        job.started_at = job.started_at or datetime.now().isoformat(timespec="seconds")
        job.external_post_id = external_post_id
        if notes:
            job.notes = notes
        _append_status_history(job, "under_review", STATUS_REASONS["marked_under_review"])
        self._save_job(job_path, job)
        log_step(f"Marked publish job {job.job_id} under review")
        return job

    def mark_jobs_under_review(
        self,
        *,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        job_ids: list[str] | None = None,
        from_statuses: set[str] | None = None,
        notes: str = "",
    ) -> list[PublishJobRecord]:
        jobs = self._select_jobs(
            platform=platform,
            batch_id=batch_id,
            run_id=run_id,
            job_ids=job_ids,
            statuses=from_statuses,
        )
        updated: list[PublishJobRecord] = []
        for job_path, job in jobs:
            if job.status == "under_review":
                continue
            job.status = "under_review"
            job.started_at = job.started_at or datetime.now().isoformat(timespec="seconds")
            if notes:
                job.notes = notes
            _append_status_history(job, "under_review", STATUS_REASONS["batch_marked_under_review"])
            self._save_job(job_path, job)
            updated.append(job)
        log_step(f"Marked {len(updated)} publish jobs under review")
        return updated

    def fail_job(self, job_id: str, reason: str) -> PublishJobRecord:
        job_path = self._find_job_path(job_id)
        job = self._load_job(job_path)
        job.status = "failed"
        job.notes = reason
        _append_status_history(job, "failed", reason or STATUS_REASONS["marked_failed"])
        self._save_job(job_path, job)
        log_step(f"Marked publish job {job.job_id} failed: {reason}")
        return job

    def fail_jobs(
        self,
        *,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        job_ids: list[str] | None = None,
        from_statuses: set[str] | None = None,
        reason: str = "",
    ) -> list[PublishJobRecord]:
        jobs = self._select_jobs(
            platform=platform,
            batch_id=batch_id,
            run_id=run_id,
            job_ids=job_ids,
            statuses=from_statuses,
        )
        updated: list[PublishJobRecord] = []
        history_reason = reason or STATUS_REASONS["batch_marked_failed"]
        for job_path, job in jobs:
            if job.status == "failed" and (not reason or job.notes == reason):
                continue
            job.status = "failed"
            job.notes = reason or job.notes
            _append_status_history(job, "failed", history_reason)
            self._save_job(job_path, job)
            updated.append(job)
        log_step(f"Marked {len(updated)} publish jobs failed")
        return updated

    def archive_jobs(
        self,
        *,
        archive_label: str | None = None,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        job_ids: list[str] | None = None,
        statuses: set[str] | None = None,
        traceability_state: str | None = "legacy_partial",
        active_only: bool = False,
    ) -> dict:
        selected = self._select_jobs(
            platform=platform,
            batch_id=batch_id,
            run_id=run_id,
            job_ids=job_ids,
            statuses=statuses,
            traceability_state=traceability_state,
            active_only=active_only,
        )
        label = archive_label or f"legacy_{datetime.now():%Y%m%d_%H%M%S}"
        archive_root = ensure_dir(self.config.publish_dir / "archive" / label / "jobs")
        archived_jobs: list[dict] = []
        for job_path, job in selected:
            target_path = archive_root / job_path.name
            shutil.move(str(job_path), str(target_path))
            archived_jobs.append(
                {
                    "job_id": job.job_id,
                    "platform": job.platform,
                    "status": job.status,
                    "traceability_state": _job_traceability_state(job),
                }
            )
        summary = {
            "archive_label": label,
            "archived_at": datetime.now().isoformat(timespec="seconds"),
            "archive_dir": str(archive_root.parent),
            "job_count": len(archived_jobs),
            "jobs": archived_jobs,
        }
        write_json(archive_root.parent / "summary.json", summary)
        log_step(f"Archived {len(archived_jobs)} publish jobs into {label}")
        return summary

    def list_archives(self) -> list[dict]:
        archive_base = ensure_dir(self.config.publish_dir / "archive")
        rows: list[dict] = []
        for archive_dir in sorted([path for path in archive_base.iterdir() if path.is_dir()]):
            jobs_dir = archive_dir / "jobs"
            job_paths = sorted(jobs_dir.glob("pub_*.json")) if jobs_dir.exists() else []
            summary_path = archive_dir / "summary.json"
            summary = _safe_read_json(summary_path)
            rows.append(
                {
                    "archive_label": archive_dir.name,
                    "archive_dir": str(archive_dir),
                    "job_count": len(job_paths),
                    "created_at": summary.get("archived_at", ""),
                    "platform_counts": _count_archive_platforms(job_paths),
                }
            )
        return rows

    def restore_archive(self, archive_label: str) -> dict:
        archive_dir = self.config.publish_dir / "archive" / archive_label
        jobs_dir = archive_dir / "jobs"
        if not jobs_dir.exists():
            raise FileNotFoundError(f"Archive not found: {archive_label}")
        active_jobs_dir = ensure_dir(self.config.publish_dir / "jobs")
        restored_jobs: list[str] = []
        for job_path in sorted(jobs_dir.glob("pub_*.json")):
            target_path = active_jobs_dir / job_path.name
            if target_path.exists():
                raise FileExistsError(f"Cannot restore {job_path.name}; active job already exists.")
            shutil.move(str(job_path), str(target_path))
            restored_jobs.append(job_path.stem)
        summary = {
            "archive_label": archive_label,
            "restored_count": len(restored_jobs),
            "restored_job_ids": restored_jobs,
            "archive_dir": str(archive_dir),
        }
        if not any(jobs_dir.iterdir()):
            shutil.rmtree(archive_dir)
        log_step(f"Restored {len(restored_jobs)} publish jobs from archive {archive_label}")
        return summary

    def _iter_job_paths(self) -> list[Path]:
        return sorted(ensure_dir(self.config.publish_dir / "jobs").glob("pub_*.json"))

    def _find_job_path(self, job_id: str) -> Path:
        job_path = self.config.publish_dir / "jobs" / f"{job_id}.json"
        if not job_path.exists():
            raise FileNotFoundError(f"Publish job not found: {job_id}")
        return job_path

    def _select_jobs(
        self,
        *,
        platform: str | None = None,
        batch_id: str | None = None,
        run_id: str | None = None,
        job_ids: list[str] | None = None,
        statuses: set[str] | None = None,
        traceability_state: str | None = None,
        active_only: bool = False,
    ) -> list[tuple[Path, PublishJobRecord]]:
        selected: list[tuple[Path, PublishJobRecord]] = []
        requested_ids = {item for item in (job_ids or []) if item}
        normalized_statuses = {item.strip() for item in (statuses or set()) if item.strip()}
        for job_path in self._iter_job_paths():
            job = self._load_job(job_path)
            if requested_ids and job.job_id not in requested_ids:
                continue
            if platform and job.platform != platform:
                continue
            if batch_id and job.batch_id != batch_id:
                continue
            if run_id and job.run_id != run_id:
                continue
            if normalized_statuses and job.status not in normalized_statuses:
                continue
            if traceability_state and _job_traceability_state(job) != traceability_state:
                continue
            if active_only and not _is_active_workflow_job(job, self.config.target_platform):
                continue
            selected.append((job_path, job))
        return selected

    def _load_job(self, job_path: Path) -> PublishJobRecord:
        raw_data = json.loads(job_path.read_text(encoding="utf-8"))
        job = PublishJobRecord.model_validate(raw_data)
        changed = False
        if raw_data.get("status") != job.status:
            changed = True
        raw_video_path = raw_data.get("video_path")
        normalized_video_path = str(job.video_path) if job.video_path else None
        if raw_video_path in {".", "", "null"} and normalized_video_path is None:
            changed = True
        if job.status not in PUBLISH_JOB_STATUSES:
            job.status = "pending"
            changed = True
        if job.platform_type == "music" and job.video_path is not None:
            job.video_path = None
            changed = True
        automation_summary = _safe_read_json(job.package_dir / "automation_last_run.json")
        if automation_summary and job.automation_summary != automation_summary:
            job.automation_summary = automation_summary
            changed = True
            if job.platform == "fanqie_music" and (
                not job.notes
                or "semi-auto upload completed" in job.notes
                or "Prepared from approved export manifest" in job.notes
            ):
                job.notes = _build_music_automation_note(job.platform, automation_summary)
        if _backfill_job_traceability(job, self.config):
            changed = True
        if not isinstance(raw_data.get("status_history"), list):
            fallback_timestamp = raw_data.get("started_at") or raw_data.get("created_at") or ""
            fallback_reason = (
                STATUS_REASONS["legacy_job_imported"]
                if fallback_timestamp
                else STATUS_REASONS["legacy_job_without_timestamp"]
            )
            job.status_history = (
                [
                    {
                        "status": job.status,
                        "timestamp": fallback_timestamp,
                        "reason": fallback_reason,
                    }
                ]
                if fallback_timestamp
                else []
            )
            changed = True
        normalized_history = _normalize_status_history(job.status_history)
        if normalized_history != job.status_history:
            job.status_history = normalized_history
            changed = True
        if changed:
            self._save_job(job_path, job)
        return job

    def _save_job(self, job_path: Path, job: PublishJobRecord) -> None:
        write_json(job_path, job.model_dump(mode="json"))

    def _run_job_from_path(
        self,
        job_path: Path,
        job: PublishJobRecord,
        launch_browser: bool = False,
    ) -> PublishJobRecord:
        _validate_publish_assets(job)
        job.status = "ready" if not launch_browser else "browser_opened"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        if launch_browser:
            subprocess.run(["cmd", "/c", "start", "", job.publish_url], check=True)
            log_step(f"Launched browser for publish job {job.job_id} -> {job.publish_url}")
        else:
            log_step(f"Validated publish job {job.job_id}")
        _append_status_history(
            job,
            job.status,
            STATUS_REASONS["browser_launched"] if launch_browser else STATUS_REASONS["assets_validated"],
        )
        self._save_job(job_path, job)
        return job


def _build_publish_payload(job: PublishJobRecord) -> dict:
    return {
        "job_id": job.job_id,
        "platform": job.platform,
        "platform_type": job.platform_type,
        "run_id": job.run_id,
        "prompt_version": job.prompt_version,
        "target_platform": job.target_platform,
        "review_source": job.review_source,
        "title": job.title,
        "caption": job.caption,
        "video_path": str(job.video_path) if job.video_path else "",
        "cover_path": str(job.cover_path),
        "audio_path": str(job.audio_path),
        "lyrics_path": str(job.lyrics_path) if job.lyrics_path else "",
        "meta_path": str(job.meta_path) if job.meta_path else "",
        "release_brief_path": str(job.package_dir / "release_brief.json"),
        "operator_checklist_path": str(job.package_dir / "operator_checklist.txt"),
        "publish_url": job.publish_url,
    }


def _build_publish_text(
    *,
    platform: str,
    title: str,
    caption_text: str,
    meta_payload: dict,
    hashtags: list[str],
    caption_limit: int,
) -> str:
    if platform == "fanqie_music":
        return _build_fanqie_publish_text(
            title=title,
            meta_payload=meta_payload,
            hashtags=hashtags,
            caption_limit=caption_limit,
        )
    return _adapt_caption(caption_text, hashtags, caption_limit)


def _build_fanqie_publish_text(
    *,
    title: str,
    meta_payload: dict,
    hashtags: list[str],
    caption_limit: int,
) -> str:
    mood = str(meta_payload.get("mood", "")).strip()
    scene = _normalize_fanqie_descriptor(str(meta_payload.get("scene", "")).strip())
    topic = str(meta_payload.get("topic", "")).strip()
    audience = _normalize_fanqie_descriptor(str(meta_payload.get("audience", "")).strip())

    intro = f"《{title}》"
    summary_parts = [part for part in [topic or mood, scene] if part]
    if summary_parts:
        summary = f"一首围绕{'，'.join(summary_parts[:2])}展开的中文流行单曲"
    else:
        summary = "一首偏情绪表达的中文流行单曲"
    companion = audience or mood or "适合一个人安静听完"
    body = f"{intro}\n{summary}。\n给{companion}的一次完整情绪落点。"
    return _append_hashtags(body, hashtags, caption_limit)


def _build_fanqie_release_brief(title: str, meta_payload: dict, publish_text: str) -> dict:
    lines = [line.strip() for line in publish_text.splitlines() if line.strip()]
    return {
        "title_display": title,
        "distribution_target": meta_payload.get("distribution_target", ""),
        "music_platform_profile": "fanqie_music_release",
        "release_summary": lines[1] if len(lines) > 1 else publish_text,
        "audience_scene": {
            "audience": _normalize_fanqie_descriptor(str(meta_payload.get("audience", "")).strip()),
            "scene": _normalize_fanqie_descriptor(str(meta_payload.get("scene", "")).strip()),
        },
        "emotion_keywords": [
            item
            for item in [
                str(meta_payload.get("mood", "")).strip(),
                str(meta_payload.get("style_hint", "")).strip(),
            ]
            if item
        ],
        "copy_style": "music_platform_release_brief",
    }


def _build_fanqie_operator_checklist(title: str, package_dir: Path) -> str:
    lines = [
        f"Fanqie Music Upload Checklist | {title}",
        "1. Confirm audio file opens and duration feels like a complete song rather than a short clip.",
        "2. Confirm cover image is clean, readable, and matches the song mood.",
        "3. Confirm publish text reads like a song release note, not a short-video caption.",
        "4. Confirm lyrics pasted into the platform are complete and free of obvious formatting issues.",
        "5. Confirm release_brief.json matches the intended audience, scene, and emotion profile.",
        "6. Review automation_last_run.json after semi-auto upload to confirm fields were filled as expected.",
        f"Package directory: {package_dir}",
    ]
    return "\n".join(lines)


def _build_music_automation_note(platform: str, automation_summary: dict) -> str:
    if not automation_summary:
        return "Music upload automation executed; review package artifacts before final submit."
    checks = [
        f"fullTrackReady={automation_summary.get('fullTrackReady', False)}",
        f"audioUploaded={automation_summary.get('audioUploaded', False)}",
        f"coverUploaded={automation_summary.get('coverUploaded', False)}",
        f"titleFilled={automation_summary.get('titleFilled', False)}",
        f"captionFilled={automation_summary.get('captionFilled', False)}",
        f"lyricsFilled={automation_summary.get('lyricsFilled', False)}",
        f"draftClicked={automation_summary.get('draftClicked', False)}",
        f"releaseBriefLoaded={automation_summary.get('releaseBriefLoaded', False)}",
        f"operatorChecklistLoaded={automation_summary.get('operatorChecklistLoaded', False)}",
    ]
    return (
        f"{platform} semi-auto upload completed; final submit still requires human review. "
        f"Automation checks: {', '.join(checks)}"
    )


def _write_simulated_music_automation(job: PublishJobRecord) -> None:
    release_brief = _safe_read_json(job.package_dir / "release_brief.json")
    operator_checklist_path = job.package_dir / "operator_checklist.txt"
    operator_checklist = (
        operator_checklist_path.read_text(encoding="utf-8")
        if operator_checklist_path.exists()
        else ""
    )
    summary = {
        "platform": job.platform,
        "mode": "simulated_local_verification",
        "releaseBriefLoaded": bool(release_brief),
        "operatorChecklistLoaded": bool(operator_checklist.strip()),
        "releaseSummary": release_brief.get("release_summary", ""),
        "operatorChecklistPreview": operator_checklist.splitlines()[:3] if operator_checklist.strip() else [],
        "fullTrackReady": True,
        "audioUploaded": True,
        "coverUploaded": True,
        "titleFilled": True,
        "captionFilled": True,
        "lyricsFilled": True,
        "draftClicked": True,
        "submitClicked": False,
        "humanReviewRequired": True,
        "nextManualChecks": [
            "Check uploaded cover and lyrics before final submit.",
            "Confirm release_brief.json matches the release intent.",
            "Record under_review or failed outcome after manual review.",
        ],
    }
    write_json(job.package_dir / "automation_last_run.json", summary)


def _normalize_fanqie_descriptor(value: str) -> str:
    normalized = value.strip()
    replacements = {
        "短视频用户": "情绪流行听众",
        "刷视频": "独处时刻",
        "短视频": "音乐听众",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _adapt_caption(caption_text: str, hashtags: list[str], caption_limit: int) -> str:
    clean = " ".join(caption_text.split())
    return _append_hashtags(clean, hashtags, caption_limit)


def _append_hashtags(base_text: str, hashtags: list[str], caption_limit: int) -> str:
    clean = base_text.strip()
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
    if job.platform == "fanqie_music":
        _validate_fanqie_publish_text(job.caption_path)
        _validate_fanqie_release_artifacts(job.package_dir)


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


def _is_job_due(job: PublishJobRecord, now: datetime) -> bool:
    if not job.scheduled_at:
        return True
    return datetime.fromisoformat(job.scheduled_at) <= now


def _append_status_history(job: PublishJobRecord, status: str, reason: str) -> None:
    current = {
        "status": status,
        "reason": reason,
    }
    if job.status_history:
        previous = job.status_history[-1]
        if previous.get("status") == current["status"] and previous.get("reason") == current["reason"]:
            return
    job.status_history.append(
        {
            "status": status,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
        }
    )


def _backfill_job_traceability(job: PublishJobRecord, config) -> bool:
    changed = False
    meta_payload = _safe_read_json(job.meta_path) if job.meta_path else {}
    song_payload = _safe_read_json(config.songs_dir / job.song_id / "song.json")
    review_payload = _safe_read_json(config.songs_dir / job.song_id / "review.json")

    run_id = (
        job.run_id
        or meta_payload.get("run_id", "")
        or song_payload.get("run_id", "")
    )
    if not run_id:
        run_id = f"legacy_missing_run_id:{job.song_id}"
    if run_id and job.run_id != run_id:
        job.run_id = run_id
        changed = True

    prompt_version = (
        job.prompt_version
        or meta_payload.get("prompt_version", "")
        or song_payload.get("prompt_version", "")
        or getattr(config, "prompt_version", "")
    )
    if prompt_version and job.prompt_version != prompt_version:
        job.prompt_version = prompt_version
        changed = True

    target_platform = (
        job.target_platform
        or meta_payload.get("target_platform", "")
        or getattr(config, "target_platform", "")
    )
    if target_platform and job.target_platform != target_platform:
        job.target_platform = target_platform
        changed = True

    review_source = (
        job.review_source
        or review_payload.get("review_source", "")
    )
    if not review_source:
        review_source = "legacy_missing_review_source"
    if review_source and job.review_source != review_source:
        job.review_source = review_source
        changed = True

    return changed


def _safe_read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _job_traceability_state(job: PublishJobRecord) -> str:
    if job.run_id.startswith("legacy_missing_run_id:") or job.review_source == "legacy_missing_review_source":
        return "legacy_partial"
    return "complete"


def _is_active_workflow_job(job: PublishJobRecord, primary_target_platform: str) -> bool:
    return _job_traceability_state(job) == "complete" and job.target_platform == primary_target_platform


def _normalize_status_history(history: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for entry in history:
        status = entry.get("status", "")
        reason = entry.get("reason", "")
        if normalized:
            previous = normalized[-1]
            if previous.get("status") == status and previous.get("reason") == reason:
                continue
        normalized.append(entry)
    return normalized


def _count_archive_platforms(job_paths: list[Path]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for job_path in job_paths:
        payload = _safe_read_json(job_path)
        platform = str(payload.get("platform", "")).strip() or "unknown"
        counts[platform] += 1
    return dict(counts)


def _validate_fanqie_publish_text(caption_path: Path) -> None:
    text = caption_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Fanqie publish text is empty: {caption_path}")
    for phrase in ["#短视频BGM", "短视频BGM"]:
        if phrase in text:
            raise RuntimeError(
                f"Fanqie publish text contains short-video phrase '{phrase}': {caption_path}"
            )


def _validate_fanqie_release_artifacts(package_dir: Path) -> None:
    release_brief = package_dir / "release_brief.json"
    operator_checklist = package_dir / "operator_checklist.txt"
    if not release_brief.exists():
        raise FileNotFoundError(f"Missing Fanqie release brief: {release_brief}")
    if not operator_checklist.exists():
        raise FileNotFoundError(f"Missing Fanqie operator checklist: {operator_checklist}")
    brief_payload = _safe_read_json(release_brief)
    required_fields = ["music_platform_profile", "release_summary", "audience_scene", "copy_style"]
    missing_fields = [field for field in required_fields if not brief_payload.get(field)]
    if missing_fields:
        raise RuntimeError(f"Fanqie release brief is missing required fields: {missing_fields}")
    checklist_text = operator_checklist.read_text(encoding="utf-8").strip()
    if "Upload Checklist" not in checklist_text:
        raise RuntimeError(f"Fanqie operator checklist looks incomplete: {operator_checklist}")
