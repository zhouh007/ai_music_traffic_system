from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .automation import AutomationService
from .config import load_app_config
from .models import ReviewRecord, SongRecord
from .orchestrator import BatchOrchestrator
from .pipeline.package_builder import (
    build_publish_manifest_entry,
    export_approved_song,
    write_export_manifest,
)
from .publish_manager import PublishManager
from .review.review_store import load_review, save_review
from .storage.file_store import ensure_dir
from .storage.run_log import log_step
from .topic_manager import load_topics_from_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Music Traffic System CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_batch_parser = subparsers.add_parser("run-batch", help="Run generation for a topics CSV file")
    run_batch_parser.add_argument("--topics-file", required=True)

    export_parser = subparsers.add_parser("export-approved", help="Export approved songs")
    export_parser.add_argument("--songs-dir", default="data/songs")

    approve_parser = subparsers.add_parser("approve-song", help="Mark a generated song as publishable")
    approve_parser.add_argument("--song-id", required=True)
    approve_parser.add_argument("--songs-dir", default="data/songs")
    approve_parser.add_argument("--hook-score", type=int, default=4)
    approve_parser.add_argument("--vocal-score", type=int, default=4)
    approve_parser.add_argument("--cover-score", type=int, default=4)
    approve_parser.add_argument("--notes", default="Approved for publishing")

    reject_parser = subparsers.add_parser("reject-song", help="Mark a generated song as not publishable")
    reject_parser.add_argument("--song-id", required=True)
    reject_parser.add_argument("--songs-dir", default="data/songs")
    reject_parser.add_argument("--notes", default="Rejected for publishing")

    review_list_parser = subparsers.add_parser("review-list", help="List songs and review readiness")
    review_list_parser.add_argument("--songs-dir", default="data/songs")

    approve_batch_parser = subparsers.add_parser("approve-batch", help="Approve every generated song in a batch")
    approve_batch_parser.add_argument("--batch-id", required=True)
    approve_batch_parser.add_argument("--songs-dir", default="data/songs")
    approve_batch_parser.add_argument("--hook-score", type=int, default=4)
    approve_batch_parser.add_argument("--vocal-score", type=int, default=4)
    approve_batch_parser.add_argument("--cover-score", type=int, default=4)
    approve_batch_parser.add_argument("--notes", default="Batch approved for publishing")

    retry_parser = subparsers.add_parser("retry-song", help="Retry selected steps for one song")
    retry_parser.add_argument("--song-id", required=True)
    retry_parser.add_argument("--step", choices=["music", "cover", "package", "all"], required=True)

    refine_title_parser = subparsers.add_parser("refine-title", help="Refine one generated song title")
    refine_title_parser.add_argument("--song-id", required=True)

    expand_topics_parser = subparsers.add_parser("expand-topics", help="Expand seed topics into a new batch CSV")
    expand_topics_parser.add_argument("--topics-file", required=True)
    expand_topics_parser.add_argument("--count", type=int, required=True)
    expand_topics_parser.add_argument("--batch-id")
    expand_topics_parser.add_argument("--output-file")

    schedule_parser = subparsers.add_parser("schedule-batch", help="Create a queued batch job")
    schedule_parser.add_argument("--topics-file", required=True)
    schedule_parser.add_argument("--run-after")

    run_scheduled_parser = subparsers.add_parser("run-scheduled", help="Run due queued batch jobs")
    run_scheduled_parser.add_argument("--auto-filter", action="store_true")
    run_scheduled_parser.add_argument("--min-total-score", type=int, default=12)
    run_scheduled_parser.add_argument("--export-approved", action="store_true")

    auto_filter_parser = subparsers.add_parser("auto-filter", help="Auto approve songs with simple quality rules")
    auto_filter_parser.add_argument("--batch-id")
    auto_filter_parser.add_argument("--songs-dir", default="data/songs")
    auto_filter_parser.add_argument("--min-total-score", type=int, default=12)

    process_parser = subparsers.add_parser("process-batch", help="Run batch with optional automation steps")
    process_parser.add_argument("--topics-file", required=True)
    process_parser.add_argument("--auto-expand-count", type=int, default=0)
    process_parser.add_argument("--auto-filter", action="store_true")
    process_parser.add_argument("--min-total-score", type=int, default=12)
    process_parser.add_argument("--export-approved", action="store_true")

    prepare_publish_parser = subparsers.add_parser("prepare-publish", help="Create multi-platform publish jobs")
    prepare_publish_parser.add_argument("--export-dir", required=True)
    prepare_publish_parser.add_argument("--platforms", required=True)
    prepare_publish_parser.add_argument("--schedule-at")

    publish_list_parser = subparsers.add_parser("publish-list", help="List publish jobs")
    publish_list_parser.add_argument("--status")
    publish_list_parser.add_argument("--platform")

    publish_run_parser = subparsers.add_parser("publish-run", help="Validate or launch one publish job")
    publish_run_parser.add_argument("--job-id", required=True)
    publish_run_parser.add_argument("--launch-browser", action="store_true")

    publish_complete_parser = subparsers.add_parser("publish-complete", help="Mark one publish job as completed")
    publish_complete_parser.add_argument("--job-id", required=True)
    publish_complete_parser.add_argument("--external-post-id", default="")

    publish_review_parser = subparsers.add_parser("publish-under-review", help="Mark one publish job as submitted and under review")
    publish_review_parser.add_argument("--job-id", required=True)
    publish_review_parser.add_argument("--external-post-id", default="")
    publish_review_parser.add_argument("--notes", default="")

    publish_fail_parser = subparsers.add_parser("publish-fail", help="Mark one publish job as failed")
    publish_fail_parser.add_argument("--job-id", required=True)
    publish_fail_parser.add_argument("--reason", required=True)

    music_auto_parser = subparsers.add_parser(
        "music-upload-run",
        help="Run semi-automatic music-platform form filling and stop before final manual submit",
    )
    music_auto_parser.add_argument("--job-id", required=True)
    music_auto_parser.add_argument("--manual-login-ms", type=int, default=60000)
    music_auto_parser.add_argument("--dry-run", action="store_true")
    music_auto_parser.add_argument(
        "--submit",
        action="store_true",
        help="Use only for controlled testing; default flow stops before final submit",
    )
    music_auto_parser.add_argument("--keep-open", action="store_true")

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    config = load_app_config(project_root)
    automation = AutomationService(project_root, config)
    publish_manager = PublishManager(project_root, config)

    if args.command == "run-batch":
        _run_batch(project_root, config, Path(args.topics_file))
        return
    if args.command == "export-approved":
        _export_approved(project_root, config, Path(args.songs_dir))
        return
    if args.command == "approve-song":
        _update_review(
            project_root=project_root,
            songs_dir=Path(args.songs_dir),
            song_id=args.song_id,
            publishable=True,
            hook_score=args.hook_score,
            vocal_score=args.vocal_score,
            cover_score=args.cover_score,
            notes=args.notes,
        )
        return
    if args.command == "reject-song":
        _update_review(
            project_root=project_root,
            songs_dir=Path(args.songs_dir),
            song_id=args.song_id,
            publishable=False,
            hook_score=0,
            vocal_score=0,
            cover_score=0,
            notes=args.notes,
        )
        return
    if args.command == "review-list":
        _review_list(project_root, Path(args.songs_dir))
        return
    if args.command == "approve-batch":
        _approve_batch(
            project_root=project_root,
            songs_dir=Path(args.songs_dir),
            batch_id=args.batch_id,
            hook_score=args.hook_score,
            vocal_score=args.vocal_score,
            cover_score=args.cover_score,
            notes=args.notes,
        )
        return
    if args.command == "retry-song":
        _retry_song(project_root, config, args.song_id, args.step)
        return
    if args.command == "refine-title":
        _refine_title(project_root, config, args.song_id)
        return
    if args.command == "expand-topics":
        output_path = automation.expand_topics(
            source_topics_file=_resolve_path(project_root, args.topics_file),
            output_count=args.count,
            batch_id=args.batch_id,
            output_file=_resolve_path(project_root, args.output_file) if args.output_file else None,
        )
        print(output_path)
        return
    if args.command == "schedule-batch":
        job_path = automation.schedule_batch(
            topics_file=_resolve_path(project_root, args.topics_file),
            run_after=args.run_after,
        )
        print(job_path)
        return
    if args.command == "run-scheduled":
        results = automation.run_scheduled(
            auto_filter=args.auto_filter,
            min_total_score=args.min_total_score,
            export_approved=args.export_approved,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if args.command == "auto-filter":
        summary = automation.auto_filter(
            batch_id=args.batch_id,
            min_total_score=args.min_total_score,
            songs_dir=_resolve_path(project_root, args.songs_dir),
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.command == "process-batch":
        result = automation.process_batch(
            topics_file=_resolve_path(project_root, args.topics_file),
            auto_expand_count=args.auto_expand_count,
            auto_filter_enabled=args.auto_filter,
            min_total_score=args.min_total_score,
            export_approved_enabled=args.export_approved,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "prepare-publish":
        jobs = publish_manager.prepare_publish_jobs(
            export_dir=_resolve_path(project_root, args.export_dir),
            platforms=[item.strip() for item in args.platforms.split(",") if item.strip()],
            schedule_at=args.schedule_at,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-list":
        rows = publish_manager.list_jobs(status=args.status, platform=args.platform)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if args.command == "publish-run":
        job = publish_manager.run_job(job_id=args.job_id, launch_browser=args.launch_browser)
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-complete":
        job = publish_manager.complete_job(
            job_id=args.job_id,
            external_post_id=args.external_post_id,
        )
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-under-review":
        job = publish_manager.mark_job_under_review(
            job_id=args.job_id,
            external_post_id=args.external_post_id,
            notes=args.notes,
        )
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-fail":
        job = publish_manager.fail_job(job_id=args.job_id, reason=args.reason)
        print(job.model_dump_json(indent=2))
        return
    if args.command == "music-upload-run":
        job = publish_manager.run_music_job_automation(
            job_id=args.job_id,
            manual_login_ms=args.manual_login_ms,
            dry_run=args.dry_run,
            submit=args.submit,
            keep_open=args.keep_open,
        )
        print(job.model_dump_json(indent=2))
        return


def _run_batch(project_root: Path, config, topics_file: Path) -> None:
    topics_path = topics_file if topics_file.is_absolute() else project_root / topics_file
    topics = load_topics_from_csv(topics_path)
    orchestrator = BatchOrchestrator(project_root, config)
    succeeded = 0
    failed = 0
    for topic in topics:
        song = orchestrator.run_topic(topic)
        if song.status == "generated":
            succeeded += 1
        else:
            failed += 1
    log_step(f"Batch complete: {topics_path} | succeeded={succeeded} failed={failed}")


def _export_approved(project_root: Path, config, songs_dir: Path) -> None:
    source_dir = songs_dir if songs_dir.is_absolute() else project_root / songs_dir
    export_root = ensure_dir(config.exports_dir / f"approved_{datetime.now():%Y%m%d_%H%M%S}")
    exported = 0
    manifest_entries: list[dict] = []
    for song_dir in source_dir.iterdir():
        if not song_dir.is_dir():
            continue
        review_path = song_dir / "review.json"
        song_path = song_dir / "song.json"
        if not review_path.exists() or not song_path.exists():
            continue
        review = load_review(review_path)
        if not review.publishable:
            continue
        song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
        exported_dir = export_approved_song(song, review, export_root)
        manifest_entries.append(build_publish_manifest_entry(song, review, exported_dir))
        exported += 1
    write_export_manifest(export_root, manifest_entries)
    log_step(f"Exported {exported} approved songs to {export_root}")


def _update_review(
    project_root: Path,
    songs_dir: Path,
    song_id: str,
    publishable: bool,
    hook_score: int,
    vocal_score: int,
    cover_score: int,
    notes: str,
) -> None:
    source_dir = songs_dir if songs_dir.is_absolute() else project_root / songs_dir
    review_path = source_dir / song_id / "review.json"
    if not review_path.exists():
        raise FileNotFoundError(f"Review file not found for song: {song_id}")
    review = ReviewRecord(
        song_id=song_id,
        hook_score=hook_score,
        vocal_score=vocal_score,
        cover_score=cover_score,
        publishable=publishable,
        notes=notes,
    )
    save_review(review_path, review)
    log_step(f"Updated review for {song_id} | publishable={publishable}")


def _review_list(project_root: Path, songs_dir: Path) -> None:
    source_dir = songs_dir if songs_dir.is_absolute() else project_root / songs_dir
    rows: list[dict] = []
    for song_dir in sorted(source_dir.iterdir()):
        if not song_dir.is_dir():
            continue
        song_path = song_dir / "song.json"
        review_path = song_dir / "review.json"
        if not song_path.exists():
            continue
        song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
        review = load_review(review_path) if review_path.exists() else ReviewRecord(song_id=song.song_id)
        rows.append(
            {
                "song_id": song.song_id,
                "batch_id": song.batch_id,
                "status": song.status,
                "publishable": review.publishable,
                "hook": review.hook_score,
                "vocal": review.vocal_score,
                "cover": review.cover_score,
                "reviewed_at": review.reviewed_at,
                "notes": review.notes,
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def _approve_batch(
    project_root: Path,
    songs_dir: Path,
    batch_id: str,
    hook_score: int,
    vocal_score: int,
    cover_score: int,
    notes: str,
) -> None:
    source_dir = songs_dir if songs_dir.is_absolute() else project_root / songs_dir
    updated = 0
    for song_dir in source_dir.iterdir():
        if not song_dir.is_dir():
            continue
        song_path = song_dir / "song.json"
        review_path = song_dir / "review.json"
        if not song_path.exists() or not review_path.exists():
            continue
        song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
        if song.batch_id != batch_id or song.status != "generated":
            continue
        review = ReviewRecord(
            song_id=song.song_id,
            hook_score=hook_score,
            vocal_score=vocal_score,
            cover_score=cover_score,
            publishable=True,
            notes=notes,
        )
        save_review(review_path, review)
        updated += 1
    log_step(f"Approved {updated} songs in batch {batch_id}")


def _retry_song(project_root: Path, config, song_id: str, step: str) -> None:
    orchestrator = BatchOrchestrator(project_root, config)
    song = orchestrator.retry_song_step(song_id=song_id, step=step)
    log_step(f"Retried {step} for {song.song_id} | status={song.status}")


def _refine_title(project_root: Path, config, song_id: str) -> None:
    orchestrator = BatchOrchestrator(project_root, config)
    song = orchestrator.refine_song_title(song_id=song_id)
    log_step(f"Refined title for {song.song_id} | title={song.title}")


def _resolve_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    main()
