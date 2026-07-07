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
    write_export_summary,
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

    workflow_status_parser = subparsers.add_parser(
        "workflow-status",
        help="Show a primary-platform workflow snapshot across review, export, and publish",
    )
    workflow_status_parser.add_argument("--songs-dir", default="data/songs")
    workflow_status_parser.add_argument("--json", action="store_true")

    workflow_next_parser = subparsers.add_parser(
        "workflow-next",
        help="Preview or execute the recommended next primary-platform workflow step",
    )
    workflow_next_parser.add_argument("--songs-dir", default="data/songs")
    workflow_next_parser.add_argument("--execute", action="store_true")
    workflow_next_parser.add_argument("--json", action="store_true")

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
    prepare_publish_parser.add_argument("--platforms")
    prepare_publish_parser.add_argument("--schedule-at")

    publish_list_parser = subparsers.add_parser("publish-list", help="List publish jobs")
    publish_list_parser.add_argument("--status")
    publish_list_parser.add_argument("--platform")
    publish_list_parser.add_argument("--batch-id")
    publish_list_parser.add_argument("--run-id")
    publish_list_parser.add_argument("--all-platforms", action="store_true")
    publish_list_parser.add_argument("--traceability-state", choices=["complete", "legacy_partial"])
    publish_list_parser.add_argument("--active-only", action="store_true")

    publish_summary_parser = subparsers.add_parser("publish-summary", help="Summarize publish jobs by status")
    publish_summary_parser.add_argument("--platform")
    publish_summary_parser.add_argument("--batch-id")
    publish_summary_parser.add_argument("--all-platforms", action="store_true")
    publish_summary_parser.add_argument("--traceability-state", choices=["complete", "legacy_partial"])
    publish_summary_parser.add_argument("--active-only", action="store_true")
    publish_summary_parser.add_argument("--pretty", action="store_true", help="Print an operator-friendly summary")

    publish_repair_parser = subparsers.add_parser(
        "publish-repair-traceability",
        help="Backfill and persist traceability defaults for publish jobs",
    )
    publish_repair_parser.add_argument("--platform")
    publish_repair_parser.add_argument("--batch-id")
    publish_repair_parser.add_argument("--run-id")
    publish_repair_parser.add_argument("--all-platforms", action="store_true")
    publish_repair_parser.add_argument("--traceability-state", choices=["complete", "legacy_partial"])
    publish_repair_parser.add_argument("--active-only", action="store_true")

    publish_archive_parser = subparsers.add_parser(
        "publish-archive-legacy",
        help="Move selected legacy publish jobs out of the active queue into a reversible archive",
    )
    publish_archive_parser.add_argument("--platform")
    publish_archive_parser.add_argument("--batch-id")
    publish_archive_parser.add_argument("--run-id")
    publish_archive_parser.add_argument("--job-ids")
    publish_archive_parser.add_argument(
        "--from-status",
        help="Only archive jobs currently in one of these comma-separated statuses",
    )
    publish_archive_parser.add_argument("--label")

    subparsers.add_parser("publish-archive-list", help="List publish job archive buckets")

    publish_archive_restore_parser = subparsers.add_parser(
        "publish-archive-restore",
        help="Restore one archived publish bucket back into the active queue",
    )
    publish_archive_restore_parser.add_argument("--label", required=True)

    publish_target_parser = subparsers.add_parser("publish-target", help="Show the configured primary target platform")
    publish_target_parser.add_argument("--json", action="store_true")

    publish_show_parser = subparsers.add_parser("publish-show", help="Show one publish job with status history")
    publish_show_parser.add_argument("--job-id", required=True)

    publish_run_parser = subparsers.add_parser("publish-run", help="Validate or launch one publish job")
    publish_run_parser.add_argument("--job-id", required=True)
    publish_run_parser.add_argument("--launch-browser", action="store_true")

    publish_run_due_parser = subparsers.add_parser("publish-run-due", help="Run due scheduled publish jobs")
    publish_run_due_parser.add_argument("--launch-browser", action="store_true")
    publish_run_due_parser.add_argument("--platform")
    publish_run_due_parser.add_argument("--limit", type=int)
    publish_run_due_parser.add_argument("--all-platforms", action="store_true")

    publish_complete_parser = subparsers.add_parser("publish-complete", help="Mark one publish job as completed")
    publish_complete_parser.add_argument("--job-id", required=True)
    publish_complete_parser.add_argument("--external-post-id", default="")

    publish_batch_complete_parser = subparsers.add_parser(
        "publish-batch-complete",
        help="Mark multiple publish jobs completed by platform, batch, run, or explicit ids",
    )
    publish_batch_complete_parser.add_argument("--platform")
    publish_batch_complete_parser.add_argument("--batch-id")
    publish_batch_complete_parser.add_argument("--run-id")
    publish_batch_complete_parser.add_argument("--job-ids")
    publish_batch_complete_parser.add_argument(
        "--from-status",
        help="Only update jobs currently in one of these comma-separated statuses",
    )

    publish_review_parser = subparsers.add_parser("publish-under-review", help="Mark one publish job as submitted and under review")
    publish_review_parser.add_argument("--job-id", required=True)
    publish_review_parser.add_argument("--external-post-id", default="")
    publish_review_parser.add_argument("--notes", default="")

    publish_batch_review_parser = subparsers.add_parser(
        "publish-batch-under-review",
        help="Mark multiple publish jobs under review by platform, batch, or explicit ids",
    )
    publish_batch_review_parser.add_argument("--platform")
    publish_batch_review_parser.add_argument("--batch-id")
    publish_batch_review_parser.add_argument("--run-id")
    publish_batch_review_parser.add_argument("--job-ids")
    publish_batch_review_parser.add_argument(
        "--from-status",
        help="Only update jobs currently in one of these comma-separated statuses",
    )
    publish_batch_review_parser.add_argument("--notes", default="")

    publish_fail_parser = subparsers.add_parser("publish-fail", help="Mark one publish job as failed")
    publish_fail_parser.add_argument("--job-id", required=True)
    publish_fail_parser.add_argument("--reason", required=True)

    publish_batch_fail_parser = subparsers.add_parser(
        "publish-batch-fail",
        help="Mark multiple publish jobs failed by platform, batch, run, or explicit ids",
    )
    publish_batch_fail_parser.add_argument("--platform")
    publish_batch_fail_parser.add_argument("--batch-id")
    publish_batch_fail_parser.add_argument("--run-id")
    publish_batch_fail_parser.add_argument("--job-ids")
    publish_batch_fail_parser.add_argument(
        "--from-status",
        help="Only update jobs currently in one of these comma-separated statuses",
    )
    publish_batch_fail_parser.add_argument("--reason", required=True)

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
    music_auto_parser.add_argument(
        "--simulate-session",
        action="store_true",
        help="Write a local mock automation session result without launching Playwright, for workflow verification.",
    )

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
        _review_list(project_root, config, Path(args.songs_dir))
        return
    if args.command == "workflow-status":
        snapshot = _build_workflow_status(project_root, config, Path(args.songs_dir))
        if args.json:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        else:
            print(_format_workflow_status(snapshot))
        return
    if args.command == "workflow-next":
        snapshot = _build_workflow_status(project_root, config, Path(args.songs_dir))
        result = _run_workflow_next(
            project_root=project_root,
            config=config,
            snapshot=snapshot,
            execute=args.execute,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(_format_workflow_next(result))
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
        selected_platforms = _resolve_prepare_platforms(args.platforms, config.target_platform)
        jobs = publish_manager.prepare_publish_jobs(
            export_dir=_resolve_path(project_root, args.export_dir),
            platforms=selected_platforms,
            schedule_at=args.schedule_at,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-list":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=args.all_platforms,
            config=config,
            command_name="publish-list",
            has_scope_override=bool(args.batch_id or args.run_id),
        )
        rows = publish_manager.list_jobs(
            status=args.status,
            platform=platform_filter,
            batch_id=args.batch_id,
            run_id=args.run_id,
            traceability_state=args.traceability_state,
            active_only=args.active_only,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if args.command == "publish-summary":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=args.all_platforms,
            config=config,
            command_name="publish-summary",
            has_scope_override=bool(args.batch_id),
        )
        summary = publish_manager.summarize_jobs(
            platform=platform_filter,
            batch_id=args.batch_id,
            traceability_state=args.traceability_state,
            active_only=args.active_only,
        )
        if args.pretty:
            print(_format_publish_summary(summary, config.target_platform))
        else:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.command == "publish-repair-traceability":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=args.all_platforms,
            config=config,
            command_name="publish-repair-traceability",
            has_scope_override=bool(args.batch_id or args.run_id),
        )
        jobs = publish_manager.normalize_jobs(
            platform=platform_filter,
            batch_id=args.batch_id,
            run_id=args.run_id,
            traceability_state=args.traceability_state,
            active_only=args.active_only,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-archive-legacy":
        archived = publish_manager.archive_jobs(
            archive_label=args.label,
            platform=args.platform,
            batch_id=args.batch_id,
            run_id=args.run_id,
            job_ids=_split_csv_values(args.job_ids),
            statuses=_parse_status_filter(args.from_status),
            traceability_state="legacy_partial",
        )
        print(json.dumps(archived, ensure_ascii=False, indent=2))
        return
    if args.command == "publish-archive-list":
        print(json.dumps(publish_manager.list_archives(), ensure_ascii=False, indent=2))
        return
    if args.command == "publish-archive-restore":
        restored = publish_manager.restore_archive(args.label)
        print(json.dumps(restored, ensure_ascii=False, indent=2))
        return
    if args.command == "publish-target":
        payload = {
            "target_platform": config.target_platform,
            "prompt_version": config.prompt_version,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"Primary target platform: {config.target_platform}\n"
                f"Prompt version: {config.prompt_version}"
            )
        return
    if args.command == "publish-show":
        job = publish_manager.get_job(job_id=args.job_id)
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-run":
        job = publish_manager.run_job(job_id=args.job_id, launch_browser=args.launch_browser)
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-run-due":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=args.all_platforms,
            config=config,
            command_name="publish-run-due",
        )
        jobs = publish_manager.run_due_jobs(
            launch_browser=args.launch_browser,
            platform=platform_filter,
            limit=args.limit,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-complete":
        job = publish_manager.complete_job(
            job_id=args.job_id,
            external_post_id=args.external_post_id,
        )
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-batch-complete":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=False,
            config=config,
            command_name="publish-batch-complete",
            has_scope_override=bool(args.batch_id or args.run_id or args.job_ids),
        )
        jobs = publish_manager.complete_jobs(
            platform=platform_filter,
            batch_id=args.batch_id,
            run_id=args.run_id,
            job_ids=[item.strip() for item in args.job_ids.split(",")] if args.job_ids else None,
            from_statuses=_parse_status_filter(args.from_status),
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-under-review":
        job = publish_manager.mark_job_under_review(
            job_id=args.job_id,
            external_post_id=args.external_post_id,
            notes=args.notes,
        )
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-batch-under-review":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=False,
            config=config,
            command_name="publish-batch-under-review",
            has_scope_override=bool(args.batch_id or args.run_id or args.job_ids),
        )
        jobs = publish_manager.mark_jobs_under_review(
            platform=platform_filter,
            batch_id=args.batch_id,
            run_id=args.run_id,
            job_ids=[item.strip() for item in args.job_ids.split(",")] if args.job_ids else None,
            from_statuses=_parse_status_filter(args.from_status),
            notes=args.notes,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "publish-fail":
        job = publish_manager.fail_job(job_id=args.job_id, reason=args.reason)
        print(job.model_dump_json(indent=2))
        return
    if args.command == "publish-batch-fail":
        platform_filter = _resolve_primary_platform_filter(
            platform=args.platform,
            use_all_platforms=False,
            config=config,
            command_name="publish-batch-fail",
            has_scope_override=bool(args.batch_id or args.run_id or args.job_ids),
        )
        jobs = publish_manager.fail_jobs(
            platform=platform_filter,
            batch_id=args.batch_id,
            run_id=args.run_id,
            job_ids=[item.strip() for item in args.job_ids.split(",")] if args.job_ids else None,
            from_statuses=_parse_status_filter(args.from_status),
            reason=args.reason,
        )
        print(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2))
        return
    if args.command == "music-upload-run":
        job = publish_manager.run_music_job_automation(
            job_id=args.job_id,
            manual_login_ms=args.manual_login_ms,
            dry_run=args.dry_run,
            submit=args.submit,
            keep_open=args.keep_open,
            simulate_session=args.simulate_session,
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
    write_export_summary(export_root, _build_export_summary(manifest_entries, config))
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
    song_path = source_dir / song_id / "song.json"
    review_path = source_dir / song_id / "review.json"
    if not review_path.exists():
        raise FileNotFoundError(f"Review file not found for song: {song_id}")
    song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8")) if song_path.exists() else None
    review = ReviewRecord(
        song_id=song_id,
        run_id=song.run_id if song else "",
        prompt_version=song.prompt_version if song else "",
        hook_score=hook_score,
        vocal_score=vocal_score,
        cover_score=cover_score,
        publishable=publishable,
        review_source="manual",
        score_evidence={
            "hook_score": hook_score,
            "vocal_score": vocal_score,
            "cover_score": cover_score,
            "updated_via": "cli_review",
        },
        notes=notes,
    )
    save_review(review_path, review)
    log_step(f"Updated review for {song_id} | publishable={publishable}")


def _review_list(project_root: Path, config, songs_dir: Path) -> None:
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
        meta_payload = _load_song_meta(song)
        target_platform = meta_payload.get("target_platform", "")
        traceability = _traceability_summary(
            run_id=song.run_id,
            prompt_version=song.prompt_version,
            review_source=review.review_source,
        )
        rows.append(
            {
                "song_id": song.song_id,
                "batch_id": song.batch_id,
                "run_id": song.run_id,
                "prompt_version": song.prompt_version,
                "target_platform": target_platform,
                "primary_target_platform": config.target_platform,
                "platform_alignment": _platform_alignment_state(target_platform, config.target_platform),
                "traceability_state": traceability["state"],
                "traceability_notes": traceability["notes"],
                "status": song.status,
                "publishable": review.publishable,
                "review_source": review.review_source,
                "hook": review.hook_score,
                "vocal": review.vocal_score,
                "cover": review.cover_score,
                "score_breakdown": _review_score_breakdown(review),
                "reviewed_at": review.reviewed_at,
                "score_evidence_summary": _review_evidence_summary(review),
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
            run_id=song.run_id,
            prompt_version=song.prompt_version,
            hook_score=hook_score,
            vocal_score=vocal_score,
            cover_score=cover_score,
            publishable=True,
            review_source="manual_batch",
            score_evidence={
                "hook_score": hook_score,
                "vocal_score": vocal_score,
                "cover_score": cover_score,
                "updated_via": "cli_approve_batch",
            },
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


def _parse_status_filter(raw_statuses: str | None) -> set[str] | None:
    if not raw_statuses:
        return None
    return {item.strip() for item in raw_statuses.split(",") if item.strip()}


def _split_csv_values(raw_value: str | None) -> list[str] | None:
    if not raw_value:
        return None
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or None


def _resolve_prepare_platforms(raw_platforms: str | None, target_platform: str) -> list[str]:
    if raw_platforms and raw_platforms.strip():
        return [item.strip() for item in raw_platforms.split(",") if item.strip()]
    return [target_platform]


def _resolve_primary_platform_filter(
    *,
    platform: str | None,
    use_all_platforms: bool,
    config,
    command_name: str,
    has_scope_override: bool = False,
) -> str | None:
    if platform:
        return platform
    if use_all_platforms or has_scope_override:
        return None
    return config.target_platform


def _format_publish_summary(summary: dict, target_platform: str) -> str:
    platform_filter = summary.get("platform_filter") or "all"
    scope_note = "primary-platform default" if summary.get("platform_filter") == target_platform else "explicit scope"
    if not summary.get("platform_filter"):
        scope_note = "all platforms"
    traceability_filter = summary.get("traceability_filter") or "all"
    active_note = "active-only" if summary.get("active_only") else "mixed"
    lines = [
        f"Publish queue summary | jobs={summary.get('job_count', 0)}"
        f" | platform={platform_filter}"
        f" | batch={summary.get('batch_id_filter') or 'all'}"
        f" | target={target_platform}",
        f"Scope: {scope_note} | traceability={traceability_filter} | workflow={active_note}",
        (
            "Backlog | action_required={action_required} | due_pending={due_pending} | ready={ready_to_open} "
            "| under_review={awaiting_platform_review} | saved_for_review={awaiting_manual_submit_review} "
            "| completed={completed} | failed={failed}"
        ).format(**summary.get("backlog", {})),
        "Status counts:",
    ]
    status_counts = summary.get("status_counts", {})
    if status_counts:
        for status, count in sorted(status_counts.items()):
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- none")
    lines.append("Per-platform:")
    platform_status_counts = summary.get("platform_status_counts", {})
    if platform_status_counts:
        for platform, counts in platform_status_counts.items():
            pieces = [f"{status}={count}" for status, count in sorted(counts.items())]
            lines.append(f"- {platform}: {', '.join(pieces)}")
    else:
        lines.append("- none")
    lines.append("Traceability:")
    traceability_counts = summary.get("traceability_counts", {})
    if traceability_counts:
        for state, count in sorted(traceability_counts.items()):
            lines.append(f"- {state}: {count}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def _review_score_breakdown(review: ReviewRecord) -> dict:
    return {
        "hook_score": review.hook_score,
        "vocal_score": review.vocal_score,
        "cover_score": review.cover_score,
        "total_score": review.hook_score + review.vocal_score + review.cover_score,
    }


def _review_evidence_summary(review: ReviewRecord) -> dict:
    evidence = review.score_evidence or {}
    breakdown = evidence.get("score_breakdown", {})
    return {
        "updated_via": evidence.get("updated_via", ""),
        "lyrics_length": evidence.get("lyrics_length"),
        "audio_exists": evidence.get("audio_exists"),
        "cover_exists": evidence.get("cover_exists"),
        "structure_score": breakdown.get("structure_score"),
        "platform_fit_score": breakdown.get("platform_fit_score"),
    }


def _build_workflow_status(project_root: Path, config, songs_dir: Path) -> dict:
    source_dir = songs_dir if songs_dir.is_absolute() else project_root / songs_dir
    review_counts = {
        "songs_total": 0,
        "publishable": 0,
        "aligned_publishable": 0,
        "traceability_complete": 0,
        "generated": 0,
    }
    review_examples: list[dict] = []
    for song_dir in sorted(source_dir.iterdir()):
        if not song_dir.is_dir():
            continue
        song_path = song_dir / "song.json"
        review_path = song_dir / "review.json"
        if not song_path.exists():
            continue
        song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
        review = load_review(review_path) if review_path.exists() else ReviewRecord(song_id=song.song_id)
        meta_payload = _load_song_meta(song)
        target_platform = meta_payload.get("target_platform", "")
        traceability = _traceability_summary(
            run_id=song.run_id,
            prompt_version=song.prompt_version,
            review_source=review.review_source,
        )
        review_counts["songs_total"] += 1
        if song.status == "generated":
            review_counts["generated"] += 1
        if review.publishable:
            review_counts["publishable"] += 1
        if review.publishable and _platform_alignment_state(target_platform, config.target_platform) == "aligned":
            review_counts["aligned_publishable"] += 1
        if traceability["state"] == "complete":
            review_counts["traceability_complete"] += 1
        if len(review_examples) < 5:
            review_examples.append(
                {
                    "song_id": song.song_id,
                    "publishable": review.publishable,
                    "target_platform": target_platform,
                    "platform_alignment": _platform_alignment_state(target_platform, config.target_platform),
                    "traceability_state": traceability["state"],
                }
            )

    latest_export = _find_latest_export_summary(config.exports_dir)
    publish_manager = PublishManager(project_root, config)
    publish_active = publish_manager.summarize_jobs(active_only=True)
    publish_primary = publish_manager.summarize_jobs(platform=config.target_platform)
    publish_legacy = publish_manager.summarize_jobs(traceability_state="legacy_partial")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "primary_target_platform": config.target_platform,
        "prompt_version": config.prompt_version,
        "review": {
            "counts": review_counts,
            "examples": review_examples,
        },
        "latest_export": latest_export,
        "publish": {
            "active_only": publish_active,
            "primary_platform": publish_primary,
            "legacy_partial": publish_legacy,
        },
        "next_action": _recommend_next_action(
            target_platform=config.target_platform,
            active_publish=publish_active,
            latest_export=latest_export,
            review_counts=review_counts,
        ),
    }


def _find_latest_export_summary(exports_dir: Path) -> dict:
    export_dirs = sorted(
        [path for path in exports_dir.iterdir() if path.is_dir() and path.name.startswith("approved_")],
        key=lambda path: path.stat().st_mtime,
    )
    if not export_dirs:
        return {}
    latest = export_dirs[-1]
    summary_path = latest / "export_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary["export_dir"] = str(latest)
    return summary


def _format_workflow_status(snapshot: dict) -> str:
    review_counts = snapshot.get("review", {}).get("counts", {})
    latest_export = snapshot.get("latest_export", {})
    active_publish = snapshot.get("publish", {}).get("active_only", {})
    primary_publish = snapshot.get("publish", {}).get("primary_platform", {})
    legacy_publish = snapshot.get("publish", {}).get("legacy_partial", {})
    lines = [
        f"Workflow status | target={snapshot.get('primary_target_platform', '')} | prompt={snapshot.get('prompt_version', '')}",
        (
            "Review | songs_total={songs_total} | generated={generated} | publishable={publishable} "
            "| aligned_publishable={aligned_publishable} | traceability_complete={traceability_complete}"
        ).format(**review_counts),
    ]
    if latest_export:
        lines.append(
            "Latest export | count={count} | aligned={aligned} | traceability_complete={traceability} | dir={export_dir}".format(
                count=latest_export.get("export_count", 0),
                aligned=latest_export.get("platform_alignment_counts", {}).get("aligned", 0),
                traceability=latest_export.get("traceability_counts", {}).get("complete", 0),
                export_dir=latest_export.get("export_dir", ""),
            )
        )
    else:
        lines.append("Latest export | none")
    lines.append(
        "Active publish | jobs={jobs} | pending={pending} | ready={ready} | under_review={under_review}".format(
            jobs=active_publish.get("job_count", 0),
            pending=active_publish.get("status_counts", {}).get("pending", 0),
            ready=active_publish.get("status_counts", {}).get("ready", 0),
            under_review=active_publish.get("status_counts", {}).get("under_review", 0),
        )
    )
    lines.append(
        "Primary-platform publish | jobs={jobs} | pending={pending} | failed={failed} | completed={completed}".format(
            jobs=primary_publish.get("job_count", 0),
            pending=primary_publish.get("status_counts", {}).get("pending", 0),
            failed=primary_publish.get("status_counts", {}).get("failed", 0),
            completed=primary_publish.get("status_counts", {}).get("completed", 0),
        )
    )
    lines.append(
        "Legacy publish carry-over | jobs={jobs}".format(
            jobs=legacy_publish.get("job_count", 0),
        )
    )
    next_action = snapshot.get("next_action", {})
    lines.append(
        "Next action | step={step} | reason={reason}".format(
            step=next_action.get("step", "none"),
            reason=next_action.get("reason", "none"),
        )
    )
    examples = snapshot.get("review", {}).get("examples", [])
    lines.append("Review examples:")
    if examples:
        for item in examples:
            lines.append(
                f"- {item['song_id']}: publishable={item['publishable']}, "
                f"alignment={item['platform_alignment']}, traceability={item['traceability_state']}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines)


def _run_workflow_next(*, project_root: Path, config, snapshot: dict, execute: bool) -> dict:
    next_action = snapshot.get("next_action", {})
    step = next_action.get("step", "")
    reason = next_action.get("reason", "")
    result = {
        "step": step,
        "reason": reason,
        "execute": execute,
        "performed": False,
        "result": None,
    }
    if not execute:
        return result

    publish_manager = PublishManager(project_root, config)
    if step.startswith("publish-run-due"):
        jobs = publish_manager.run_due_jobs(platform=config.target_platform)
        result["performed"] = True
        result["result"] = [job.model_dump(mode="json") for job in jobs]
        return result
    if step.startswith("publish-batch-under-review"):
        jobs = publish_manager.mark_jobs_under_review(
            platform=config.target_platform,
            from_statuses={"ready"},
        )
        result["performed"] = True
        result["result"] = [job.model_dump(mode="json") for job in jobs]
        return result
    if step.startswith("publish-batch-complete"):
        jobs = publish_manager.complete_jobs(
            platform=config.target_platform,
            from_statuses={"under_review"},
        )
        result["performed"] = True
        result["result"] = [job.model_dump(mode="json") for job in jobs]
        return result
    if step == "prepare-publish":
        latest_export = snapshot.get("latest_export", {})
        export_dir = latest_export.get("export_dir", "")
        if not export_dir:
            raise RuntimeError("No export directory available for prepare-publish.")
        jobs = publish_manager.prepare_publish_jobs(
            export_dir=Path(export_dir),
            platforms=[config.target_platform],
        )
        result["performed"] = True
        result["result"] = [job.model_dump(mode="json") for job in jobs]
        return result
    if step == "export-approved":
        _export_approved(project_root, config, config.songs_dir)
        result["performed"] = True
        result["result"] = {"exported": True}
        return result
    return result


def _format_workflow_next(result: dict) -> str:
    lines = [
        f"Workflow next | step={result.get('step', '')}",
        f"Reason: {result.get('reason', '')}",
        f"Execute: {result.get('execute', False)} | performed: {result.get('performed', False)}",
    ]
    payload = result.get("result")
    if payload is None:
        lines.append("Result: preview only")
    elif isinstance(payload, list):
        lines.append(f"Result: {len(payload)} item(s)")
    else:
        lines.append(f"Result: {json.dumps(payload, ensure_ascii=False)}")
    return "\n".join(lines)


def _recommend_next_action(*, target_platform: str, active_publish: dict, latest_export: dict, review_counts: dict) -> dict:
    active_status = active_publish.get("status_counts", {})
    if active_status.get("pending", 0) > 0:
        return {
            "step": f"publish-run-due --platform {target_platform}",
            "reason": "There are active primary-platform publish jobs waiting for validation or browser launch.",
        }
    if active_status.get("ready", 0) > 0:
        return {
            "step": f"publish-batch-under-review --platform {target_platform} --from-status ready",
            "reason": "There are validated primary-platform jobs ready to be submitted and marked under review.",
        }
    if active_status.get("under_review", 0) > 0:
        return {
            "step": f"publish-batch-complete --platform {target_platform} --from-status under_review",
            "reason": "There are active primary-platform jobs waiting for final review outcome recording.",
        }
    if latest_export.get("export_count", 0) > 0:
        return {
            "step": "prepare-publish",
            "reason": "There is an aligned export available but no active primary-platform publish job yet.",
        }
    if review_counts.get("aligned_publishable", 0) > 0:
        return {
            "step": "export-approved",
            "reason": "There are approved songs aligned with the primary platform but no current export snapshot.",
        }
    return {
        "step": "run-batch / approve-song",
        "reason": "No active aligned publishable workflow item is currently in progress.",
    }


def _build_export_summary(entries: list[dict], config) -> dict:
    alignment_counts: dict[str, int] = {}
    traceability_counts: dict[str, int] = {}
    for entry in entries:
        alignment = _platform_alignment_state(entry.get("target_platform", ""), config.target_platform)
        alignment_counts[alignment] = alignment_counts.get(alignment, 0) + 1
        traceability = _traceability_summary(
            run_id=entry.get("run_id", ""),
            prompt_version=entry.get("prompt_version", ""),
            review_source=entry.get("review_source", ""),
        )
        traceability_counts[traceability["state"]] = traceability_counts.get(traceability["state"], 0) + 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "export_count": len(entries),
        "primary_target_platform": config.target_platform,
        "prompt_version": config.prompt_version,
        "platform_alignment_counts": alignment_counts,
        "traceability_counts": traceability_counts,
        "entries": [
            {
                "song_id": entry.get("song_id", ""),
                "run_id": entry.get("run_id", ""),
                "target_platform": entry.get("target_platform", ""),
                "platform_alignment": _platform_alignment_state(
                    entry.get("target_platform", ""),
                    config.target_platform,
                ),
                "traceability_state": _traceability_summary(
                    run_id=entry.get("run_id", ""),
                    prompt_version=entry.get("prompt_version", ""),
                    review_source=entry.get("review_source", ""),
                )["state"],
                "review_source": entry.get("review_source", ""),
            }
            for entry in entries
        ],
    }


def _load_song_meta(song: SongRecord) -> dict:
    if not song.meta_path.exists():
        return {}
    return json.loads(song.meta_path.read_text(encoding="utf-8"))


def _platform_alignment_state(target_platform: str, primary_target_platform: str) -> str:
    if not target_platform:
        return "unknown"
    if target_platform == primary_target_platform:
        return "aligned"
    return "mismatch"


def _traceability_summary(*, run_id: str, prompt_version: str, review_source: str) -> dict:
    missing: list[str] = []
    if not run_id:
        missing.append("run_id")
    if not prompt_version:
        missing.append("prompt_version")
    if not review_source:
        missing.append("review_source")
    if not missing:
        return {"state": "complete", "notes": []}
    return {"state": "partial", "notes": missing}


if __name__ == "__main__":
    main()
